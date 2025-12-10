"""
Tests for data leakage prevention in DataProcessor normalization.

These tests verify that the fit/transform pattern properly prevents
data leakage from test data into training normalization parameters.

Reference: https://www.kdnuggets.com/5-critical-feature-engineering-mistakes-that-kill-machine-learning-projects
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.data_processor import DataProcessor


@pytest.fixture
def sample_data():
    """Create sample data with known statistics for testing."""
    np.random.seed(42)
    n_samples = 100

    # Create data where train and test have DIFFERENT distributions
    # This makes leakage detectable
    train_data = pd.DataFrame(
        {
            "Close": np.random.normal(100, 10, n_samples),  # mean=100, std=10
            "Volume": np.random.normal(1000, 100, n_samples),
            "Returns": np.random.normal(0.001, 0.02, n_samples),
            "RSI": np.random.uniform(30, 70, n_samples),
            "MACD": np.random.normal(0, 1, n_samples),
            "Signal": np.random.normal(0, 0.5, n_samples),
            "Volatility": np.random.uniform(0.01, 0.05, n_samples),
            "Bogleheads_Sentiment": np.zeros(n_samples),
            "Bogleheads_Regime": np.zeros(n_samples),
            "Bogleheads_Risk": np.full(n_samples, 0.5),
        }
    )

    # Test data with DIFFERENT distribution (higher values)
    test_data = pd.DataFrame(
        {
            "Close": np.random.normal(200, 20, n_samples),  # mean=200, std=20 (different!)
            "Volume": np.random.normal(2000, 200, n_samples),
            "Returns": np.random.normal(0.005, 0.04, n_samples),
            "RSI": np.random.uniform(50, 90, n_samples),
            "MACD": np.random.normal(2, 2, n_samples),
            "Signal": np.random.normal(1, 1, n_samples),
            "Volatility": np.random.uniform(0.03, 0.08, n_samples),
            "Bogleheads_Sentiment": np.zeros(n_samples),
            "Bogleheads_Regime": np.zeros(n_samples),
            "Bogleheads_Risk": np.full(n_samples, 0.5),
        }
    )

    return train_data, test_data


class TestNormalizationLeakagePrevention:
    """Test suite for data leakage prevention in normalization."""

    def test_fit_transform_uses_only_train_stats(self, sample_data):
        """Verify that fit_normalization only uses training data statistics."""
        train_df, test_df = sample_data
        processor = DataProcessor()

        # Fit on training data only
        processor.fit_normalization(train_df)
        params = processor.get_norm_params()

        # Verify parameters match training data (not combined data)
        assert abs(params["Close"]["mean"] - train_df["Close"].mean()) < 1e-10
        assert abs(params["Close"]["std"] - train_df["Close"].std()) < 1e-10

        # Parameters should NOT match combined data
        combined = pd.concat([train_df, test_df])
        assert abs(params["Close"]["mean"] - combined["Close"].mean()) > 1.0

    def test_transform_without_fit_raises_error(self, sample_data):
        """Verify that transform() fails if fit_normalization() not called."""
        train_df, _ = sample_data
        processor = DataProcessor()

        with pytest.raises(ValueError, match="Normalization parameters not fitted"):
            processor.transform(train_df)

    def test_transform_uses_fitted_params(self, sample_data):
        """Verify that transform applies pre-fitted parameters consistently."""
        train_df, test_df = sample_data
        processor = DataProcessor()

        # Fit on training data
        processor.fit_normalization(train_df)

        # Transform both datasets
        train_norm = processor.transform(train_df)
        test_norm = processor.transform(test_df)

        # Training data should be normalized around 0 (since we fit on it)
        assert abs(train_norm["Close"].mean()) < 0.5

        # Test data should NOT be normalized around 0 (different distribution)
        # This is correct behavior - we use train params on test data
        # Test mean is ~200, train mean is ~100, so normalized test should be positive
        assert test_norm["Close"].mean() > 3.0  # Significantly above 0

    def test_deprecated_normalize_data_warns(self, sample_data):
        """Verify that deprecated normalize_data() emits warning."""
        train_df, _ = sample_data
        processor = DataProcessor()

        with pytest.warns(DeprecationWarning, match="data leakage risk"):
            processor.normalize_data(train_df)

    def test_params_persistence(self, sample_data):
        """Verify that normalization params can be saved and restored."""
        train_df, test_df = sample_data

        # Fit processor 1
        processor1 = DataProcessor()
        processor1.fit_normalization(train_df)
        params = processor1.get_norm_params()
        test_norm1 = processor1.transform(test_df)

        # Create new processor and load params
        processor2 = DataProcessor()
        processor2.set_norm_params(params)
        test_norm2 = processor2.transform(test_df)

        # Results should be identical
        pd.testing.assert_frame_equal(test_norm1, test_norm2)

    def test_fit_transform_convenience_method(self, sample_data):
        """Verify fit_transform() works correctly for training data."""
        train_df, _ = sample_data
        processor = DataProcessor()

        # fit_transform should fit and return normalized data
        train_norm = processor.fit_transform(train_df)

        # Should be fitted now
        assert processor._is_fitted

        # Normalized training data should be centered around 0
        assert abs(train_norm["Close"].mean()) < 0.5


class TestLeakageDetection:
    """Tests that demonstrate how leakage would manifest."""

    def test_leakage_scenario_demonstration(self, sample_data):
        """
        Demonstrate what happens with vs without leakage.

        In the LEAKY scenario, we normalize on combined train+test data.
        In the SAFE scenario, we normalize only on train data.

        The difference shows why proper fit/transform matters.
        """
        train_df, test_df = sample_data
        combined = pd.concat([train_df, test_df], ignore_index=True)

        # LEAKY approach (what old normalize_data did on full dataset)
        leaky_processor = DataProcessor()
        leaky_processor.fit_normalization(combined)  # BAD: includes test data!
        leaky_test_norm = leaky_processor.transform(test_df)

        # SAFE approach (fit only on train)
        safe_processor = DataProcessor()
        safe_processor.fit_normalization(train_df)  # GOOD: only train data
        safe_test_norm = safe_processor.transform(test_df)

        # The normalized test data should be DIFFERENT between approaches
        # because the parameters were computed differently
        leaky_mean = leaky_test_norm["Close"].mean()
        safe_mean = safe_test_norm["Close"].mean()

        # They should be meaningfully different (leaky is closer to 0)
        assert abs(leaky_mean - safe_mean) > 1.0, (
            f"Leaky mean: {leaky_mean}, Safe mean: {safe_mean}. "
            "Expected significant difference demonstrating leakage impact."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
