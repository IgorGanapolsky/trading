#!/usr/bin/env python3
"""
Summarize orchestrator telemetry into a CLI-friendly report.
"""

from __future__ import annotations

import argparse
import json
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
        "--adapt-rl",
        action="store_true",
        help="Run RL filter adaptation using the same telemetry log after reporting.",
    )
    return parser.parse_args()


def print_report(summary: dict[str, Any]) -> None:
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


def main() -> None:
    args = parse_args()
    events = load_events(Path(args.log))
    summary = summarize_events(events)
    print_report(summary)

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
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
