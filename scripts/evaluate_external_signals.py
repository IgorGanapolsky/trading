#!/usr/bin/env python3
"""
Sandbox utility to backtest stored external signals against future price moves.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yfinance as yf
from src.utils.external_signal_loader import list_signal_files, load_signals_file

logger = logging.getLogger("external_signal_eval")
BACKTEST_DIR = Path("data/external_signals/backtests")
BACKTEST_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate stored external signals.")
    parser.add_argument(
        "--signals-file",
        type=str,
        help="Specific signals_<timestamp>.json file to evaluate (defaults to latest).",
    )
    parser.add_argument(
        "--horizon-days",
        type=int,
        default=5,
        help="Forward horizon (trading days) to measure returns.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def evaluate_signals(signals: dict[str, dict], horizon_days: int) -> dict:
    results = []
    for ticker, info in signals.items():
        timestamp_str = info.get("timestamp") or info.get("generated_at")
        if not timestamp_str:
            logger.warning("Skipping %s - missing timestamp", ticker)
            continue

        signal_time = datetime.fromisoformat(timestamp_str)
        start = signal_time - timedelta(days=1)
        end = signal_time + timedelta(days=horizon_days * 2)

        data = yf.download(
            ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=False,
        )
        if data.empty:
            logger.warning("No price data for %s in evaluation window", ticker)
            continue

        data = data.sort_index()
        entry_price = float(data["Close"].iloc[0].item())
        exit_index = min(horizon_days - 1, len(data) - 1)
        exit_price = float(data["Close"].iloc[exit_index].item())
        forward_return = (exit_price - entry_price) / entry_price

        results.append(
            {
                "ticker": ticker,
                "signal_score": info.get("score", 0.0),
                "confidence": info.get("confidence", 0.0),
                "return": forward_return,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "source": info.get("source", "unknown"),
            }
        )

    if not results:
        return {"results": [], "summary": {}}

    avg_return = sum(item["return"] for item in results) / len(results)
    alignment = sum(
        1
        for item in results
        if (item["signal_score"] >= 0 and item["return"] >= 0)
        or (item["signal_score"] < 0 and item["return"] < 0)
    ) / len(results)

    summary = {
        "count": len(results),
        "avg_return": avg_return,
        "directional_alignment": alignment,
    }
    return {"results": results, "summary": summary}


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if args.signals_file:
        path = Path(args.signals_file)
    else:
        files = list_signal_files(limit=1)
        if not files:
            logger.error("No external signal files found")
            return
        path = files[0]

    signals = load_signals_file(path)
    evaluation = evaluate_signals(signals, args.horizon_days)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = BACKTEST_DIR / f"evaluation_{timestamp}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source_file": str(path),
                "horizon_days": args.horizon_days,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                **evaluation,
            },
            f,
            indent=2,
        )

    logger.info(
        "Saved evaluation with %d results to %s",
        len(evaluation["results"]),
        output_path,
    )
    logger.info("Summary: %s", evaluation["summary"])


if __name__ == "__main__":
    main()
