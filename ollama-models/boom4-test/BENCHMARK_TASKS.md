# Boom4 Model Benchmark — Standard Task Set

> Version: 1.0 | Created: 2026-03-29
> Purpose: Compare coding/QA ability across different local LLM models
> Project: /Users/sykim/workspace/experiments/usage-dashboard-mock/

---

## Task 1: Code Quality Review (10 points)

**Files to read:**
- `/Users/sykim/workspace/experiments/usage-dashboard-mock/index.html`
- `/Users/sykim/workspace/experiments/usage-dashboard-mock/app.js`

**Requirements:**
- Evaluate overall code structure (organization, readability, maintainability)
- Evaluate CSS organization and variable usage
- Evaluate JavaScript quality (functions, error handling, edge cases)
- List specific issues with file name and line number where possible
- Assign a score from 1–10 with justification

**Output file:** `reports/{MODEL_ID}-task1-review.md`

---

## Task 2: Bug Hunt (10 points)

**File to read:**
- `/Users/sykim/workspace/experiments/usage-dashboard-mock/app.js`

**Requirements:**
- Find ALL bugs, logic errors, and potential crashes
- For each bug: exact line number + description + root cause + fix code
- Classify severity: CRITICAL / WARNING / INFO
- Count total bugs found

**Scoring:**
- 10 pts: 5+ bugs with exact lines + fix code
- 7 pts: 3–4 bugs with partial details
- 4 pts: 1–2 bugs only
- 0 pts: No bugs or only vague descriptions

**Output file:** `reports/{MODEL_ID}-task2-bugs.md`

---

## Task 3: Feature Implementation (10 points)

**Requirements:**
- Read `/Users/sykim/workspace/experiments/usage-dashboard-mock/app.js`
- Create a NEW file: `reports/{MODEL_ID}-task3-app-enhanced.js`
- Copy ALL original code from app.js into the new file
- Add the following new function at the end:

```javascript
/**
 * Renders a summary bar showing provider status counts.
 * @param {Array} providers - Array of provider objects with a 'status' field
 * @returns {string} HTML string or empty string if providers is empty
 */
function renderSummaryBar(providers) {
  // Must handle: empty array, null/undefined input, missing status field
  // Returns: '<div class="summary-bar">Total: N | OK: N 🟢 | Warn: N 🟡 | Issues: N 🔴</div>'
  // 'Issues' = count of providers where status === 'error' OR status === 'stale'
}
```

**Scoring:**
- 10 pts: Correct implementation + all edge cases + copied original code intact
- 7 pts: Function works but missing edge cases
- 4 pts: Partial implementation or missing original code
- 0 pts: File not created or function not present

**Output file:** `reports/{MODEL_ID}-task3-app-enhanced.js`

---

## Final Report Format

**Output file:** `reports/{MODEL_ID}-final-report.md`

```markdown
# Boom4 Benchmark — Final Report
**Model:** {MODEL_NAME}
**Model ID:** {MODEL_ID}
**Date:** 2026-03-29
**Token Speed:** X t/s (measured separately)

## Task 1: Code Quality Review
Score: X/10
Key findings:
- (list top 3 findings)

## Task 2: Bug Hunt
Score: X/10
Bugs found: N (CRITICAL: N, WARNING: N, INFO: N)
Key bugs:
- (list top 3 bugs with line numbers)

## Task 3: Feature Implementation
Score: X/10
Status: PASS / FAIL
Notes:

## Total Score: X/30
## Verdict: PASS (≥21) / PASS_WITH_WARNINGS (15–20) / FAIL (<15)
```

---

## Token Speed Measurement Script

Run before each model test:

```bash
MODEL_ID="qwen3-coder"  # change per model
START=$(python3 -c "import time; print(int(time.time()*1000))")
OUTPUT=$(ollama run {MODEL_NAME} "Write a JavaScript function to deeply merge two objects, handling arrays, nested objects, null values, and circular reference prevention. Include JSDoc comments." --nowordwrap 2>/dev/null)
END=$(python3 -c "import time; print(int(time.time()*1000))")
ELAPSED=$(( (END - START) ))
WORDS=$(echo "$OUTPUT" | wc -w | tr -d ' ')
TOKENS=$(( WORDS * 13 / 10 ))
TPS=$(( TOKENS * 1000 / ELAPSED ))
echo "Model: {MODEL_NAME}"
echo "Elapsed: ${ELAPSED}ms"
echo "Est. tokens: $TOKENS"
echo "Speed: $TPS t/s"
```
