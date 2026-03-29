#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESULT_BASE="$ROOT_DIR/results"
RUN_TS="$(date +%Y%m%d-%H%M%S)"
SUBJECT_ID="${1:-subject}"
PERSONA_ID="${2:-none}"
RUN_ID="${RUN_TS}-${SUBJECT_ID}-${PERSONA_ID}"
RUN_DIR="$RESULT_BASE/$(date +%F)/$RUN_ID"

mkdir -p "$RUN_DIR"

echo "Run directory: $RUN_DIR"
echo "This is a scaffold runner. Plug in the actual model invocation here."

echo '{"note":"runner scaffold only","run_id":"'"$RUN_ID"'"}' > "$RUN_DIR/run.json"
