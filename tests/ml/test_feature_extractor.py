"""Unit tests for FeatureExtractor & MarketFeatures."""

import numpy as np
from src.ml.feature_extractor import FeatureExtractor, MarketFeatures


def test_market_features_vector_shape():
    mf = MarketFeatures()
    vec = mf.to_vector()
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (14,)
    assert vec.dtype == np.float32


def test_feature_extractor_from_snapshot():
    extractor = FeatureExtractor()
    snapshot = {
        "vix_level": 18.5,
        "vix_percentile": 0.42,
        "vix_term_structure": 1.05,
        "iv_rank": 45.0,
        "spy_20d_return": 0.012,
    }
    mf = extractor.extract_from_snapshot(snapshot)
    assert mf.vix_level == 18.5
    assert mf.vix_percentile == 0.42
    assert mf.vix_term_structure == 1.05
    assert mf.iv_rank == 45.0
    assert mf.spy_20d_return == 0.012


def test_feature_extractor_batch():
    extractor = FeatureExtractor()
    snapshots = [
        {"vix_level": 20.0},
        {"vix_level": 25.0},
    ]
    matrix = extractor.batch_extract(snapshots)
    assert matrix.shape == (2, 14)
