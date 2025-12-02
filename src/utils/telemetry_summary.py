"""
Shared helpers for summarizing hybrid funnel telemetry.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Telemetry log not found at {path}. "
            "Run the orchestrator to generate telemetry or provide a sample file."
        )
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def summarize_events(events: list[dict[str, Any]], top_n: int = 10) -> dict[str, Any]:
    gate_counts = defaultdict(lambda: Counter())
    ticker_counts = Counter()
    errors: list[dict[str, Any]] = []

    for event in events:
        gate = event.get("event", "unknown")
        status = event.get("status", "unknown")
        gate_counts[gate][status] += 1
        ticker = event.get("ticker")
        if ticker:
            ticker_counts[ticker] += 1
        if status in {"error", "reject"}:
            errors.append(event)

    summary = {
        "generated_at": datetime.utcnow().isoformat(),
        "event_count": len(events),
        "gates": {
            gate: {
                "total": sum(counter.values()),
                "pass": counter.get("pass", 0),
                "reject": counter.get("reject", 0),
                "error": counter.get("error", 0),
            }
            for gate, counter in gate_counts.items()
        },
        "top_tickers": ticker_counts.most_common(top_n),
        "recent_errors": errors[-5:],
    }
    return summary
