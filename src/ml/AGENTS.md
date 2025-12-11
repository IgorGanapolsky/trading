# ML Module - Agent Instructions

> Machine learning models for trading predictions and analysis.

## Purpose

Contains ML/AI components:
- Price forecasting models
- Sentiment analysis
- Feature engineering
- Model training and evaluation

## Current Models

| Model | Purpose | Status |
|-------|---------|--------|
| LSTM Forecaster | Price prediction | R&D |
| Sentiment Analyzer | News/social sentiment | Active |
| Feature Generator | Technical indicators | Active |
| RL Agent | Trade decision making | R&D |

## Directory Structure

```
ml/
├── forecasters/       # Price prediction models
├── sentiment/         # Sentiment analysis
├── features/          # Feature engineering
├── training/          # Training pipelines
└── evaluation/        # Model evaluation
```

## Model Requirements

Before deploying any model:
1. **Walk-forward validation** (not random split)
2. **Out-of-sample testing** on 6+ months data
3. **Feature importance analysis**
4. **Drift detection** monitoring
5. **Latency requirements** met (< 100ms inference)

## Code Standards

### Data Handling

```python
import pandas as pd
from typing import Tuple

def prepare_features(
    df: pd.DataFrame,
    lookback: int = 20
) -> Tuple[pd.DataFrame, pd.Series]:
    """Prepare features for model training.

    Args:
        df: Raw OHLCV data
        lookback: Lookback period for features

    Returns:
        Tuple of (features DataFrame, target Series)

    Note:
        - Never use future data (look-ahead bias)
        - Handle missing values explicitly
        - Scale features appropriately
    """
    # Drop last row to prevent look-ahead bias
    df = df.iloc[:-1].copy()

    # Generate features
    features = pd.DataFrame(index=df.index)
    features['returns'] = df['close'].pct_change()
    features['volatility'] = features['returns'].rolling(lookback).std()

    # Target is next-day return
    target = df['close'].pct_change().shift(-1)

    # Drop NaN rows
    valid_idx = features.dropna().index.intersection(target.dropna().index)

    return features.loc[valid_idx], target.loc[valid_idx]
```

### Model Interface

```python
from abc import ABC, abstractmethod
import numpy as np

class BasePredictor(ABC):
    """Base class for ML predictors."""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Train the model."""
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate predictions."""
        pass

    @abstractmethod
    def get_feature_importance(self) -> dict:
        """Return feature importance scores."""
        pass
```

## Testing

```bash
pytest tests/unit/ml/ -v
pytest tests/ml/test_forecasters.py -v
```

## Warnings

- **Never overfit** - Use proper cross-validation
- **Monitor drift** - Models degrade over time
- **Log predictions** - Full audit trail for debugging
- **Version models** - Track which model made each prediction
