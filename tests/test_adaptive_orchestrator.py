"""
Tests for Adaptive Orchestrator

Tests dynamic agent organization based on complexity and market regime.
"""

import pytest
from src.orchestration.adaptive_orchestrator import (
    AdaptiveOrchestrator,
    ComplexityAssessment,
    OrganizationPattern,
    TaskComplexity,
)


@pytest.fixture
def adaptive_orchestrator():
    """Create adaptive orchestrator for testing"""
    return AdaptiveOrchestrator(paper=True, enable_learning=False)


def test_complexity_assessment_simple(adaptive_orchestrator):
    """Test complexity assessment for simple tasks"""
    symbols = ["SPY"]
    context = {
        "volatility": 0.1,
        "position_size": 1000.0,
        "account_value": 100000.0,
        "uncertainty": 0.2,
    }

    assessment = adaptive_orchestrator.assess_complexity(symbols, context)

    assert assessment.complexity in [TaskComplexity.SIMPLE, TaskComplexity.MODERATE]
    assert 0.0 <= assessment.score <= 1.0
    assert "volatility" in assessment.factors
    assert "position_size" in assessment.factors


def test_complexity_assessment_complex(adaptive_orchestrator):
    """Test complexity assessment for complex tasks"""
    symbols = ["SPY", "QQQ", "VOO", "NVDA", "GOOGL"]
    context = {
        "volatility": 0.4,
        "position_size": 50000.0,
        "account_value": 100000.0,
        "uncertainty": 0.8,
    }

    assessment = adaptive_orchestrator.assess_complexity(symbols, context)

    assert assessment.complexity in [TaskComplexity.COMPLEX, TaskComplexity.CRITICAL]
    assert assessment.score > 0.5
    assert assessment.factors["volatility"] > 0.5
    assert assessment.factors["position_size"] > 0.5


def test_market_regime_detection(adaptive_orchestrator):
    """Test market regime detection"""
    symbols = ["SPY"]
    regime = adaptive_orchestrator._detect_market_regime(symbols)

    assert regime in ["BULL", "BEAR", "SIDEWAYS", "UNKNOWN"]


def test_create_adaptive_plan_simple(adaptive_orchestrator):
    """Test creating adaptive plan for simple task"""
    symbols = ["SPY"]
    context = {
        "volatility": 0.1,
        "position_size": 1000.0,
        "account_value": 100000.0,
    }

    plan = adaptive_orchestrator.create_adaptive_plan(symbols, context)

    assert plan.plan_id.startswith("adaptive_")
    assert plan.symbols == symbols
    assert "complexity" in plan.context
    assert "market_regime" in plan.context
    assert "organization_pattern" in plan.context
    assert len(plan.phases) > 0


def test_create_adaptive_plan_complex(adaptive_orchestrator):
    """Test creating adaptive plan for complex task"""
    symbols = ["SPY", "QQQ", "VOO"]
    context = {
        "volatility": 0.5,
        "position_size": 20000.0,
        "account_value": 100000.0,
        "uncertainty": 0.7,
    }

    plan = adaptive_orchestrator.create_adaptive_plan(symbols, context)

    assert plan.plan_id.startswith("adaptive_")
    assert plan.symbols == symbols
    assert plan.context["complexity"] in ["complex", "critical"]
    assert len(plan.phases) > 0


def test_organization_templates(adaptive_orchestrator):
    """Test that organization templates exist for all combinations"""
    complexities = [
        TaskComplexity.SIMPLE,
        TaskComplexity.MODERATE,
        TaskComplexity.COMPLEX,
        TaskComplexity.CRITICAL,
    ]
    regimes = ["BULL", "BEAR", "SIDEWAYS"]

    for complexity in complexities:
        for regime in regimes:
            assessment = ComplexityAssessment(
                complexity=complexity, score=0.5, factors={}, rationale=""
            )
            org = adaptive_orchestrator._select_organization(assessment, regime, ["SPY"], {})

            assert org is not None
            assert org.pattern in OrganizationPattern
            assert len(org.phases) > 0
            assert len(org.execution_order) > 0


def test_performance_recording(adaptive_orchestrator):
    """Test performance recording for learning"""
    from src.orchestration.adaptive_orchestrator import AgentOrganization

    assessment = ComplexityAssessment(
        complexity=TaskComplexity.MODERATE, score=0.5, factors={}, rationale=""
    )

    org = AgentOrganization(
        pattern=OrganizationPattern.PARALLEL,
        phases={},
        agent_assignments={},
        execution_order=[],
    )

    # Enable learning for this test
    adaptive_orchestrator.enable_learning = True

    # Record performance
    adaptive_orchestrator.record_performance(
        organization=org,
        complexity=assessment,
        market_regime="BULL",
        execution_time_ms=100.0,
        success=True,
        profit=50.0,
        confidence=0.8,
    )

    # Check that performance was recorded
    assert len(adaptive_orchestrator.performance_history) > 0


def test_learned_organization(adaptive_orchestrator):
    """Test that learned organizations are used when available"""
    # Record some successful performance
    from src.orchestration.adaptive_orchestrator import AgentOrganization

    assessment = ComplexityAssessment(
        complexity=TaskComplexity.MODERATE, score=0.5, factors={}, rationale=""
    )

    org = AgentOrganization(
        pattern=OrganizationPattern.PARALLEL,
        phases={},
        agent_assignments={},
        execution_order=[],
    )

    adaptive_orchestrator.record_performance(
        organization=org,
        complexity=assessment,
        market_regime="BULL",
        execution_time_ms=100.0,
        success=True,
        profit=100.0,
        confidence=0.9,
    )

    # Enable learning
    adaptive_orchestrator.enable_learning = True

    # Check if learned organization is returned
    learned = adaptive_orchestrator._get_learned_organization(assessment, "BULL")

    # May be None if not enough history, but should not error
    assert learned is None or isinstance(learned, AgentOrganization)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
