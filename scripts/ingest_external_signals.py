#!/usr/bin/env python3
"""
Ingest free external trading signals (Alpha Vantage news + YouTube analysis).

This script consolidates open-source sentiment feeds into
data/external_signals/signals_<timestamp>.json so the trading agents can use
them without relying on paid services.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.bogleheads_integration import get_bogleheads_signal_for_symbol
from src.utils.external_signal_loader import ExternalSignal, save_signals

logger = logging.getLogger("external_signal_ingest")

DEFAULT_TICKERS = ["NVDA", "GOOGL", "AMZN", "UBER", "LLY", "PINS", "SPY"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest open-source external signals.")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=DEFAULT_TICKERS,
        help="List of tickers to monitor.",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=3,
        help="News lookback window for Alpha Vantage sentiment.",
    )
    parser.add_argument(
        "--youtube-docs",
        nargs="*",
        default=[
            "docs/youtube_analysis/video_2_top_6_stocks_nov_2025.md",
        ],
        help="Markdown files containing analyst recommendations to parse.",
    )
    parser.add_argument(
        "--min-articles",
        type=int,
        default=2,
        help="Minimum Alpha Vantage articles required to form a sentiment signal.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def collect_alpha_vantage_signals(
    tickers: list[str], days_back: int, min_articles: int
) -> dict[str, list[dict]]:
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        logger.warning("Alpha Vantage API key missing - skipping news ingestion")
        return {}

    contributions: dict[str, list[dict]] = defaultdict(list)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    for ticker in tickers:
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "apikey": api_key,
            "limit": 50,
        }

        try:
            response = requests.get("https://www.alphavantage.co/query", params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Alpha Vantage request failed for %s: %s", ticker, exc)
            continue

        feed = data.get("feed", [])
        sentiments = []
        for item in feed:
            published = item.get("time_published")
            try:
                pub_dt = datetime.strptime(published, "%Y%m%dT%H%M%S")
            except Exception:
                continue
            if pub_dt < cutoff:
                continue

            for ticker_sent in item.get("ticker_sentiment", []):
                if ticker_sent.get("ticker") == ticker:
                    raw = float(ticker_sent.get("ticker_sentiment_score", 0.0))
                    sentiments.append((raw + 1) / 2)  # map -1..1 to 0..1
                    break

        if len(sentiments) < min_articles:
            logger.info(
                "Skipping %s Alpha Vantage signal - only %d articles (min=%d)",
                ticker,
                len(sentiments),
                min_articles,
            )
            continue

        avg_sent = statistics.mean(sentiments)
        score = max(-100.0, min(100.0, (avg_sent - 0.5) * 200))
        confidence = min(1.0, len(sentiments) / 10.0)

        contributions[ticker.upper()].append(
            {
                "score": score,
                "confidence": confidence,
                "source": "AlphaVantageNews",
                "signal_type": "sentiment",
                "notes": f"{len(sentiments)} articles avg_sent={avg_sent:.2f}",
            }
        )

    return contributions


def extract_value_from_line(line: str) -> float | None:
    match = re.search(r"\$([\d,\.]+)", line)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def collect_youtube_signals(md_paths: list[str]) -> dict[str, list[dict]]:
    contributions: dict[str, list[dict]] = defaultdict(list)
    header_pattern = re.compile(r"^### .*?\((?P<ticker>[A-Z\.]+)\)")

    for path_str in md_paths:
        path = Path(path_str)
        if not path.exists():
            logger.warning("YouTube analysis file not found: %s", path)
            continue

        lines = path.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines):
            match = header_pattern.match(line.strip())
            if not match:
                continue

            ticker = match.group("ticker").upper()
            current_price = None
            intrinsic_value = None

            for look_ahead in range(idx + 1, min(len(lines), idx + 15)):
                candidate_line = lines[look_ahead]
                if candidate_line.startswith("###"):
                    break
                if "Current Price" in candidate_line:
                    current_price = extract_value_from_line(candidate_line)
                if "Intrinsic Value" in candidate_line:
                    intrinsic_value = extract_value_from_line(candidate_line)

            if not current_price or not intrinsic_value or intrinsic_value <= 0:
                continue

            discount = (intrinsic_value - current_price) / intrinsic_value
            score = max(-100.0, min(100.0, discount * 200))
            confidence = 0.6  # qualitative analyst confidence

            contributions[ticker].append(
                {
                    "score": score,
                    "confidence": confidence,
                    "source": f"YouTube:{path.stem}",
                    "signal_type": "fundamental_recommendation",
                    "notes": f"DCF discount {discount * 100:.1f}%",
                }
            )

    return contributions


def aggregate_contributions(contributions: dict[str, list[dict]]) -> list[ExternalSignal]:
    aggregated: list[ExternalSignal] = []

    for ticker, items in contributions.items():
        if not items:
            continue

        weighted_score = 0.0
        total_confidence = 0.0
        sources = []
        notes = []
        signal_types = set()

        for item in items:
            confidence = max(0.05, float(item.get("confidence", 0.0)))
            total_confidence += confidence
            weighted_score += item.get("score", 0.0) * confidence
            sources.append(item.get("source", "unknown"))
            signal_types.add(item.get("signal_type", "unspecified"))
            if item.get("notes"):
                notes.append(item["notes"])

        aggregated_confidence = min(1.0, total_confidence)
        aggregated_score = weighted_score / total_confidence if total_confidence else 0.0

        aggregated.append(
            ExternalSignal(
                ticker=ticker,
                score=aggregated_score,
                confidence=aggregated_confidence,
                source="+".join(sources),
                signal_type="+".join(sorted(signal_types)),
                timestamp=datetime.now(timezone.utc),
                notes="; ".join(notes) if notes else None,
            )
        )

    return aggregated


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    contributions: dict[str, list[dict]] = defaultdict(list)

    news_contrib = collect_alpha_vantage_signals(args.tickers, args.days_back, args.min_articles)
    for ticker, items in news_contrib.items():
        contributions[ticker].extend(items)

    youtube_contrib = collect_youtube_signals(args.youtube_docs)
    for ticker, items in youtube_contrib.items():
        contributions[ticker].extend(items)

    # Add Bogleheads signals
    try:
        bogleheads_contrib: dict[str, list[dict]] = defaultdict(list)
        for t in args.tickers:
            try:
                sig = get_bogleheads_signal_for_symbol(t)
                bogleheads_contrib[t].append(
                    {
                        "score": sig.get("score", 0.0) / 100.0,
                        "confidence": sig.get("confidence", 0.0),
                        "source": "bogleheads",
                        "signal_type": "forum_longterm",
                        "notes": sig.get("reasoning"),
                    }
                )
            except Exception as e:
                logger.debug(f"Bogleheads signal failed for {t}: {e}")
        for ticker, items in bogleheads_contrib.items():
            contributions[ticker].extend(items)
        if bogleheads_contrib:
            logger.info("✅ Bogleheads signals collected")
    except Exception as e:
        logger.warning(f"⚠️  Could not collect Bogleheads signals: {e}")

    if not contributions:
        logger.warning("No external signals were generated - exiting")
        return

    aggregated_signals = aggregate_contributions(contributions)
    metadata = {
        "sources": list({item.source for item in aggregated_signals}),
        "tickers": sorted(contributions.keys()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_signals(aggregated_signals, metadata)


if __name__ == "__main__":
    main()
