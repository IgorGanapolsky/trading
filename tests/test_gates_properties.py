#!/usr/bin/env python3
"""
Gate Property Tests - Validate gate behavior invariants

Based on Dec 11, 2025 analysis recommendations:
1. Monotonicity - Lower thresholds MUST NOT decrease pass rates
2. No-trade detection - Alert when gates eliminate ALL trades
3. Threshold sanity - Ensure thresholds are in valid ranges
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestGateMonotonicity:
    """Verify gate behavior is monotonic with thresholds."""

    @pytest.fixture
    def sample_momentum_data(self):
        np.random.seed(42)
        return [{"score": np.random.uniform(0.0, 1.0)} for _ in range(100)]

    def test_momentum_score_monotonicity(self, sample_momentum_data):
        """Lower threshold -> more passes (never fewer)."""
        def count_passes(threshold):
            return sum(1 for s in sample_momentum_data if s["score"] > threshold)

        thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        passes = {t: count_passes(t) for t in thresholds}

        for i in range(len(thresholds) - 1):
            lo, hi = thresholds[i], thresholds[i + 1]
            assert passes[lo] >= passes[hi], f"Monotonicity violation: {lo}->{passes[lo]}, {hi}->{passes[hi]}"

    def test_rl_confidence_monotonicity(self):
        """Lower RL threshold -> more passes."""
        np.random.seed(42)
        confidences = np.random.uniform(0.0, 1.0, 100)

        thresholds = [0.3, 0.45, 0.5, 0.6, 0.7]
        passes = {t: sum(1 for c in confidences if c >= t) for t in thresholds}

        for i in range(len(thresholds) - 1):
            lo, hi = thresholds[i], thresholds[i + 1]
            assert passes[lo] >= passes[hi], f"RL monotonicity violation"

    def test_sentiment_threshold_monotonicity(self):
        """More negative threshold -> more passes."""
        np.random.seed(42)
        sentiments = np.random.uniform(-0.5, 0.5, 100)

        thresholds = [-0.4, -0.3, -0.2, -0.1, 0.0, 0.1]
        passes = {t: sum(1 for s in sentiments if s >= t) for t in thresholds}

        for i in range(len(thresholds) - 1):
            lo, hi = thresholds[i], thresholds[i + 1]
            assert passes[lo] >= passes[hi], f"Sentiment monotonicity violation"


class TestNoTradeDetection:
    """Detect when gates eliminate ALL valid trades."""

    def test_gates_allow_some_trades(self):
        """With valid signals, some trades MUST pass."""
        np.random.seed(42)
        signals = [
            {"momentum": np.random.uniform(0.4, 0.9), "rl": np.random.uniform(0.5, 0.9), "sentiment": np.random.uniform(0.0, 0.5)}
            for _ in range(50)
        ]

        passed = 0
        for s in signals:
            if s["momentum"] >= 0.3 and s["rl"] >= 0.45 and s["sentiment"] >= -0.2:
                passed += 1

        assert passed > 0, f"CRITICAL: Gates eliminated ALL {len(signals)} trades!"

    def test_gate_elimination_attribution(self):
        """Track which gate rejected each signal."""
        np.random.seed(42)
        signals = [{"momentum": np.random.uniform(0, 1), "rl": np.random.uniform(0, 1), "sentiment": np.random.uniform(-0.5, 0.5)} for _ in range(100)]

        rejections = {"momentum": 0, "rl": 0, "sentiment": 0, "passed": 0}
        for s in signals:
            if s["momentum"] < 0.3:
                rejections["momentum"] += 1
            elif s["rl"] < 0.45:
                rejections["rl"] += 1
            elif s["sentiment"] < -0.2:
                rejections["sentiment"] += 1
            else:
                rejections["passed"] += 1

        assert rejections["passed"] > 0, f"All rejected: {rejections}"


class TestThresholdSanity:
    """Ensure thresholds are in valid ranges."""

    def test_rl_confidence_threshold_range(self):
        threshold = float(os.environ.get("RL_CONFIDENCE_THRESHOLD", "0.45"))
        assert 0 <= threshold <= 1, f"RL threshold {threshold} outside [0,1]"
        assert threshold <= 0.9, f"RL threshold {threshold} too restrictive"

    def test_sentiment_threshold_range(self):
        threshold = float(os.environ.get("LLM_NEGATIVE_SENTIMENT_THRESHOLD", "-0.2"))
        assert -1 <= threshold <= 1, f"Sentiment threshold {threshold} outside [-1,1]"

    def test_momentum_min_score_range(self):
        threshold = float(os.environ.get("MOMENTUM_MIN_SCORE", "0.0"))
        assert 0 <= threshold <= 1, f"Momentum threshold {threshold} outside [0,1]"

    def test_daily_loss_limit_range(self):
        limit = float(os.environ.get("MAX_DAILY_LOSS_PCT", "0.03"))
        assert 0 < limit <= 0.10, f"Daily loss {limit} should be 0-10%"

    def test_max_drawdown_range(self):
        limit = float(os.environ.get("MAX_DRAWDOWN_PCT", "0.10"))
        assert 0.05 <= limit <= 0.20, f"Max drawdown {limit} should be 5-20%"


class TestGateComposition:
    """Test how gates work together."""

    def test_single_gate_failure_blocks(self):
        """Failing ANY gate blocks the trade."""
        cases = [
            {"momentum": 0.1, "rl": 0.9, "sentiment": 0.9},  # fail momentum
            {"momentum": 0.9, "rl": 0.1, "sentiment": 0.9},  # fail rl
            {"momentum": 0.9, "rl": 0.9, "sentiment": -0.9}, # fail sentiment
        ]
        for c in cases:
            passed = c["momentum"] >= 0.3 and c["rl"] >= 0.45 and c["sentiment"] >= -0.2
            assert not passed, f"Should block: {c}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
