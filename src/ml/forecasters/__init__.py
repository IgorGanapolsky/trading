"""
Forecasters module for time series prediction.

Available forecasters:
- DeepMomentumForecaster: Lightweight NumPy MLP for momentum prediction
- HybridLSTMTransformerForecaster: Advanced LSTM+Transformer hybrid (PyTorch)
"""

from src.ml.forecasters.deep_momentum import DeepMomentumForecaster

# Try to import hybrid forecaster (requires PyTorch)
try:
    from src.ml.forecasters.lstm_transformer import (
        HybridLSTMTransformerForecaster,
        LSTMTransformerForecaster,
    )
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False
    HybridLSTMTransformerForecaster = None
    LSTMTransformerForecaster = None

__all__ = [
    "DeepMomentumForecaster",
    "HybridLSTMTransformerForecaster",
    "LSTMTransformerForecaster",
    "HYBRID_AVAILABLE",
]
