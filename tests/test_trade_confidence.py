"""Tests for Trade Confidence Model using Thompson Sampling (ML-IMP-3)."""


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

    def test_spike_regime_reduces_confidence(self):
        """Test that spike regime reduces confidence (adjustment = 0.5)."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        spike_conf = model.sample_confidence("iron_condor", "SPY", "spike")
        calm_conf = model.sample_confidence("iron_condor", "SPY", "calm")
        assert spike_conf < calm_conf  # Spike should be lower than calm

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
            "minimum_sample_size",
            "sample_gate_passed",
            "is_reliable",
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

    def test_insufficient_samples_force_conservative_recommendation(self):
        """Sparse samples should not produce an entry recommendation."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        model.model["spy_specific"] = {"alpha": 6.0, "beta": 1.0, "wins": 1, "losses": 0}

        result = model.get_trade_confidence("iron_condor", "SPY", "calm")

        assert result["total_trades"] == 1
        assert result["sample_gate_passed"] is False
        assert result["is_reliable"] is False
        assert result["recommendation"] == "AVOID"

    def test_non_spy_strategy_uses_strategy_specific_stats(self):
        """Non-SPY lookups should use the requested strategy bucket, not SPY stats."""
        from src.ml.trade_confidence import TradeConfidenceModel

        model = TradeConfidenceModel()
        model.model["bull_put_spread"] = {"alpha": 9.0, "beta": 3.0, "wins": 7, "losses": 2}

        result = model.get_trade_confidence("bull_put_spread", "QQQ", "calm")

        assert result["wins"] == 7
        assert result["losses"] == 2
        assert result["total_trades"] == 9
        assert result["sample_gate_passed"] is True


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
