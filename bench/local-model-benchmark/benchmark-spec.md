# Benchmark Spec

## Scope
This benchmark measures local model usefulness for coding and QA work.
Primary priority is **quality and instruction-following**, not raw speed.

## Required Constraints
1. All benchmark prompts must be written in English.
2. Three baseline models must be included:
   - qwen3-coder:30b-a3b-q4_K_M
   - deepseek-r1:32b
   - deepseek-r1:70b
3. Lightweight models only perform execution, failure classification support, and log production.
4. Advanced models perform analysis, scoring, and comparison.
5. The procedure must remain identical regardless of which model initiates the test.
6. Persona variation must be measurable as a separate factor.
7. Failures need first-pass classification from exit code + logs.
8. Better ideas may be documented separately but not forced into the base flow.

## Evaluation Dimensions
- instruction_following
- completeness
- technical_correctness
- edge_case_handling
- artifact_integrity
- bug_detection_quality
- hallucination_or_overclaiming
- speed_reference (informational only)

## Pass Bands
- PASS: 21–30
- PASS_WITH_WARNINGS: 15–20
- FAIL: 0–14

## Failure Categories (first pass)
- INVOCATION_ERROR: runner could not start
- TIMEOUT: process exceeded allowed time
- EMPTY_OUTPUT: blank or near-blank result
- PARTIAL_ARTIFACT: required file missing or incomplete
- FORMAT_VIOLATION: prompt instructions ignored in structure/output format
- RUNTIME_ERROR: generated code or script crashes
- CONTEXT_OVERFLOW: truncation or obvious context exhaustion
- UNKNOWN: unclassified

## Standard Run Contract
For each task, save:
- prompt.txt
- persona.txt
- stdout.txt
- stderr.txt
- meta.json
- artifacts/...
- classification.json
- evaluation.json

## Naming Convention
Use:
- run_id = YYYYMMDD-HHMMSS-subjectmodel-shortpersona
- task_dir = task-XX

## Comparison Rules
- Compare same task, same persona, same prompt version only.
- Never compare warm runs to cold runs without labeling.
- Do not mix judge models inside a single comparison table unless shown explicitly.
