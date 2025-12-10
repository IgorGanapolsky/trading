"""
Alpha Information Coefficient (IC) Analysis

Measures the correlation between trading signals/predictions and actual returns.
This is the gold standard for quantifying whether a model has real predictive edge.

Key Metrics:
- IC (Information Coefficient): Correlation between signal and future returns
- IR (Information Ratio): IC / std(IC) - consistency of signal
- IC Decay: How quickly signal's predictive power decays over time

Interpretation:
- IC > 0.05: Weak but potentially useful signal
- IC > 0.10: Moderate signal strength
- IC > 0.15: Strong signal (rare in liquid markets)
- IC < 0.02: No edge - likely random

Warning Signs:
- IC varies wildly across time = unstable model
- IC drops sharply at longer horizons = short-term noise, not alpha
- IC negative = model is anti-predictive (reverse the signal!)

Author: Trading System
Created: 2025-12-10
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class AlphaICReport:
    """Report containing alpha IC analysis results."""

    timestamp: str
    symbol: str
    signal_name: str
    horizons: list[int]  # Return horizons in bars

    # Core metrics
    ic_values: dict[int, float]  # horizon -> IC
    ic_pvalues: dict[int, float]  # horizon -> p-value
    ir_values: dict[int, float]  # horizon -> IR

    # Summary
    mean_ic: float
    max_ic: float
    best_horizon: int
    has_edge: bool

    # Diagnostics
    ic_stability: float  # std of rolling IC
    ic_decay_rate: float  # how fast IC drops with horizon
    warnings: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "signal_name": self.signal_name,
            "horizons": self.horizons,
            "ic_values": self.ic_values,
            "ic_pvalues": self.ic_pvalues,
            "ir_values": self.ir_values,
            "mean_ic": self.mean_ic,
            "max_ic": self.max_ic,
            "best_horizon": self.best_horizon,
            "has_edge": self.has_edge,
            "ic_stability": self.ic_stability,
            "ic_decay_rate": self.ic_decay_rate,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
        }

    def save(self, filepath: Path) -> None:
        """Save report to JSON."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Alpha IC report saved to {filepath}")


