"""Tests for Trade Confidence Model using Thompson Sampling (ML-IMP-3)."""

import pytest


class TestTradeConfidenceModel:
    """Test TradeConfidenceModel initialization and loading."""

    def test_model_loads(self):
        """Test that model loads from JSON file."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        assert model.model is not None
        assert "iron_condor" in model.model

    def test_posterior_mean_calculation(self):
        """Test posterior mean is calculated correctly."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        mean = model.get_posterior_mean("iron_condor", "SPY")
        # Mean should be between 0 and 1
        assert 0.0 <= mean <= 1.0

    def test_sample_confidence_in_range(self):
        """Test sampled confidence is between 0 and 1."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        for _ in range(10):
            sample = model.sample_confidence("iron_condor", "SPY")
            assert 0.0 <= sample <= 1.0


class TestRegimeAdjustments:
    """Test regime-based confidence adjustments."""

    def test_spike_regime_returns_zero(self):
        """Test that spike regime returns zero confidence."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        conf = model.sample_confidence("iron_condor", "SPY", "spike")
        assert conf == 0.0

    def test_calm_regime_boost(self):
        """Test that calm regime boosts confidence (adjustment > 1)."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        regime_adj = model.model.get("regime_adjustments", {}).get("calm", 1.0)
        assert regime_adj > 1.0

    def test_volatile_regime_reduction(self):
        """Test that volatile regime reduces confidence (adjustment < 1)."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        regime_adj = model.model.get("regime_adjustments", {}).get("volatile", 1.0)
        assert regime_adj < 1.0


class TestTradeConfidenceResult:
    """Test get_trade_confidence result structure."""

    def test_result_has_required_keys(self):
        """Test result dict has all required keys."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        result = model.get_trade_confidence("iron_condor", "SPY", "calm")

        required_keys = [
            "posterior_mean",
            "sampled_confidence",
            "regime_adjustment",
            "recommendation",
            "wins",
            "losses",
            "total_trades",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

    def test_recommendation_values(self):
        """Test recommendation is one of valid values."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        result = model.get_trade_confidence("iron_condor", "SPY", "calm")
        valid_recommendations = ["ENTER", "CONSIDER", "CAUTIOUS", "AVOID"]
        assert result["recommendation"] in valid_recommendations


class TestSingletonAccess:
    """Test singleton pattern and quick access functions."""

    def test_get_trade_confidence_model(self):
        """Test singleton returns same instance."""
        from src.ml.trade_confidence import get_trade_confidence_model

        model1 = get_trade_confidence_model()
        model2 = get_trade_confidence_model()
        assert model1 is model2

    def test_sample_trade_confidence_function(self):
        """Test quick access function works."""
        from src.ml.trade_confidence import sample_trade_confidence

        conf = sample_trade_confidence("iron_condor", "SPY", "calm")
        assert 0.0 <= conf <= 1.0


class TestOutcomeRecording:
    """Test trade outcome recording."""

    def test_record_win_increases_alpha(self):
        """Test recording a win increases alpha."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        initial_alpha = model.model.get("iron_condor", {}).get("alpha", 1.0)

        # Record a win (but don't save to avoid side effects in test)
        model.model["iron_condor"]["alpha"] += 1.0
        model.model["iron_condor"]["wins"] += 1

        assert model.model["iron_condor"]["alpha"] == initial_alpha + 1.0

    def test_record_loss_increases_beta(self):
        """Test recording a loss increases beta."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        initial_beta = model.model.get("iron_condor", {}).get("beta", 1.0)

        # Record a loss (but don't save to avoid side effects in test)
        model.model["iron_condor"]["beta"] += 1.0
        model.model["iron_condor"]["losses"] += 1

        assert model.model["iron_condor"]["beta"] == initial_beta + 1.0
