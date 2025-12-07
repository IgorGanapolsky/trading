"""
Portfolio optimization engine.

Implements multiple optimization methods for portfolio construction.
"""

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd
from scipy.optimize import minimize


class OptimizationMethod(Enum):
    """Available portfolio optimization methods."""

    MEAN_VARIANCE = "mean_variance"
    MIN_VARIANCE = "min_variance"
    RISK_PARITY = "risk_parity"
    EQUAL_WEIGHT = "equal_weight"
    MAX_SHARPE = "max_sharpe"
    MAX_DIVERSIFICATION = "max_diversification"
    HRP = "hierarchical_risk_parity"


@dataclass
class PortfolioConstraints:
    """Portfolio construction constraints."""

    min_weight: float = 0.0
    max_weight: float = 1.0
    max_concentration: float = 0.25
    min_assets: int = 3
    max_assets: int | None = None
    target_volatility: float | None = None
    max_turnover: float | None = None
    sector_caps: dict = field(default_factory=dict)
    long_only: bool = True


@dataclass
class OptimizationResult:
    """Result of portfolio optimization."""

    weights: pd.Series
    expected_return: float
    volatility: float
    sharpe_ratio: float
    method: OptimizationMethod
    constraints_satisfied: bool = True
    optimization_success: bool = True
    message: str = ""


