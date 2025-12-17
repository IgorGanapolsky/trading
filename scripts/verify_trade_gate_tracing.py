#!/usr/bin/env python3
"""
Verify LangSmith tracing is working for the trade gate.

Run this after adding your LANGSMITH_API_KEY to .env or environment:
    python3 scripts/verify_trade_gate_tracing.py

Expected output:
    ✅ Trade gate decision traced to LangSmith
    👉 Go to https://smith.langchain.com to see your traces
"""

from __future__ import annotations

import os
import sys

# Ensure we can import from src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    # Check for API key
    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        print("❌ LANGSMITH_API_KEY not set!")
        print()
        print("To enable LangSmith tracing:")
        print("  1. Go to https://smith.langchain.com")
        print("  2. Get your API key from Settings")
        print("  3. Set it in your environment:")
        print("     export LANGSMITH_API_KEY='your-key-here'")
        print()
        print("  Or add to .env file:")
        print("     LANGSMITH_API_KEY=your-key-here")
        print()
        print("Running gate WITHOUT tracing to show it still works...")
        print()
    else:
        print(f"✅ Found LANGSMITH_API_KEY: {api_key[:8]}...")
        print()

    # Enable tracing
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "ai-trading-system")

    # Import and test the trade gate
    from src.safety.mandatory_trade_gate import validate_trade_mandatory

    print("Testing trade gate with LangSmith tracing...")
    print("-" * 50)

    # Test 1: Valid equity trade
    print("\n🧪 Test 1: Valid SPY BUY order")
    result1 = validate_trade_mandatory(
        symbol="SPY",
        amount=100.0,
        side="BUY",
        strategy="equities",
    )
    print(f"   Result: {'✅ APPROVED' if result1.approved else '🚫 BLOCKED'}")
    print(f"   Confidence: {result1.confidence:.2f}")
    print(f"   RAG warnings: {len(result1.rag_warnings)}")
    print(f"   ML anomalies: {len(result1.ml_anomalies)}")

    result2 = validate_trade_mandatory(
        symbol="AAPL",
        amount=500.0,
        side="BUY",
    )
    print(f"   Result: {'✅ APPROVED' if result2.approved else '🚫 BLOCKED'}")
    print(f"   Confidence: {result2.confidence:.2f}")
    print(f"   RAG warnings: {len(result2.rag_warnings)}")
    print(f"   ML anomalies: {len(result2.ml_anomalies)}")

    # Test 3: Large order (should trigger ML anomaly)
    print("\n🧪 Test 3: Large AAPL order ($50,000)")
    result3 = validate_trade_mandatory(
        symbol="AAPL",
        amount=50000.0,
        side="BUY",
        strategy="equities",
    )
    print(f"   Result: {'✅ APPROVED' if result3.approved else '🚫 BLOCKED'}")
    print(f"   Confidence: {result3.confidence:.2f}")
    print(f"   RAG warnings: {len(result3.rag_warnings)}")
    print(f"   ML anomalies: {len(result3.ml_anomalies)}")

    print("\n" + "-" * 50)

    if api_key:
        print("✅ All tests completed with LangSmith tracing!")
        print()
        print("👉 Check your traces at: https://smith.langchain.com")
        print("   Project: ai-trading-system")
        print("   Look for traces named: trade_gate_SPY_BUY, trade_gate__BUY, etc.")
    else:
        print("⚠️ Tests completed WITHOUT LangSmith tracing (API key not set)")
        print("   Set LANGSMITH_API_KEY to enable tracing")


if __name__ == "__main__":
    main()
