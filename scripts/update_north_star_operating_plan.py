#!/usr/bin/env python3
"""Update weekly North Star gate and contribution plan from current state/trades."""

# ruff: noqa: E402

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.safety.milestone_controller import (
    apply_snapshot_to_state as apply_milestone_snapshot_to_state,
)
from src.safety.milestone_controller import (
    compute_milestone_snapshot,
)
from src.safety.north_star_autopilot import (
    apply_snapshot_to_state as apply_autopilot_snapshot_to_state,
)
from src.safety.north_star_autopilot import (
    build_autopilot_snapshot,
    render_autopilot_markdown,
    write_gate_overrides,
)
from src.safety.north_star_operating_plan import apply_operating_plan_to_state

from scripts.build_north_star_blocker_report import compute_report

STATE_PATH = PROJECT_ROOT / "data" / "system_state.json"
TRADES_PATH = PROJECT_ROOT / "data" / "trades.json"
WEEKLY_HISTORY_PATH = PROJECT_ROOT / "data" / "north_star_weekly_history.json"
HALT_FILE = PROJECT_ROOT / "data" / "TRADING_HALTED"
AUTOPILOT_JSON_PATH = PROJECT_ROOT / "artifacts" / "devloop" / "north_star_autopilot_report.json"
AUTOPILOT_MD_PATH = PROJECT_ROOT / "artifacts" / "devloop" / "north_star_autopilot_report.md"


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def _run_autopilot(state: dict[str, Any]) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    blocker_report = compute_report(
        state=state,
        weekly_history=_load_history(WEEKLY_HISTORY_PATH),
        halt_exists=HALT_FILE.exists(),
        now_utc=now_utc,
    )
    snapshot = build_autopilot_snapshot(
        state=state,
        blocker_report=blocker_report,
        now_utc=now_utc,
        halt_exists=HALT_FILE.exists(),
    )
    apply_autopilot_snapshot_to_state(state, snapshot)

    override_result = write_gate_overrides(
        data_dir=STATE_PATH.parent,
        snapshot=snapshot,
        now_utc=now_utc,
    )
    # If override changed, recompute weekly gate immediately and refresh snapshot.
    if bool(override_result.get("changed")):
        apply_operating_plan_to_state(
            state,
            trades_path=TRADES_PATH,
            weekly_history_path=WEEKLY_HISTORY_PATH,
        )
        now_utc = datetime.now(timezone.utc)
        blocker_report = compute_report(
            state=state,
            weekly_history=_load_history(WEEKLY_HISTORY_PATH),
            halt_exists=HALT_FILE.exists(),
            now_utc=now_utc,
        )
        snapshot = build_autopilot_snapshot(
            state=state,
            blocker_report=blocker_report,
            now_utc=now_utc,
            halt_exists=HALT_FILE.exists(),
        )
        apply_autopilot_snapshot_to_state(state, snapshot)
        override_result = write_gate_overrides(
            data_dir=STATE_PATH.parent,
            snapshot=snapshot,
            now_utc=now_utc,
        )

    snapshot["override_write"] = override_result
    return snapshot


def main() -> int:
    state = _load_state(STATE_PATH)
    apply_operating_plan_to_state(
        state,
        trades_path=TRADES_PATH,
        weekly_history_path=WEEKLY_HISTORY_PATH,
    )
    snapshot = _run_autopilot(state)
    milestone_snapshot = compute_milestone_snapshot(
        state=state,
        state_path=STATE_PATH,
        trades_path=TRADES_PATH,
    )
    apply_milestone_snapshot_to_state(state, milestone_snapshot)

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    AUTOPILOT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTOPILOT_JSON_PATH.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    AUTOPILOT_MD_PATH.write_text(render_autopilot_markdown(snapshot), encoding="utf-8")

    weekly = state.get("north_star_weekly_gate", {})
    contrib = state.get("north_star_contributions", {})
    hard_gate = snapshot.get("hard_gate_monitor", {})
    cadence = snapshot.get("cadence_optimizer", {})
    print(
        "Updated North Star plan:",
        f"mode={weekly.get('mode')}",
        f"max_position={weekly.get('recommended_max_position_pct')}",
        f"monthly_target=${contrib.get('monthly_after_tax_target')}",
        f"month_progress={contrib.get('monthly_target_progress_pct')}%",
        f"autopilot_hard_gate={hard_gate.get('status')}",
        f"cadence_decision={cadence.get('decision')}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
