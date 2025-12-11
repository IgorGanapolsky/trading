#!/usr/bin/env python3
"""
Demo script for Dynamic Pre-Trade Risk Gate

Shows how the gate validates trades before execution.

Usage:
    python scripts/demo_pretrade_gate.py
"""

import logging
from datetime import datetime

from src.verification.dynamic_pretrade_risk_gate import (
    DynamicPreTradeGate,
    create_pretrade_gate,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def demo_basic_validation():
    """Demo 1: Basic trade validation."""
    print("\n" + "=" * 80)
    print("DEMO 1: Basic Trade Validation")
    print("=" * 80)

    # Create gate with $100k portfolio
    gate = create_pretrade_gate(portfolio_value=100000.0)

    # Test trade
    trade = {
        "symbol": "SPY",
        "side": "buy",
        "notional": 1000.0,
        "model": "gpt-4",
        "confidence": 0.65,
        "reasoning": "Strong uptrend with RSI at 45",
    }

    result = gate.validate_trade(trade)

    print(f"\nTrade: {trade['side'].upper()} ${trade['notional']:.2f} of {trade['symbol']}")
    print(f"\nRisk Score: {result.risk_score:.1f}/100")
    print(f"Decision: {'✅ APPROVED' if result.safe_to_trade else '🚫 BLOCKED'}")
    print(f"Recommendation: {result.recommendation}")

    print("\nCheck Results:")
    for check_name, check_data in result.checks.items():
        status = "✅" if check_data["passed"] else "❌"
        print(
            f"  {status} {check_name}: {check_data['score']:.1f}/100 - {check_data['recommendation']}"
        )

    if result.prevention_checklist:
        print("\nWarnings:")
        for warning in result.prevention_checklist:
            print(f"  ⚠️  {warning}")


def demo_oversized_trade():
    """Demo 2: Oversized trade rejection."""
    print("\n" + "=" * 80)
    print("DEMO 2: Oversized Trade Detection")
    print("=" * 80)

    gate = create_pretrade_gate(portfolio_value=100000.0)

    # Oversized trade (60% of portfolio)
    trade = {
        "symbol": "NVDA",
        "side": "buy",
        "notional": 60000.0,
        "model": "claude-sonnet-4",
        "confidence": 0.8,
        "reasoning": "AI chip demand is skyrocketing",
    }

    result = gate.validate_trade(trade)

    print(f"\nTrade: {trade['side'].upper()} ${trade['notional']:,.2f} of {trade['symbol']}")
    print(f"Portfolio: $100,000 → Trade is {trade['notional']/100000*100:.0f}% of portfolio")

    print(f"\nRisk Score: {result.risk_score:.1f}/100")
    print(f"Decision: {'✅ APPROVED' if result.safe_to_trade else '🚫 BLOCKED'}")

    print("\nPosition Validation:")
    pos_check = result.checks.get("position_validation", {})
    print(f"  Score: {pos_check.get('score', 0):.1f}/100")
    print(f"  Passed: {pos_check.get('passed', False)}")
    for issue in pos_check.get("details", {}).get("issues", []):
        print(f"  ❌ {issue}")


def demo_invalid_trade():
    """Demo 3: Invalid trade detection."""
    print("\n" + "=" * 80)
    print("DEMO 3: Invalid Trade Detection")
    print("=" * 80)

    gate = create_pretrade_gate(portfolio_value=100000.0)

    # Invalid trade (bad symbol, wrong side)
    trade = {
        "symbol": "INVALID123",  # Invalid symbol
        "side": "hold",  # Invalid side
        "notional": 500.0,
    }

    result = gate.validate_trade(trade)

    print(f"\nTrade: {trade['side'].upper()} ${trade['notional']:.2f} of {trade['symbol']}")

    print(f"\nRisk Score: {result.risk_score:.1f}/100")
    print(f"Decision: {'✅ APPROVED' if result.safe_to_trade else '🚫 BLOCKED'}")

    print("\nValidation Errors:")
    for warning in result.prevention_checklist:
        print(f"  ❌ {warning}")


def demo_risk_score_aggregation():
    """Demo 4: Risk score aggregation."""
    print("\n" + "=" * 80)
    print("DEMO 4: Risk Score Aggregation")
    print("=" * 80)

    gate = create_pretrade_gate(portfolio_value=100000.0)

    print("\nWeighted Risk Score Calculation:")
    print("  - Semantic Anomaly (RAG):    25% weight")
    print("  - Regime Aware Sizing:       20% weight")
    print("  - LLM Hallucination Guard:   25% weight")
    print("  - Traditional Anomaly:       15% weight")
    print("  - Position Validation:       15% weight")

    # Test different risk scenarios
    scenarios = [
        {
            "name": "Low Risk",
            "checks": {
                "semantic_anomaly": 10.0,
                "regime_aware": 15.0,
                "llm_guard": 5.0,
                "traditional": 10.0,
                "position_validation": 0.0,
            },
        },
        {
            "name": "Medium Risk",
            "checks": {
                "semantic_anomaly": 40.0,
                "regime_aware": 35.0,
                "llm_guard": 30.0,
                "traditional": 25.0,
                "position_validation": 20.0,
            },
        },
        {
            "name": "High Risk",
            "checks": {
                "semantic_anomaly": 80.0,
                "regime_aware": 90.0,
                "llm_guard": 85.0,
                "traditional": 70.0,
                "position_validation": 60.0,
            },
        },
    ]

    for scenario in scenarios:
        score = gate.aggregate_risk_scores(scenario["checks"])
        decision = "APPROVE" if score < 30 else "WARN" if score < 60 else "BLOCK"
        print(f"\n{scenario['name']}: {score:.1f}/100 → {decision}")


def demo_comparison():
    """Demo 5: Compare multiple trades."""
    print("\n" + "=" * 80)
    print("DEMO 5: Trade Comparison")
    print("=" * 80)

    gate = create_pretrade_gate(portfolio_value=100000.0)

    trades = [
        {
            "name": "Conservative ETF",
            "symbol": "SPY",
            "side": "buy",
            "notional": 500.0,
        },
        {
            "name": "Growth Stock",
            "symbol": "NVDA",
            "side": "buy",
            "notional": 2000.0,
        },
        {
            "name": "Small Position",
            "symbol": "AAPL",
            "side": "buy",
            "notional": 100.0,
        },
    ]

    print(f"\n{'Trade':<20} {'Risk Score':<12} {'Decision':<15}")
    print("-" * 47)

    for trade in trades:
        result = gate.validate_trade(trade)
        decision = "✅ APPROVED" if result.safe_to_trade else "🚫 BLOCKED"
        print(
            f"{trade['name']:<20} {result.risk_score:>5.1f}/100     {decision}"
        )


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Dynamic Pre-Trade Risk Gate - Demo")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Run all demos
    demo_basic_validation()
    demo_oversized_trade()
    demo_invalid_trade()
    demo_risk_score_aggregation()
    demo_comparison()

    print("\n" + "=" * 80)
    print("Demo Complete")
    print("=" * 80)
    print()
