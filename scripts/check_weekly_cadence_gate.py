#!/usr/bin/env python3
"""Check weekly cadence KPI and emit CI-friendly diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_STATE_PATH = Path("data/system_state.json")
LEVEL_ORDER = {"ok": 0, "warning": 1, "critical": 2, "unknown": 1}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def evaluate_weekly_cadence(state: dict[str, Any]) -> dict[str, Any]:
    weekly_gate = state.get("north_star_weekly_gate", {})
    cadence = weekly_gate.get("cadence_kpi", {}) if isinstance(weekly_gate, dict) else {}
    diagnostic = weekly_gate.get("no_trade_diagnostic", {}) if isinstance(weekly_gate, dict) else {}

    passed = bool(cadence.get("passed"))
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
    ai_credit_stress = gate_status.get("ai_credit_stress", {}) if isinstance(gate_status, dict) else {}
    ai_credit_status = str(ai_credit_stress.get("status") or "unknown").lower()
    ai_credit_score = ai_credit_stress.get("severity_score")
    ai_credit_source = str(ai_credit_stress.get("source") or "none")

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


def _should_fail(*, result: dict[str, Any], strict: bool, fail_on: str) -> bool:
    if result.get("passed"):
        return False
    if strict:
        return True
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

    state_path = Path(args.state)
    state = _load_json(state_path)
    if not state:
        print(f"error: state file missing or invalid -> {state_path}")
        return 1

    result = evaluate_weekly_cadence(state)
    should_fail = _should_fail(
        result=result,
        strict=bool(args.strict),
        fail_on=str(args.fail_on),
    )

    report = markdown_report(result)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report + "\n", encoding="utf-8")
        print(f"ok: cadence report -> {out_path}")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(report)

    if args.emit_github_warning and not result["passed"]:
        message = (
            "Weekly cadence KPI missed: "
            f"setups {result['qualified_setups_observed']}/{result['min_qualified_setups_per_week']}, "
            f"closed trades {result['closed_trades_observed']}/{result['min_closed_trades_per_week']}. "
            f"Blocked categories: {', '.join(result['blocked_categories']) or 'none'}. "
            f"AI credit stress={result.get('ai_credit_stress_status', 'unknown')}."
        )
        if should_fail:
            print(f"::error::{message}")
        else:
            print(f"::warning::{message}")

    return 1 if should_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
