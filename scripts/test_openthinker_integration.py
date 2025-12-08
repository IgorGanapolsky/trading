#!/usr/bin/env python3
"""
Test OpenThinker-Agent Integration

Verifies that OpenThinker is properly integrated with the trading system.
Run: python scripts/test_openthinker_integration.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_local_llm_client():
    """Test basic local LLM client functionality."""
    print("\n" + "=" * 60)
    print("TEST 1: Local LLM Client")
    print("=" * 60)

    from src.core.local_llm import LocalLLMClient, LocalLLMBackend, LocalModel

    client = LocalLLMClient(
        backend=LocalLLMBackend.OLLAMA,
        model=LocalModel.OPENTHINKER_7B,
    )

    # Check availability
    available = await client.is_available()
    print(f"Ollama available: {available}")

    if available:
        # List models
        models = await client.list_models()
        print(f"Available models: {models[:5]}...")

        # Check if OpenThinker is installed
        openthinker_installed = any("openthinker" in m.lower() for m in models)
        print(f"OpenThinker installed: {openthinker_installed}")

        if not openthinker_installed:
            print("\n⚠️  OpenThinker not installed. Run:")
            print("   ollama pull openthinker:7b")
    else:
        print("\n⚠️  Ollama not running. Start with:")
        print("   ollama serve")

    await client.close()
    return available


async def test_openthinker_reasoner():
    """Test OpenThinker reasoning capabilities."""
    print("\n" + "=" * 60)
    print("TEST 2: OpenThinker Reasoner")
    print("=" * 60)

    from src.core.local_llm import OpenThinkerReasoner, LocalModel

    reasoner = OpenThinkerReasoner(model=LocalModel.OPENTHINKER_7B)

    available = await reasoner.is_available()
    print(f"OpenThinker Reasoner available: {available}")

    if available:
        print("\nTesting trade analysis...")
        result = await reasoner.analyze_trade(
            symbol="AAPL",
            action="BUY",
            market_data={
                "price": 185.50,
                "change_pct": 1.2,
                "rsi": 55,
                "macd_signal": "bullish",
                "volume": 45000000,
            },
        )

        print(f"Success: {result.get('success')}")
        print(f"Decision: {result.get('decision')}")
        print(f"Confidence: {result.get('confidence')}")
        print(f"Latency: {result.get('latency', 0):.2f}s")

        if result.get("thinking"):
            print(f"\nThinking (first 200 chars):\n{result['thinking'][:200]}...")

        print(f"\nReasoning (first 300 chars):\n{result.get('reasoning', '')[:300]}...")

    await reasoner.close()
    return available


async def test_openthinker_agent():
    """Test OpenThinker Agent."""
    print("\n" + "=" * 60)
    print("TEST 3: OpenThinker Agent")
    print("=" * 60)

    from src.agents.openthinker_agent import create_openthinker_agent

    agent = await create_openthinker_agent(check_availability=True)

    print(f"Agent available: {agent._available}")

    if agent._available:
        print("\nTesting contrarian trade validation...")
        result = await agent.validate_trade(
            symbol="TSLA",
            action="BUY",
            market_data={
                "price": 245.00,
                "change_pct": 3.5,
                "rsi": 72,  # Overbought
                "macd_signal": "bullish",
                "volume": 80000000,
            },
            context={
                "portfolio_value": 100000,
                "current_tsla_exposure": 0.0,
            },
        )

        print(f"Approved: {result['approved']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Concerns: {result.get('concerns', [])}")

        if result.get("concerns"):
            print("\nConcerns identified:")
            for concern in result["concerns"][:3]:
                print(f"  - {concern}")

    await agent.close()
    return agent._available


async def test_enhanced_council():
    """Test Enhanced Trading Council with OpenThinker."""
    print("\n" + "=" * 60)
    print("TEST 4: Enhanced Trading Council")
    print("=" * 60)

    from src.core.openthinker_council_integration import create_enhanced_trading_council

    # Create council (cloud disabled for test, just OpenThinker)
    council = create_enhanced_trading_council(
        enabled=False,  # Disable cloud for faster test
        openthinker_enabled=True,
    )

    # Initialize OpenThinker
    await council._initialize_openthinker()
    print(f"OpenThinker initialized: {council._openthinker_available}")

    if council._openthinker_available:
        print("\nTesting position size calculation...")
        result = await council.calculate_position_size(
            symbol="AAPL",
            account_value=100000,
            entry_price=185.50,
            stop_loss=180.00,
            risk_pct=0.02,
        )

        print(f"Success: {result.get('success')}")
        if result.get("shares"):
            print(f"Recommended shares: {result.get('shares')}")
            print(f"Position value: ${result.get('position_value', 0):,.2f}")
        print(f"\nReasoning (first 300 chars):\n{result.get('reasoning', '')[:300]}...")

    await council.close()
    return council._openthinker_available


async def main():
    """Run all integration tests."""
    print("=" * 60)
    print("OpenThinker-Agent Integration Tests")
    print("=" * 60)

    results = {}

    # Test 1: Local LLM Client
    try:
        results["local_llm"] = await test_local_llm_client()
    except Exception as e:
        print(f"❌ Local LLM test failed: {e}")
        results["local_llm"] = False

    # Test 2: OpenThinker Reasoner
    try:
        results["reasoner"] = await test_openthinker_reasoner()
    except Exception as e:
        print(f"❌ Reasoner test failed: {e}")
        results["reasoner"] = False

    # Test 3: OpenThinker Agent
    try:
        results["agent"] = await test_openthinker_agent()
    except Exception as e:
        print(f"❌ Agent test failed: {e}")
        results["agent"] = False

    # Test 4: Enhanced Council
    try:
        results["council"] = await test_enhanced_council()
    except Exception as e:
        print(f"❌ Council test failed: {e}")
        results["council"] = False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False

    if not all_passed:
        print("\n⚠️  Some tests failed. To fix:")
        print("1. Ensure Ollama is running: ollama serve")
        print("2. Install OpenThinker: ollama pull openthinker:7b")
        print("3. Check Ollama is accessible at http://localhost:11434")

    print("\n" + "=" * 60)
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
