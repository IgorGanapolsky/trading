"""
Tests for Microstructure Features Signal.
"""

import pytest

# Skip entire module if numpy/pandas not available (sandbox limitation)
pytest.importorskip("pandas")

from src.signals.microstructure_features import (
    MicrostructureFeatures,
    MicrostructureFeatureExtractor,
    extract_microstructure,
)


def test_microstructure_features_init():
    """Test instantiation and initial state of MicrostructureFeatures."""
    extractor = MicrostructureFeatures()
    assert extractor.features == {}


def test_microstructure_features_extract():
    """Test extract method returns expected dummy microstructure features."""
    extractor = MicrostructureFeatures()
    market_data = {"dummy": "data"}
    features = extractor.extract(market_data)

    assert isinstance(features, dict)
    assert features["bid_ask_spread"] == 0.01
    assert features["volume_imbalance"] == 0.0
    assert features["order_flow"] == "neutral"
    assert features["liquidity_score"] == 0.5


def test_microstructure_features_get_signal():
    """Test get_signal returns the expected trading signal dictionary."""
    extractor = MicrostructureFeatures()
    dummy_features = {"bid_ask_spread": 0.02}
    signal = extractor.get_signal(dummy_features)

    assert isinstance(signal, dict)
    assert signal["action"] == "hold"
    assert signal["confidence"] == 0.5
    assert signal["features"] == dummy_features


def test_extract_microstructure():
    """Test the convenience function extract_microstructure."""
    market_data = {"price": 100}
    features = extract_microstructure(market_data)

    assert isinstance(features, dict)
    assert features["bid_ask_spread"] == 0.01
    assert features["volume_imbalance"] == 0.0
    assert features["order_flow"] == "neutral"
    assert features["liquidity_score"] == 0.5


def test_microstructure_feature_extractor_alias():
    """Test that MicrostructureFeatureExtractor is a valid alias for MicrostructureFeatures."""
    assert MicrostructureFeatureExtractor is MicrostructureFeatures

    extractor = MicrostructureFeatureExtractor()
    assert isinstance(extractor, MicrostructureFeatures)
    assert extractor.features == {}
