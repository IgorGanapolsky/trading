"""
Unit tests for HybridLSTMTransformerForecaster.
"""

import numpy as np
import pandas as pd
import pytest
from pathlib import Path
import tempfile
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.forecasters.lstm_transformer import (
    HybridLSTMTransformerForecaster,
    TORCH_AVAILABLE,
)


def create_sample_ohlcv(n_days: int = 100) -> pd.DataFrame:
    """Create sample OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_days, freq="D")

    # Generate realistic price movements
    returns = np.random.normal(0.0005, 0.02, n_days)
    close = 100 * np.exp(np.cumsum(returns))

    # Generate OHLCV
    high = close * (1 + np.abs(np.random.normal(0, 0.01, n_days)))
    low = close * (1 - np.abs(np.random.normal(0, 0.01, n_days)))
    open_ = close * (1 + np.random.normal(0, 0.005, n_days))
    volume = np.random.randint(1000000, 10000000, n_days)

    return pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    }, index=dates)


class TestHybridForecasterBasic:
    """Basic functionality tests."""

    def test_initialization(self):
        """Test forecaster initializes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"
            forecaster = HybridLSTMTransformerForecaster(
                lookback=30,
                hidden_dim=32,
                model_path=model_path,
            )

            assert forecaster.lookback == 30
            assert forecaster.hidden_dim == 32
            assert not forecaster._trained_once

    def test_get_model_info(self):
        """Test model info returns correct data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"
            forecaster = HybridLSTMTransformerForecaster(model_path=model_path)

            info = forecaster.get_model_info()

            assert info["type"] == "HybridLSTMTransformerForecaster"
            assert info["backend"] in ["pytorch", "numpy"]
            assert "lookback" in info
            assert "hidden_dim" in info


class TestHybridForecasterPrediction:
    """Prediction tests."""

    def test_predict_with_valid_data(self):
        """Test prediction with valid OHLCV data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"
            forecaster = HybridLSTMTransformerForecaster(
                lookback=30,
                hidden_dim=32,
                epochs=5,  # Fast training for tests
                model_path=model_path,
            )

            hist = create_sample_ohlcv(100)
            prob = forecaster.predict_probability("TEST", hist)

            # Probability should be between 0 and 1
            assert 0.0 <= prob <= 1.0

    def test_predict_with_insufficient_data(self):
        """Test prediction returns 0.5 with insufficient data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"
            forecaster = HybridLSTMTransformerForecaster(model_path=model_path)

            # Only 10 days of data (insufficient)
            hist = create_sample_ohlcv(10)
            prob = forecaster.predict_probability("TEST", hist)

            # Should return default probability
            assert prob == 0.5

    def test_predict_with_empty_data(self):
        """Test prediction handles empty data gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"
            forecaster = HybridLSTMTransformerForecaster(model_path=model_path)

            prob = forecaster.predict_probability("TEST", pd.DataFrame())
            assert prob == 0.5

    def test_predict_with_none_data(self):
        """Test prediction handles None data gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"
            forecaster = HybridLSTMTransformerForecaster(model_path=model_path)

            prob = forecaster.predict_probability("TEST", None)
            assert prob == 0.5


class TestHybridForecasterFeatures:
    """Feature engineering tests."""

    def test_build_dataset_features(self):
        """Test that dataset has correct number of features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"
            forecaster = HybridLSTMTransformerForecaster(model_path=model_path)

            hist = create_sample_ohlcv(100)
            X, y = forecaster._build_dataset(hist)

            # Should have 8 features
            assert X.shape[1] == 8
            # Target should be same length as features
            assert len(X) == len(y)
            # Target should be binary (0 or 1)
            assert set(np.unique(y)).issubset({0.0, 1.0})

    def test_no_nan_in_features(self):
        """Test that features have no NaN values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"
            forecaster = HybridLSTMTransformerForecaster(model_path=model_path)

            hist = create_sample_ohlcv(100)
            X, y = forecaster._build_dataset(hist)

            assert not np.isnan(X).any()
            assert not np.isnan(y).any()


class TestHybridForecasterTraining:
    """Training tests."""

    def test_training_updates_model(self):
        """Test that training updates the model state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"
            forecaster = HybridLSTMTransformerForecaster(
                lookback=30,
                hidden_dim=32,
                epochs=5,
                model_path=model_path,
            )

            hist = create_sample_ohlcv(100)

            # First prediction should trigger training
            assert not forecaster._trained_once
            _ = forecaster.predict_probability("TEST", hist)
            assert forecaster._trained_once

    def test_model_persistence(self):
        """Test that model can be saved and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.pt"

            # Train and save
            forecaster1 = HybridLSTMTransformerForecaster(
                lookback=30,
                hidden_dim=32,
                epochs=5,
                model_path=model_path,
            )
            hist = create_sample_ohlcv(100)
            prob1 = forecaster1.predict_probability("TEST", hist)

            # Check model was saved
            if forecaster1._use_torch:
                assert model_path.exists()

            # Load in new instance
            forecaster2 = HybridLSTMTransformerForecaster(
                lookback=30,
                hidden_dim=32,
                model_path=model_path,
            )

            # Should be loaded as trained
            if forecaster2._use_torch and model_path.exists():
                assert forecaster2._trained_once


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not available")
class TestPyTorchSpecific:
    """PyTorch-specific tests."""

    def test_model_architecture(self):
        """Test model has correct architecture components."""
        from src.ml.forecasters.lstm_transformer import LSTMTransformerHybrid

        model = LSTMTransformerHybrid(
            input_dim=8,
            hidden_dim=64,
            lstm_layers=2,
            transformer_heads=4,
            transformer_layers=2,
        )

        # Check components exist
        assert hasattr(model, "lstm")
        assert hasattr(model, "transformer")
        assert hasattr(model, "fusion")
        assert hasattr(model, "output_head")

    def test_forward_pass_shape(self):
        """Test forward pass produces correct output shape."""
        import torch
        from src.ml.forecasters.lstm_transformer import LSTMTransformerHybrid

        model = LSTMTransformerHybrid(input_dim=8, hidden_dim=64)

        batch_size = 4
        seq_len = 20
        x = torch.randn(batch_size, seq_len, 8)

        output = model(x)

        assert output.shape == (batch_size, 1)
        assert (output >= 0).all() and (output <= 1).all()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
