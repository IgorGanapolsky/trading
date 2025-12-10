"""
Kelly Criterion position sizing.

The Kelly Criterion maximizes long-term geometric growth rate by sizing
positions based on edge and odds.
"""

import numpy as np
import pandas as pd


def calculate_kelly_fraction(
    expected_return: float,
    volatility: float,
    risk_free_rate: float = 0.0,
) -> float:
    """
    Calculate the Kelly fraction for a single asset.

    Kelly fraction = (expected_return - risk_free_rate) / volatility^2

    Args:
        expected_return: Expected return of the asset
        volatility: Standard deviation of returns
        risk_free_rate: Risk-free rate

    Returns:
        Optimal Kelly fraction (can be > 1 for leveraged positions)
    """
    if volatility <= 0:
        return 0.0

    excess_return = expected_return - risk_free_rate
    kelly = excess_return / (volatility**2)

    return kelly


def calculate_half_kelly(
    expected_return: float,
    volatility: float,
    risk_free_rate: float = 0.0,
) -> float:
    """
    Calculate half-Kelly fraction (more conservative).

    Half-Kelly is commonly used in practice as it provides nearly the same
    growth rate with significantly lower variance.

    Args:
        expected_return: Expected return of the asset
        volatility: Standard deviation of returns
        risk_free_rate: Risk-free rate

    Returns:
        Half-Kelly fraction
    """
    return calculate_kelly_fraction(expected_return, volatility, risk_free_rate) / 2


def calculate_kelly_portfolio(
    expected_returns: pd.Series,
    covariance_matrix: pd.DataFrame,
    risk_free_rate: float = 0.0,
    max_leverage: float = 1.0,
) -> pd.Series:
    """
    Calculate Kelly-optimal portfolio weights.

    For a portfolio, Kelly weights = Sigma^(-1) * (mu - rf)

    Args:
        expected_returns: Expected returns for each asset
        covariance_matrix: Covariance matrix
        risk_free_rate: Risk-free rate
        max_leverage: Maximum total leverage (1.0 = no leverage)

    Returns:
        Kelly-optimal portfolio weights
    """
    assets = expected_returns.index.tolist()
    excess_returns = expected_returns - risk_free_rate

    try:
        cov_inv = np.linalg.inv(covariance_matrix.values)
        kelly_weights = np.dot(cov_inv, excess_returns.values)
    except np.linalg.LinAlgError:
        return pd.Series(np.ones(len(assets)) / len(assets), index=assets)

    total_weight = np.abs(kelly_weights).sum()
    if total_weight > max_leverage:
        kelly_weights = kelly_weights * max_leverage / total_weight

    return pd.Series(kelly_weights, index=assets)


def calculate_fractional_kelly(
    expected_return: float,
    volatility: float,
    fraction: float = 0.5,
    risk_free_rate: float = 0.0,
) -> float:
    """
    Calculate fractional Kelly (any fraction from 0 to 1).

    Args:
        expected_return: Expected return of the asset
        volatility: Standard deviation of returns
        fraction: Kelly fraction to use (0.5 = half-Kelly)
        risk_free_rate: Risk-free rate

    Returns:
        Fractional Kelly position size
    """
    full_kelly = calculate_kelly_fraction(expected_return, volatility, risk_free_rate)
    return full_kelly * fraction


def calculate_kelly_from_win_rate(
    win_rate: float,
    win_loss_ratio: float,
) -> float:
    """
    Calculate Kelly fraction from win rate and win/loss ratio.

    Kelly = W - (1-W)/R where W = win rate, R = win/loss ratio

    Args:
        win_rate: Probability of winning (0 to 1)
        win_loss_ratio: Average win / average loss

    Returns:
        Kelly fraction
    """
    if win_loss_ratio <= 0:
        return 0.0

    kelly = win_rate - (1 - win_rate) / win_loss_ratio
    return max(0, kelly)
