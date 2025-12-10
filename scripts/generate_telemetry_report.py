#!/usr/bin/env python3
"""
Summarize orchestrator telemetry into a CLI-friendly report.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_LOG = Path("data/audit_trail/hybrid_funnel_runs.jsonl")

from src.utils.telemetry_summary import load_events, summarize_events  # noqa:E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate telemetry summary report.")
    parser.add_argument(
        "--log",
        default=str(DEFAULT_LOG),
        help="Telemetry JSONL file (default: data/audit_trail/hybrid_funnel_runs.jsonl).",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional path to write structured JSON summary.",
    )
    parser.add_argument(
        "--tax-rate",
        type=float,
        default=0.28,
        help="Marginal tax rate used for sweep guidance (default: 0.28).",
    )
    parser.add_argument(
        "--adapt-rl",
        action="store_true",
        help="Run RL filter adaptation using the same telemetry log after reporting.",
    )
    return parser.parse_args()


def load_account_state(path: Path | None = None) -> dict[str, Any] | None:
    state_path = path or Path("data/system_state.json")
    if not state_path.exists():
        return None
    try:
        with state_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
            return payload.get("account")
    except Exception:
        return None


def print_report(
    summary: dict[str, Any],
    account_snapshot: dict[str, Any] | None,
    tax_sweep: float | None,
    tax_rate: float,
) -> None:
    print("==== Hybrid Funnel Telemetry ====")
    print(f"Generated at: {summary['generated_at']}")
    print(f"Total events: {summary['event_count']}")
    print("")
    print("Gate status:")
    for gate, stats in sorted(summary["gates"].items()):
        total = stats["total"]
        pass_rate = (stats["pass"] / total * 100) if total else 0
        print(
            f"  - {gate:<18} pass={stats['pass']:>3} "
            f"reject={stats['reject']:>3} error={stats['error']:>3} "
            f"pass_rate={pass_rate:5.1f}%"
        )

    if summary["top_tickers"]:
        print("\nMost active tickers:")
        for ticker, count in summary["top_tickers"]:
            print(f"  - {ticker}: {count} events")

    if summary["recent_errors"]:
        print("\nRecent failures:")
        for event in summary["recent_errors"]:
            ts = event.get("ts")
            gate = event.get("event")
            ticker = event.get("ticker")
            reason = event.get("payload", {}).get("reason") or event.get("status")
            print(f"  - {ts} | {gate} | {ticker} | {reason}")

    if account_snapshot:
        equity = account_snapshot.get("current_equity")
        total_pl = account_snapshot.get("total_pl")
        print(
            f"\nAccount Snapshot: equity=${equity:.2f} | cumulative P/L=${total_pl:.2f}"
            if equity is not None and total_pl is not None
            else "\nAccount Snapshot: unavailable"
        )
    if tax_sweep:
        print(f"Suggested Tax Sweep ({tax_rate * 100:.0f}%): ${tax_sweep:.2f}")


def _current_quarter_start(ref: datetime | None = None) -> datetime:
    ref = ref or datetime.utcnow()
    quarter = (ref.month - 1) // 3
    start_month = quarter * 3 + 1
    return datetime(ref.year, start_month, 1)


def _parse_ts(raw: Any) -> datetime | None:
    if not raw:
        return None
    value = str(raw)
    if value.endswith("Z"):
        value = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _safe_float(value: Any) -> float | None:
    try:
        number = float(value)
        if number != number:  # NaN check
            return None
        return number
    except (TypeError, ValueError):
        return None


def calculate_tax_sweep(events: list[dict[str, Any]], rate: float = 0.28) -> dict[str, Any]:
    """Estimate quarter-to-date profits and the 28% HYSA sweep."""
    quarter_start = _current_quarter_start()
    realized = 0.0
    premium_by_day: dict[str, float] = {}

    for event in events:
        ts = _parse_ts(event.get("ts") or event.get("generated_at"))
        if ts is None or ts < quarter_start:
            continue
        payload = event.get("payload") or {}
        value = None
        for key in ("net_profit", "realized_pnl", "realized_profit", "pnl"):
            if key in payload:
                value = _safe_float(payload.get(key))
                break
        if value is not None:
            realized += value
            continue

        if str(event.get("event", "")).startswith("gate.options"):
            premium = _safe_float(payload.get("total_premium"))
            if premium is not None:
                day_key = ts.date().isoformat()
                previous = premium_by_day.get(day_key, 0.0)
                premium_by_day[day_key] = max(previous, premium)

    quarter_profit = realized + sum(premium_by_day.values())
    tax_reserve = max(0.0, quarter_profit * rate)
    return {
        "quarter_profit": round(quarter_profit, 2),
        "tax_reserve": round(tax_reserve, 2),
        "sweep_rate": rate,
        "days_accounted": len(premium_by_day),
    }


def print_tax_sweep(tax_summary: dict[str, Any]) -> None:
    print("\nQuarterly tax sweep (28% HYSA bucket):")
    profit = tax_summary.get("quarter_profit", 0.0)
    reserve = tax_summary.get("tax_reserve", 0.0)
    if profit <= 0:
        print("  - No positive profit recorded this quarter yet.")
        return
    print(f"  - Profit captured: ${profit:,.2f}")
    print(f"  - Reserve 28%: ${reserve:,.2f} → move to HYSA / tax bucket.")


def main() -> None:
    args = parse_args()
    events = load_events(Path(args.log))
    summary = summarize_events(events)
    account_snapshot = load_account_state()
    tax_sweep = None
    if account_snapshot:
        try:
            cumulative_pl = float(account_snapshot.get("total_pl", 0.0))
            if cumulative_pl > 0:
                tax_sweep = round(cumulative_pl * args.tax_rate, 2)
        except (TypeError, ValueError):
            tax_sweep = None

    print_report(summary, account_snapshot, tax_sweep, args.tax_rate)

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(summary)
        payload["account_snapshot"] = account_snapshot
        payload["tax_sweep_recommendation"] = tax_sweep
        payload["tax_rate"] = args.tax_rate
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\nStructured summary written to {output_path}")

    if args.adapt_rl:
        try:
            from src.agents.rl_agent import RLFilter

            rl_filter = RLFilter()
            adaptation = rl_filter.update_from_telemetry(audit_path=args.log)
            print("\nRL filter adaptation summary:")
            print(json.dumps(adaptation, indent=2))
        except Exception as exc:  # pragma: no cover - adaptation is optional
            print(f"\n⚠️  RL adaptation failed: {exc}")


if __name__ == "__main__":
    main()
