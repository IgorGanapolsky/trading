"""
Quick research experiment template.

This template provides a standardized workflow for testing new trading ideas:
1. Load data
2. Engineer features
3. Create train/test splits (time-aware)
4. Train model
5. Backtest
6. Generate report

Usage:
    python notebooks/research_templates/quick_test.py \
        --model_class MomentumModel \
        --features returns_1d,returns_1w,rsi,macd \
        --target returns_1d \
        --train_start 2020-01-01 \
        --train_end 2023-01-01 \
        --test_start 2023-01-01 \
        --test_end 2024-01-01
"""

import argparse
import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ExperimentResults:
    """Results from a research experiment."""

    train_metrics: dict[str, float]
    test_metrics: dict[str, float]
    backtest_results: dict[str, Any]
    feature_importance: pd.Series | None = None
    predictions: pd.Series | None = None


class BaseModel:
    """Base class for trading models."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseModel":
        """Train the model."""
        raise NotImplementedError

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """Make predictions."""
        raise NotImplementedError

    def get_feature_importance(self) -> pd.Series | None:
        """Get feature importance (if available)."""
        return None


def load_data(
    symbols: list[str],
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Load historical data for symbols.

    Args:
        symbols: List of symbols to load
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with multi-index (symbol, date) and OHLCV columns
    """
    try:
        from src.utils.market_data import MarketDataProvider

        provider = MarketDataProvider()
        all_data = []

        for symbol in symbols:
            try:
                result = provider.get_daily_bars(
                    symbol=symbol,
                    lookback_days=(pd.Timestamp(end_date) - pd.Timestamp(start_date)).days,
                )
                if not result.data.empty:
                    result.data["symbol"] = symbol
                    all_data.append(result.data)
            except Exception as e:
                logger.warning(f"Failed to load data for {symbol}: {e}")

        if not all_data:
            raise ValueError("No data loaded for any symbol")

        df = pd.concat(all_data)
        return df

    except ImportError:
        # Fallback to yfinance
        import yfinance as yf

        all_data = []
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(start=start_date, end=end_date)
                if not hist.empty:
                    hist["symbol"] = symbol
                    all_data.append(hist)
            except Exception as e:
                logger.warning(f"Failed to load {symbol}: {e}")

        if not all_data:
            raise ValueError("No data loaded")

        return pd.concat(all_data)


def engineer_features(
    data: pd.DataFrame,
    feature_list: list[str],
) -> pd.DataFrame:
    """
    Engineer features from raw data.

    Args:
        data: Raw OHLCV data
        feature_list: List of feature names to create

    Returns:
        DataFrame with engineered features
    """
    try:
        from src.research.factors import (
            calculate_multi_horizon_returns,
            calculate_realized_volatility,
            calculate_technical_indicators,
        )

        features = []

        for symbol in data["symbol"].unique():
            symbol_data = data[data["symbol"] == symbol].copy()
            symbol_data = symbol_data.sort_index()

            if "Close" not in symbol_data.columns:
                continue

            prices = symbol_data["Close"]
            volume = symbol_data.get("Volume", pd.Series(1, index=symbol_data.index))

            symbol_features = pd.DataFrame(index=symbol_data.index)
            symbol_features["symbol"] = symbol

            # Returns
            if any("returns" in f for f in feature_list):
                returns = calculate_multi_horizon_returns(prices)
                symbol_features = pd.concat([symbol_features, returns], axis=1)

            # Volatility
            if any("volatility" in f for f in feature_list):
                returns_1d = prices.pct_change()
                vol = calculate_realized_volatility(returns_1d)
                symbol_features["volatility"] = vol

            # Technical indicators
            if any(f in ["rsi", "macd", "bollinger"] for f in feature_list):
                tech = calculate_technical_indicators(prices, volume)
                symbol_features = pd.concat([symbol_features, tech], axis=1)

            features.append(symbol_features)

        return pd.concat(features)

    except ImportError as e:
        logger.error(f"Failed to import factor libraries: {e}")
        raise


