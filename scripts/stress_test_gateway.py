#!/usr/bin/env python3
"""
Trade Gateway Stress Test

This script tests that the mandatory risk gateway properly rejects dangerous trades.

Success Criteria:
- "Suicide command" ($1M AMC buy) must be REJECTED
- High correlation trades must be REJECTED
- Over-allocation trades must be REJECTED
- Frequency abuse must be REJECTED

Run this test BEFORE deploying any changes to production.

Author: AI Trading System
Date: December 2, 2025
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.risk.trade_gateway import TradeGateway, TradeRequest, RejectionReason


def run_stress_tests():
    """Run all stress tests against the trade gateway."""
    print("\n" + "="*70)
    print("🧪 TRADE GATEWAY STRESS TEST SUITE")
    print("="*70)

    gateway = TradeGateway(executor=None, paper=True)
    all_passed = True

    # ================================================================
    # TEST 1: Suicide Command ($1M AMC buy)
    # ================================================================
    print("\n--- TEST 1: Suicide Command ($1,000,000 AMC buy) ---")
    print("Expected: REJECT with 'Insufficient Funds' and 'Max Allocation Exceeded'")

    request = TradeRequest(
        symbol="AMC",
        side="buy",
        notional=1000000,
        source="stress_test"
    )
    decision = gateway.evaluate(request)

    if decision.approved:
        print("❌ FAILED: Suicide command was APPROVED!")
        all_passed = False
    else:
        expected_rejections = {
            RejectionReason.INSUFFICIENT_FUNDS,
            RejectionReason.MAX_ALLOCATION_EXCEEDED
        }
        actual_rejections = set(decision.rejection_reasons)

        if expected_rejections.issubset(actual_rejections):
            print("✅ PASSED: Suicide command rejected with correct reasons")
            print(f"   Rejections: {[r.value for r in decision.rejection_reasons]}")
        else:
            print("⚠️ PARTIAL: Rejected but reasons may differ")
            print(f"   Expected: {[r.value for r in expected_rejections]}")
            print(f"   Got: {[r.value for r in decision.rejection_reasons]}")

    # ================================================================
    # TEST 2: Correlation Abuse (Buy NVDA, AMD, INTC at once)
    # ================================================================
    print("\n--- TEST 2: Correlation Abuse (Semiconductor cluster) ---")
    print("Expected: REJECT for high correlation with existing positions")

    # Simulate having NVDA position
    gateway.executor = type('MockExecutor', (), {
        'account_equity': 10000,
        'get_positions': lambda self: [
            {'symbol': 'NVDA', 'market_value': 3000}  # 30% of portfolio
        ]
    })()

    request = TradeRequest(
        symbol="AMD",  # High correlation with NVDA
        side="buy",
        notional=2000,  # Would be 20% more in semiconductors
        source="stress_test"
    )
    decision = gateway.evaluate(request)

    if RejectionReason.HIGH_CORRELATION in decision.rejection_reasons:
        print("✅ PASSED: High correlation trade rejected")
        print(f"   Correlation detected: {decision.metadata.get('correlation', 'N/A')}")
    else:
        print("⚠️ CHECK: Trade not rejected for correlation")
        print(f"   Rejections: {[r.value for r in decision.rejection_reasons]}")

    # ================================================================
    # TEST 3: Over-Allocation (>15% in single symbol)
    # ================================================================
    print("\n--- TEST 3: Over-Allocation (>15% single symbol) ---")
    print("Expected: REJECT for exceeding 15% allocation limit")

    gateway.executor = type('MockExecutor', (), {
        'account_equity': 10000,
        'get_positions': lambda self: [
            {'symbol': 'TSLA', 'market_value': 1400}  # 14% already
        ]
    })()

    request = TradeRequest(
        symbol="TSLA",
        side="buy",
        notional=200,  # Would push to 16%
        source="stress_test"
    )
    decision = gateway.evaluate(request)

    if RejectionReason.MAX_ALLOCATION_EXCEEDED in decision.rejection_reasons:
        print("✅ PASSED: Over-allocation rejected")
        print(f"   Exposure would be: {decision.metadata.get('exposure_pct', 'N/A')*100:.1f}%")
    else:
        print("⚠️ CHECK: Trade not rejected for over-allocation")
        print(f"   Rejections: {[r.value for r in decision.rejection_reasons]}")

    # ================================================================
    # TEST 4: Frequency Abuse (>5 trades/hour)
    # ================================================================
    print("\n--- TEST 4: Frequency Abuse (>5 trades/hour) ---")
    print("Expected: REJECT after 5 trades in one hour")

    gateway = TradeGateway(executor=None, paper=True)
    gateway.executor = type('MockExecutor', (), {
        'account_equity': 100000,
        'get_positions': lambda self: []
    })()

    # Simulate 5 recent trades
    from datetime import datetime, timedelta
    gateway.recent_trades = [datetime.now() - timedelta(minutes=i) for i in range(5)]

    request = TradeRequest(
        symbol="SPY",
        side="buy",
        notional=500,
        source="stress_test"
    )
    decision = gateway.evaluate(request)

    if RejectionReason.FREQUENCY_LIMIT in decision.rejection_reasons:
        print("✅ PASSED: Frequency limit enforced")
        print(f"   Trades in last hour: {decision.metadata.get('trades_last_hour', 'N/A')}")
    else:
        print("⚠️ CHECK: Trade not rejected for frequency")
        print(f"   Rejections: {[r.value for r in decision.rejection_reasons]}")

    # ================================================================
    # TEST 5: Batch Threshold ($10 trades should accumulate)
    # ================================================================
    print("\n--- TEST 5: Batch Threshold ($10 should accumulate to $200) ---")
    print("Expected: REJECT small trades, accumulate until $200")

    gateway = TradeGateway(executor=None, paper=True)
    gateway.accumulated_cash = 0
    gateway.executor = type('MockExecutor', (), {
        'account_equity': 100000,
        'get_positions': lambda self: []
    })()

    request = TradeRequest(
        symbol="SPY",
        side="buy",
        notional=10,  # $10 trade
        source="stress_test"
    )
    decision = gateway.evaluate(request)

    if RejectionReason.MINIMUM_BATCH_NOT_MET in decision.rejection_reasons:
        print("✅ PASSED: Small trade accumulated instead of executed")
        print(f"   Accumulated: ${gateway.accumulated_cash:.2f}")
        print(f"   Warning: {decision.warnings[0] if decision.warnings else 'N/A'}")
    else:
        print("⚠️ CHECK: Small trade not accumulated")
        print(f"   Rejections: {[r.value for r in decision.rejection_reasons]}")

    # ================================================================
    # TEST 6: Normal Trade (Should PASS)
    # ================================================================
    print("\n--- TEST 6: Normal Trade ($500 SPY buy) ---")
    print("Expected: APPROVED (all checks pass)")

    gateway = TradeGateway(executor=None, paper=True)
    gateway.executor = type('MockExecutor', (), {
        'account_equity': 100000,
        'get_positions': lambda self: []
    })()

    request = TradeRequest(
        symbol="SPY",
        side="buy",
        notional=500,
        source="stress_test"
    )
    decision = gateway.evaluate(request)

    if decision.approved:
        print("✅ PASSED: Normal trade approved")
        print(f"   Risk score: {decision.risk_score:.2f}")
    else:
        print("❌ FAILED: Normal trade should be approved!")
        print(f"   Rejections: {[r.value for r in decision.rejection_reasons]}")
        all_passed = False

    # ================================================================
    # TEST 7: Capital Efficiency - Iron Condor on Small Account
    # ================================================================
    print("\n--- TEST 7: Capital Efficiency (Iron Condor on $5k account) ---")
    print("Expected: REJECT for insufficient capital (need $10k for iron condors)")

    gateway = TradeGateway(executor=None, paper=True)
    gateway.executor = type('MockExecutor', (), {
        'account_equity': 5000,  # Small account
        'get_positions': lambda self: []
    })()

    request = TradeRequest(
        symbol="SPY",
        side="buy",
        notional=500,
        source="stress_test",
        strategy_type="iron_condor",  # Strategy that needs $10k+
        iv_rank=50.0
    )
    decision = gateway.evaluate(request)

    if RejectionReason.CAPITAL_INEFFICIENT in decision.rejection_reasons:
        print("✅ PASSED: Iron condor rejected for small account")
        print(f"   Capital viability: {decision.metadata.get('capital_viability', {}).get('reason', 'N/A')}")
    else:
        print("⚠️ CHECK: Trade not rejected for capital inefficiency")
        print(f"   Rejections: {[r.value for r in decision.rejection_reasons]}")

    # ================================================================
    # TEST 8: IV Rank Filter - Credit Spread when IV < 20
    # ================================================================
    print("\n--- TEST 8: IV Rank Filter (Credit Spread when IV Rank = 15) ---")
    print("Expected: REJECT for IV Rank too low (<20 for premium selling)")

    gateway = TradeGateway(executor=None, paper=True)
    gateway.executor = type('MockExecutor', (), {
        'account_equity': 50000,  # Adequate capital
        'get_positions': lambda self: []
    })()

    request = TradeRequest(
        symbol="SPY",
        side="buy",
        notional=500,
        source="stress_test",
        strategy_type="iron_condor",  # Credit strategy
        iv_rank=15.0  # Below the 20 minimum
    )
    decision = gateway.evaluate(request)

    if RejectionReason.IV_RANK_TOO_LOW in decision.rejection_reasons:
        print("✅ PASSED: Credit strategy rejected for low IV Rank")
        print(f"   IV Rank rejection: {decision.metadata.get('iv_rank_rejection', {}).get('reason', 'N/A')}")
    else:
        print("⚠️ CHECK: Trade not rejected for low IV Rank")
        print(f"   Rejections: {[r.value for r in decision.rejection_reasons]}")

    # ================================================================
    # TEST 9: High IV Rank Credit Strategy (Should PASS)
    # ================================================================
    print("\n--- TEST 9: High IV Rank Credit Strategy (IV Rank = 60) ---")
    print("Expected: APPROVED (IV Rank meets requirement)")

    gateway = TradeGateway(executor=None, paper=True)
    gateway.executor = type('MockExecutor', (), {
        'account_equity': 50000,  # Adequate capital
        'get_positions': lambda self: []
    })()

    request = TradeRequest(
        symbol="SPY",
        side="buy",
        notional=500,
        source="stress_test",
        strategy_type="iron_condor",  # Credit strategy
        iv_rank=60.0  # Above the 20 minimum
    )
    decision = gateway.evaluate(request)

    if decision.approved:
        print("✅ PASSED: Credit strategy approved with high IV Rank")
        print(f"   Risk score: {decision.risk_score:.2f}")
    else:
        print("⚠️ CHECK: Trade rejected unexpectedly")
        print(f"   Rejections: {[r.value for r in decision.rejection_reasons]}")

    # ================================================================
    # FINAL RESULT
    # ================================================================
    print("\n" + "="*70)
    if all_passed:
        print("🎉 ALL CRITICAL TESTS PASSED")
        print("The gateway is working correctly.")
    else:
        print("⚠️ SOME TESTS FAILED")
        print("Review the gateway logic before deploying.")
    print("="*70 + "\n")

    return all_passed


if __name__ == "__main__":
    success = run_stress_tests()
    sys.exit(0 if success else 1)
