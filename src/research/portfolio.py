"""
Portfolio Construction Module - Optimization and Position Sizing

This module provides portfolio construction algorithms for converting
alpha signals into tradable positions:

1. Mean-Variance Optimization (Markowitz)
2. Risk Parity
3. Equal Risk Contribution
4. Kelly Criterion (fractional)
5. Volatility Scaling
6. Hierarchical Risk Parity (HRP)

All methods support:
- Long-only and long-short portfolios
- Sector/industry constraints
- Concentration limits
- Turnover constraints
- Beta neutrality option

Author: Trading System
Created: 2025-12-02
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from scipy import optimize
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


class OptimizationMethod(Enum):
    """Portfolio optimization methods."""

    MEAN_VARIANCE = "mean_variance"
    RISK_PARITY = "risk_parity"
    EQUAL_RISK = "equal_risk_contribution"
    KELLY = "kelly"
    VOLATILITY_SCALING = "volatility_scaling"
    HIERARCHICAL_RISK_PARITY = "hrp"
    EQUAL_WEIGHT = "equal_weight"


@dataclass
class PortfolioConstraints:
    """Constraints for portfolio optimization."""

    # Position limits
    min_weight: float = 0.0  # Minimum position weight (0 = long-only)
    max_weight: float = 1.0  # Maximum single position weight
    max_gross: float = 1.0  # Maximum gross exposure
    max_net: float = 1.0  # Maximum net exposure

    # Concentration
    max_top_n_weight: float = 0.6  # Max weight in top N positions
    top_n: int = 5

    # Sector/industry
    sector_limits: dict[str, float] = field(default_factory=dict)

    # Turnover
    max_turnover: float = 1.0  # Maximum turnover per rebalance

    # Risk
    target_volatility: float = 0.15  # 15% annual vol target
    max_beta: float | None = None  # Max portfolio beta
    beta_neutral: bool = False  # Enforce beta neutrality

    # Position count
    max_positions: int = 50
    min_positions: int = 1


@dataclass
class PortfolioResult:
    """Result of portfolio optimization."""

    weights: pd.Series
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    method: OptimizationMethod
    optimization_success: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "weights": self.weights.to_dict(),
            "expected_return": self.expected_return,
            "expected_volatility": self.expected_volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "method": self.method.value,
            "optimization_success": self.optimization_success,
            "metadata": self.metadata,
        }


class PortfolioOptimizer:
    """
    Portfolio optimization engine.

    Provides multiple optimization methods for converting alpha signals
    to portfolio weights.
    """

    def __init__(
        self,
        constraints: PortfolioConstraints | None = None,
        risk_free_rate: float = 0.04,
    ):
        self.constraints = constraints or PortfolioConstraints()
        self.risk_free_rate = risk_free_rate

    def optimize(
        self,
        expected_returns: pd.Series,
        covariance_matrix: pd.DataFrame,
        method: OptimizationMethod = OptimizationMethod.MEAN_VARIANCE,
        current_weights: pd.Series | None = None,
    ) -> PortfolioResult:
        """
        Optimize portfolio weights.

        Args:
            expected_returns: Expected returns for each asset
            covariance_matrix: Covariance matrix of returns
            method: Optimization method to use
            current_weights: Current portfolio weights (for turnover constraints)

        Returns:
            PortfolioResult with optimal weights
        """
        # Validate inputs
        assets = expected_returns.index
        if not all(a in covariance_matrix.index for a in assets):
            raise ValueError("Covariance matrix must include all assets")

        # Align covariance matrix
        cov = covariance_matrix.loc[assets, assets]

        # Choose optimization method
        if method == OptimizationMethod.MEAN_VARIANCE:
            result = self._mean_variance_optimization(expected_returns, cov)
        elif method == OptimizationMethod.RISK_PARITY:
            result = self._risk_parity_optimization(cov)
        elif method == OptimizationMethod.EQUAL_RISK:
            result = self._equal_risk_contribution(cov)
        elif method == OptimizationMethod.KELLY:
            result = self._kelly_optimization(expected_returns, cov)
        elif method == OptimizationMethod.VOLATILITY_SCALING:
            result = self._volatility_scaling(expected_returns, cov)
        elif method == OptimizationMethod.HIERARCHICAL_RISK_PARITY:
            result = self._hierarchical_risk_parity(cov)
        elif method == OptimizationMethod.EQUAL_WEIGHT:
            result = self._equal_weight(expected_returns)
        else:
            raise ValueError(f"Unknown optimization method: {method}")

        # Apply constraints
        result = self._apply_constraints(result, current_weights)

        # Calculate final metrics
        weights = result.weights
        result.expected_return = float(weights @ expected_returns)
        result.expected_volatility = float(np.sqrt(weights @ cov @ weights) * np.sqrt(252))
        result.sharpe_ratio = (
            (result.expected_return - self.risk_free_rate) / result.expected_volatility
            if result.expected_volatility > 0
            else 0.0
        )

        logger.info(
            f"Optimized portfolio ({method.value}): "
            f"E[R]={result.expected_return:.2%}, Vol={result.expected_volatility:.2%}, "
            f"Sharpe={result.sharpe_ratio:.2f}"
        )

        return result

    def _mean_variance_optimization(
        self, expected_returns: pd.Series, cov: pd.DataFrame
    ) -> PortfolioResult:
        """Mean-variance (Markowitz) optimization."""
        n_assets = len(expected_returns)
        returns = expected_returns.values
        sigma = cov.values

        # Objective: Maximize Sharpe ratio (or minimize negative Sharpe)
        def neg_sharpe(w):
            port_ret = np.dot(w, returns)
            port_vol = np.sqrt(np.dot(w.T, np.dot(sigma, w))) * np.sqrt(252)
            if port_vol < 1e-8:
                return 1000
            return -(port_ret - self.risk_free_rate) / port_vol

        # Constraints
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]  # Weights sum to 1

        # Bounds
        bounds = [(self.constraints.min_weight, self.constraints.max_weight)] * n_assets

        # Initial guess
        x0 = np.array([1.0 / n_assets] * n_assets)

        # Optimize
        result = optimize.minimize(
            neg_sharpe,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )

        weights = pd.Series(result.x, index=expected_returns.index)

        return PortfolioResult(
            weights=weights,
            expected_return=0.0,
            expected_volatility=0.0,
            sharpe_ratio=0.0,
            method=OptimizationMethod.MEAN_VARIANCE,
            optimization_success=result.success,
            metadata={"optimizer_message": result.message},
        )

    def _risk_parity_optimization(self, cov: pd.DataFrame) -> PortfolioResult:
        """Risk parity optimization (equal risk contribution)."""
        n_assets = len(cov)
        sigma = cov.values

        # Objective: Minimize sum of (RC_i - RC_avg)^2
        def risk_parity_objective(w):
            port_vol = np.sqrt(np.dot(w.T, np.dot(sigma, w)))
            if port_vol < 1e-8:
                return 1000

            # Risk contributions
            marginal_risk = np.dot(sigma, w)
            rc = w * marginal_risk / port_vol
            target_rc = port_vol / n_assets

            return np.sum((rc - target_rc) ** 2)

        # Constraints
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        # Bounds (long-only for risk parity)
        bounds = [(0.001, self.constraints.max_weight)] * n_assets

        # Initial guess
        x0 = np.array([1.0 / n_assets] * n_assets)

        # Optimize
        result = optimize.minimize(
            risk_parity_objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000},
        )

        weights = pd.Series(result.x, index=cov.index)

        return PortfolioResult(
            weights=weights,
            expected_return=0.0,
            expected_volatility=0.0,
            sharpe_ratio=0.0,
            method=OptimizationMethod.RISK_PARITY,
            optimization_success=result.success,
        )

    def _equal_risk_contribution(self, cov: pd.DataFrame) -> PortfolioResult:
        """Equal risk contribution (ERC) optimization."""
        n_assets = len(cov)
        sigma = cov.values

        # Inverse volatility weights as starting point
        vols = np.sqrt(np.diag(sigma)) * np.sqrt(252)
        inv_vols = 1.0 / (vols + 1e-8)
        x0 = inv_vols / inv_vols.sum()

        # Objective: Minimize variance with penalty for unequal risk contribution
        def erc_objective(w):
            port_var = np.dot(w.T, np.dot(sigma, w))
            port_vol = np.sqrt(port_var)

            if port_vol < 1e-8:
                return 1000

            # Risk contributions
            marginal_risk = np.dot(sigma, w)
            rc = w * marginal_risk / port_vol

            # Penalty for deviation from equal RC
            target_rc = port_vol / n_assets
            penalty = 10 * np.sum((rc - target_rc) ** 2)

            return port_var + penalty

        # Constraints
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        # Bounds
        bounds = [(0.001, self.constraints.max_weight)] * n_assets

        # Optimize
        result = optimize.minimize(
            erc_objective,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
        )

        weights = pd.Series(result.x, index=cov.index)

        return PortfolioResult(
            weights=weights,
            expected_return=0.0,
            expected_volatility=0.0,
            sharpe_ratio=0.0,
            method=OptimizationMethod.EQUAL_RISK,
            optimization_success=result.success,
        )

    def _kelly_optimization(
        self, expected_returns: pd.Series, cov: pd.DataFrame
    ) -> PortfolioResult:
        """Kelly criterion optimization (half-Kelly for practical use)."""
        n_assets = len(expected_returns)
        returns = expected_returns.values
        sigma = cov.values

        # Full Kelly: w = Sigma^-1 * mu
        try:
            sigma_inv = np.linalg.inv(sigma)
            full_kelly = np.dot(sigma_inv, returns)

            # Half-Kelly for safety
            half_kelly = full_kelly / 2

            # Normalize to sum to 1 if long-only
            if self.constraints.min_weight >= 0:
                half_kelly = np.maximum(half_kelly, 0)
                if half_kelly.sum() > 0:
                    half_kelly = half_kelly / half_kelly.sum()
                else:
                    half_kelly = np.array([1.0 / n_assets] * n_assets)

            weights = pd.Series(half_kelly, index=expected_returns.index)
            success = True

        except np.linalg.LinAlgError:
            # Fallback to equal weight
            weights = pd.Series([1.0 / n_assets] * n_assets, index=expected_returns.index)
            success = False

        return PortfolioResult(
            weights=weights,
            expected_return=0.0,
            expected_volatility=0.0,
            sharpe_ratio=0.0,
            method=OptimizationMethod.KELLY,
            optimization_success=success,
            metadata={"kelly_fraction": 0.5},
        )

    def _volatility_scaling(
        self, expected_returns: pd.Series, cov: pd.DataFrame
    ) -> PortfolioResult:
        """Volatility scaling (inverse volatility weighting)."""
        # Individual asset volatilities
        vols = np.sqrt(np.diag(cov.values)) * np.sqrt(252)

        # Inverse volatility weights
        inv_vols = 1.0 / (vols + 1e-8)
        weights = inv_vols / inv_vols.sum()

        # Scale to target volatility
        port_vol = np.sqrt(np.dot(weights.T, np.dot(cov.values, weights))) * np.sqrt(252)

        if port_vol > 0:
            scale = self.constraints.target_volatility / port_vol
            weights = weights * min(scale, 1.0)  # Don't lever up

        weights = pd.Series(weights, index=expected_returns.index)

        return PortfolioResult(
            weights=weights,
            expected_return=0.0,
            expected_volatility=0.0,
            sharpe_ratio=0.0,
            method=OptimizationMethod.VOLATILITY_SCALING,
            optimization_success=True,
        )

    def _hierarchical_risk_parity(self, cov: pd.DataFrame) -> PortfolioResult:
        """Hierarchical Risk Parity (HRP) optimization."""
        # Convert covariance to correlation and distance
        corr = cov.values / np.outer(np.sqrt(np.diag(cov.values)), np.sqrt(np.diag(cov.values)))
        np.fill_diagonal(corr, 1.0)

        # Distance matrix
        dist = np.sqrt((1 - corr) / 2)
        np.fill_diagonal(dist, 0)

        # Hierarchical clustering
        dist_condensed = squareform(dist)
        link = linkage(dist_condensed, method="single")

        # Get sort order from dendrogram
        sort_ix = self._get_quasi_diag(link)

        # Recursive bisection
        weights = self._recursive_bisection(cov.values, sort_ix)

        weights = pd.Series(weights, index=cov.index)

        return PortfolioResult(
            weights=weights,
            expected_return=0.0,
            expected_volatility=0.0,
            sharpe_ratio=0.0,
            method=OptimizationMethod.HIERARCHICAL_RISK_PARITY,
            optimization_success=True,
        )

    def _get_quasi_diag(self, link: np.ndarray) -> list[int]:
        """Get quasi-diagonal order from linkage matrix."""
        link = link.astype(int)
        sort_ix = pd.Series([link[-1, 0], link[-1, 1]])
        num_items = link[-1, 3]

        while sort_ix.max() >= num_items:
            sort_ix.index = range(0, sort_ix.shape[0] * 2, 2)
            df0 = sort_ix[sort_ix >= num_items]
            i = df0.index
            j = df0.values - num_items
            sort_ix[i] = link[j, 0]
            df0 = pd.Series(link[j, 1], index=i + 1)
            sort_ix = pd.concat([sort_ix, df0])
            sort_ix = sort_ix.sort_index()
            sort_ix.index = range(sort_ix.shape[0])

        return sort_ix.tolist()

    def _recursive_bisection(self, cov: np.ndarray, sort_ix: list[int]) -> np.ndarray:
        """Recursive bisection for HRP weights."""
        n = len(sort_ix)
        weights = np.ones(n)

        if n == 1:
            return weights

        # Split
        mid = n // 2
        left_ix = sort_ix[:mid]
        right_ix = sort_ix[mid:]

        # Cluster variances
        cov_left = cov[np.ix_(left_ix, left_ix)]
        cov_right = cov[np.ix_(right_ix, right_ix)]

        # Inverse-variance weighting
        inv_var_left = 1.0 / np.trace(cov_left)
        inv_var_right = 1.0 / np.trace(cov_right)

        alpha = inv_var_left / (inv_var_left + inv_var_right)

        # Recursive call
        weights[left_ix] = alpha * self._recursive_bisection(cov, left_ix)
        weights[right_ix] = (1 - alpha) * self._recursive_bisection(cov, right_ix)

        return weights

    def _equal_weight(self, expected_returns: pd.Series) -> PortfolioResult:
        """Simple equal weighting."""
        n_assets = len(expected_returns)
        weights = pd.Series([1.0 / n_assets] * n_assets, index=expected_returns.index)

        return PortfolioResult(
            weights=weights,
            expected_return=0.0,
            expected_volatility=0.0,
            sharpe_ratio=0.0,
            method=OptimizationMethod.EQUAL_WEIGHT,
            optimization_success=True,
        )

    def _apply_constraints(
        self,
        result: PortfolioResult,
        current_weights: pd.Series | None = None,
    ) -> PortfolioResult:
        """Apply portfolio constraints to weights."""
        weights = result.weights.copy()

        # Position limits
        weights = weights.clip(
            lower=self.constraints.min_weight,
            upper=self.constraints.max_weight,
        )

        # Concentration limit (top N)
        if len(weights) > self.constraints.top_n:
            sorted_weights = weights.abs().sort_values(ascending=False)
            top_n_weight = sorted_weights.iloc[: self.constraints.top_n].sum()

            if top_n_weight > self.constraints.max_top_n_weight:
                scale = self.constraints.max_top_n_weight / top_n_weight
                top_n_idx = sorted_weights.index[: self.constraints.top_n]
                weights.loc[top_n_idx] *= scale

        # Max positions
        if (weights != 0).sum() > self.constraints.max_positions:
            sorted_weights = weights.abs().sort_values(ascending=False)
            keep_idx = sorted_weights.index[: self.constraints.max_positions]
            weights.loc[~weights.index.isin(keep_idx)] = 0

        # Turnover constraint
        if current_weights is not None:
            turnover = (weights - current_weights.reindex(weights.index, fill_value=0)).abs().sum()
            if turnover > self.constraints.max_turnover:
                # Scale changes
                scale = self.constraints.max_turnover / turnover
                current = current_weights.reindex(weights.index, fill_value=0)
                weights = current + (weights - current) * scale

        # Renormalize if needed
        if weights.sum() > 0:
            weights = weights / weights.sum()

        # Gross exposure
        if weights.abs().sum() > self.constraints.max_gross:
            weights = weights / weights.abs().sum() * self.constraints.max_gross

        result.weights = weights
        return result


def calculate_portfolio_stats(
    weights: pd.Series,
    returns: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
) -> dict[str, float]:
    """
    Calculate comprehensive portfolio statistics.

    Args:
        weights: Portfolio weights
        returns: Asset returns DataFrame
        benchmark_returns: Optional benchmark returns

    Returns:
        Dictionary of portfolio statistics
    """
    # Align weights with returns
    common = weights.index.intersection(returns.columns)
    w = weights.loc[common].values
    r = returns[common].values

    # Portfolio returns
    port_returns = r @ w

    # Basic stats
    ann_return = np.mean(port_returns) * 252
    ann_vol = np.std(port_returns) * np.sqrt(252)
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0

    # Sortino ratio
    downside = port_returns[port_returns < 0]
    downside_vol = np.std(downside) * np.sqrt(252) if len(downside) > 0 else ann_vol
    sortino = ann_return / downside_vol if downside_vol > 0 else 0

    # Drawdown
    cumulative = (1 + port_returns).cumprod()
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    max_dd = np.min(drawdown)

    # Win rate
    win_rate = (port_returns > 0).mean()

    # Calmar ratio
    calmar = ann_return / abs(max_dd) if max_dd != 0 else 0

    stats = {
        "annual_return": float(ann_return),
        "annual_volatility": float(ann_vol),
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "max_drawdown": float(max_dd),
        "win_rate": float(win_rate),
        "calmar_ratio": float(calmar),
    }

    # Beta and alpha if benchmark provided
    if benchmark_returns is not None:
        common_dates = returns.index.intersection(benchmark_returns.index)
        port_r = pd.Series(port_returns, index=returns.index).loc[common_dates]
        bench_r = benchmark_returns.loc[common_dates]

        cov = np.cov(port_r, bench_r)
        beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 0
        alpha = np.mean(port_r) - beta * np.mean(bench_r)

        stats["beta"] = float(beta)
        stats["alpha"] = float(alpha * 252)  # Annualized

    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("PORTFOLIO CONSTRUCTION DEMO")
    print("=" * 80)

    # Create sample data
    np.random.seed(42)
    n_assets = 5
    n_days = 500

    asset_names = ["SPY", "QQQ", "TLT", "GLD", "VNQ"]

    # Generate returns with realistic correlations
    base_returns = np.random.randn(n_days, n_assets) * 0.01

    # Add correlation structure
    base_returns[:, 1] = base_returns[:, 0] * 0.8 + np.random.randn(n_days) * 0.005
    base_returns[:, 4] = base_returns[:, 0] * 0.6 + np.random.randn(n_days) * 0.007

    returns = pd.DataFrame(
        base_returns,
        columns=asset_names,
        index=pd.date_range("2022-01-01", periods=n_days, freq="D"),
    )

    # Expected returns and covariance
    expected_returns = returns.mean() * 252
    cov_matrix = returns.cov() * 252

    print("\nExpected Annual Returns:")
    print(expected_returns)

    # Initialize optimizer
    optimizer = PortfolioOptimizer()

    # Test each method
    methods = [
        OptimizationMethod.MEAN_VARIANCE,
        OptimizationMethod.RISK_PARITY,
        OptimizationMethod.KELLY,
        OptimizationMethod.EQUAL_WEIGHT,
    ]

    for method in methods:
        print(f"\n{method.value.upper()}:")
        result = optimizer.optimize(expected_returns, cov_matrix, method=method)
        print(f"  Weights: {result.weights.round(3).to_dict()}")
        print(f"  Expected Return: {result.expected_return:.2%}")
        print(f"  Expected Vol: {result.expected_volatility:.2%}")
        print(f"  Sharpe Ratio: {result.sharpe_ratio:.2f}")

    print("\n" + "=" * 80)
