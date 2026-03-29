#!/bin/bash
# Boom4 Token Speed Measurement Script
# Usage: ./measure_speed.sh <model_name> <model_id>
# Example: ./measure_speed.sh boom4 qwen3-coder

MODEL_NAME="${1:-boom4}"
MODEL_ID="${2:-unknown}"
REPORT_DIR="/Users/sykim/workspace/experiments/usage-dashboard-mock/reports"
mkdir -p "$REPORT_DIR"

echo "=== Measuring token speed for: $MODEL_NAME ==="
echo "Warming up..."

# Warmup
ollama run "$MODEL_NAME" "Reply with exactly: READY" --nowordwrap 2>/dev/null > /dev/null

echo "Running speed test..."
START_MS=$(python3 -c "import time; print(int(time.time()*1000))")

OUTPUT=$(ollama run "$MODEL_NAME" "Write a JavaScript function to deeply merge two objects. Handle: nested objects, arrays (concatenate), null/undefined values (skip), and type mismatches (use source value). Include JSDoc comments and 3 usage examples." --nowordwrap 2>/dev/null)

END_MS=$(python3 -c "import time; print(int(time.time()*1000))")

ELAPSED=$(( END_MS - START_MS ))
WORDS=$(echo "$OUTPUT" | wc -w | tr -d ' ')
TOKENS=$(( WORDS * 13 / 10 ))
TPS=$(( TOKENS * 1000 / ELAPSED ))

echo ""
echo "=== Results ==="
echo "Model:    $MODEL_NAME"
echo "Elapsed:  ${ELAPSED}ms ($(( ELAPSED / 1000 ))s)"
echo "Words:    $WORDS"
echo "Est t/s:  $TPS t/s"
echo ""

# Save to report
RESULT_FILE="$REPORT_DIR/${MODEL_ID}-speed.md"
cat > "$RESULT_FILE" << EOF
# Token Speed Test — ${MODEL_ID}
**Model:** ${MODEL_NAME}
**Date:** $(date '+%Y-%m-%d %H:%M KST')

## Result
| Metric | Value |
|--------|-------|
| Elapsed | ${ELAPSED}ms |
| Est. output tokens | ${TOKENS} |
| **Speed** | **${TPS} t/s** |

## GPU Status
\`\`\`
$(ollama ps 2>/dev/null)
\`\`\`
EOF

echo "Saved to: $RESULT_FILE"
