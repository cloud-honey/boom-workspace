#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: summarize_results.py RUN_DIR", file=sys.stderr)
        return 2
    run_dir = Path(sys.argv[1])
    rows = []
    total = 0
    for task_dir in sorted(p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith("task-")):
        eval_path = task_dir / "evaluation.json"
        class_path = task_dir / "classification.json"
        evaluation = json.loads(eval_path.read_text()) if eval_path.exists() else {}
        classification = json.loads(class_path.read_text()) if class_path.exists() else {}
        score = int(evaluation.get("score", 0))
        total += score
        rows.append({
            "task": task_dir.name,
            "score": score,
            "category": classification.get("category", "MISSING")
        })
    verdict = "PASS" if total >= 21 else "PASS_WITH_WARNINGS" if total >= 15 else "FAIL"
    print(json.dumps({"total": total, "verdict": verdict, "tasks": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
