#!/usr/bin/env python3
"""
Test Elite Orchestrator
Verifies elite multi-agent orchestration system
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()

from src.orchestration.context_engine import ContextEngine
from src.orchestration.elite_orchestrator import EliteOrchestrator, PlanningPhase


def test_elite_orchestrator():
    """Test Elite Orchestrator"""
    print("\n" + "=" * 80)
    print("ELITE ORCHESTRATOR TEST")
    print("=" * 80)

    try:
        # Initialize orchestrator
        orchestrator = EliteOrchestrator(paper=True, enable_planning=True)
        print("✅ Elite Orchestrator initialized")

        # Test plan creation
        plan = orchestrator.create_trade_plan(symbols=["SPY", "QQQ"])
        print(f"✅ Trade plan created: {plan.plan_id}")
        print(f"   Phases: {len(plan.phases)}")
        print(f"   Symbols: {plan.symbols}")

        # Verify phases
        expected_phases = [
            PlanningPhase.INITIALIZE.value,
            PlanningPhase.DATA_COLLECTION.value,
            PlanningPhase.ANALYSIS.value,
            PlanningPhase.RISK_ASSESSMENT.value,
            PlanningPhase.EXECUTION.value,
            PlanningPhase.AUDIT.value,
        ]

        for phase in expected_phases:
            if phase in plan.phases:
                print(f"   ✅ Phase: {phase}")
            else:
                print(f"   ❌ Missing phase: {phase}")

        return True
    except Exception as e:
        print(f"❌ Elite Orchestrator test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_context_engine():
    """Test Context Engine"""
    print("\n" + "=" * 80)
    print("CONTEXT ENGINE TEST")
    print("=" * 80)

    try:
        # Initialize context engine
        context_engine = ContextEngine()
        print("✅ Context Engine initialized")

        # Test saving trade log
        trade_data = {
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 10,
            "price": 450.00,
            "pnl": 0,
            "agent_type": "test",
            "timestamp": "2025-11-25T10:00:00",
        }
        log_path = context_engine.save_trade_log(trade_data)
        print(f"✅ Trade log saved: {log_path}")

        # Test loading recent trades
        recent_trades = context_engine.load_recent_trades(symbol="SPY", days=7)
        print(f"✅ Loaded {len(recent_trades)} recent trades")

        # Test context summary
        summary = context_engine.get_context_summary("SPY", days=30)
        print("✅ Context summary generated")
        print(f"   Total trades: {summary['summary']['total_trades']}")
        print(f"   Win rate: {summary['summary']['win_rate_pct']:.1f}%")

        return True
    except Exception as e:
        print(f"❌ Context Engine test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("ELITE AI TRADING SYSTEM TEST SUITE")
    print("=" * 80)

    results = {}

    results["elite_orchestrator"] = test_elite_orchestrator()
    results["context_engine"] = test_context_engine()

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{status} {test_name.replace('_', ' ').title()}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Elite system ready!")
        return 0
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