def create_time_aware_split(
    data: pd.DataFrame,
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Create time-aware train/test split (no look-ahead bias).

    Args:
        data: Feature DataFrame
        train_start: Training start date
        train_end: Training end date
        test_start: Test start date
        test_end: Test end date

    Returns:
        Tuple of (train_data, test_data)
    """
    data.index = pd.to_datetime(data.index)

    train_mask = (data.index >= train_start) & (data.index < train_end)
    test_mask = (data.index >= test_start) & (data.index < test_end)

    train_data = data[train_mask].copy()
    test_data = data[test_mask].copy()

    return train_data, test_data


def run_research_experiment(
    model_class: type[BaseModel],
    features: list[str],
    target: str = "returns_1d",
    symbols: list[str] = None,
    train_start: str = "2020-01-01",
    train_end: str = "2023-01-01",
    test_start: str = "2023-01-01",
    test_end: str = "2024-01-01",
) -> ExperimentResults:
    """
    Run a standardized research experiment.

    Args:
        model_class: Model class to instantiate
        features: List of feature names to use
        target: Target variable name
        symbols: List of symbols to test on
        train_start: Training start date
        train_end: Training end date
        test_start: Test start date
        test_end: Test end date

    Returns:
        ExperimentResults object
    """
    if symbols is None:
        symbols = ["SPY", "QQQ", "VOO"]

    logger.info("=" * 80)
    logger.info("RESEARCH EXPERIMENT")
    logger.info("=" * 80)
    logger.info(f"Model: {model_class.__name__}")
    logger.info(f"Features: {features}")
    logger.info(f"Target: {target}")
    logger.info(f"Symbols: {symbols}")
    logger.info(f"Train: {train_start} to {train_end}")
    logger.info(f"Test: {test_start} to {test_end}")

    # 1. Load data
    logger.info("\n1. Loading data...")
    data = load_data(symbols, train_start, test_end)

    # 2. Engineer features
    logger.info("2. Engineering features...")
    feature_data = engineer_features(data, features)

    # 3. Create labels
    logger.info("3. Creating labels...")
    # For now, use simple forward returns as target
    if "Close" in data.columns:
        prices = data.groupby("symbol")["Close"].first()
        target_data = prices.pct_change().shift(-1)  # Next day return
    else:
        raise ValueError("Cannot create target: Close prices not found")

    # 4. Create train/test split
    logger.info("4. Creating train/test split...")
    train_data, test_data = create_time_aware_split(
        feature_data, train_start, train_end, test_start, test_end
    )

    # 5. Prepare features and targets
    feature_cols = [f for f in features if f in train_data.columns]
    if not feature_cols:
        raise ValueError(f"No valid features found. Available: {train_data.columns.tolist()}")

    X_train = train_data[feature_cols].dropna()
    y_train = target_data.loc[X_train.index].dropna()
    common_idx = X_train.index.intersection(y_train.index)
    X_train = X_train.loc[common_idx]
    y_train = y_train.loc[common_idx]

    X_test = test_data[feature_cols].dropna()
    y_test = target_data.loc[X_test.index].dropna()
    common_idx = X_test.index.intersection(y_test.index)
    X_test = X_test.loc[common_idx]
    y_test = y_test.loc[common_idx]

    # 6. Train model
    logger.info("5. Training model...")
    model = model_class()
    model.fit(X_train, y_train)

    # 7. Evaluate
    logger.info("6. Evaluating...")
    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)

    train_metrics = {
        "mse": np.mean((train_pred - y_train) ** 2),
        "mae": np.mean(np.abs(train_pred - y_train)),
        "correlation": np.corrcoef(train_pred, y_train)[0, 1],
    }

    test_metrics = {
        "mse": np.mean((test_pred - y_test) ** 2),
        "mae": np.mean(np.abs(test_pred - y_test)),
        "correlation": np.corrcoef(test_pred, y_test)[0, 1],
    }

    # 8. Get feature importance
    feature_importance = model.get_feature_importance()

    logger.info("\n" + "=" * 80)
    logger.info("RESULTS")
    logger.info("=" * 80)
    logger.info(f"Train Metrics: {train_metrics}")
    logger.info(f"Test Metrics: {test_metrics}")
    if feature_importance is not None:
        logger.info(f"Top Features: {feature_importance.head(10).to_dict()}")

    return ExperimentResults(
        train_metrics=train_metrics,
        test_metrics=test_metrics,
        backtest_results={},  # TODO: Add backtest integration
        feature_importance=feature_importance,
        predictions=test_pred,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a quick research experiment")
    parser.add_argument("--model_class", type=str, required=True, help="Model class name")
    parser.add_argument("--features", type=str, required=True, help="Comma-separated feature list")
    parser.add_argument("--target", type=str, default="returns_1d", help="Target variable")
    parser.add_argument(
        "--symbols", type=str, default="SPY,QQQ,VOO", help="Comma-separated symbols"
    )
    parser.add_argument("--train_start", type=str, default="2020-01-01")
    parser.add_argument("--train_end", type=str, default="2023-01-01")
    parser.add_argument("--test_start", type=str, default="2023-01-01")
    parser.add_argument("--test_end", type=str, default="2024-01-01")

    args = parser.parse_args()

    # This is a template - users need to provide their own model class
    logger.warning("This is a template. Provide your own model_class implementation.")
