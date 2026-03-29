#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def evaluate_task(task_dir: Path):
    task_id = task_dir.name
    classification = json.loads((task_dir / 'classification.json').read_text()) if (task_dir / 'classification.json').exists() else {}
    stdout = (task_dir / 'stdout.txt').read_text() if (task_dir / 'stdout.txt').exists() else ''
    artifact_dir = task_dir / 'artifacts'

    if classification.get('category') != 'OK':
        return {
            'task_id': task_id,
            'score': 0,
            'notes': [f"First-pass failure: {classification.get('category', 'UNKNOWN')}"]
        }

    notes = []
    score = 0

    if task_id == 'task-01':
        text = stdout.lower()
        if 'score' in text:
            score += 2
        if 'line' in text:
            score += 3
        if 'maintain' in text or 'readab' in text or 'structure' in text:
            score += 3
        if len(stdout.strip().splitlines()) >= 6:
            score += 2
        notes.append('Heuristic scoring used; replace with advanced-model judging later.')

    elif task_id == 'task-02':
        text = stdout.lower()
        if 'critical' in text or 'warning' in text or 'info' in text:
            score += 2
        if 'root cause' in text or 'cause' in text:
            score += 3
        if 'fix' in text:
            score += 3
        if 'line' in text:
            score += 2
        notes.append('Heuristic scoring used; replace with advanced-model judging later.')

    elif task_id == 'task-03':
        artifact = artifact_dir / 'app-enhanced.js'
        if artifact.exists() and artifact.stat().st_size > 0:
            score += 4
            content = artifact.read_text()
            if 'function renderSummaryBar' in content:
                score += 3
            if 'status === \'error\'' in content or 'status === "error"' in content:
                score += 1
            if 'status === \'stale\'' in content or 'status === "stale"' in content:
                score += 1
            if 'null' in content or 'undefined' in content:
                score += 1
        else:
            notes.append('Required artifact missing.')
        notes.append('Heuristic scoring used; replace with advanced-model judging later.')

    return {
        'task_id': task_id,
        'score': min(score, 10),
        'notes': notes
    }


def main():
    if len(sys.argv) != 2:
        print('usage: judge_run.py RUN_DIR', file=sys.stderr)
        return 2
    run_dir = Path(sys.argv[1])
    total = 0
    tasks = []
    for task_dir in sorted([p for p in run_dir.iterdir() if p.is_dir() and p.name.startswith('task-')]):
        result = evaluate_task(task_dir)
        tasks.append(result)
        total += result['score']
        (task_dir / 'evaluation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))

    verdict = 'PASS' if total >= 21 else 'PASS_WITH_WARNINGS' if total >= 15 else 'FAIL'
    summary = {
        'total': total,
        'verdict': verdict,
        'judge_mode': 'heuristic-scaffold',
        'tasks': tasks
    }
    (run_dir / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
