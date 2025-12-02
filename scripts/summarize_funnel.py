#!/usr/bin/env python3
"""
Summarize hybrid funnel telemetry (JSONL) into a quick report.

Usage:
  PYTHONPATH=src python3 scripts/summarize_funnel.py \
      --log data/audit_trail/hybrid_funnel_runs.jsonl \
      --export-md out.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_gate = defaultdict(lambda: Counter(pass_=0, reject=0, skipped=0))
    by_ticker = defaultdict(lambda: Counter(pass_=0, reject=0))
    orders = []
    stops = []

    for e in events:
        event = e.get("event", "")
        status = e.get("status", "")
        ticker = e.get("ticker", "-")
        if event.startswith("gate."):
            gate = event.split(".", 1)[1]
            key = "skipped" if status == "skipped" else status
            by_gate[gate][key] += 1
            if status in {"pass", "reject"}:
                by_ticker[ticker][status] += 1
        elif event == "execution.order":
            orders.append(e)
        elif event == "execution.stop":
            stops.append(e)

    return {
        "gates": {g: dict(c) for g, c in by_gate.items()},
        "tickers": {t: dict(c) for t, c in by_ticker.items()},
        "orders": orders,
        "stops": stops,
    }


def to_markdown(summary: dict[str, Any]) -> str:
    lines = []
    lines.append(f"# Hybrid Funnel Summary — {datetime.utcnow().isoformat()}Z")
    lines.append("")
    lines.append("## Gate Outcomes")
    for gate, counts in summary["gates"].items():
        lines.append(
            f"- {gate}: pass={counts.get('pass_', 0)}, reject={counts.get('reject', 0)}, skipped={counts.get('skipped', 0)}"
        )
    lines.append("")
    lines.append("## Orders")
    if not summary["orders"]:
        lines.append("- No orders submitted")
    else:
        for o in summary["orders"]:
            t = o.get("ticker")
            p = o.get("payload", {})
            order = p.get("order", {})
            size = p.get("order_size") or order.get("notional")
            lines.append(f"- {t}: notional=${size}")
    lines.append("")
    lines.append("## Stops")
    if not summary.get("stops"):
        lines.append("- No stop orders submitted")
    else:
        for s in summary["stops"]:
            t = s.get("ticker")
            p = s.get("payload", {})
            stop = p.get("stop", {})
            stop_price = stop.get("stop_price")
            atr_pct = p.get("atr_pct")
            atr_mult = p.get("atr_multiplier")
            if atr_pct is not None:
                lines.append(f"- {t}: stop=${stop_price} (ATR%={atr_pct:.2%}, mult={atr_mult})")
            else:
                lines.append(f"- {t}: stop=${stop_price}")
    lines.append("")
    lines.append("## Ticker Pass/Reject")
    for t, counts in summary["tickers"].items():
        lines.append(f"- {t}: pass={counts.get('pass_', 0)}, reject={counts.get('reject', 0)}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="data/audit_trail/hybrid_funnel_runs.jsonl")
    parser.add_argument("--export-md", default=None)
    args = parser.parse_args()

    path = Path(args.log)
    events = load_events(path)
    summary = summarize(events)
    md = to_markdown(summary)

    print(md)
    if args.export_md:
        out = Path(args.export_md)
        out.write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