class AlphaICAnalyzer:
    """
    Analyzes the predictive power of trading signals using Information Coefficient.

    Usage:
        analyzer = AlphaICAnalyzer()
        report = analyzer.analyze(
            signals=model_predictions,
            returns=actual_returns,
            horizons=[1, 5, 20]
        )
    """

    # IC interpretation thresholds
    IC_THRESHOLD_WEAK = 0.02
    IC_THRESHOLD_MODERATE = 0.05
    IC_THRESHOLD_STRONG = 0.10

    def __init__(
        self,
        min_samples: int = 100,
        rolling_window: int = 63,  # ~3 months for daily data
    ):
        """
        Initialize the analyzer.

        Args:
            min_samples: Minimum samples required for valid analysis
            rolling_window: Window size for rolling IC calculation
        """
        self.min_samples = min_samples
        self.rolling_window = rolling_window

    def calculate_ic(
        self,
        signals: np.ndarray,
        returns: np.ndarray,
    ) -> tuple[float, float]:
        """
        Calculate Spearman rank correlation (IC) between signals and returns.

        Uses Spearman (rank correlation) rather than Pearson because:
        - More robust to outliers
        - Doesn't assume linear relationship
        - Standard in quant finance

        Args:
            signals: Array of signal values
            returns: Array of corresponding forward returns

        Returns:
            Tuple of (IC value, p-value)
        """
        # Remove NaN values
        mask = ~(np.isnan(signals) | np.isnan(returns))
        signals_clean = signals[mask]
        returns_clean = returns[mask]

        if len(signals_clean) < self.min_samples:
            logger.warning(f"Insufficient samples: {len(signals_clean)} < {self.min_samples}")
            return 0.0, 1.0

        # Spearman rank correlation
        ic, pvalue = stats.spearmanr(signals_clean, returns_clean)

        return float(ic), float(pvalue)

    def calculate_ir(
        self,
        signals: np.ndarray,
        returns: np.ndarray,
    ) -> float:
        """
        Calculate Information Ratio (IC / std(IC)).

        Higher IR = more consistent signal.

        Args:
            signals: Array of signal values
            returns: Array of corresponding forward returns

        Returns:
            Information Ratio
        """
        # Calculate rolling ICs
        rolling_ics = []

        for i in range(self.rolling_window, len(signals)):
            window_signals = signals[i - self.rolling_window:i]
            window_returns = returns[i - self.rolling_window:i]

            ic, _ = self.calculate_ic(window_signals, window_returns)
            rolling_ics.append(ic)

        if not rolling_ics or np.std(rolling_ics) == 0:
            return 0.0

        mean_ic = np.mean(rolling_ics)
        std_ic = np.std(rolling_ics)

        ir = mean_ic / std_ic if std_ic > 0 else 0.0
        return float(ir)

    def calculate_forward_returns(
        self,
        prices: np.ndarray,
        horizon: int,
    ) -> np.ndarray:
        """
        Calculate forward returns for a given horizon.

        Args:
            prices: Price series
            horizon: Number of periods forward

        Returns:
            Array of forward returns (NaN padded at end)
        """
        forward_prices = np.roll(prices, -horizon)
        forward_prices[-horizon:] = np.nan

        returns = (forward_prices - prices) / prices
        return returns

    def analyze(
        self,
        signals: np.ndarray,
        prices: np.ndarray,
        horizons: list[int] = None,
        signal_name: str = "model_signal",
        symbol: str = "UNKNOWN",
    ) -> AlphaICReport:
        """
        Run full alpha IC analysis across multiple horizons.

        Args:
            signals: Array of signal/prediction values
            prices: Array of price values (to calculate returns)
            horizons: List of forward return horizons to test
            signal_name: Name of the signal being analyzed
            symbol: Symbol being analyzed

        Returns:
            AlphaICReport with comprehensive analysis
        """
        if horizons is None:
            horizons = [1, 5, 10, 20, 60]  # 1d, 1w, 2w, 1m, 3m

        logger.info(f"Analyzing alpha IC for {signal_name} on {symbol}")
        logger.info(f"Horizons: {horizons}, Samples: {len(signals)}")

        ic_values = {}
        ic_pvalues = {}
        ir_values = {}

        for horizon in horizons:
            # Calculate forward returns
            forward_returns = self.calculate_forward_returns(prices, horizon)

            # Calculate IC
            ic, pvalue = self.calculate_ic(signals, forward_returns)
            ic_values[horizon] = ic
            ic_pvalues[horizon] = pvalue

            # Calculate IR
            ir = self.calculate_ir(signals, forward_returns)
            ir_values[horizon] = ir

            logger.info(f"  Horizon {horizon}: IC={ic:.4f} (p={pvalue:.4f}), IR={ir:.2f}")

        # Summary statistics
        mean_ic = np.mean(list(ic_values.values()))
        max_ic = max(ic_values.values())
        best_horizon = max(ic_values, key=ic_values.get)

        # Determine if we have edge
        has_edge = max_ic >= self.IC_THRESHOLD_WEAK

        # Calculate IC stability (std of rolling IC at best horizon)
        best_returns = self.calculate_forward_returns(prices, best_horizon)
        rolling_ics = self._calculate_rolling_ic(signals, best_returns)
        ic_stability = float(np.std(rolling_ics)) if rolling_ics else 0.0

        # Calculate IC decay rate
        ic_decay_rate = self._calculate_ic_decay(ic_values, horizons)

        # Generate warnings and recommendations
        warnings = []
        recommendations = []

        # Check IC strength
        if max_ic < self.IC_THRESHOLD_WEAK:
            warnings.append(
                f"⚠️ Max IC ({max_ic:.4f}) below threshold ({self.IC_THRESHOLD_WEAK}) - "
                "likely no predictive edge"
            )
            recommendations.append("Consider different features or model architecture")

        # Check statistical significance
        significant_horizons = [h for h, p in ic_pvalues.items() if p < 0.05]
        if len(significant_horizons) < len(horizons) / 2:
            warnings.append(
                f"⚠️ Only {len(significant_horizons)}/{len(horizons)} horizons statistically "
                "significant (p < 0.05)"
            )

        # Check IC stability
        if ic_stability > abs(mean_ic):
            warnings.append(
                f"⚠️ IC unstable: std ({ic_stability:.4f}) > mean ({abs(mean_ic):.4f})"
            )
            recommendations.append("Model may be overfitting - add regularization")

        # Check IC decay
        if ic_decay_rate > 0.5:
            warnings.append(
                f"⚠️ Rapid IC decay ({ic_decay_rate:.2f}) - signal is short-term noise"
            )
            recommendations.append("Focus on shorter holding periods")

        # Check for negative IC (anti-predictive)
        if mean_ic < -self.IC_THRESHOLD_WEAK:
            warnings.append(
                f"⚠️ Negative IC ({mean_ic:.4f}) - model is anti-predictive!"
            )
            recommendations.append("REVERSE the signal direction")

        # Positive recommendations
        if has_edge and ic_stability < abs(mean_ic):
            recommendations.append(
                f"✅ Stable positive alpha at horizon {best_horizon} "
                f"(IC={max_ic:.4f}, IR={ir_values[best_horizon]:.2f})"
            )

        return AlphaICReport(
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            signal_name=signal_name,
            horizons=horizons,
            ic_values=ic_values,
            ic_pvalues=ic_pvalues,
            ir_values=ir_values,
            mean_ic=float(mean_ic),
            max_ic=float(max_ic),
            best_horizon=best_horizon,
            has_edge=has_edge,
            ic_stability=ic_stability,
            ic_decay_rate=ic_decay_rate,
            warnings=warnings,
            recommendations=recommendations,
        )

    def _calculate_rolling_ic(
        self,
        signals: np.ndarray,
        returns: np.ndarray,
    ) -> list[float]:
        """Calculate rolling IC values."""
        rolling_ics = []

        for i in range(self.rolling_window, len(signals)):
            window_signals = signals[i - self.rolling_window:i]
            window_returns = returns[i - self.rolling_window:i]

            # Skip if too many NaNs
            valid = ~(np.isnan(window_signals) | np.isnan(window_returns))
            if valid.sum() < self.rolling_window * 0.7:
                continue

            ic, _ = stats.spearmanr(
                window_signals[valid],
                window_returns[valid]
            )
            rolling_ics.append(ic)

        return rolling_ics

    def _calculate_ic_decay(
        self,
        ic_values: dict[int, float],
        horizons: list[int],
    ) -> float:
        """
        Calculate IC decay rate.

        Returns percentage drop from best horizon to longest horizon.
        """
        if len(horizons) < 2:
            return 0.0

        sorted_horizons = sorted(ic_values.keys())
        first_ic = abs(ic_values[sorted_horizons[0]])
        last_ic = abs(ic_values[sorted_horizons[-1]])

        if first_ic == 0:
            return 0.0

        decay = (first_ic - last_ic) / first_ic
        return max(0.0, float(decay))


