#!/usr/bin/env python3
"""
Append a trading run record to data/trading_runs.jsonl.

Intended to be called from GitHub Actions. Keeps only the most recent
MAX_RECORDS entries to prevent unbounded growth.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_RECORDS = 200
RUN_LOG = Path("data/trading_runs.jsonl")


def load_runs() -> list[dict[str, Any]]:
    if not RUN_LOG.exists():
        return []
    try:
        return [json.loads(line) for line in RUN_LOG.read_text().splitlines() if line.strip()]
    except Exception:
        # Corrupted file? Start fresh but keep a backup for debugging.
        RUN_LOG.rename(RUN_LOG.with_suffix(".jsonl.bak"))
        return []


def main() -> None:
    run_id = os.getenv("GITHUB_RUN_ID")
    run_number = os.getenv("GITHUB_RUN_NUMBER")
    sha = os.getenv("GITHUB_SHA")
    repo = os.getenv("GITHUB_REPOSITORY")
    job_status = os.getenv("JOB_STATUS", "unknown")
    failing_step = os.getenv("FAILING_STEP") or None
    error_message = os.getenv("ERROR_MESSAGE") or None

    now = datetime.now(timezone.utc)

    record = {
        "ts": now.isoformat(),
        "status": job_status.lower(),
        "run_id": run_id,
        "run_number": run_number,
        "sha": sha,
        "repo": repo,
        "failing_step": failing_step,
        "error": error_message,
        "actions_url": f"https://github.com/{repo}/actions/runs/{run_id}"
        if repo and run_id
        else None,
    }

    runs = load_runs()
    runs.append(record)
    runs = runs[-MAX_RECORDS:]

    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("w", encoding="utf-8") as f:
        for row in runs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
