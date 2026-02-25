"""Autonomous North Star optimization and monitoring.

This module converts weekly gate diagnostics into deterministic automation:
- Cadence optimizer: safe liquidity-floor tuning when cadence is blocked by liquidity.
- Regime-aware sizing tuner: applies macro/regime multipliers to the weekly size cap.
- Hard gate monitor: fail-closed checks for stale/missing state and target mismatch.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.trading_constants import NORTH_STAR_MONTHLY_AFTER_TAX
from src.safety.north_star_operating_plan import DEFAULT_MIN_LIQUIDITY_VOLUME_RATIO

DEFAULT_GATE_OVERRIDE_RELATIVE_PATH = Path("runtime/north_star_gate_overrides.json")
DEFAULT_STALE_THRESHOLD_HOURS = 30.0


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_dt(raw: Any) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    candidates = [text, text.replace("Z", "+00:00"), f"{text}T00:00:00+00:00"]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _clamp(value: float, *, lo: float, hi: float) -> float:
    return min(hi, max(lo, value))


def _weekly_gate(state: dict[str, Any]) -> dict[str, Any]:
    payload = state.get("north_star_weekly_gate", {})
    return payload if isinstance(payload, dict) else {}


def _cadence_kpi(weekly_gate: dict[str, Any]) -> dict[str, Any]:
    payload = weekly_gate.get("cadence_kpi", {})
    return payload if isinstance(payload, dict) else {}


def _no_trade_diag(weekly_gate: dict[str, Any]) -> dict[str, Any]:
    payload = weekly_gate.get("no_trade_diagnostic", {})
    return payload if isinstance(payload, dict) else {}


def _gate_status(diag: dict[str, Any]) -> dict[str, Any]:
    payload = diag.get("gate_status", {})
    return payload if isinstance(payload, dict) else {}


def compute_cadence_optimizer(state: dict[str, Any]) -> dict[str, Any]:
    """Return safe cadence tuning decisions from current weekly evidence."""
    weekly = _weekly_gate(state)
    cadence = _cadence_kpi(weekly)
    diag = _no_trade_diag(weekly)
    gate_status = _gate_status(diag)

    current_floor = _clamp(
        _to_float(
            weekly.get("liquidity_min_volume_ratio"),
            _to_float(
                gate_status.get("liquidity", {}).get("threshold_min_volume_ratio"),
                DEFAULT_MIN_LIQUIDITY_VOLUME_RATIO,
            ),
        ),
        lo=0.10,
        hi=0.50,
    )
    blocked_categories = diag.get("blocked_categories", [])
    if not isinstance(blocked_categories, list):
        blocked_categories = []
    blocked_categories = [str(item).lower() for item in blocked_categories]

    block_counts = diag.get("gate_block_counts", {})
    if not isinstance(block_counts, dict):
        block_counts = {}
    liquidity_blocks = _to_int(block_counts.get("liquidity"), 0)
    total_blocks = sum(_to_int(v, 0) for v in block_counts.values())
    liquidity_share = (liquidity_blocks / total_blocks) if total_blocks > 0 else 0.0

    setups_observed = _to_int(cadence.get("qualified_setups_observed"), 0)
    setups_min = _to_int(cadence.get("min_qualified_setups_per_week"), 0)
    setups_shortfall = max(0, setups_min - setups_observed)
    cadence_passed = bool(cadence.get("passed"))

    ai_status = str(gate_status.get("ai_credit_stress", {}).get("status") or "unknown").lower()
    usd_status = str(gate_status.get("usd_macro", {}).get("status") or "unknown").lower()
    block_new_positions = bool(weekly.get("block_new_positions"))
    expectancy = _to_float(weekly.get("expectancy_per_trade"), 0.0)

    decision = "hold"
    reason = "Liquidity floor unchanged."
    target_floor = current_floor

    tune_eligible = (
        not cadence_passed
        and setups_shortfall > 0
        and ("liquidity" in blocked_categories or liquidity_blocks > 0)
        and ai_status != "blocked"
        and usd_status != "blocked"
        and not block_new_positions
    )
    if tune_eligible and liquidity_share >= 0.50:
        target_floor = _clamp(round(current_floor - 0.02, 2), lo=0.15, hi=0.50)
        if target_floor < current_floor:
            decision = "loosen_liquidity_floor"
            reason = (
                "Cadence shortfall is dominated by liquidity blocks; "
                f"reduce floor from {current_floor:.2f} to {target_floor:.2f}."
            )
    elif block_new_positions:
        decision = "hold_risk_blocked"
        reason = "Block-new-positions is active; no cadence tuning is applied."
    elif ai_status == "blocked" or usd_status == "blocked":
        decision = "hold_macro_blocked"
        reason = "Macro stress is blocked; keep liquidity floor conservative."
    elif expectancy <= 0 and _to_int(weekly.get("sample_size"), 0) >= 5:
        decision = "hold_negative_expectancy"
        reason = "Expectancy is non-positive with sufficient samples; keep floor unchanged."

    return {
        "decision": decision,
        "reason": reason,
        "cadence_passed": cadence_passed,
        "setups_shortfall": setups_shortfall,
        "liquidity_block_share": round(liquidity_share, 4),
        "liquidity_blocks": liquidity_blocks,
        "target_min_liquidity_volume_ratio": round(target_floor, 4),
        "current_min_liquidity_volume_ratio": round(current_floor, 4),
        "apply_override": bool(target_floor < current_floor),
    }


def compute_regime_aware_sizing(state: dict[str, Any]) -> dict[str, Any]:
    """Return a tuned position cap from weekly gate + macro signals."""
    weekly = _weekly_gate(state)
    diag = _no_trade_diag(weekly)
    gate_status = _gate_status(diag)

    base_cap = _clamp(
        _to_float(weekly.get("recommended_max_position_pct"), 0.02), lo=0.005, hi=0.05
    )
    if bool(weekly.get("block_new_positions")):
        return {
            "base_max_position_pct": round(base_cap, 4),
            "recommended_max_position_pct": 0.0,
            "block_new_positions": True,
            "applied_multipliers": [{"name": "weekly_block", "value": 0.0}],
            "reason": "Weekly gate blocks new positions.",
        }

    multipliers: list[dict[str, Any]] = []
    tuned_cap = base_cap

    ai_status = str(gate_status.get("ai_credit_stress", {}).get("status") or "unknown").lower()
    if ai_status == "watch":
        tuned_cap *= 0.90
        multipliers.append({"name": "ai_credit_stress_watch", "value": 0.90})
    elif ai_status == "blocked":
        tuned_cap *= 0.75
        multipliers.append({"name": "ai_credit_stress_blocked", "value": 0.75})

    usd_multiplier = _to_float(
        weekly.get("scale_multiplier_from_usd_macro"),
        _to_float(gate_status.get("usd_macro", {}).get("position_size_multiplier"), 1.0),
    )
    usd_multiplier = _clamp(usd_multiplier, lo=0.10, hi=1.00)
    if usd_multiplier < 1.0:
        tuned_cap *= usd_multiplier
        multipliers.append({"name": "usd_macro_multiplier", "value": round(usd_multiplier, 4)})

    regime_status = str(gate_status.get("regime", {}).get("status") or "unknown").lower()
    if regime_status == "blocked":
        tuned_cap *= 0.90
        multipliers.append({"name": "regime_blocked", "value": 0.90})

    ai_cycle_gate = gate_status.get("ai_cycle", {}) if isinstance(gate_status, dict) else {}
    ai_cycle_status = str(ai_cycle_gate.get("status") or "unknown").lower()
    ai_cycle_multiplier = _to_float(ai_cycle_gate.get("position_size_multiplier"), 1.0)
    if ai_cycle_multiplier <= 0:
        ai_cycle_multiplier = 1.0
    ai_cycle_multiplier = _clamp(ai_cycle_multiplier, lo=0.10, hi=1.00)
    if ai_cycle_status in {"watch", "blocked"} and ai_cycle_multiplier < 1.0:
        tuned_cap *= ai_cycle_multiplier
        multipliers.append(
            {"name": "ai_cycle_multiplier", "value": round(ai_cycle_multiplier, 4)}
        )

    if bool(ai_cycle_gate.get("capex_deceleration_shock")):
        tuned_cap *= 0.80
        multipliers.append({"name": "ai_cycle_capex_shock", "value": 0.80})

    tuned_cap = _clamp(tuned_cap, lo=0.005, hi=base_cap)
    if not multipliers:
        multipliers.append({"name": "none", "value": 1.0})

    return {
        "base_max_position_pct": round(base_cap, 4),
        "recommended_max_position_pct": round(tuned_cap, 4),
        "block_new_positions": False,
        "applied_multipliers": multipliers,
        "reason": "Applied regime/macro multipliers to weekly cap.",
    }


def compute_hard_gate_monitor(
    state: dict[str, Any],
    *,
    now_utc: datetime,
    halt_exists: bool,
    stale_threshold_hours: float = DEFAULT_STALE_THRESHOLD_HOURS,
) -> dict[str, Any]:
    """Return critical/warning monitor state for autonomous fail-closed checks."""
    weekly = _weekly_gate(state)
    meta = state.get("meta", {}) if isinstance(state.get("meta"), dict) else {}
    north_star = state.get("north_star", {}) if isinstance(state.get("north_star"), dict) else {}

    checks: list[dict[str, Any]] = []

    def add_check(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    if halt_exists:
        add_check("trading_halted", "critical", "data/TRADING_HALTED exists.")
    else:
        add_check("trading_halted", "ok", "halt file absent.")

    if weekly:
        add_check("weekly_gate_presence", "ok", "north_star_weekly_gate is present.")
    else:
        add_check("weekly_gate_presence", "critical", "north_star_weekly_gate missing.")

    state_updated = _parse_dt(meta.get("last_updated") or state.get("last_updated"))
    if state_updated is None:
        add_check("state_freshness", "warning", "system_state timestamp missing.")
    else:
        age_hours = (now_utc - state_updated).total_seconds() / 3600.0
        if age_hours > stale_threshold_hours:
            add_check(
                "state_freshness",
                "critical",
                f"system_state stale by {age_hours:.1f}h (> {stale_threshold_hours:.0f}h).",
            )
        else:
            add_check("state_freshness", "ok", f"fresh ({age_hours:.1f}h old).")

    weekly_updated = _parse_dt(weekly.get("updated_at")) if weekly else None
    if weekly_updated is None:
        add_check("weekly_gate_freshness", "warning", "weekly gate timestamp missing.")
    else:
        age_hours = (now_utc - weekly_updated).total_seconds() / 3600.0
        if age_hours > stale_threshold_hours:
            add_check(
                "weekly_gate_freshness",
                "critical",
                f"weekly gate stale by {age_hours:.1f}h (> {stale_threshold_hours:.0f}h).",
            )
        else:
            add_check("weekly_gate_freshness", "ok", f"fresh ({age_hours:.1f}h old).")

    monthly_target = _to_float(
        north_star.get("monthly_after_tax_target"),
        _to_float(
            state.get("north_star_contributions", {}).get("monthly_after_tax_target"),
            NORTH_STAR_MONTHLY_AFTER_TAX,
        ),
    )
    if abs(monthly_target - NORTH_STAR_MONTHLY_AFTER_TAX) > 1e-6:
        add_check(
            "north_star_monthly_target",
            "critical",
            f"monthly_after_tax_target mismatch ({monthly_target:.2f} != {NORTH_STAR_MONTHLY_AFTER_TAX:.2f}).",
        )
    else:
        add_check("north_star_monthly_target", "ok", "monthly target is consistent.")

    critical = [c for c in checks if c["status"] == "critical"]
    warnings = [c for c in checks if c["status"] == "warning"]
    status = "critical" if critical else ("warning" if warnings else "ok")

    return {
        "status": status,
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "block_new_positions": len(critical) > 0,
        "checks": checks,
    }


def build_execution_actions(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    cadence = snapshot.get("cadence_optimizer", {})
    sizing = snapshot.get("regime_aware_sizing", {})
    hard_gate = snapshot.get("hard_gate_monitor", {})
    blocker = snapshot.get("blocker_report", {})

    actions: list[dict[str, Any]] = []
    if hard_gate.get("status") == "critical":
        actions.append(
            {
                "priority": 1,
                "action": "freeze_new_positions",
                "automated": True,
                "reason": "Hard gate monitor is critical.",
            }
        )
    if cadence.get("apply_override"):
        actions.append(
            {
                "priority": 2,
                "action": "apply_liquidity_floor_override",
                "automated": True,
                "reason": str(cadence.get("reason") or ""),
            }
        )
    if _to_float(sizing.get("recommended_max_position_pct"), 0.0) < _to_float(
        sizing.get("base_max_position_pct"), 0.0
    ):
        actions.append(
            {
                "priority": 3,
                "action": "enforce_regime_sizing_cap",
                "automated": True,
                "reason": str(sizing.get("reason") or ""),
            }
        )
    if blocker.get("blocked"):
        actions.append(
            {
                "priority": 4,
                "action": "publish_blocker_report",
                "automated": True,
                "reason": "Blockers detected; report should stay visible.",
            }
        )
    actions.sort(key=lambda item: int(item.get("priority", 99)))
    return actions


def build_autopilot_snapshot(
    *,
    state: dict[str, Any],
    blocker_report: dict[str, Any],
    now_utc: datetime,
    halt_exists: bool,
) -> dict[str, Any]:
    cadence_optimizer = compute_cadence_optimizer(state)
    regime_sizing = compute_regime_aware_sizing(state)
    hard_gate_monitor = compute_hard_gate_monitor(
        state,
        now_utc=now_utc,
        halt_exists=halt_exists,
    )
    snapshot = {
        "generated_at_utc": now_utc.isoformat().replace("+00:00", "Z"),
        "cadence_optimizer": cadence_optimizer,
        "regime_aware_sizing": regime_sizing,
        "hard_gate_monitor": hard_gate_monitor,
        "blocker_report": {
            "blocked": bool(blocker_report.get("blocked")),
            "blocker_count": len(blocker_report.get("blockers", []))
            if isinstance(blocker_report.get("blockers"), list)
            else 0,
            "warning_count": len(blocker_report.get("warnings", []))
            if isinstance(blocker_report.get("warnings"), list)
            else 0,
            "root_causes": blocker_report.get("root_causes", []),
        },
    }
    snapshot["active_overrides"] = {
        "min_liquidity_volume_ratio": cadence_optimizer.get("target_min_liquidity_volume_ratio"),
        "max_position_pct_cap": regime_sizing.get("recommended_max_position_pct"),
    }
    snapshot["execution_actions"] = build_execution_actions(snapshot)
    return snapshot


def render_autopilot_markdown(snapshot: dict[str, Any]) -> str:
    cadence = snapshot.get("cadence_optimizer", {})
    sizing = snapshot.get("regime_aware_sizing", {})
    hard_gate = snapshot.get("hard_gate_monitor", {})
    blocker = snapshot.get("blocker_report", {})
    lines: list[str] = []
    lines.append("# North Star Autopilot")
    lines.append("")
    lines.append(f"- Generated (UTC): `{snapshot.get('generated_at_utc', 'n/a')}`")
    lines.append(f"- Hard Gate Status: `{hard_gate.get('status', 'unknown')}`")
    lines.append(
        f"- Blockers: `{blocker.get('blocked', False)}` "
        f"(count={blocker.get('blocker_count', 0)}, warnings={blocker.get('warning_count', 0)})"
    )
    lines.append("")
    lines.append("## Cadence Optimizer")
    lines.append(f"- Decision: `{cadence.get('decision', 'unknown')}`")
    lines.append(
        f"- Current Liquidity Floor: `{cadence.get('current_min_liquidity_volume_ratio')}`"
    )
    lines.append(f"- Target Liquidity Floor: `{cadence.get('target_min_liquidity_volume_ratio')}`")
    lines.append(f"- Reason: {cadence.get('reason', 'n/a')}")
    lines.append("")
    lines.append("## Regime-Aware Sizing")
    lines.append(f"- Base Max Position %: `{sizing.get('base_max_position_pct')}`")
    lines.append(f"- Tuned Max Position %: `{sizing.get('recommended_max_position_pct')}`")
    lines.append(f"- Block New Positions: `{sizing.get('block_new_positions')}`")
    lines.append("")
    lines.append("## Hard Gate Checks")
    for check in hard_gate.get("checks", []):
        lines.append(
            f"- `{check.get('name', 'unknown')}` -> `{check.get('status', 'unknown')}`: {check.get('detail', '')}"
        )
    lines.append("")
    lines.append("## Execution Actions")
    actions = snapshot.get("execution_actions", [])
    if actions:
        for idx, action in enumerate(actions, start=1):
            lines.append(
                f"{idx}. `{action.get('action')}` (priority={action.get('priority')}, automated={action.get('automated')})"
            )
            lines.append(f"   Reason: {action.get('reason', 'n/a')}")
    else:
        lines.append("1. None.")
    lines.append("")
    return "\n".join(lines)


def write_gate_overrides(
    *,
    data_dir: Path,
    snapshot: dict[str, Any],
    now_utc: datetime,
) -> dict[str, Any]:
    """Persist liquidity-floor override so weekly gate math can consume it."""
    overrides = snapshot.get("active_overrides", {})
    min_liq = _to_float(
        overrides.get("min_liquidity_volume_ratio"),
        DEFAULT_MIN_LIQUIDITY_VOLUME_RATIO,
    )
    min_liq = _clamp(min_liq, lo=0.10, hi=0.50)

    payload = {
        "min_liquidity_volume_ratio": round(min_liq, 4),
        "updated_at": now_utc.isoformat(),
        "source": "north_star_autopilot",
    }
    path = data_dir / DEFAULT_GATE_OVERRIDE_RELATIVE_PATH
    previous: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                previous = loaded
        except Exception:
            previous = {}

    changed = _to_float(previous.get("min_liquidity_volume_ratio"), -1.0) != _to_float(
        payload.get("min_liquidity_volume_ratio"),
        -2.0,
    )
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    return {
        "path": str(path),
        "changed": changed,
        "payload": payload,
    }


def apply_snapshot_to_state(state: dict[str, Any], snapshot: dict[str, Any]) -> None:
    state["north_star_autopilot"] = snapshot
