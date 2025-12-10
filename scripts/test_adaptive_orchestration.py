#!/usr/bin/env python3
"""
Test script for Adaptive Orchestrator

Demonstrates adaptive agent organization in action.
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.adaptive_orchestrator import (
    AdaptiveOrchestrator,
    TaskComplexity,
)
from src.orchestration.elite_orchestrator import EliteOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_complexity_assessment():
    """Test complexity assessment for different scenarios"""
    logger.info("=" * 80)
    logger.info("TEST 1: Complexity Assessment")
    logger.info("=" * 80)

    orchestrator = AdaptiveOrchestrator(paper=True, enable_learning=False)

    # Simple scenario
    logger.info("\n📊 Simple Task:")
    simple_context = {
        "volatility": 0.1,
        "position_size": 1000.0,
        "account_value": 100000.0,
        "uncertainty": 0.2,
    }
    simple_assessment = orchestrator.assess_complexity(["SPY"], simple_context)
    logger.info(f"   Complexity: {simple_assessment.complexity.value}")
    logger.info(f"   Score: {simple_assessment.score:.2f}")
    logger.info(f"   Rationale: {simple_assessment.rationale}")

    # Complex scenario
    logger.info("\n📊 Complex Task:")
    complex_context = {
        "volatility": 0.5,
        "position_size": 50000.0,
        "account_value": 100000.0,
        "uncertainty": 0.8,
    }
    complex_assessment = orchestrator.assess_complexity(
        ["SPY", "QQQ", "VOO", "NVDA", "GOOGL"], complex_context
    )
    logger.info(f"   Complexity: {complex_assessment.complexity.value}")
    logger.info(f"   Score: {complex_assessment.score:.2f}")
    logger.info(f"   Rationale: {complex_assessment.rationale}")


def test_organization_patterns():
    """Test different organization patterns"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Organization Patterns")
    logger.info("=" * 80)

    orchestrator = AdaptiveOrchestrator(paper=True, enable_learning=False)

    complexities = [
        TaskComplexity.SIMPLE,
        TaskComplexity.MODERATE,
        TaskComplexity.COMPLEX,
        TaskComplexity.CRITICAL,
    ]
    regimes = ["BULL", "BEAR", "SIDEWAYS"]

    from src.orchestration.adaptive_orchestrator import ComplexityAssessment

    for complexity in complexities:
        for regime in regimes:
            assessment = ComplexityAssessment(
                complexity=complexity, score=0.5, factors={}, rationale=""
            )
            org = orchestrator._select_organization(assessment, regime, ["SPY"], {})

            logger.info(f"\n   {complexity.value.upper()} + {regime}: {org.pattern.value.upper()}")
            logger.info(f"   Rationale: {org.rationale}")
            logger.info(f"   Phases: {len(org.phases)}")


def test_adaptive_plan_creation():
    """Test adaptive plan creation"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Adaptive Plan Creation")
    logger.info("=" * 80)

    orchestrator = AdaptiveOrchestrator(paper=True, enable_learning=False)

    # Simple plan
    logger.info("\n📋 Simple Plan:")
    simple_plan = orchestrator.create_adaptive_plan(
        ["SPY"],
        {
            "volatility": 0.1,
            "position_size": 1000.0,
            "account_value": 100000.0,
        },
    )
    logger.info(f"   Plan ID: {simple_plan.plan_id}")
    logger.info(f"   Complexity: {simple_plan.context.get('complexity')}")
    logger.info(f"   Regime: {simple_plan.context.get('market_regime')}")
    logger.info(f"   Pattern: {simple_plan.context.get('organization_pattern')}")
    logger.info(f"   Phases: {list(simple_plan.phases.keys())}")

    # Complex plan
    logger.info("\n📋 Complex Plan:")
    complex_plan = orchestrator.create_adaptive_plan(
        ["SPY", "QQQ", "VOO"],
        {
            "volatility": 0.5,
            "position_size": 20000.0,
            "account_value": 100000.0,
            "uncertainty": 0.7,
        },
    )
    logger.info(f"   Plan ID: {complex_plan.plan_id}")
    logger.info(f"   Complexity: {complex_plan.context.get('complexity')}")
    logger.info(f"   Regime: {complex_plan.context.get('market_regime')}")
    logger.info(f"   Pattern: {complex_plan.context.get('organization_pattern')}")
    logger.info(f"   Phases: {list(complex_plan.phases.keys())}")


def test_elite_integration():
    """Test integration with EliteOrchestrator"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Elite Orchestrator Integration")
    logger.info("=" * 80)

    # Test with adaptive enabled
    logger.info("\n✅ With Adaptive Organization:")
    elite_adaptive = EliteOrchestrator(paper=True, enable_adaptive=True)
    plan_adaptive = elite_adaptive.create_trade_plan(["SPY"])
    logger.info(f"   Plan ID: {plan_adaptive.plan_id}")
    logger.info(f"   Organization: {plan_adaptive.context.get('organization_pattern', 'fixed')}")

    # Test with adaptive disabled
    logger.info("\n📋 With Fixed Organization:")
    elite_fixed = EliteOrchestrator(paper=True, enable_adaptive=False)
    plan_fixed = elite_fixed.create_trade_plan(["SPY"])
    logger.info(f"   Plan ID: {plan_fixed.plan_id}")
    logger.info("   Organization: fixed (no adaptive context)")


def test_performance_learning():
    """Test performance learning mechanism"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: Performance Learning")
    logger.info("=" * 80)

    orchestrator = AdaptiveOrchestrator(paper=True, enable_learning=True)

    from src.orchestration.adaptive_orchestrator import (
        AgentOrganization,
        ComplexityAssessment,
        OrganizationPattern,
    )

    # Record some performance
    assessment = ComplexityAssessment(
        complexity=TaskComplexity.MODERATE, score=0.5, factors={}, rationale=""
    )

    org = AgentOrganization(
        pattern=OrganizationPattern.PARALLEL,
        phases={},
        agent_assignments={},
        execution_order=[],
    )

    logger.info("\n📊 Recording Performance:")
    orchestrator.record_performance(
        organization=org,
        complexity=assessment,
        market_regime="BULL",
        execution_time_ms=150.0,
        success=True,
        profit=75.0,
        confidence=0.85,
    )
    logger.info(f"   Recorded {len(orchestrator.performance_history)} performance entries")

    # Test learned organization
    logger.info("\n📚 Testing Learned Organization:")
    learned = orchestrator._get_learned_organization(assessment, "BULL")
    if learned:
        logger.info(f"   Found learned pattern: {learned.pattern.value}")
    else:
        logger.info("   No learned pattern yet (need more data)")


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 80)
    logger.info("ADAPTIVE ORCHESTRATOR TEST SUITE")
    logger.info("=" * 80)

    try:
        test_complexity_assessment()
        test_organization_patterns()
        test_adaptive_plan_creation()
        test_elite_integration()
        test_performance_learning()

        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL TESTS COMPLETED")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
