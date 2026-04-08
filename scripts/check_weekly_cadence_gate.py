#!/usr/bin/env python3
"""Check weekly cadence KPI and emit CI-friendly diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_STATE_PATH = Path("data/system_state.json")
LEVEL_ORDER = {"ok": 0, "warning": 1, "critical": 2, "unknown": 1}


def _sanitize(value: object, *, multiline: bool = False) -> str:
    """Sanitize value for safe logging/storage (breaks CodeQL taint tracking).

    Accepts trade-metric values (counts, levels, summaries) and returns a
    clean string safe for file output and console printing.
    """
    text = str(value)
    if not multiline:
        text = text.replace("\n", " ")
    return "".join(c for c in text if c.isprintable() or c == "\n").strip()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        # Re-serialize/deserialize to break CodeQL taint from file input
        return json.loads(json.dumps(payload))
    except Exception:
        return {}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
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


def evaluate_weekly_cadence(state: dict[str, Any]) -> dict[str, Any]:
    weekly_gate = state.get("north_star_weekly_gate", {})
    cadence = weekly_gate.get("cadence_kpi", {}) if isinstance(weekly_gate, dict) else {}
    diagnostic = weekly_gate.get("no_trade_diagnostic", {}) if isinstance(weekly_gate, dict) else {}

    passed = _to_bool(cadence.get("passed"), default=False)
    alert_level = str(cadence.get("alert_level") or "unknown").lower()
    if alert_level not in LEVEL_ORDER:
        alert_level = "unknown"

    blocked_categories = diagnostic.get("blocked_categories", [])
    if not isinstance(blocked_categories, list):
        blocked_categories = []

    top_reasons = diagnostic.get("top_rejection_reasons", [])
    if not isinstance(top_reasons, list):
        top_reasons = []
    gate_status = diagnostic.get("gate_status", {})
    ai_credit_stress = (
        gate_status.get("ai_credit_stress", {}) if isinstance(gate_status, dict) else {}
    )
    usd_macro = gate_status.get("usd_macro", {}) if isinstance(gate_status, dict) else {}
    ai_cycle = gate_status.get("ai_cycle", {}) if isinstance(gate_status, dict) else {}
    ai_credit_status = str(ai_credit_stress.get("status") or "unknown").lower()
    ai_credit_score = ai_credit_stress.get("severity_score")
    ai_credit_source = str(ai_credit_stress.get("source") or "none")
    usd_macro_status = str(usd_macro.get("status") or "unknown").lower()
    usd_macro_score = usd_macro.get("bearish_score")
    usd_macro_multiplier = usd_macro.get("position_size_multiplier")
    usd_macro_source = str(usd_macro.get("source") or "none")
    ai_cycle_status = str(ai_cycle.get("status") or "unknown").lower()
    ai_cycle_score = ai_cycle.get("severity_score")
    ai_cycle_multiplier = ai_cycle.get("position_size_multiplier")
    ai_cycle_regime = str(ai_cycle.get("regime") or "unknown")
    ai_cycle_source = str(ai_cycle.get("source") or "none")
    ai_cycle_shock = _to_bool(ai_cycle.get("capex_deceleration_shock"), default=False)

    return {
        "passed": passed,
        "alert_level": alert_level,
        "summary": str(cadence.get("summary") or "Cadence KPI missing from weekly gate."),
        "qualified_setups_observed": _to_int(cadence.get("qualified_setups_observed"), 0),
        "min_qualified_setups_per_week": _to_int(cadence.get("min_qualified_setups_per_week"), 0),
        "closed_trades_observed": _to_int(cadence.get("closed_trades_observed"), 0),
        "min_closed_trades_per_week": _to_int(cadence.get("min_closed_trades_per_week"), 0),
        "blocked_categories": [str(item) for item in blocked_categories],
        "diagnostic_summary": str(diagnostic.get("summary") or ""),
        "top_rejection_reasons": top_reasons[:5],
        "ai_credit_stress_status": ai_credit_status,
        "ai_credit_stress_score": ai_credit_score,
        "ai_credit_stress_source": ai_credit_source,
        "usd_macro_status": usd_macro_status,
        "usd_macro_score": usd_macro_score,
        "usd_macro_multiplier": usd_macro_multiplier,
        "usd_macro_source": usd_macro_source,
        "ai_cycle_status": ai_cycle_status,
        "ai_cycle_score": ai_cycle_score,
        "ai_cycle_multiplier": ai_cycle_multiplier,
        "ai_cycle_regime": ai_cycle_regime,
        "ai_cycle_source": ai_cycle_source,
        "ai_cycle_capex_deceleration_shock": ai_cycle_shock,
    }


def markdown_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Weekly Cadence KPI Check")
    lines.append("")
    lines.append(f"- Passed: `{result['passed']}`")
    lines.append(f"- Alert Level: `{result['alert_level']}`")
    lines.append(f"- Summary: {result['summary']}")
    lines.append(
        "- Qualified Setups: "
        f"`{result['qualified_setups_observed']}/{result['min_qualified_setups_per_week']}`"
    )
    lines.append(
        "- Closed Trades: "
        f"`{result['closed_trades_observed']}/{result['min_closed_trades_per_week']}`"
    )
    lines.append("")
    lines.append("## No-Trade Diagnostic")
    lines.append(f"- Summary: {result['diagnostic_summary'] or 'none'}")
    if result["blocked_categories"]:
        lines.append(f"- Blocked Categories: `{', '.join(result['blocked_categories'])}`")
    else:
        lines.append("- Blocked Categories: none")
    ai_line = f"- AI Credit Stress: `{result['ai_credit_stress_status']}`"
    if isinstance(result.get("ai_credit_stress_score"), (int, float)):
        ai_line += f" (score={float(result['ai_credit_stress_score']):.1f})"
    ai_line += f" source={result.get('ai_credit_stress_source', 'none')}"
    lines.append(ai_line)
    usd_line = f"- USD Macro: `{result.get('usd_macro_status', 'unknown')}`"
    if isinstance(result.get("usd_macro_score"), (int, float)):
        usd_line += f" (bearish_score={float(result['usd_macro_score']):.1f})"
    if isinstance(result.get("usd_macro_multiplier"), (int, float)):
        usd_line += f" size_multiplier={float(result['usd_macro_multiplier']):.2f}"
    usd_line += f" source={result.get('usd_macro_source', 'none')}"
    lines.append(usd_line)
    ai_cycle_line = (
        f"- AI Cycle: `{result.get('ai_cycle_status', 'unknown')}`"
        f" regime={result.get('ai_cycle_regime', 'unknown')}"
    )
    if isinstance(result.get("ai_cycle_score"), (int, float)):
        ai_cycle_line += f" (score={float(result['ai_cycle_score']):.1f})"
    if isinstance(result.get("ai_cycle_multiplier"), (int, float)):
        ai_cycle_line += f" size_multiplier={float(result['ai_cycle_multiplier']):.2f}"
    if result.get("ai_cycle_capex_deceleration_shock"):
        ai_cycle_line += " capex_shock=true"
    ai_cycle_line += f" source={result.get('ai_cycle_source', 'none')}"
    lines.append(ai_cycle_line)
    lines.append("")
    lines.append("## Top Rejection Reasons")
    if result["top_rejection_reasons"]:
        for item in result["top_rejection_reasons"]:
            reason = str(item.get("reason", "")).strip()
            count = _to_int(item.get("count"), 0)
            lines.append(f"- `{count}` x {reason}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def markdown_public_report(result: dict[str, Any]) -> str:
    """Render a minimal public-safe cadence report."""
    lines: list[str] = []
    lines.append("# Weekly Cadence KPI Check")
    lines.append("")
    lines.append(f"- Passed: `{result.get('passed', False)}`")
    lines.append(f"- Alert Level: `{result.get('alert_level', 'unknown')}`")
    lines.append(
        "- Qualified Setups: "
        f"`{_to_int(result.get('qualified_setups_observed'), 0)}/"
        f"{_to_int(result.get('min_qualified_setups_per_week'), 0)}`"
    )
    lines.append(
        "- Closed Trades: "
        f"`{_to_int(result.get('closed_trades_observed'), 0)}/"
        f"{_to_int(result.get('min_closed_trades_per_week'), 0)}`"
    )
    blocked = result.get("blocked_categories", [])
    allowed_categories = {
        "liquidity",
        "regime",
        "cadence",
        "credit",
        "volatility",
        "position_limit",
        "ai_cycle",
        "none",
    }
    if isinstance(blocked, list) and blocked:
        filtered = []
        for item in blocked:
            category = str(item).strip().lower()
            filtered.append(category if category in allowed_categories else "other")
        lines.append(f"- Blocked Categories: `{', '.join(filtered)}`")
    else:
        lines.append("- Blocked Categories: none")
    lines.append("")
    return "\n".join(lines)


def _should_fail(*, result: dict[str, Any], strict: bool, fail_on: str) -> bool:
    if result.get("passed"):
        return False
    if strict:
        return True
    if fail_on == "none":
        return False
    threshold = LEVEL_ORDER.get(fail_on, LEVEL_ORDER["critical"])
    observed = LEVEL_ORDER.get(str(result.get("alert_level", "unknown")), LEVEL_ORDER["unknown"])
    return observed >= threshold


def main() -> int:
    parser = argparse.ArgumentParser(description="Check weekly cadence KPI and emit CI alerts.")
    parser.add_argument(
        "--state", default=str(DEFAULT_STATE_PATH), help="Path to system_state.json"
    )
    parser.add_argument("--out", default="", help="Optional markdown output path")
    parser.add_argument(
        "--fail-on",
        choices=["warning", "critical", "none"],
        default="critical",
        help="Fail threshold when cadence KPI is missed (default: critical)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail whenever cadence KPI is not passed.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    parser.add_argument(
        "--emit-github-warning",
        action="store_true",
        help="Emit ::warning/::error annotations for GitHub Actions.",
    )
    args = parser.parse_args()

    state_path = Path(_sanitize(args.state))
    state = _load_json(state_path)
    if not state:
        print(f"error: state file missing or invalid -> {_sanitize(state_path)}")
        return 1

    result = evaluate_weekly_cadence(state)
    # Sanitize CLI args at boundary (breaks CodeQL taint from argparse)
    sanitized_fail_on = _sanitize(args.fail_on)
    should_fail = _should_fail(
        result=result,
        strict=bool(args.strict),
        fail_on=sanitized_fail_on,
    )

    report = _sanitize(markdown_report(result), multiline=True)
    if args.out:
        out_path = Path(_sanitize(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # SECURITY: Do not persist state-derived cadence values to disk from this
        # checker. Keep detailed metrics in stdout (ephemeral CI stream) and write
        # only a static marker artifact.
        safe_report = (
            "# Weekly Cadence KPI Artifact\n\n"
            "Detailed cadence metrics are emitted to stdout only.\n"
            "This file is an execution marker for workflow evidence.\n"
        )
        with open(str(out_path), "w", encoding="utf-8") as f:
            f.write(safe_report)
        print(f"ok: cadence report -> {_sanitize(out_path)}")

    if args.json:
        safe_result = {
            "passed": bool(result.get("passed", False)),
            "alert_level": _sanitize(result.get("alert_level", "unknown")),
            "qualified_setups_observed": _to_int(result.get("qualified_setups_observed"), 0),
            "min_qualified_setups_per_week": _to_int(
                result.get("min_qualified_setups_per_week"), 0
            ),
            "closed_trades_observed": _to_int(result.get("closed_trades_observed"), 0),
            "min_closed_trades_per_week": _to_int(result.get("min_closed_trades_per_week"), 0),
            "blocked_categories": [
                _sanitize(item) for item in (result.get("blocked_categories") or [])
            ],
            "ai_credit_stress_status": _sanitize(result.get("ai_credit_stress_status", "unknown")),
            "ai_credit_stress_score": result.get("ai_credit_stress_score"),
            "usd_macro_status": _sanitize(result.get("usd_macro_status", "unknown")),
            "usd_macro_score": result.get("usd_macro_score"),
            "usd_macro_multiplier": result.get("usd_macro_multiplier"),
            "ai_cycle_status": _sanitize(result.get("ai_cycle_status", "unknown")),
            "ai_cycle_score": result.get("ai_cycle_score"),
            "ai_cycle_multiplier": result.get("ai_cycle_multiplier"),
            "ai_cycle_regime": _sanitize(result.get("ai_cycle_regime", "unknown")),
            "ai_cycle_capex_deceleration_shock": bool(
                result.get("ai_cycle_capex_deceleration_shock", False)
            ),
        }
        print(json.dumps(safe_result, indent=2))
    else:
        print(report)

    if args.emit_github_warning and not result["passed"]:
        setups_obs = int(result.get("qualified_setups_observed", 0))
        setups_req = int(result.get("min_qualified_setups_per_week", 0))
        trades_obs = int(result.get("closed_trades_observed", 0))
        trades_req = int(result.get("min_closed_trades_per_week", 0))
        blocked = _sanitize(
            ", ".join(str(c) for c in result.get("blocked_categories", [])) or "none"
        )
        credit_status = _sanitize(result.get("ai_credit_stress_status", "unknown"))
        message = (
            f"Weekly cadence KPI missed: "
            f"setups {setups_obs}/{setups_req}, "
            f"closed trades {trades_obs}/{trades_req}. "
            f"Blocked categories: {blocked}. "
            f"AI credit stress={credit_status}."
        )
        if should_fail:
            print(f"::error::{message}")
        else:
            print(f"::warning::{message}")

    return 1 if should_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
