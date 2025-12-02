#!/usr/bin/env python3
"""
Test script for LLM Council trading system.

Demonstrates the 3-stage council process:
1. First opinions from all council members
2. Peer review and ranking
3. Chairman synthesis
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Configure logging
import logging

from src.core.llm_council_integration import create_trading_council

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_trade_validation():
    """Test trade validation with LLM Council."""
    print("\n" + "=" * 80)
    print("TEST 1: Trade Validation")
    print("=" * 80)

    council = create_trading_council(enabled=True)

    market_data = {
        "symbol": "SPY",
        "price": 652.42,
        "change_percent": -0.5,
        "volume": 50000000,
        "rsi": 45,
        "macd_histogram": 0.15,
        "volume_ratio": 1.1,
        "ma_50": 650.0,
        "ma_200": 640.0,
    }

    context = {
        "portfolio_value": 100000,
        "current_positions": {"SPY": 0.74},  # 74% already in SPY
        "risk_limits": {"max_position_pct": 0.30},
    }

    result = await council.validate_trade(
        symbol="SPY",
        action="BUY",
        market_data=market_data,
        context=context,
    )

    print(f"\n✅ Approved: {result['approved']}")
    print(f"📊 Confidence: {result['confidence']:.2%}")
    print(f"\n💭 Reasoning:\n{result['reasoning']}")

    if result.get("council_response"):
        print("\n📋 Individual Responses:")
        for model, response in result["individual_responses"].items():
            print(f"\n  {model}:")
            print(f"    {response[:200]}...")

    council.close()


async def test_trading_recommendation():
    """Test trading recommendation from LLM Council."""
    print("\n" + "=" * 80)
    print("TEST 2: Trading Recommendation")
    print("=" * 80)

    council = create_trading_council(enabled=True)

    market_data = {
        "symbol": "GOOGL",
        "price": 289.04,
        "change_percent": 2.34,
        "volume": 25000000,
        "rsi": 58,
        "macd_histogram": 0.25,
        "volume_ratio": 1.3,
        "ma_50": 285.0,
        "ma_200": 275.0,
        "momentum_score": 0.75,
    }

    result = await council.get_trading_recommendation(symbol="GOOGL", market_data=market_data)

    print(f"\n🎯 Recommendation: {result['action']}")
    print(f"📊 Confidence: {result['confidence']:.2%}")
    print(f"\n💭 Reasoning:\n{result['reasoning']}")

    council.close()


async def test_risk_assessment():
    """Test risk assessment with LLM Council."""
    print("\n" + "=" * 80)
    print("TEST 3: Risk Assessment")
    print("=" * 80)

    council = create_trading_council(enabled=True)

    market_data = {
        "symbol": "QQQ",
        "price": 485.50,
        "volatility": 0.22,
        "beta": 1.15,
        "rsi": 62,
        "atr": 8.5,
    }

    portfolio_context = {
        "portfolio_value": 100000,
        "current_positions": {
            "SPY": 0.74,  # 74% concentration
            "GOOGL": 0.26,  # 26% concentration
        },
        "cash": 0.0,
    }

    result = await council.assess_risk(
        symbol="QQQ",
        position_size=30000,  # Would be 30% of portfolio
        market_data=market_data,
        portfolio_context=portfolio_context,
    )

    print(f"\n⚠️  Risk Level: {result['risk_level']}")
    print(f"✅ Approved: {result['approved']}")
    print(f"📊 Confidence: {result['confidence']:.2%}")
    print(f"\n💭 Reasoning:\n{result['reasoning']}")

    council.close()


async def test_full_council_process():
    """Test the full 3-stage council process directly."""
    print("\n" + "=" * 80)
    print("TEST 4: Full Council Process (3 Stages)")
    print("=" * 80)

    from src.core.multi_llm_analysis import LLMCouncilAnalyzer

    council = LLMCouncilAnalyzer()

    query = """Should we buy SPY right now?

Current situation:
- SPY price: $652.42
- RSI: 45 (neutral)
- MACD: Bullish (histogram: 0.15)
- Volume: Above average (1.1x)
- Price is above 50-day MA ($650) and 200-day MA ($640)
- Portfolio already has 74% in SPY (concentration risk)

Provide a clear recommendation with reasoning."""

    system_prompt = """You are an expert trading analyst. Provide objective,
data-driven recommendations based on technical analysis and risk management."""

    response = await council.query_council(query, system_prompt, include_reviews=True)

    print(f"\n🎯 Final Answer:\n{response.final_answer}")
    print(f"\n📊 Confidence: {response.confidence:.2%}")
    print(f"\n👥 Council Members: {', '.join(response.metadata['council_models'])}")
    print(f"👑 Chairman: {response.metadata['chairman_model']}")
    print(f"⏱️  Total Time: {response.metadata['total_time']:.2f}s")

    print("\n📋 Individual Responses:")
    for model, content in response.individual_responses.items():
        print(f"\n  {model}:")
        print(f"    {content[:300]}...")

    if response.reviews:
        print("\n🔍 Peer Reviews:")
        for reviewer, review in response.reviews.items():
            print(f"\n  {reviewer}:")
            if review.get("rankings"):
                print(f"    Rankings: {review['rankings']}")
            if review.get("reasoning"):
                print(f"    Reasoning: {review['reasoning'][:200]}...")

    council.close()


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("LLM COUNCIL TRADING SYSTEM - TEST SUITE")
    print("=" * 80)

    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("\n❌ ERROR: OPENROUTER_API_KEY not set in environment")
        print("Please set it before running tests:")
        print("  export OPENROUTER_API_KEY=sk-or-v1-...")
        return

    try:
        # Test 1: Trade validation
        await test_trade_validation()

        # Test 2: Trading recommendation
        await test_trading_recommendation()

        # Test 3: Risk assessment
        await test_risk_assessment()

        # Test 4: Full council process
        await test_full_council_process()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS COMPLETE")
        print("=" * 80)

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        print(f"\n❌ TEST FAILED: {e}")


if __name__ == "__main__":
    asyncio.run(main())