class PortfolioOptimizer:
    """
    Portfolio optimization engine supporting multiple methods.

    Example:
        >>> optimizer = PortfolioOptimizer()
        >>> result = optimizer.optimize(
        ...     expected_returns, covariance_matrix,
        ...     method=OptimizationMethod.MEAN_VARIANCE
        ... )
        >>> print(result.weights)
    """

    def __init__(self, risk_free_rate: float = 0.02):
        self.risk_free_rate = risk_free_rate

    def optimize(
        self,
        expected_returns: pd.Series,
        covariance_matrix: pd.DataFrame,
        method: OptimizationMethod = OptimizationMethod.MEAN_VARIANCE,
        constraints: PortfolioConstraints | None = None,
    ) -> OptimizationResult:
        """
        Optimize portfolio weights using the specified method.

        Args:
            expected_returns: Expected returns for each asset
            covariance_matrix: Covariance matrix of returns
            method: Optimization method to use
            constraints: Portfolio constraints

        Returns:
            OptimizationResult with optimal weights and metrics
        """
        if constraints is None:
            constraints = PortfolioConstraints()

        assets = expected_returns.index.tolist()
        n_assets = len(assets)

        if method == OptimizationMethod.EQUAL_WEIGHT:
            weights = np.ones(n_assets) / n_assets
        elif method == OptimizationMethod.MIN_VARIANCE:
            weights = self._min_variance(covariance_matrix, constraints)
        elif method == OptimizationMethod.MEAN_VARIANCE:
            weights = self._mean_variance(expected_returns, covariance_matrix, constraints)
        elif method == OptimizationMethod.MAX_SHARPE:
            weights = self._max_sharpe(expected_returns, covariance_matrix, constraints)
        elif method == OptimizationMethod.RISK_PARITY:
            weights = self._risk_parity(covariance_matrix, constraints)
        elif method == OptimizationMethod.HRP:
            weights = self._hierarchical_risk_parity(covariance_matrix)
        elif method == OptimizationMethod.MAX_DIVERSIFICATION:
            weights = self._max_diversification(covariance_matrix, constraints)
        else:
            weights = np.ones(n_assets) / n_assets

        weights = pd.Series(weights, index=assets)
        weights = self._apply_constraints(weights, constraints)

        port_return = float(np.dot(weights, expected_returns))
        port_vol = float(np.sqrt(np.dot(weights.T, np.dot(covariance_matrix, weights))))
        sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0

        return OptimizationResult(
            weights=weights,
            expected_return=port_return,
            volatility=port_vol,
            sharpe_ratio=sharpe,
            method=method,
        )

    def _min_variance(self, cov: pd.DataFrame, constraints: PortfolioConstraints) -> np.ndarray:
        """Minimum variance optimization."""
        n = len(cov)

        def objective(w):
            return np.dot(w.T, np.dot(cov.values, w))

        x0 = np.ones(n) / n
        bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n)]
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        result = minimize(objective, x0, method="SLSQP", bounds=bounds, constraints=cons)
        return result.x if result.success else x0

    def _mean_variance(
        self, mu: pd.Series, cov: pd.DataFrame, constraints: PortfolioConstraints
    ) -> np.ndarray:
        """Mean-variance optimization (maximize Sharpe)."""
        return self._max_sharpe(mu, cov, constraints)

    def _max_sharpe(
        self, mu: pd.Series, cov: pd.DataFrame, constraints: PortfolioConstraints
    ) -> np.ndarray:
        """Maximize Sharpe ratio."""
        n = len(mu)

        def neg_sharpe(w):
            ret = np.dot(w, mu.values)
            vol = np.sqrt(np.dot(w.T, np.dot(cov.values, w)))
            return -(ret - self.risk_free_rate) / vol if vol > 1e-10 else 0

        x0 = np.ones(n) / n
        bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n)]
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        result = minimize(neg_sharpe, x0, method="SLSQP", bounds=bounds, constraints=cons)
        return result.x if result.success else x0

    def _risk_parity(self, cov: pd.DataFrame, constraints: PortfolioConstraints) -> np.ndarray:
        """Risk parity (equal risk contribution)."""
        n = len(cov)

        def risk_budget_objective(w):
            port_vol = np.sqrt(np.dot(w.T, np.dot(cov.values, w)))
            marginal_contrib = np.dot(cov.values, w)
            risk_contrib = w * marginal_contrib / port_vol
            target_risk = port_vol / n
            return np.sum((risk_contrib - target_risk) ** 2)

        x0 = np.ones(n) / n
        bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n)]
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        result = minimize(
            risk_budget_objective, x0, method="SLSQP", bounds=bounds, constraints=cons
        )
        return result.x if result.success else x0

    def _hierarchical_risk_parity(self, cov: pd.DataFrame) -> np.ndarray:
        """Hierarchical Risk Parity using correlation clustering."""
        from scipy.cluster.hierarchy import leaves_list, linkage
        from scipy.spatial.distance import squareform

        corr = cov.values / np.outer(np.sqrt(np.diag(cov)), np.sqrt(np.diag(cov)))
        corr = np.clip(corr, -1, 1)
        dist = np.sqrt(0.5 * (1 - corr))
        np.fill_diagonal(dist, 0)

        try:
            dist_condensed = squareform(dist)
            link = linkage(dist_condensed, method="single")
            sort_ix = leaves_list(link)
        except Exception:
            sort_ix = np.arange(len(cov))

        weights = np.ones(len(cov))
        cluster_items = [sort_ix.tolist()]

        while len(cluster_items) > 0:
            cluster_items = [
                item[start:end]
                for item in cluster_items
                for start, end in [(0, len(item) // 2), (len(item) // 2, len(item))]
                if len(item) > 1
            ]
            for subcluster in cluster_items:
                if len(subcluster) == 0:
                    continue
                left = subcluster[: len(subcluster) // 2]
                right = subcluster[len(subcluster) // 2 :]
                if len(left) == 0 or len(right) == 0:
                    continue

                left_var = self._cluster_variance(cov.iloc[left, left].values)
                right_var = self._cluster_variance(cov.iloc[right, right].values)
                alpha = 1 - left_var / (left_var + right_var) if (left_var + right_var) > 0 else 0.5

                weights[left] *= alpha
                weights[right] *= 1 - alpha

        weights = weights / weights.sum()
        return weights

    def _cluster_variance(self, cov: np.ndarray) -> float:
        """Calculate inverse-variance portfolio variance for a cluster."""
        inv_diag = 1 / np.diag(cov)
        inv_diag = inv_diag / inv_diag.sum()
        return float(np.dot(inv_diag.T, np.dot(cov, inv_diag)))

    def _max_diversification(
        self, cov: pd.DataFrame, constraints: PortfolioConstraints
    ) -> np.ndarray:
        """Maximize diversification ratio."""
        n = len(cov)
        stds = np.sqrt(np.diag(cov.values))

        def neg_div_ratio(w):
            port_vol = np.sqrt(np.dot(w.T, np.dot(cov.values, w)))
            weighted_std = np.dot(w, stds)
            return -weighted_std / port_vol if port_vol > 1e-10 else 0

        x0 = np.ones(n) / n
        bounds = [(constraints.min_weight, constraints.max_weight) for _ in range(n)]
        cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        result = minimize(neg_div_ratio, x0, method="SLSQP", bounds=bounds, constraints=cons)
        return result.x if result.success else x0

    def _apply_constraints(
        self, weights: pd.Series, constraints: PortfolioConstraints
    ) -> pd.Series:
        """Apply post-optimization constraints."""
        weights = weights.clip(lower=constraints.min_weight, upper=constraints.max_weight)

        if constraints.max_concentration < 1.0:
            weights = weights.clip(upper=constraints.max_concentration)

        if constraints.long_only:
            weights = weights.clip(lower=0)

        total = weights.sum()
        if total > 0:
            weights = weights / total

        return weights
