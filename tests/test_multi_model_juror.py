import pytest

from src.safety.multi_model_juror import MultiModelJuror


def test_juror_refuses_simulated_agree():
    """Never invent multi-model agreement — simulated AGREE is forbidden."""
    juror = MultiModelJuror()
    proposal = {"symbol": "SPY", "strategy": "iron_condor", "amount": 500.0}
    reasoning = "VIX is optimal, 15-delta selected."

    with pytest.raises(RuntimeError, match="JUROR_UNAVAILABLE"):
        juror.get_consensus(proposal, primary_reasoning=reasoning)


def test_juror_consensus_exception_fails_closed(monkeypatch):
    juror = MultiModelJuror()
    proposal = {"symbol": "SPY"}

    # Non-RuntimeError paths still fail closed (return False).
    with monkeypatch.context() as m:

        def mock_error(*args, **kwargs):
            raise ValueError("API Offline")

        m.setattr("src.safety.multi_model_juror.logger.info", mock_error)

        result = juror.get_consensus(proposal, "test reasoning")
        assert result is False  # Must fail closed on exception
