#!/usr/bin/env python3
"""Run Automated Eval Engineering Suite.

Mines traces, loads evaluation cases, executes eval benchmarks,
and outputs pass rate % and detailed diagnostics.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eval.eval_harness import EvalHarness
from src.eval.trace_miner import TraceMiner

logger = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    print("=== 🔬 Running Automated Eval Engineering Suite ===")

    # 1. Mine traces and refresh eval dataset
    miner = TraceMiner()
    dataset_path = miner.save_eval_dataset()

    # 2. Run Eval Harness
    harness = EvalHarness(dataset_path=dataset_path)
    report = harness.run_evals()

    # 3. Print Report Summary
    report_dict = asdict(report)
    print(f"\nTotal Evals Evaluated : {report.total_evals}")
    print(f"Passed                : {report.passed_count}")
    print(f"Failed                : {report.failed_count}")
    print(f"Pass Rate             : {report.pass_rate_pct}%\n")

    print(json.dumps(report_dict, indent=2))

    if report.pass_rate_pct < 100.0:
        logger.error("🚨 Eval Suite failed with pass rate %s%%", report.pass_rate_pct)
        return 1

    print("\n✅ ALL EVAL BENCHMARKS PASSED (100.0%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
