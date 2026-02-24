#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

# Import constants from the single source of truth
from src.core.trading_constants import (
    NORTH_STAR_MONTHLY_AFTER_TAX,
    NORTH_STAR_PAPER_VALIDATION_DAYS,
    NORTH_STAR_TARGET_WIN_RATE_PCT,
)

logger = logging.getLogger(__name__)


def main():
    repo_root = Path(__file__).parent.parent.resolve()
    system_state_path = repo_root / "data/system_state.json"
    artifact_path = repo_root / "artifacts/devloop/promotion_gate.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)

    if not system_state_path.exists():
        print(f"❌ Error: {system_state_path} not found.")
        return

    with open(system_state_path) as f:
        state = json.load(f)

    # Extract metrics
    # Note: Using the paper account metrics for promotion decisions
    paper = state.get("paper_trading", {})
    win_rate = float(paper.get("win_rate", 0.0) or 0.0) * 100.0

    # Calculate run rate from history if possible
    # (Simple version: use the milestone controller's estimate if available)
    milestones = state.get("strategy_milestones", {})
    families = milestones.get("strategy_families", {})
    options_income = families.get("options_income", {})
    metrics = options_income.get("metrics", {})
    run_rate = float(metrics.get("monthly_run_rate", 0.0) or 0.0)

    # Gate Logic
    status = "BLOCKED"
    reasons = []

    # Check 1: Win Rate
    if win_rate < NORTH_STAR_TARGET_WIN_RATE_PCT:
        reasons.append(f"Win Rate {win_rate:.1f}% below target {NORTH_STAR_TARGET_WIN_RATE_PCT}%")

    # Check 2: Validation Days
    start_date_str = paper.get("start_date")
    if start_date_str:
        start_date = datetime.fromisoformat(start_date_str)
        days_elapsed = (datetime.now() - start_date).days
        if days_elapsed < NORTH_STAR_PAPER_VALIDATION_DAYS:
            reasons.append(
                f"Validation period {days_elapsed}d below target {NORTH_STAR_PAPER_VALIDATION_DAYS}d"
            )
    else:
        reasons.append("Paper trading start date missing")

    # Final Decision
    if not reasons:
        status = "OPEN"
        summary = "All strategy promotion criteria met. Ready for live scaling."
    else:
        summary = f"Promotion blocked: {'; '.join(reasons)}"

    gate_artifact = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "summary": summary,
        "metrics": {
            "current_win_rate_pct": round(win_rate, 2),
            "target_win_rate_pct": NORTH_STAR_TARGET_WIN_RATE_PCT,
            "current_run_rate_mo": round(run_rate, 2),
            "target_run_rate_mo": NORTH_STAR_MONTHLY_AFTER_TAX,
            "days_validated": days_elapsed if "days_elapsed" in locals() else 0,
        },
        "blockers": reasons,
    }

    with open(artifact_path, "w") as f:
        json.dump(gate_artifact, f, indent=2)

    print(f"✅ Promotion gate generated: {status}")
    print(f"   Summary: {summary}")


if __name__ == "__main__":
    main()
