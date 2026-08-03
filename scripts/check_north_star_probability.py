#!/usr/bin/env python3
"""Report the canonical after-tax goal without inventing readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.trading_constants import NORTH_STAR_MONTHLY_AFTER_TAX  # noqa: E402
from src.safety.milestone_controller import compute_milestone_snapshot  # noqa: E402


def build_report() -> dict:
    status = compute_milestone_snapshot()
    ns = status.get("north_star_probability", {})
    score = float(ns.get("score", ns.get("probability_score", 0.0)) or 0.0)
    label = str(ns.get("label", ns.get("probability_label", "unknown")) or "unknown")
    estimated = float(ns.get("estimated_monthly_after_tax_from_expectancy", 0.0) or 0.0)
    progress = float(ns.get("monthly_target_progress_pct", 0.0) or 0.0)
    sample = int(ns.get("sample_size", 0) or 0)
    return {
        "goal": {
            "monthly_after_tax_usd": NORTH_STAR_MONTHLY_AFTER_TAX,
            "proof_surface": "confirmed broker-to-bank remittance ledger",
        },
        "assessment": {
            "confidence_score": round(score, 2),
            "label": label.upper(),
            "target_mode": ns.get("target_mode", "unknown"),
            "estimated_monthly_after_tax_from_expectancy": round(estimated, 2),
            "monthly_target_progress_pct": round(progress, 2),
            "sample_size": sample,
        },
        "proven": bool(score > 80 and estimated >= NORTH_STAR_MONTHLY_AFTER_TAX),
        "blockers": [
            "active strategy cohort has insufficient verified closed outcomes"
            if sample < 30
            else None,
            "estimated after-tax run rate is below target"
            if estimated < NORTH_STAR_MONTHLY_AFTER_TAX
            else None,
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    # Embedded callers must not accidentally consume their process arguments.
    args = parser.parse_args([] if argv is None else argv)
    report = build_report()
    report["blockers"] = [item for item in report["blockers"] if item]
    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print("=" * 60)
    print("NORTH STAR PROBABILITY REPORT")
    print("=" * 60)
    print(f"Goal: ${NORTH_STAR_MONTHLY_AFTER_TAX:,.0f}/month after tax")
    assessment = report["assessment"]
    print(f"Confidence Score: {assessment['confidence_score']:.1f}%")
    print(f"Label: {assessment['label']}")
    print(
        "Estimated Monthly (Current Expectancy): "
        f"${assessment['estimated_monthly_after_tax_from_expectancy']:,.2f}"
    )
    print(f"Monthly Target Progress: {assessment['monthly_target_progress_pct']:.2f}%")
    print(f"Proven: {report['proven']}")
    for blocker in report["blockers"]:
        print(f"BLOCK: {blocker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
