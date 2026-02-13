#!/usr/bin/env python3
"""Update weekly North Star gate and contribution plan from current state/trades."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.safety.north_star_operating_plan import apply_operating_plan_to_state

STATE_PATH = PROJECT_ROOT / "data" / "system_state.json"
TRADES_PATH = PROJECT_ROOT / "data" / "trades.json"
WEEKLY_HISTORY_PATH = PROJECT_ROOT / "data" / "north_star_weekly_history.json"


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    state = _load_state(STATE_PATH)
    apply_operating_plan_to_state(
        state,
        trades_path=TRADES_PATH,
        weekly_history_path=WEEKLY_HISTORY_PATH,
    )
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

    weekly = state.get("north_star_weekly_gate", {})
    contrib = state.get("north_star_contributions", {})
    print(
        "Updated North Star plan:",
        f"mode={weekly.get('mode')}",
        f"max_position={weekly.get('recommended_max_position_pct')}",
        f"req_monthly@30%=${contrib.get('required_monthly_contribution_at_assumed_return')}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

