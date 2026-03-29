#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESULT_BASE="$ROOT_DIR/results"
TARGET_WORKSPACE_DEFAULT="/Users/sykim/workspace/experiments/usage-dashboard-mock"
TIMEOUT_SECONDS_DEFAULT=600
PROMPT_VERSION="v1"

SUBJECT_MODEL="${1:-}"
PERSONA_ID="${2:-none}"
WORKSPACE_TARGET="${3:-$TARGET_WORKSPACE_DEFAULT}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-$TIMEOUT_SECONDS_DEFAULT}"

if [[ -z "$SUBJECT_MODEL" ]]; then
  echo "usage: $(basename "$0") <subject-model> [persona-id] [workspace-target]" >&2
  exit 2
fi

case "$PERSONA_ID" in
  none|qa-strict|coding-implementer) ;;
  *)
    echo "unknown persona: $PERSONA_ID" >&2
    exit 2
    ;;
esac

slugify() {
  echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9._-]/-/g; s/--*/-/g; s/^-//; s/-$//'
}

SUBJECT_ID="$(slugify "$SUBJECT_MODEL")"
RUN_TS="$(date +%Y%m%d-%H%M%S)"
RUN_DATE="$(date +%F)"
RUN_ID="${RUN_TS}-${SUBJECT_ID}-${PERSONA_ID}"
RUN_DIR="$RESULT_BASE/$RUN_DATE/$RUN_ID"
PERSONA_FILE="$ROOT_DIR/personas/$PERSONA_ID.txt"

mkdir -p "$RUN_DIR"
mkdir -p "$RUN_DIR/logs"

JSON_ESCAPE_PY='import json,sys; print(json.dumps(sys.stdin.read()))'

run_task() {
  local task_id="$1"
  local prompt_file="$2"
  local required_artifact="$3"
  local output_mode="$4"
  local task_dir="$RUN_DIR/$task_id"
  local artifacts_dir="$task_dir/artifacts"
  local stdout_file="$task_dir/stdout.txt"
  local stderr_file="$task_dir/stderr.txt"
  local meta_file="$task_dir/meta.json"
  local prompt_out="$task_dir/prompt.txt"
  local persona_out="$task_dir/persona.txt"
  local full_prompt_file="$task_dir/full-prompt.txt"
  local start_ts end_ts elapsed_ms exit_code status

  mkdir -p "$artifacts_dir"
  cp "$prompt_file" "$prompt_out"
  cp "$PERSONA_FILE" "$persona_out"

  {
    echo "System instructions:"
    cat "$PERSONA_FILE"
    echo
    echo "Benchmark task instructions:"
    cat "$prompt_file"
    echo
    echo "Target workspace: $WORKSPACE_TARGET"
    echo "Subject model: $SUBJECT_MODEL"
    echo "Task output mode: $output_mode"
    if [[ -n "$required_artifact" ]]; then
      echo "Required artifact path: $required_artifact"
    fi
    case "$task_id" in
      task-01)
        echo "Files to inspect: $WORKSPACE_TARGET/index.html and $WORKSPACE_TARGET/app.js"
        ;;
      task-02)
        echo "File to inspect: $WORKSPACE_TARGET/app.js"
        ;;
      task-03)
        echo "Source file: $WORKSPACE_TARGET/app.js"
        echo "Create the required artifact file under the exact path listed above."
        echo "Copy the entire source content first, then append the new function."
        ;;
    esac
    echo
    echo "Important rules:"
    echo "- Use English only."
    echo "- Be concrete and evidence-based."
    echo "- Do not invent files or results."
    echo "- If you cannot complete a step, state the exact limitation."
  } > "$full_prompt_file"

  start_ts="$(python3 - <<'PY'
import time
print(int(time.time()*1000))
PY
)"

  set +e
  ollama run "$SUBJECT_MODEL" < "$full_prompt_file" > "$stdout_file.raw" 2> "$stderr_file.raw"
  exit_code=$?
  set -e

  python3 - "$stdout_file.raw" "$stdout_file" <<'PY'
from pathlib import Path
import re
import sys
src = Path(sys.argv[1]).read_text(errors='ignore')
src = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', src)
src = re.sub(r'[\r\x08]', '', src)
Path(sys.argv[2]).write_text(src)
PY

  python3 - "$stderr_file.raw" "$stderr_file" <<'PY'
from pathlib import Path
import re
import sys
src = Path(sys.argv[1]).read_text(errors='ignore')
src = re.sub(r'\x1b\[[0-9;?]*[A-Za-z]', '', src)
src = re.sub(r'[\r\x08]', '', src)
Path(sys.argv[2]).write_text(src)
PY

  end_ts="$(python3 - <<'PY'
import time
print(int(time.time()*1000))
PY
)"
  elapsed_ms=$(( end_ts - start_ts ))

  if [[ "$output_mode" == "artifact" && "$exit_code" -eq 0 && -n "$required_artifact" ]]; then
    python3 - "$stdout_file" "$artifacts_dir/$required_artifact" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1]).read_text()
out = Path(sys.argv[2])
out.write_text(src)
PY
  fi

  if [[ "$exit_code" -eq 0 ]]; then
    status="ok"
  else
    status="fail"
  fi

  cat > "$meta_file" <<EOF_META
{
  "task_id": "$task_id",
  "subject_model": "$SUBJECT_MODEL",
  "subject_id": "$SUBJECT_ID",
  "persona_id": "$PERSONA_ID",
  "persona_enabled": $( [[ "$PERSONA_ID" == "none" ]] && echo false || echo true ),
  "workspace_target": "$WORKSPACE_TARGET",
  "prompt_version": "$PROMPT_VERSION",
  "required_artifact": "$required_artifact",
  "output_mode": "$output_mode",
  "exit_code": $exit_code,
  "status": "$status",
  "elapsed_ms": $elapsed_ms,
  "timestamp": "$(date -Iseconds)"
}
EOF_META

  python3 "$ROOT_DIR/scripts/classify_failure.py" "$task_dir" > "$task_dir/classification.json"
}

run_task "task-01" "$ROOT_DIR/prompts/task-01-review.md" "review.md" "text"
run_task "task-02" "$ROOT_DIR/prompts/task-02-bug-hunt.md" "bugs.md" "text"
run_task "task-03" "$ROOT_DIR/prompts/task-03-feature-impl.md" "app-enhanced.js" "artifact"

cat > "$RUN_DIR/run.json" <<EOF_RUN
{
  "run_id": "$RUN_ID",
  "run_date": "$RUN_DATE",
  "subject_model": "$SUBJECT_MODEL",
  "subject_id": "$SUBJECT_ID",
  "persona_id": "$PERSONA_ID",
  "workspace_target": "$WORKSPACE_TARGET",
  "prompt_version": "$PROMPT_VERSION",
  "timeout_seconds": $TIMEOUT_SECONDS
}
EOF_RUN

echo "Run complete: $RUN_DIR"
