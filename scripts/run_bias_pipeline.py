#!/usr/bin/env python3
"""
Generate analyst biases asynchronously and persist them for the fast trader.
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from src.analyst.bias_store import BiasSnapshot, BiasStore
from src.langchain_agents.analyst import LangChainSentimentAgent

logger = logging.getLogger(__name__)


def _parse_tickers(raw: str | None) -> list[str]:
    raw = raw or "SPY,QQQ,VOO"
    return [ticker.strip().upper() for ticker in raw.split(",") if ticker.strip()]


def _score_to_direction(score: float) -> str:
    if score >= 0.2:
        return "bullish"
    if score <= -0.2:
        return "bearish"
    return "neutral"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the slow analyst loop and persist biases.")
    parser.add_argument(
        "--tickers",
        default=os.getenv("ANALYST_TICKERS", os.getenv("TARGET_TICKERS")),
        help="Comma-separated tickers (defaults to ANALYST_TICKERS/TARGET_TICKERS).",
    )
    parser.add_argument(
        "--bias-dir",
        default=os.getenv("BIAS_DATA_DIR", "data/bias"),
        help="Directory for bias artifacts.",
    )
    parser.add_argument(
        "--ttl-hours",
        type=int,
        default=int(os.getenv("BIAS_TTL_HOURS", "6")),
        help="Number of hours before a bias expires.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("HYBRID_LLM_MODEL"),
        help="Override LLM model for the analyst agent.",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("BIAS_JOB_LOG_LEVEL", "INFO"),
        help="Logging level.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s"
    )
    load_dotenv()

    tickers = _parse_tickers(args.tickers)
    if not tickers:
        raise SystemExit("No tickers supplied for bias job.")

    agent = LangChainSentimentAgent(model_name=args.model)
    store = BiasStore(root=args.bias_dir)

    logger.info("Running bias job for %s", ", ".join(tickers))
    for symbol in tickers:
        try:
            indicators = {"symbol": symbol}
            result = agent.analyze_news(symbol, indicators)
        except Exception as exc:
            logger.error("Analyst invocation failed for %s: %s", symbol, exc, exc_info=True)
            continue

        score = float(result.get("score", 0.0))
        direction = _score_to_direction(score)
        conviction = min(1.0, max(0.0, abs(score)))
        now = datetime.now(timezone.utc)
        snapshot = BiasSnapshot(
            symbol=symbol,
            score=score,
            direction=direction,
            conviction=conviction,
            reason=result.get("reason", "no rationale"),
            created_at=now,
            expires_at=now + timedelta(hours=args.ttl_hours),
            model=result.get("model"),
            sources=result.get("sources", []),
            metadata={
                "raw_result": result,
                "indicators": indicators,
            },
        )
        store.persist(snapshot)
        logger.info(
            "Stored bias for %s (direction=%s, score=%.2f, conviction=%.2f)",
            symbol,
            direction,
            score,
            conviction,
        )

    logger.info("Bias publishing job complete.")


if __name__ == "__main__":
    main()