def run_alpha_audit(
    model_predictions: np.ndarray,
    prices: np.ndarray,
    symbol: str = "SPY",
    output_dir: Optional[str] = None,
) -> AlphaICReport:
    """
    Convenience function to run alpha IC analysis.

    Args:
        model_predictions: Model signal/prediction values
        prices: Historical prices
        symbol: Symbol being analyzed
        output_dir: Optional directory to save report

    Returns:
        AlphaICReport
    """
    analyzer = AlphaICAnalyzer()
    report = analyzer.analyze(
        signals=model_predictions,
        prices=prices,
        symbol=symbol,
    )

    if output_dir:
        report.save(Path(output_dir) / f"alpha_ic_{symbol}_{datetime.now():%Y%m%d}.json")

    return report


def quick_ic_check(
    signals: np.ndarray,
    prices: np.ndarray,
    horizon: int = 5,
) -> dict[str, Any]:
    """
    Quick IC check for a single horizon.

    Args:
        signals: Signal values
        prices: Price values
        horizon: Forward return horizon

    Returns:
        Dict with IC, p-value, and has_edge flag
    """
    analyzer = AlphaICAnalyzer(min_samples=30)

    # Calculate forward returns
    forward_returns = analyzer.calculate_forward_returns(prices, horizon)

    # Calculate IC
    ic, pvalue = analyzer.calculate_ic(signals, forward_returns)

    return {
        "ic": ic,
        "pvalue": pvalue,
        "has_edge": abs(ic) >= 0.02 and pvalue < 0.05,
        "strength": (
            "strong" if abs(ic) >= 0.10 else
            "moderate" if abs(ic) >= 0.05 else
            "weak" if abs(ic) >= 0.02 else
            "none"
        ),
    }


if __name__ == "__main__":
    """Demo the alpha IC analyzer."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("ALPHA IC ANALYSIS DEMO")
    print("=" * 80)

    # Generate synthetic data
    np.random.seed(42)
    n_days = 500

    # Create price series with trend
    returns = np.random.randn(n_days) * 0.01  # 1% daily vol
    prices = 100 * np.cumprod(1 + returns)

    # Create signal with some predictive power
    # Signal = 0.1 * future_return + 0.9 * noise (IC should be ~0.1)
    noise = np.random.randn(n_days)
    forward_1d = np.roll(returns, -1)
    forward_1d[-1] = 0
    signals = 0.15 * forward_1d + 0.85 * noise * 0.01

    print(f"\nSynthetic data: {n_days} days")
    print(f"Expected IC: ~0.10-0.15 at 1-day horizon")

    # Run analysis
    analyzer = AlphaICAnalyzer()
    report = analyzer.analyze(
        signals=signals,
        prices=prices,
        horizons=[1, 5, 10, 20],
        signal_name="synthetic_signal",
        symbol="DEMO",
    )

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)

    print(f"\nHas Edge: {'✅ YES' if report.has_edge else '❌ NO'}")
    print(f"Best Horizon: {report.best_horizon} days")
    print(f"Max IC: {report.max_ic:.4f}")
    print(f"Mean IC: {report.mean_ic:.4f}")
    print(f"IC Stability: {report.ic_stability:.4f}")

    print("\nIC by Horizon:")
    for h in report.horizons:
        ic = report.ic_values[h]
        p = report.ic_pvalues[h]
        ir = report.ir_values[h]
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
        print(f"  {h:2d}d: IC={ic:+.4f} (p={p:.4f}){sig}, IR={ir:.2f}")

    if report.warnings:
        print("\nWarnings:")
        for w in report.warnings:
            print(f"  {w}")

    if report.recommendations:
        print("\nRecommendations:")
        for r in report.recommendations:
            print(f"  - {r}")
