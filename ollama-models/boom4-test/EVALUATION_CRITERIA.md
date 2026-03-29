# Boom4 Model Evaluation Criteria

> Version: 1.0 | Created: 2026-03-29

---

## Scoring Overview

| Task | Max Points | Weight |
|------|-----------|--------|
| Task 1: Code Quality Review | 10 | 33% |
| Task 2: Bug Hunt | 10 | 33% |
| Task 3: Feature Implementation | 10 | 33% |
| **Total** | **30** | 100% |

---

## Task 1: Code Quality Review (10 pts)

| Score | Criteria |
|-------|----------|
| 9–10 | Specific issues with file+line references, accurate CSS/JS analysis, actionable recommendations |
| 7–8  | Good analysis but missing some line references or minor inaccuracies |
| 5–6  | General observations only, no specific line numbers |
| 3–4  | Superficial review, misses obvious issues |
| 0–2  | Incorrect analysis or no meaningful content |

---

## Task 2: Bug Hunt (10 pts)

| Score | Criteria |
|-------|----------|
| 9–10 | 5+ bugs found, each with exact line + root cause + fix code |
| 7–8  | 3–4 bugs with partial fix details |
| 5–6  | 2–3 bugs, vague descriptions |
| 3–4  | 1–2 bugs only |
| 0–2  | No real bugs or only hallucinated issues |

**Bonus:** +1 if CRITICAL bug correctly identified (e.g., CSS class case mismatch on line 56, DOM ID disconnect)

---

## Task 3: Feature Implementation (10 pts)

| Score | Criteria |
|-------|----------|
| 9–10 | Function correct + all edge cases (null, empty, missing status) + original code intact |
| 7–8  | Function works but 1–2 edge cases missing |
| 5–6  | Partial implementation or minor logic error |
| 3–4  | Function exists but incorrect output format or missing edge cases |
| 0–2  | File not created, function missing, or original code destroyed |

**Automatic FAIL conditions:**
- Modified original app.js
- renderSummaryBar returns wrong format
- Crashes on empty array input

---

## Overall Verdict

| Score | Verdict |
|-------|---------|
| 24–30 | ✅ PASS — Production ready |
| 18–23 | ⚠️ PASS_WITH_WARNINGS — Usable with caveats |
| 10–17 | ❌ FAIL — Not suitable for QA work |
| 0–9   | ❌ FAIL — Cannot perform basic tasks |

---

## Additional Metrics (not scored, informational)

| Metric | Measurement Method |
|--------|-------------------|
| Token speed (t/s) | Measured with standard prompt before test |
| Response time (total) | Wall clock time for all 3 tasks |
| Instruction following | Did it follow output file naming? |
| Hallucination rate | Did it invent non-existent code/bugs? |

---

## Known Reference Answers (for grading Task 2)

The following bugs are known to exist in app.js:

1. **Line 56** — `renderBadge`: CSS class uses `value` directly but CSS expects lowercase
   - Fix: `badge.className = \`badge \${type}-\${value.toLowerCase()}\``

2. **init() function** — DOM element IDs (`header-container`, `cards-container`, `legend-container`) referenced but not present in index.html
   - Fix: Add matching div IDs to index.html

3. **renderUsageBar** — Percentage string parsing may produce NaN for edge case values

4. **renderProviderCard** — Warning/error threshold logic uses hardcoded values without null checks

5. **DOMContentLoaded** — May fire before all resources loaded in some environments

A model that finds bugs 1 and 2 shows genuine code understanding. Finding only surface issues scores lower.
