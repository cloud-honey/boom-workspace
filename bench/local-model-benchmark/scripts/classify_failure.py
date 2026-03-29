#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path


def detect_category(exit_code: int, stdout: str, stderr: str, task_dir: Path, meta: dict) -> str:
    text = f"{stdout}\n{stderr}".lower()
    if "timed out" in text or "timeout" in text:
        return "TIMEOUT"
    if exit_code != 0 and ("not found" in text or "unknown model" in text or "failed to start" in text):
        return "INVOCATION_ERROR"
    if len(stdout.strip()) < 10 and len(stderr.strip()) < 10:
        return "EMPTY_OUTPUT"
    artifacts_dir = task_dir / "artifacts"
    required_artifact = meta.get("required_artifact")
    if required_artifact:
        required_path = artifacts_dir / required_artifact
        if not required_path.exists() or required_path.stat().st_size == 0:
            return "PARTIAL_ARTIFACT"
    if "maximum context" in text or "context window" in text or "truncated" in text:
        return "CONTEXT_OVERFLOW"
    if re.search(r"traceback|exception|syntaxerror|referenceerror|typeerror", text):
        return "RUNTIME_ERROR"
    return "UNKNOWN" if exit_code != 0 else "OK"


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: classify_failure.py TASK_DIR", file=sys.stderr)
        return 2
    task_dir = Path(sys.argv[1])
    meta_path = task_dir / "meta.json"
    stdout_path = task_dir / "stdout.txt"
    stderr_path = task_dir / "stderr.txt"

    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    stdout = stdout_path.read_text() if stdout_path.exists() else ""
    stderr = stderr_path.read_text() if stderr_path.exists() else ""
    exit_code = int(meta.get("exit_code", 0))

    category = detect_category(exit_code, stdout, stderr, task_dir, meta)
    payload = {
        "status": "pass" if category == "OK" else "fail",
        "category": category,
        "exit_code": exit_code
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
