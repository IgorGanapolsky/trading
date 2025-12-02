#!/usr/bin/env python3
"""
Dry Run Script for Growth Strategy with RAG Integration.

This script executes the GrowthStrategy in a safe mode to verify:
1. RAG database integration (fetching news/sentiment)
2. Multi-LLM ranking logic
3. Sentiment blending (RAG + Legacy)
"""

import logging
import os
import sys
from unittest.mock import MagicMock

# Ensure src is in path
sys.path.append(os.getcwd())

# Configure logging to show RAG details
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Mock keys if not present to avoid crashes in DCF calculator
if "POLYGON_API_KEY" not in os.environ:
    os.environ["POLYGON_API_KEY"] = "mock_key"
if "ALPHA_VANTAGE_API_KEY" not in os.environ:
    os.environ["ALPHA_VANTAGE_API_KEY"] = "mock_key"

from src.strategies.growth_strategy import CandidateStock, GrowthStrategy


def main():
    logger.info("🚀 Starting Growth Strategy Dry Run...")

    # Initialize strategy
    strategy = GrowthStrategy(weekly_allocation=1000.0, use_sentiment=True)

    # Mock the DCF calculator to avoid external API calls during dry run
    # We want to focus on RAG sentiment logic
    strategy.dcf_calculator.get_intrinsic_value = MagicMock(return_value=None)
    # Or better, return a dummy result so stocks aren't filtered out
    from datetime import datetime

    from src.utils.dcf_valuation import DCFResult

    dummy_dcf = DCFResult(
        intrinsic_value=200.0,
        discount_rate=0.1,
        terminal_growth=0.02,
        projected_growth=0.05,
        timestamp=datetime.now(),
    )
    strategy.dcf_calculator.get_intrinsic_value = MagicMock(return_value=dummy_dcf)

    # Mock technical filters to pass some stocks
    # We'll manually create some candidates to test ranking
    candidates = [
        CandidateStock(
            symbol="NVDA",
            technical_score=80.0,
            consensus_score=0.0,
            current_price=150.0,
            momentum=10.0,
            rsi=60.0,
            macd_value=1.0,
            macd_signal=0.5,
            macd_histogram=0.5,
            volume_ratio=1.5,
            intrinsic_value=200.0,
            dcf_discount=0.25,
        ),
        CandidateStock(
            symbol="AAPL",
            technical_score=70.0,
            consensus_score=0.0,
            current_price=180.0,
            momentum=5.0,
            rsi=55.0,
            macd_value=0.5,
            macd_signal=0.2,
            macd_histogram=0.3,
            volume_ratio=1.1,
            intrinsic_value=220.0,
            dcf_discount=0.18,
        ),
        CandidateStock(
            symbol="TSLA",
            technical_score=60.0,
            consensus_score=0.0,
            current_price=250.0,
            momentum=-2.0,
            rsi=40.0,
            macd_value=-0.5,
            macd_signal=-0.2,
            macd_histogram=-0.3,
            volume_ratio=0.9,
            intrinsic_value=300.0,
            dcf_discount=0.16,
        ),
    ]

    logger.info(f"\n🧪 Testing Multi-LLM Ranking with {len(candidates)} candidates...")

    # This is the method that uses RAG
    ranked = strategy.get_multi_llm_ranking(candidates)

    logger.info("\n📊 Ranking Results:")
    for i, stock in enumerate(ranked):
        logger.info(
            f"{i + 1}. {stock.symbol} (Score: {stock.consensus_score:.1f}, Sentiment Mod: {stock.sentiment_modifier:+.1f})"
        )

    logger.info("\n✅ Dry Run Complete!")


if __name__ == "__main__":
    main()
