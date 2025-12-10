from src.agents.anthropic_patterns import (
    ActionTool,
    ErrorRecoveryFramework,
    EvaluatorOptimizerLoop,
    HumanCheckpoint,
)
from src.agents.gateway_integration import EnhancedTradeGateway
from src.agents.rl_evaluator_optimizer import RLEvaluatorOptimizer


def test_anthropic_patterns_import():
    assert HumanCheckpoint is not None
    assert ErrorRecoveryFramework is not None
    assert EvaluatorOptimizerLoop is not None
    assert ActionTool is not None


def test_gateway_integration_import():
    assert EnhancedTradeGateway is not None


def test_rl_evaluator_optimizer_import():
    assert RLEvaluatorOptimizer is not None


def test_initialization():
    # Basic initialization test
    optimizer = RLEvaluatorOptimizer()
    assert optimizer is not None
