#!/usr/bin/env python3
"""Build North Star blocker report with dated evidence.

This script is intentionally deterministic and side-effect free:
- Reads local state files.
- Computes blocker status + root causes.
- Emits markdown and JSON artifacts for automation.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _to_bool(value: Any, default: bool | None = None) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on", "passed", "pass"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", "failed", "fail"}:
            return False
        return default
    if isinstance(value, (int, float)):
        return bool(value)
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
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _fmt_utc(dt: datetime | None) -> str:
    if dt is None:
        return "n/a"
    return dt.isoformat().replace("+00:00", "Z")


@dataclass
class Blocker:
    id: str
    severity: str
    message: str
    evidence: str


def _normalize_history_rows(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    rows: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "week_start": str(row.get("week_start", "")),
                "updated_at": str(row.get("updated_at", "")),
                "mode": str(row.get("mode", "")),
                "sample_size": _to_int(row.get("sample_size")) or 0,
                "expectancy_per_trade": _to_float(row.get("expectancy_per_trade")),
                "cadence_passed": _to_bool(row.get("cadence_passed"), default=None),
            }
        )
    rows.sort(
        key=lambda r: (
            _parse_dt(r.get("updated_at"))
            or _parse_dt(r.get("week_start"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
    )
    return rows


def compute_report(
    *,
    state: dict[str, Any],
    weekly_history: list[dict[str, Any]],
    halt_exists: bool,
    halt_reason: str = "",
    now_utc: datetime,
) -> dict[str, Any]:
    meta = state.get("meta", {}) if isinstance(state.get("meta"), dict) else {}
    weekly_gate = (
        state.get("north_star_weekly_gate", {})
        if isinstance(state.get("north_star_weekly_gate"), dict)
        else {}
    )
    cadence = (
        weekly_gate.get("cadence_kpi", {})
        if isinstance(weekly_gate.get("cadence_kpi"), dict)
        else {}
    )
    north_star = state.get("north_star", {}) if isinstance(state.get("north_star"), dict) else {}

    blockers: list[Blocker] = []
    warnings: list[Blocker] = []
    root_causes: list[str] = []
    validation_reset_active = bool(
        str(weekly_gate.get("mode") or "").strip().lower() == "validation_reset"
        and _to_bool(weekly_gate.get("allow_validation_entries"), default=False)
        and _to_bool(weekly_gate.get("block_live_new_positions"), default=False)
        and not _to_bool(weekly_gate.get("block_new_positions"), default=False)
    )
    ml_halt_allows_validation = bool(
        halt_exists
        and validation_reset_active
        and "ML GATE BLOCKED" in str(halt_reason or "").upper()
    )

    if ml_halt_allows_validation:
        warnings.append(
            Blocker(
                id="ml_halt_validation_reset_bypass",
                severity="warning",
                message=(
                    "Legacy ML halt is active, but controlled paper validation "
                    "entries remain allowed."
                ),
                evidence=(
                    "data/TRADING_HALTED contains an ML gate halt and "
                    "north_star_weekly_gate is validation_reset with "
                    "allow_validation_entries=true and block_live_new_positions=true."
                ),
            )
        )
        root_causes.append("Legacy ML halt still blocks live/scaling, but not paper validation.")
    elif halt_exists:
        blockers.append(
            Blocker(
                id="trading_halted",
                severity="critical",
                message="TRADING_HALTED is active; new risk-on entries are blocked.",
                evidence="data/TRADING_HALTED exists.",
            )
        )
        root_causes.append("Crisis latch is active.")

    if not weekly_gate:
        blockers.append(
            Blocker(
                id="weekly_gate_missing",
                severity="high",
                message="Weekly North Star gate data is missing.",
                evidence="north_star_weekly_gate not found in system state.",
            )
        )
        root_causes.append("Weekly gate snapshot unavailable.")
    else:
        expectancy = _to_float(weekly_gate.get("expectancy_per_trade"))
        sample_size = _to_int(weekly_gate.get("sample_size")) or 0
        mode = str(weekly_gate.get("mode") or "unknown")

        if _to_bool(weekly_gate.get("block_new_positions"), default=False):
            blockers.append(
                Blocker(
                    id="block_new_positions",
                    severity="high",
                    message="Weekly gate blocks new positions.",
                    evidence=str(weekly_gate.get("reason") or "No reason provided."),
                )
            )
            root_causes.append("Weekly gate set `block_new_positions=true`.")
        elif _to_bool(weekly_gate.get("block_live_new_positions"), default=False):
            blockers.append(
                Blocker(
                    id="live_block_new_positions",
                    severity="high",
                    message="Live/scaling remains blocked while paper validation reset continues.",
                    evidence=str(
                        weekly_gate.get("validation_reset_reason")
                        or weekly_gate.get("reason")
                        or "No reason provided."
                    ),
                )
            )
            root_causes.append(
                "Legacy ledger still blocks live/scaling; paper validation reset is active."
            )

        if _to_bool(weekly_gate.get("scale_blocked_by_cadence"), default=False):
            blockers.append(
                Blocker(
                    id="cadence_scale_block",
                    severity="high",
                    message="Scale-up blocked by cadence KPI.",
                    evidence=(
                        f"setups {cadence.get('qualified_setups_observed')}/"
                        f"{cadence.get('min_qualified_setups_per_week')}, "
                        f"closed trades {cadence.get('closed_trades_observed')}/"
                        f"{cadence.get('min_closed_trades_per_week')}"
                    ),
                )
            )
            root_causes.append("Setup cadence is below weekly minimum.")

        cadence_passed = _to_bool(cadence.get("passed"), default=None)
        if cadence_passed is False:
            blockers.append(
                Blocker(
                    id="cadence_failed",
                    severity="high",
                    message="Cadence KPI is failing.",
                    evidence=str(cadence.get("summary") or "Cadence KPI miss."),
                )
            )
            root_causes.append("Cadence KPI is failing.")

        if expectancy is not None and sample_size >= 1 and expectancy <= 0:
            blockers.append(
                Blocker(
                    id="negative_expectancy",
                    severity="high",
                    message="Per-trade expectancy is non-positive.",
                    evidence=f"expectancy_per_trade={expectancy:.2f}, sample_size={sample_size}.",
                )
            )
            root_causes.append("Trade quality/edge is below zero expectancy.")

        if _to_bool(weekly_gate.get("scale_blocked_by_ai_credit_stress"), default=False):
            blockers.append(
                Blocker(
                    id="ai_credit_stress_block",
                    severity="high",
                    message="Scale-up blocked by AI credit stress signal.",
                    evidence=json.dumps(weekly_gate.get("ai_credit_stress", {}), sort_keys=True),
                )
            )
            root_causes.append("Macro credit-stress block is active.")

        if mode.lower() == "validation":
            warnings.append(
                Blocker(
                    id="validation_mode",
                    severity="warning",
                    message="System is still in validation mode.",
                    evidence="Mode=validation requires conservative sizing until evidence improves.",
                )
            )
        if _to_bool(weekly_gate.get("validation_reset_active"), default=False):
            warnings.append(
                Blocker(
                    id="validation_reset_active",
                    severity="warning",
                    message="Controlled paper-validation reset is active.",
                    evidence=str(
                        weekly_gate.get("reason")
                        or weekly_gate.get("validation_reset_reason")
                        or "Legacy ledger remains negative."
                    ),
                )
            )

    # Staleness checks with concrete timestamps.
    report_last = _parse_dt(meta.get("last_updated")) or _parse_dt(state.get("last_updated"))
    weekly_updated = _parse_dt(weekly_gate.get("updated_at"))
    stale_threshold_hours = 30.0
    for stale_id, label, dt in (
        ("stale_state", "system_state", report_last),
        ("stale_weekly_gate", "north_star_weekly_gate", weekly_updated),
    ):
        if dt is None:
            warnings.append(
                Blocker(
                    id=stale_id,
                    severity="warning",
                    message=f"{label} timestamp unavailable.",
                    evidence="No parseable timestamp.",
                )
            )
            continue
        age_h = (now_utc - dt).total_seconds() / 3600.0
        if age_h > stale_threshold_hours:
            blockers.append(
                Blocker(
                    id=stale_id,
                    severity="high",
                    message=f"{label} is stale.",
                    evidence=f"last_update={_fmt_utc(dt)} age_hours={age_h:.1f} (> {stale_threshold_hours:.0f}h)",
                )
            )
            root_causes.append(f"{label} data is stale.")

    if not root_causes:
        root_causes.append("No active blocker-level root causes detected.")

    probability = _to_float(north_star.get("probability_score"))
    probability_label = str(north_star.get("probability_label") or "unknown")
    recent_history = weekly_history[-8:]
    allow_validation_entries = _to_bool(weekly_gate.get("allow_validation_entries"), default=False)
    block_live_new_positions = _to_bool(weekly_gate.get("block_live_new_positions"), default=False)
    block_new_positions = _to_bool(weekly_gate.get("block_new_positions"), default=False)
    lifetime_ledger = (
        weekly_gate.get("lifetime_ledger", {})
        if isinstance(weekly_gate.get("lifetime_ledger"), dict)
        else {}
    )
    scaling_gate = (
        weekly_gate.get("scaling_sample_gate", {})
        if isinstance(weekly_gate.get("scaling_sample_gate"), dict)
        else {}
    )
    min_scaling_trades = _to_int(scaling_gate.get("min_closed_trades_for_scaling")) or _to_int(
        lifetime_ledger.get("min_closed_trades_for_confirmed_edge")
    )
    closed_for_scaling = _to_int(scaling_gate.get("closed_trades_observed")) or _to_int(
        lifetime_ledger.get("closed_trades")
    )

    if block_new_positions:
        action_lane_summary = "All new risk-on entries are blocked."
    elif allow_validation_entries and block_live_new_positions:
        action_lane_summary = "Controlled paper validation entries are allowed; live trading and scale-up remain blocked."
    elif block_live_new_positions:
        action_lane_summary = "Live trading and scale-up remain blocked."
    else:
        action_lane_summary = "No North Star live/scale lane block is active."

    resolution_criteria: list[str] = []
    if lifetime_ledger:
        min_text = min_scaling_trades if min_scaling_trades is not None else "configured"
        closed_text = closed_for_scaling if closed_for_scaling is not None else "current"
        resolution_criteria.append(
            "Confirm positive edge before live/scaling: "
            f"sample {closed_text}/{min_text}; required metrics are expectancy > 0, "
            "profit factor > 1, and total realized P/L > 0."
        )
    if cadence:
        resolution_criteria.append(
            "Meet weekly cadence KPI: "
            f"qualified setups {cadence.get('qualified_setups_observed')}/"
            f"{cadence.get('min_qualified_setups_per_week')}, closed trades "
            f"{cadence.get('closed_trades_observed')}/{cadence.get('min_closed_trades_per_week')}."
        )
    resolution_criteria.append(
        f"Keep system_state and north_star_weekly_gate fresh within {stale_threshold_hours:.0f} hours."
    )

    return {
        "generated_at_utc": _fmt_utc(now_utc),
        "blocked": bool(blockers),
        "blockers": [asdict(item) for item in blockers],
        "warnings": [asdict(item) for item in warnings],
        "root_causes": root_causes,
        "state_timestamps": {
            "meta_last_updated": _fmt_utc(_parse_dt(meta.get("last_updated"))),
            "state_last_updated": _fmt_utc(_parse_dt(state.get("last_updated"))),
            "weekly_gate_updated_at": _fmt_utc(_parse_dt(weekly_gate.get("updated_at"))),
        },
        "current_gate": {
            "mode": str(weekly_gate.get("mode") or "unknown"),
            "expectancy_per_trade": _to_float(weekly_gate.get("expectancy_per_trade")),
            "sample_size": _to_int(weekly_gate.get("sample_size")),
            "block_new_positions": block_new_positions,
            "block_live_new_positions": block_live_new_positions,
            "allow_validation_entries": allow_validation_entries,
            "validation_reset_active": _to_bool(
                weekly_gate.get("validation_reset_active"), default=False
            ),
            "scale_blocked_by_cadence": _to_bool(
                weekly_gate.get("scale_blocked_by_cadence"), default=False
            ),
            "cadence_summary": str(cadence.get("summary") or ""),
            "qualified_setups_observed": _to_int(cadence.get("qualified_setups_observed")),
            "min_qualified_setups_per_week": _to_int(cadence.get("min_qualified_setups_per_week")),
            "closed_trades_observed": _to_int(cadence.get("closed_trades_observed")),
            "min_closed_trades_per_week": _to_int(cadence.get("min_closed_trades_per_week")),
        },
        "north_star_probability": {
            "score": probability,
            "label": probability_label,
        },
        "action_lane": {
            "summary": action_lane_summary,
            "paper_validation_allowed": bool(allow_validation_entries and not block_new_positions),
            "live_scaling_blocked": bool(block_new_positions or block_live_new_positions),
            "resolution_criteria": resolution_criteria,
        },
        "last_trade_date": str(state.get("trades", {}).get("last_trade_date", "")),
        "trading_halted_file_exists": halt_exists,
        "recent_weekly_history": recent_history,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# North Star Blockers (Automated)")
    lines.append("")
    lines.append(f"- Generated (UTC): `{report.get('generated_at_utc', 'n/a')}`")
    lines.append(
        f"- Trading Halt File: `{'present' if report.get('trading_halted_file_exists') else 'absent'}`"
    )
    lines.append(f"- Last Trade Date: `{report.get('last_trade_date') or 'n/a'}`")
    ts = report.get("state_timestamps", {})
    lines.append(f"- System State Updated (UTC): `{ts.get('meta_last_updated', 'n/a')}`")
    lines.append(f"- Weekly Gate Updated (UTC): `{ts.get('weekly_gate_updated_at', 'n/a')}`")
    lines.append("")

    gate = report.get("current_gate", {})
    prob = report.get("north_star_probability", {})
    lines.append("## Current Gate Snapshot")
    lines.append(f"- Mode: `{gate.get('mode', 'unknown')}`")
    lines.append(f"- Expectancy / Trade: `{gate.get('expectancy_per_trade')}`")
    lines.append(f"- Sample Size: `{gate.get('sample_size')}`")
    lines.append(f"- Block New Positions: `{gate.get('block_new_positions')}`")
    lines.append(f"- Block Live/Scale Only: `{gate.get('block_live_new_positions')}`")
    lines.append(f"- Allow Validation Entries: `{gate.get('allow_validation_entries')}`")
    lines.append(
        "- Cadence: "
        f"`{gate.get('qualified_setups_observed')}/{gate.get('min_qualified_setups_per_week')}` setups, "
        f"`{gate.get('closed_trades_observed')}/{gate.get('min_closed_trades_per_week')}` closed trades"
    )
    lines.append(f"- Cadence Summary: {gate.get('cadence_summary') or 'n/a'}")
    lines.append(
        f"- North Star Probability: `{prob.get('score')}` (`{prob.get('label', 'unknown')}`)"
    )
    lines.append("")

    lane = report.get("action_lane", {})
    lines.append("## Action Lane")
    lines.append(f"- Summary: {lane.get('summary') or 'n/a'}")
    lines.append(f"- Paper Validation Allowed: `{lane.get('paper_validation_allowed')}`")
    lines.append(f"- Live/Scaling Blocked: `{lane.get('live_scaling_blocked')}`")
    lines.append("- Resolution Criteria:")
    criteria = lane.get("resolution_criteria", [])
    if criteria:
        for i, item in enumerate(criteria, start=1):
            lines.append(f"  {i}. {item}")
    else:
        lines.append("  1. None.")
    lines.append("")

    blockers = report.get("blockers", [])
    warnings = report.get("warnings", [])
    if blockers:
        lines.append("## Active Blockers")
        for i, blocker in enumerate(blockers, start=1):
            lines.append(
                f"{i}. **[{blocker.get('severity', 'unknown').upper()}] {blocker.get('message')}**"
            )
            lines.append(f"   Evidence: `{blocker.get('evidence')}`")
    else:
        lines.append("## Active Blockers")
        lines.append("1. None. North Star blockers are currently clear.")

    if warnings:
        lines.append("")
        lines.append("## Warnings")
        for i, warning in enumerate(warnings, start=1):
            lines.append(f"{i}. {warning.get('message')}")
            lines.append(f"   Evidence: `{warning.get('evidence')}`")

    lines.append("")
    lines.append("## Root Cause Snapshot")
    for i, item in enumerate(report.get("root_causes", []), start=1):
        lines.append(f"{i}. {item}")

    history = report.get("recent_weekly_history", [])
    lines.append("")
    lines.append("## Recent Weekly Evidence")
    lines.append("")
    lines.append("| Week Start | Updated At (UTC) | Mode | Sample | Expectancy | Cadence Passed |")
    lines.append("|---|---|---|---:|---:|---|")
    if history:
        for row in history:
            lines.append(
                "| "
                + f"{row.get('week_start') or 'n/a'} | "
                + f"{row.get('updated_at') or 'n/a'} | "
                + f"{row.get('mode') or 'n/a'} | "
                + f"{row.get('sample_size') if row.get('sample_size') is not None else 'n/a'} | "
                + f"{row.get('expectancy_per_trade') if row.get('expectancy_per_trade') is not None else 'n/a'} | "
                + f"{row.get('cadence_passed') if row.get('cadence_passed') is not None else 'n/a'} |"
            )
    else:
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a |")

    lines.append("")
    lines.append(
        "_Auto-generated. This issue is updated by workflow and auto-closed when blockers clear._"
    )
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build North Star blocker report artifacts.")
    parser.add_argument("--state", default="data/system_state.json")
    parser.add_argument("--history", default="data/north_star_weekly_history.json")
    parser.add_argument("--halt-file", default="data/TRADING_HALTED")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--print-markdown", action="store_true")
    parser.add_argument("--fail-on-blockers", action="store_true")
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    state_path = Path(args.state)
    history_path = Path(args.history)
    halt_file = Path(args.halt_file)

    state = _load_json(state_path)
    if not isinstance(state, dict):
        state = {}
    history = _normalize_history_rows(_load_json(history_path))
    now_utc = datetime.now(timezone.utc)

    report = compute_report(
        state=state,
        weekly_history=history,
        halt_exists=halt_file.exists(),
        halt_reason=halt_file.read_text(encoding="utf-8", errors="ignore")
        if halt_file.exists()
        else "",
        now_utc=now_utc,
    )
    markdown = render_markdown(report)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.markdown_out:
        out = Path(args.markdown_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")

    print(json.dumps(report))
    if args.print_markdown:
        print(markdown)

    if args.fail_on_blockers and report.get("blocked"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
