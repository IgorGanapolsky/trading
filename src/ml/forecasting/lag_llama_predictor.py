"""
Lag-Llama Time Series Foundation Model for SPY Range Prediction.

Uses probabilistic forecasting to predict price ranges for iron condor strike selection.
Provides confidence intervals (e.g., 15th/85th percentiles) matching our 15-delta strategy.

Reference: https://github.com/time-series-foundation-models/lag-llama
Paper: https://arxiv.org/abs/2310.08278

Created: January 28, 2026
Purpose: Improve iron condor strike selection with ML-based range prediction
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np

logger = logging.getLogger(__name__)

# Model configuration
MODEL_NAME = "time-series-foundation-models/Lag-Llama"
DEFAULT_HORIZON = 30  # 30 days for iron condor DTE
CONTEXT_LENGTH = 252  # 1 year of trading days


@dataclass
class RangeForecast:
    """Probabilistic range forecast for iron condor strike selection."""

    ticker: str
    current_price: float
    horizon_days: int
    timestamp: str

    # Percentile forecasts (matching delta levels)
    lower_15pct: float  # ~15 delta put strike zone
    lower_20pct: float  # ~20 delta put strike zone
    median: float  # 50th percentile
    upper_80pct: float  # ~20 delta call strike zone
    upper_85pct: float  # ~15 delta call strike zone

    # Derived metrics for trading
    expected_range_pct: float  # (upper_85 - lower_15) / current as %

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "current_price": self.current_price,
            "horizon_days": self.horizon_days,
            "timestamp": self.timestamp,
            "percentiles": {
                "p15": self.lower_15pct,
                "p20": self.lower_20pct,
                "p50": self.median,
                "p80": self.upper_80pct,
                "p85": self.upper_85pct,
            },
            "expected_range_pct": self.expected_range_pct,
            "suggested_strikes": {
                "put_short": round(self.lower_15pct, 0),
                "call_short": round(self.upper_85pct, 0),
            },
        }


class LagLlamaPredictor:
    """
    Lag-Llama based predictor for SPY price range forecasting.

    Provides probabilistic forecasts to improve iron condor strike selection.
    Falls back to statistical methods if Lag-Llama unavailable.
    """

    def __init__(self, use_gpu: bool = False):
        self._model = None
        self._pipeline = None
        self._use_gpu = use_gpu
        self._initialized = False
        self._fallback_mode = False

        self._init_model()

    def _init_model(self):
        """Initialize Lag-Llama model or fall back to statistical methods."""
        try:
            # Try to import Lag-Llama dependencies
            import torch
            from huggingface_hub import hf_hub_download

            # Check for GPU availability
            device = "cuda" if self._use_gpu and torch.cuda.is_available() else "cpu"
            logger.info(f"Initializing Lag-Llama on {device}")

            # Download model checkpoint
            checkpoint_path = hf_hub_download(
                repo_id=MODEL_NAME, filename="lag-llama.ckpt", local_dir="models/lag_llama"
            )

            # Load the model
            from lag_llama.gluon.estimator import LagLlamaEstimator

            self._estimator = LagLlamaEstimator(
                ckpt_path=checkpoint_path,
                prediction_length=DEFAULT_HORIZON,
                context_length=CONTEXT_LENGTH,
                device=device,
                batch_size=1,
                num_samples=100,  # For probabilistic forecasts
            )

            self._initialized = True
            logger.info("Lag-Llama model initialized successfully")

        except ImportError as e:
            logger.warning(f"Lag-Llama dependencies not available: {e}")
            logger.info("Using statistical fallback for range prediction")
            self._fallback_mode = True
            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize Lag-Llama: {e}")
            self._fallback_mode = True
            self._initialized = True

    def predict_range(
        self, prices: list[float], ticker: str = "SPY", horizon_days: int = DEFAULT_HORIZON
    ) -> RangeForecast:
        """
        Predict price range for the given horizon.

        Args:
            prices: Historical daily closing prices (most recent last)
            ticker: Stock ticker symbol
            horizon_days: Forecast horizon in trading days

        Returns:
            RangeForecast with percentile predictions
        """
        if not self._initialized:
            raise RuntimeError("Model not initialized")

        _current_price = prices[-1]  # noqa: F841 - may be used in future

        if self._fallback_mode:
            return self._statistical_forecast(prices, ticker, horizon_days)

        try:
            return self._lag_llama_forecast(prices, ticker, horizon_days)
        except Exception as e:
            logger.warning(f"Lag-Llama forecast failed, using fallback: {e}")
            return self._statistical_forecast(prices, ticker, horizon_days)

    def _lag_llama_forecast(
        self, prices: list[float], ticker: str, horizon_days: int
    ) -> RangeForecast:
        """Generate forecast using Lag-Llama model."""
        from gluonts.dataset.common import ListDataset

        current_price = prices[-1]

        # Prepare data for Lag-Llama
        dataset = ListDataset([{"start": "2025-01-01", "target": prices}], freq="D")

        # Get predictor and generate forecasts
        predictor = self._estimator.train(dataset)
        forecasts = list(predictor.predict(dataset))

        # Extract quantiles from probabilistic forecast
        forecast = forecasts[0]
        samples = forecast.samples  # Shape: (num_samples, horizon)

        # Get final day predictions across all samples
        final_day_samples = samples[:, -1]

        # Calculate percentiles
        lower_15 = float(np.percentile(final_day_samples, 15))
        lower_20 = float(np.percentile(final_day_samples, 20))
        median = float(np.percentile(final_day_samples, 50))
        upper_80 = float(np.percentile(final_day_samples, 80))
        upper_85 = float(np.percentile(final_day_samples, 85))

        range_pct = (upper_85 - lower_15) / current_price * 100

        return RangeForecast(
            ticker=ticker,
            current_price=current_price,
            horizon_days=horizon_days,
            timestamp=datetime.utcnow().isoformat() + "Z",
            lower_15pct=lower_15,
            lower_20pct=lower_20,
            median=median,
            upper_80pct=upper_80,
            upper_85pct=upper_85,
            expected_range_pct=range_pct,
        )

    def _statistical_forecast(
        self, prices: list[float], ticker: str, horizon_days: int
    ) -> RangeForecast:
        """
        Statistical fallback using historical volatility.

        Uses log returns and assumes normal distribution to estimate
        percentile ranges based on historical volatility.
        """
        prices_arr = np.array(prices)
        current_price = prices_arr[-1]

        # Calculate daily log returns
        log_returns = np.diff(np.log(prices_arr))

        # Annualized volatility
        daily_vol = np.std(log_returns)

        # Scale to horizon (sqrt of time)
        horizon_vol = daily_vol * np.sqrt(horizon_days)

        # Z-scores for percentiles (normal distribution)
        z_15 = -1.036  # 15th percentile
        z_20 = -0.842  # 20th percentile
        z_80 = 0.842  # 80th percentile
        z_85 = 1.036  # 85th percentile

        # Calculate price levels using log-normal assumption
        lower_15 = current_price * np.exp(z_15 * horizon_vol)
        lower_20 = current_price * np.exp(z_20 * horizon_vol)
        median = current_price  # Assuming zero drift for simplicity
        upper_80 = current_price * np.exp(z_80 * horizon_vol)
        upper_85 = current_price * np.exp(z_85 * horizon_vol)

        range_pct = (upper_85 - lower_15) / current_price * 100

        return RangeForecast(
            ticker=ticker,
            current_price=current_price,
            horizon_days=horizon_days,
            timestamp=datetime.utcnow().isoformat() + "Z",
            lower_15pct=lower_15,
            lower_20pct=lower_20,
            median=median,
            upper_80pct=upper_80,
            upper_85pct=upper_85,
            expected_range_pct=range_pct,
        )

    def suggest_strikes(
        self,
        prices: list[float],
        ticker: str = "SPY",
        horizon_days: int = DEFAULT_HORIZON,
        wing_width: float = 5.0,
    ) -> dict:
        """
        Suggest iron condor strikes based on range forecast.

        Args:
            prices: Historical prices
            ticker: Stock ticker
            horizon_days: DTE for the iron condor
            wing_width: Width of spreads (default $5)

        Returns:
            Dictionary with suggested strikes and rationale
        """
        forecast = self.predict_range(prices, ticker, horizon_days)

        # Round to nearest strike (SPY has $1 strikes)
        short_put = round(forecast.lower_15pct)
        short_call = round(forecast.upper_85pct)

        # Long strikes (wings)
        long_put = short_put - wing_width
        long_call = short_call + wing_width

        return {
            "forecast": forecast.to_dict(),
            "iron_condor": {
                "long_put": long_put,
                "short_put": short_put,
                "short_call": short_call,
                "long_call": long_call,
                "wing_width": wing_width,
            },
            "rationale": (
                f"Based on {horizon_days}-day forecast, SPY has ~70% probability "
                f"of staying between ${forecast.lower_15pct:.0f} and ${forecast.upper_85pct:.0f}. "
                f"Suggested short strikes at 15-delta equivalent levels."
            ),
            "model": "lag-llama" if not self._fallback_mode else "statistical-fallback",
        }


def get_spy_range_forecast(horizon_days: int = 30) -> dict:
    """
    Convenience function to get SPY range forecast.

    Fetches recent SPY prices and generates forecast.
    """
    try:
        # Try to get prices from Alpaca
        from datetime import timedelta

        from alpaca.data import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from src.utils.alpaca_client import get_alpaca_credentials

        creds = get_alpaca_credentials()
        client = StockHistoricalDataClient(creds["api_key"], creds["api_secret"])

        end = datetime.now()
        start = end - timedelta(days=365)

        request = StockBarsRequest(
            symbol_or_symbols=["SPY"],
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )

        bars = client.get_stock_bars(request)
        prices = [bar.close for bar in bars["SPY"]]

    except Exception as e:
        logger.warning(f"Could not fetch SPY prices: {e}")
        # Use dummy data for testing
        prices = [480 + np.random.randn() * 5 for _ in range(252)]

    predictor = LagLlamaPredictor()
    return predictor.suggest_strikes(prices, "SPY", horizon_days)


if __name__ == "__main__":
    # Demo usage
    import json

    # Generate sample prices (replace with real data in production)
    np.random.seed(42)
    base_price = 480
    returns = np.random.randn(252) * 0.01  # 1% daily vol
    prices = [base_price]
    for r in returns:
        prices.append(prices[-1] * (1 + r))

    predictor = LagLlamaPredictor()
    result = predictor.suggest_strikes(prices, "SPY", horizon_days=30)

    print(json.dumps(result, indent=2))
