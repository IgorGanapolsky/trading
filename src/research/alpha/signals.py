"""
Alpha signal generation and analysis.
"""

from dataclasses import dataclass

import pandas as pd


@dataclass
class AlphaSignal:
    """A single alpha signal with metadata."""

    name: str
    signal: pd.Series
    ic: float | None = None
    ir: float | None = None
    turnover: float | None = None
    description: str = ""

    def normalize(self) -> "AlphaSignal":
        """Return a normalized version of the signal."""
        normalized = (self.signal - self.signal.mean()) / self.signal.std()
        return AlphaSignal(
            name=f"{self.name}_norm",
            signal=normalized,
            description=f"Normalized {self.description}",
        )

    def rank(self) -> "AlphaSignal":
        """Return a rank-transformed version of the signal."""
        ranked = self.signal.rank(pct=True) - 0.5
        return AlphaSignal(
            name=f"{self.name}_rank",
            signal=ranked,
            description=f"Ranked {self.description}",
        )


class SignalGenerator:
    """
    Generate alpha signals from features.

    Example:
        >>> gen = SignalGenerator()
        >>> signals = gen.generate_momentum_signal(features)
    """

    def generate_momentum_signal(
        self,
        features: pd.DataFrame,
        lookback: int = 20,
    ) -> AlphaSignal:
        """Generate a momentum signal."""
        col = f"return_{lookback}d"
        if col in features.columns:
            signal = features[col]
        else:
            signal = features.get("Close", pd.Series()).pct_change(lookback)

        return AlphaSignal(
            name=f"momentum_{lookback}",
            signal=signal,
            description=f"{lookback}-day momentum signal",
        )

    def generate_mean_reversion_signal(
        self,
        features: pd.DataFrame,
        lookback: int = 20,
    ) -> AlphaSignal:
        """Generate a mean reversion signal."""
        col = f"return_{lookback}d"
        if col in features.columns:
            signal = -features[col]
        else:
            returns = features.get("Close", pd.Series()).pct_change(lookback)
            signal = -returns

        return AlphaSignal(
            name=f"mean_reversion_{lookback}",
            signal=signal,
            description=f"{lookback}-day mean reversion signal",
        )

    def generate_rsi_signal(
        self,
        features: pd.DataFrame,
    ) -> AlphaSignal:
        """Generate RSI-based signal (contrarian)."""
        if "rsi" not in features.columns:
            return AlphaSignal(
                name="rsi_signal",
                signal=pd.Series(dtype=float),
                description="RSI contrarian signal (no data)",
            )

        rsi = features["rsi"]
        signal = 50 - rsi

        return AlphaSignal(
            name="rsi_contrarian",
            signal=signal,
            description="RSI contrarian signal (buy oversold, sell overbought)",
        )

    def generate_volatility_signal(
        self,
        features: pd.DataFrame,
    ) -> AlphaSignal:
        """Generate volatility-based signal."""
        vol_col = next(
            (c for c in features.columns if c.startswith("vol_") and "ratio" not in c),
            None,
        )
        if vol_col is None:
            return AlphaSignal(
                name="low_vol",
                signal=pd.Series(dtype=float),
                description="Low volatility signal (no data)",
            )

        signal = -features[vol_col]

        return AlphaSignal(
            name="low_volatility",
            signal=signal,
            description="Low volatility preference signal",
        )


def calculate_ic(
    signal: pd.Series,
    forward_returns: pd.Series,
) -> float:
    """
    Calculate Information Coefficient (rank correlation with forward returns).

    Args:
        signal: Alpha signal values
        forward_returns: Forward returns

    Returns:
        Spearman rank correlation
    """
    valid_mask = signal.notna() & forward_returns.notna()
    if valid_mask.sum() < 10:
        return 0.0

    return signal[valid_mask].corr(forward_returns[valid_mask], method="spearman")


def calculate_ir(
    ic_series: pd.Series,
) -> float:
    """
    Calculate Information Ratio (mean IC / std IC).

    Args:
        ic_series: Series of IC values over time

    Returns:
        Information Ratio
    """
    if len(ic_series) < 2:
        return 0.0

    mean_ic = ic_series.mean()
    std_ic = ic_series.std()

    if std_ic == 0:
        return 0.0

    return mean_ic / std_ic


def rank_signals_by_ic(
    signals: list[AlphaSignal],
    forward_returns: pd.Series,
) -> list[tuple[str, float]]:
    """
    Rank signals by their Information Coefficient.

    Args:
        signals: List of alpha signals
        forward_returns: Forward returns for IC calculation

    Returns:
        List of (signal_name, ic) tuples sorted by IC descending
    """
    results = []
    for signal in signals:
        ic = calculate_ic(signal.signal, forward_returns)
        results.append((signal.name, ic))

    return sorted(results, key=lambda x: abs(x[1]), reverse=True)


def combine_signals(
    signals: list[AlphaSignal],
    weights: dict[str, float] | None = None,
    method: str = "equal",
) -> AlphaSignal:
    """
    Combine multiple alpha signals.

    Args:
        signals: List of alpha signals
        weights: Optional weight dict (signal_name -> weight)
        method: 'equal', 'ic_weighted', or 'custom'

    Returns:
        Combined alpha signal
    """
    if not signals:
        return AlphaSignal(
            name="combined",
            signal=pd.Series(dtype=float),
            description="No signals to combine",
        )

    normalized_signals = [s.normalize() for s in signals]

    if method == "equal" or weights is None:
        weights = {s.name: 1.0 / len(signals) for s in normalized_signals}

    combined = pd.Series(0.0, index=normalized_signals[0].signal.index)
    total_weight = 0.0

    for signal in normalized_signals:
        original_name = signal.name.replace("_norm", "")
        w = weights.get(original_name, weights.get(signal.name, 0))
        combined += signal.signal.fillna(0) * w
        total_weight += w

    if total_weight > 0:
        combined = combined / total_weight

    return AlphaSignal(
        name="combined_alpha",
        signal=combined,
        description=f"Combined signal using {method} weighting",
    )
