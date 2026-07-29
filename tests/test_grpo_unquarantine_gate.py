import pytest
from src.ml.grpo_unquarantine_gate import GRPOUnquarantineGate
from src.observability.llm_gateway import LLMGateway


def test_grpo_quarantine_default():
    gate = GRPOUnquarantineGate(required_outcomes=30)
    status = gate.check_status([])

    assert status.is_quarantined is True
    assert status.total_verified_outcomes == 0
    assert "Quarantined" in status.status_message


def test_grpo_unquarantine_transition():
    gate = GRPOUnquarantineGate(required_outcomes=30, min_win_rate_pct=75.0)
    # Generate 35 winning outcomes
    outcomes = [{"profit_usd": 50.0, "behavior_prob": 0.8} for _ in range(35)]
    status = gate.check_status(outcomes)

    assert status.is_quarantined is False
    assert status.total_verified_outcomes == 35
    assert status.win_rate_pct == 100.0
    assert "UNQUARANTINED" in status.status_message


def test_llm_gateway_status():
    status = LLMGateway.get_routing_status()
    assert status.primary_route == "anthropic"
    assert status.is_fully_configured is True
