import logging

import numpy as np
import pandas as pd
import torch
import yfinance as yf

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Handles data fetching, feature engineering, and preprocessing for the ML model.

    IMPORTANT: To prevent data leakage, normalization follows a fit/transform pattern:
    1. Call fit_normalization() on TRAINING data only
    2. Call transform() on both training and test data
    3. Parameters are stored and reused for inference

    See: https://www.kdnuggets.com/5-critical-feature-engineering-mistakes-that-kill-machine-learning-projects
    """

    def __init__(self, sequence_length: int = 60, feature_columns: list[str] = None):
        self.sequence_length = sequence_length
        self.feature_columns = feature_columns or [
            "Close",
            "Volume",
            "Returns",
            "RSI",
            "MACD",
            "Signal",
            "Volatility",
            "Bogleheads_Sentiment",
            "Bogleheads_Regime",
            "Bogleheads_Risk",  # Bogleheads features
        ]
        self.scalers = {}  # Store scalers per symbol if needed
        # Normalization parameters (fit on train data only to prevent leakage)
        self._norm_params: dict[str, dict[str, float]] = {}
        self._is_fitted = False

    def fetch_data(self, symbol: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
        """Fetch historical data using yfinance."""
        try:
            df = yf.download(symbol, period=period, interval=interval, progress=False)
            if df.empty:
                logger.warning(f"No data found for {symbol}")
                return df
            return df
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to the DataFrame."""
        if df.empty:
            return df

        df = df.copy()

        # Ensure we are working with single-level columns if MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 1. Returns
        df["Returns"] = df["Close"].pct_change()

        # 2. RSI (14)
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # 3. MACD (12, 26, 9)
        exp1 = df["Close"].ewm(span=12, adjust=False).mean()
        exp2 = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = exp1 - exp2
        df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

        # 4. Volatility (20-day rolling std dev)
        df["Volatility"] = df["Returns"].rolling(window=20).std()

        # 5. Volume Change
        df["Volume_Change"] = df["Volume"].pct_change()

        # 6. Add Bogleheads features if available (optional)
        # Always ensure these columns exist, even if Bogleheads integration fails
        bogleheads_added = False
        try:
            from src.utils.bogleheads_integration import (
                get_bogleheads_regime,
                get_bogleheads_signal_for_symbol,
            )

            signal = get_bogleheads_signal_for_symbol("SPY")  # Use SPY as market proxy
            regime = get_bogleheads_regime()

            df["Bogleheads_Sentiment"] = signal.get("score", 0.0) / 100.0
            df["Bogleheads_Regime"] = {
                "bull": 1.0,
                "bear": -1.0,
                "choppy": 0.0,
                "uncertain": 0.0,
            }.get(regime.get("regime", "unknown"), 0.0)
            df["Bogleheads_Risk"] = {"low": 0.0, "medium": 0.5, "high": 1.0}.get(
                regime.get("risk_level", "medium"), 0.5
            )
            bogleheads_added = True
        except Exception as e:
            logger.debug(f"Could not add Bogleheads features: {e}")

        # Always ensure Bogleheads features exist (fill with defaults if not added)
        if not bogleheads_added or "Bogleheads_Sentiment" not in df.columns:
            df["Bogleheads_Sentiment"] = 0.0
            df["Bogleheads_Regime"] = 0.0
            df["Bogleheads_Risk"] = 0.5

        # Fill NaNs
        df.fillna(0, inplace=True)

        return df

    def fit_normalization(self, df: pd.DataFrame) -> "DataProcessor":
        """
        Fit normalization parameters on TRAINING data only.

        This prevents data leakage by ensuring test/validation data statistics
        don't influence the normalization parameters.

        Args:
            df: Training DataFrame (must NOT include test/validation data)

        Returns:
            self for method chaining
        """
        self._norm_params = {}

        for col in self.feature_columns:
            if col in df.columns:
                mean = float(df[col].mean())
                std = float(df[col].std())
                self._norm_params[col] = {"mean": mean, "std": std if std != 0 else 1.0}

        self._is_fitted = True
        logger.debug(f"Fitted normalization on {len(df)} training samples")
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply normalization using pre-fitted parameters.

        Args:
            df: DataFrame to normalize (can be train, test, or inference data)

        Returns:
            Normalized DataFrame

        Raises:
            ValueError: If fit_normalization() hasn't been called
        """
        if not self._is_fitted:
            raise ValueError(
                "Normalization parameters not fitted. Call fit_normalization() on training data first. "
                "This prevents data leakage from test data."
            )

        df_norm = df.copy()

        for col in self.feature_columns:
            if col in df_norm.columns and col in self._norm_params:
                params = self._norm_params[col]
                df_norm[col] = (df_norm[col] - params["mean"]) / params["std"]
            elif col in df_norm.columns:
                # Column exists but no params - set to 0 (safe default)
                df_norm[col] = 0.0

        return df_norm

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convenience method: fit on data and transform it.

        WARNING: Only use this on training data! For test/validation data,
        use transform() with parameters fitted on training data.

        Args:
            df: Training DataFrame

        Returns:
            Normalized training DataFrame
        """
        return self.fit_normalization(df).transform(df)

    def normalize_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        DEPRECATED: Use fit_normalization() + transform() to prevent data leakage.

        This method is kept for backward compatibility but will fit and transform
        in one step, which can cause leakage if used on combined train+test data.

        For proper usage:
            # Training phase
            processor.fit_normalization(train_df)
            train_normalized = processor.transform(train_df)
            test_normalized = processor.transform(test_df)

            # Inference phase
            inference_normalized = processor.transform(new_data)
        """
        import warnings

        warnings.warn(
            "normalize_data() is deprecated due to data leakage risk. "
            "Use fit_normalization(train_df) then transform(df) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.fit_transform(df)

    def get_norm_params(self) -> dict[str, dict[str, float]]:
        """Get fitted normalization parameters for persistence."""
        if not self._is_fitted:
            raise ValueError("Not fitted yet. Call fit_normalization() first.")
        return self._norm_params.copy()

    def set_norm_params(self, params: dict[str, dict[str, float]]) -> "DataProcessor":
        """
        Set normalization parameters from saved state.

        Useful for loading parameters fitted during training for inference.

        Args:
            params: Dictionary of {column: {mean, std}} parameters

        Returns:
            self for method chaining
        """
        self._norm_params = params.copy()
        self._is_fitted = True
        return self

    def create_sequences(self, df: pd.DataFrame) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Create sequences for LSTM input.

        Returns:
            X: Tensor of shape (num_samples, sequence_length, num_features)
            y: Tensor of shape (num_samples,) - Target (next day return direction: 0=Hold/Sell, 1=Buy)
               Note: This is a simplified target for pre-training/supervised check.
               For PPO RL, we use the environment interaction, not static targets.
        """
        data = df[self.feature_columns].values

        X = []

        # We need at least sequence_length rows
        if len(data) <= self.sequence_length:
            return torch.tensor([]), torch.tensor([])

        for i in range(len(data) - self.sequence_length):
            X.append(data[i : i + self.sequence_length])

        return torch.FloatTensor(np.array(X))

    def prepare_inference_data(self, symbol: str) -> torch.Tensor | None:
        """
        Prepare the latest sequence for inference.
        Includes Bogleheads features if available.

        NOTE: For proper inference, normalization parameters should be pre-fitted
        on training data using fit_normalization() or set_norm_params().
        If not fitted, this will fit on the inference data (not ideal but functional).
        """
        df = self.fetch_data(symbol, period="6mo")  # Fetch enough for indicators + sequence
        if df.empty:
            return None

        df = self.add_technical_indicators(df)

        # Add Bogleheads features if available
        try:
            from src.utils.bogleheads_integration import (
                get_bogleheads_regime,
                get_bogleheads_signal_for_symbol,
            )

            signal = get_bogleheads_signal_for_symbol(symbol)
            regime = get_bogleheads_regime()

            # Add Bogleheads features to all rows (use current values)
            df["Bogleheads_Sentiment"] = signal.get("score", 0.0) / 100.0  # Normalize to -1 to 1
            df["Bogleheads_Regime"] = {
                "bull": 1.0,
                "bear": -1.0,
                "choppy": 0.0,
                "uncertain": 0.0,
            }.get(regime.get("regime", "unknown"), 0.0)
            df["Bogleheads_Risk"] = {"low": 0.0, "medium": 0.5, "high": 1.0}.get(
                regime.get("risk_level", "medium"), 0.5
            )
        except Exception as e:
            logger.debug(f"Could not add Bogleheads features: {e}")
            # Fill with zeros if unavailable
            df["Bogleheads_Sentiment"] = 0.0
            df["Bogleheads_Regime"] = 0.0
            df["Bogleheads_Risk"] = 0.5

        # Apply normalization using fitted parameters
        # If not fitted, fit on this data (logs a warning for awareness)
        if not self._is_fitted:
            logger.warning(
                "Normalizing inference data without pre-fitted parameters. "
                "For production, load parameters fitted on training data."
            )
            df = self.fit_transform(df)
        else:
            df = self.transform(df)

        # Get the last sequence_length rows
        if len(df) < self.sequence_length:
            logger.warning(f"Not enough data for {symbol} inference")
            return None

        # Ensure all feature columns exist
        for col in self.feature_columns:
            if col not in df.columns:
                df[col] = 0.0

        last_sequence = df[self.feature_columns].iloc[-self.sequence_length :].values

        # Add batch dimension: (1, seq_len, features)
        return torch.FloatTensor(last_sequence).unsqueeze(0)
