"""
Risk parity and equal risk contribution implementations.
"""

from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def calculate_risk_parity_weights(
    covariance_matrix: pd.DataFrame,
    target_risk_budgets: Optional[pd.Series] = None,
) -> pd.Series:
    """
    Calculate risk parity portfolio weights.

    Risk parity allocates capital such that each asset contributes equally
    to the total portfolio risk.

    Args:
        covariance_matrix: Asset covariance matrix
        target_risk_budgets: Optional target risk budget per asset (defaults to equal)

    Returns:
        Portfolio weights as a Series
    """
    assets = covariance_matrix.index.tolist()
    n = len(assets)
    cov = covariance_matrix.values

    if target_risk_budgets is None:
        target_risk_budgets = pd.Series(np.ones(n) / n, index=assets)

    def objective(w):
        port_vol = np.sqrt(np.dot(w.T, np.dot(cov, w)))
        if port_vol < 1e-10:
            return 0

        marginal_contrib = np.dot(cov, w)
        risk_contrib = w * marginal_contrib / port_vol
        target = target_risk_budgets.values * port_vol

        return np.sum((risk_contrib - target) ** 2)

    x0 = np.ones(n) / n
    bounds = [(0.01, 1.0) for _ in range(n)]
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

    result = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=constraints)

    weights = result.x if result.success else x0
    weights = weights / weights.sum()

    return pd.Series(weights, index=assets)


def calculate_equal_risk_contribution(
    covariance_matrix: pd.DataFrame,
) -> pd.Series:
    """
    Calculate equal risk contribution (ERC) portfolio weights.

    This is equivalent to risk parity with equal risk budgets.

    Args:
        covariance_matrix: Asset covariance matrix

    Returns:
        Portfolio weights with equal risk contribution
    """
    return calculate_risk_parity_weights(covariance_matrix, target_risk_budgets=None)


def calculate_risk_contributions(
    weights: pd.Series,
    covariance_matrix: pd.DataFrame,
) -> pd.Series:
    """
    Calculate the risk contribution of each asset.

    Args:
        weights: Portfolio weights
        covariance_matrix: Asset covariance matrix

    Returns:
        Percentage risk contribution of each asset
    """
    cov = covariance_matrix.values
    w = weights.values

    port_vol = np.sqrt(np.dot(w.T, np.dot(cov, w)))
    if port_vol < 1e-10:
        return pd.Series(np.zeros(len(weights)), index=weights.index)

    marginal_contrib = np.dot(cov, w)
    risk_contrib = w * marginal_contrib / port_vol

    return pd.Series(risk_contrib / risk_contrib.sum(), index=weights.index)


def calculate_marginal_risk(
    weights: pd.Series,
    covariance_matrix: pd.DataFrame,
) -> pd.Series:
    """
    Calculate marginal risk contribution of each asset.

    Args:
        weights: Portfolio weights
        covariance_matrix: Asset covariance matrix

    Returns:
        Marginal risk contribution of each asset
    """
    cov = covariance_matrix.values
    w = weights.values

    port_vol = np.sqrt(np.dot(w.T, np.dot(cov, w)))
    if port_vol < 1e-10:
        return pd.Series(np.zeros(len(weights)), index=weights.index)

    marginal = np.dot(cov, w) / port_vol

    return pd.Series(marginal, index=weights.index)
