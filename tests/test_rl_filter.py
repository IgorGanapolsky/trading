"""Tests for RLFilter - Linear Feature Scoring Model (ML-IMP-1)."""

import pytest


class TestRLFilterInit:
    """Test RLFilter initialization."""

    def test_filter_loads_weights(self):
        """Test that RLFilter loads weights from JSON file."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        assert rl.weights is not None
        assert "default" in rl.weights
        assert "SPY" in rl.weights

    def test_filter_enabled_by_default(self):
        """Test that RLFilter is enabled by default."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        assert rl.enabled is True

    def test_spy_weights_exist(self):
        """Test SPY-specific weights are loaded."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        spy_weights = rl._get_ticker_weights("SPY")
        assert "bias" in spy_weights
        assert "weights" in spy_weights
        assert "action_threshold" in spy_weights


class TestRLFilterScoring:
    """Test RLFilter scoring logic."""

    def test_compute_score_with_features(self):
        """Test score computation with sample features."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        features = {
            "strength": 1.0,
            "momentum": 0.5,
            "rsi_gap": 0.3,
        }
        score = rl._compute_score(features, "SPY")
        # Score should be non-zero with these features
        assert score != 0.0

    def test_compute_score_empty_features(self):
        """Test score computation with empty features returns bias only."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        score = rl._compute_score({}, "SPY")
        # Should return just the bias
        spy_weights = rl._get_ticker_weights("SPY")
        assert score == spy_weights.get("bias", 0.0)

    def test_default_weights_fallback(self):
        """Test that unknown ticker falls back to default weights."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        unknown_weights = rl._get_ticker_weights("UNKNOWN")
        default_weights = rl._get_ticker_weights("default")
        assert unknown_weights == default_weights


class TestRLFilterActions:
    """Test RLFilter action determination."""

    def test_high_score_returns_enter(self):
        """Test that high score returns 'enter' action."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        # High feature values should produce high score -> enter
        features = {
            "strength": 2.0,
            "momentum": 1.5,
            "rsi_gap": 1.0,
            "volume_premium": 1.0,
            "sma_ratio": 1.0,
            "adx_normalized": 1.0,
            "di_difference": 1.0,
        }
        result = rl.filter({"features": features}, "SPY")
        assert result["action"] == "enter"
        assert result["confidence"] > 0.5

    def test_low_score_returns_hold(self):
        """Test that low/neutral score returns 'hold' action."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        # Zero features should produce low score -> hold
        result = rl.filter({"features": {}}, "SPY")
        assert result["action"] == "hold"
        assert result["confidence"] == 0.5

    def test_get_action_returns_tuple(self):
        """Test get_action returns (action, confidence) tuple."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        action, confidence = rl.get_action({"strength": 0.5}, "SPY")
        assert isinstance(action, str)
        assert isinstance(confidence, float)
        assert action in ("enter", "hold", "exit")

    def test_predict_returns_dict(self):
        """Test predict returns dict with required keys."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        result = rl.predict({"strength": 0.5}, "SPY")
        assert "action" in result
        assert "confidence" in result


class TestRLFilterBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_filter_without_features_key(self):
        """Test filter works when features are passed directly."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        # Features passed directly (not nested under 'features' key)
        result = rl.filter({"strength": 0.5, "momentum": 0.3}, "SPY")
        assert "action" in result
        assert "confidence" in result

    def test_health_check_compatibility(self):
        """Test predict returns valid response for health check."""
        from src.agents.rl_agent import RLFilter

        rl = RLFilter()
        result = rl.predict({}, "SPY")
        # Health check expects these keys
        assert "action" in result
        assert "confidence" in result
        assert result["action"] in ("enter", "hold", "exit")
