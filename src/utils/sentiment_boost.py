"""
Sentiment Boost Utility - Alpha Generation Enhancement

Integrates sentiment scores from sentiment analysis into trading decisions.
Implements "The Sentiment Edge" strategy: Boost position sizes when sentiment > 0.8 AND technical_score > 0.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default sentiment data directory
DEFAULT_SENTIMENT_DIR = Path(__file__).parent.parent.parent / "data" / "sentiment"


def get_sentiment_score(symbol: str, sentiment_dir: Path | None = None) -> float | None:
    """
    Get sentiment score for a symbol from latest sentiment file.

    Args:
        symbol: Stock ticker symbol (e.g., "SPY", "NVDA")
        sentiment_dir: Optional path to sentiment directory (default: data/sentiment)

    Returns:
        Sentiment score (0-100 scale) or None if not found
    """
    if sentiment_dir is None:
        sentiment_dir = DEFAULT_SENTIMENT_DIR

    if not sentiment_dir.exists():
        logger.debug(f"Sentiment directory not found: {sentiment_dir}")
        return None

    # Try today's file first, then go back up to 7 days
    for days_back in range(8):
        date_str = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        sentiment_file = sentiment_dir / f"news_{date_str}.json"

        if sentiment_file.exists():
            try:
                with open(sentiment_file) as f:
                    data = json.load(f)

                # Check if symbol exists in tickers
                tickers = data.get("tickers", {})
                if symbol in tickers:
                    ticker_data = tickers[symbol]
                    # Try different possible keys for sentiment score
                    score = ticker_data.get("aggregate_score") or ticker_data.get("score")
                    if score is not None:
                        logger.debug(
                            f"Found sentiment score for {symbol}: {score} (from {date_str})"
                        )
                        return float(score)
            except Exception as e:
                logger.warning(f"Error reading sentiment file {sentiment_file}: {e}")
                continue

    logger.debug(f"No sentiment score found for {symbol}")
    return None


def calculate_sentiment_boost(
    symbol: str,
    base_amount: float,
    technical_score: float,
    sentiment_threshold: float = 0.8,
    boost_multiplier: float = 1.2,
    sentiment_dir: Path | None = None,
) -> tuple[float, dict[str, Any]]:
    """
    Calculate position size boost based on sentiment and technical scores.

    Implements "The Sentiment Edge" strategy:
    - If sentiment > threshold (default 0.8) AND technical_score > 0, boost by multiplier (default 20%)

    Args:
        symbol: Stock ticker symbol
        base_amount: Base position size in dollars
        technical_score: Technical analysis score (0-1 scale)
        sentiment_threshold: Minimum sentiment score to trigger boost (default: 0.8 = 80%)
        boost_multiplier: Multiplier to apply when conditions met (default: 1.2 = 20% boost)
        sentiment_dir: Optional path to sentiment directory

    Returns:
        Tuple of (adjusted_amount, boost_info_dict)
    """
    # Get sentiment score (0-100 scale)
    sentiment_score_raw = get_sentiment_score(symbol, sentiment_dir)

    if sentiment_score_raw is None:
        return base_amount, {
            "boost_applied": False,
            "reason": "No sentiment data available",
            "sentiment_score": None,
            "technical_score": technical_score,
            "base_amount": base_amount,
            "adjusted_amount": base_amount,
        }

    # Convert sentiment score to 0-1 scale (assuming 0-100 input)
    sentiment_score = (
        sentiment_score_raw / 100.0 if sentiment_score_raw > 1.0 else sentiment_score_raw
    )

    # Check if boost conditions are met
    boost_applied = sentiment_score >= sentiment_threshold and technical_score > 0

    if boost_applied:
        adjusted_amount = base_amount * boost_multiplier
        reason = (
            f"Sentiment Edge: sentiment={sentiment_score:.2f} >= {sentiment_threshold} "
            f"AND technical_score={technical_score:.2f} > 0"
        )
        logger.info(
            f"🚀 Sentiment boost applied to {symbol}: "
            f"${base_amount:.2f} -> ${adjusted_amount:.2f} "
            f"(+{(boost_multiplier - 1) * 100:.0f}%)"
        )
    else:
        adjusted_amount = base_amount
        if sentiment_score < sentiment_threshold:
            reason = f"Sentiment {sentiment_score:.2f} < threshold {sentiment_threshold}"
        elif technical_score <= 0:
            reason = f"Technical score {technical_score:.2f} <= 0"
        else:
            reason = "Unknown"

    return adjusted_amount, {
        "boost_applied": boost_applied,
        "reason": reason,
        "sentiment_score": sentiment_score,
        "sentiment_score_raw": sentiment_score_raw,
        "technical_score": technical_score,
        "base_amount": base_amount,
        "adjusted_amount": adjusted_amount,
        "boost_multiplier": boost_multiplier if boost_applied else 1.0,
    }
