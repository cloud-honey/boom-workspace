# Local Model Benchmark Framework

Version: 0.1
Date: 2026-03-29
Owner: Boom

## Goal
Create a reusable benchmark framework for local coding models so that:
- the same procedure works no matter which model runs the benchmark
- benchmark prompts stay fixed in English
- lightweight models focus on execution, failure classification, and log capture
- advanced models focus on analysis, scoring, and comparison
- persona on/off or persona type differences can be compared separately
- failures are classified first from exit code and logs before manual review

## Fixed Target Models
- qwen3-coder:30b-a3b-q4_K_M
- deepseek-r1:32b
- deepseek-r1:70b

The framework must remain extensible so more models can be added later.

## Core Principles
1. Separate **runner** from **judge**.
2. Keep benchmark prompts versioned and immutable.
3. Store raw outputs first, then derived scores.
4. Make persona a matrix dimension, not a hidden variable.
5. Classify failures mechanically before subjective review.
6. Do not let one model grade its own results unless explicitly allowed.

## Recommended Directory Layout
```
bench/local-model-benchmark/
├── README.md
├── benchmark-spec.md
├── models.example.json
├── prompts/
│   ├── task-01-review.md
│   ├── task-02-bug-hunt.md
│   ├── task-03-feature-impl.md
│   └── judge-evaluation.md
├── personas/
│   ├── none.txt
│   ├── qa-strict.txt
│   └── coding-implementer.txt
├── rubrics/
│   └── default-rubric.json
├── scripts/
│   ├── run_benchmark.sh
│   ├── classify_failure.py
│   └── summarize_results.py
└── results/
    └── YYYY-MM-DD/
        └── RUN_ID/
```

## Run Flow
1. Select target model set.
2. Select persona set.
3. Run each benchmark task with fixed English prompts.
4. Save stdout, stderr, timing, exit code, and artifacts.
5. Run first-pass failure classifier.
6. Run judge prompt with advanced model on saved artifacts.
7. Generate per-run summary and cross-model comparison.

## Matrix Dimensions
Each run should include these dimensions in metadata:
- subject_model
- subject_role: lightweight | advanced
- persona_id
- persona_enabled: true | false
- task_id
- prompt_version
- workspace_target
- runner_model
- judge_model
- timestamp

## Role Split
### Lightweight model responsibilities
- execute task prompts
- generate files/artifacts
- return raw answer
- allow failure detection
- never do final comparative scoring

### Advanced model responsibilities
- review artifacts
- score against rubric
- compare outputs across models
- detect overclaiming, omissions, and weak reasoning
- produce final ranking and recommendations

## Suggested Improvements Beyond Current Requirements
These are proposals only and should be applied after confirmation.
- Add repeat runs (N=3) to reduce luck/noise.
- Add cold-start vs warm-start distinction.
- Add token-speed and wall-clock as separate metrics.
- Add prompt adherence score distinct from code quality score.
- Add self-check penalty when model claims work not present in files.
- Add deterministic artifact checksum capture.

## Current Status
This folder now contains the first framework draft and runnable scaffolding.
