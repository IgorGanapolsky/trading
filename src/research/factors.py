"""
Factor Analysis and Exposure Tracking

This module provides factor analysis tools for understanding portfolio exposures
and risk decomposition:

1. Factor Exposure Calculation: Market, size, value, momentum exposures
2. Factor Attribution: Decompose returns into factor contributions
3. Risk Factor Monitoring: Track factor exposures over time
4. PCA-based Factor Discovery: Data-driven factor identification

Reference: Barra, Fama-French, Carhart models

Author: Trading System
Created: 2025-12-02
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class FactorExposure:
    """Factor exposure results."""

    factor_name: str
    exposure: float  # Beta to factor
    t_stat: float  # Statistical significance
    p_value: float
    r_squared: float  # Explained variance
    confidence_interval: tuple[float, float]

    def is_significant(self, alpha: float = 0.05) -> bool:
        return self.p_value < alpha


@dataclass
class FactorAttributionResult:
    """Factor attribution analysis result."""

    total_return: float
    factor_contributions: dict[str, float]
    alpha: float  # Unexplained return
    residual_return: float
    r_squared: float
    factors_used: list[str]
    period_start: str
    period_end: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_return": self.total_return,
            "factor_contributions": self.factor_contributions,
            "alpha": self.alpha,
            "residual_return": self.residual_return,
            "r_squared": self.r_squared,
            "factors_used": self.factors_used,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "metadata": self.metadata,
        }


class FactorModel:
    """
    Multi-factor model for risk and return attribution.

    Supports:
    - Market factor (CAPM beta)
    - Fama-French factors (Size, Value)
    - Momentum factor (Carhart)
    - Custom factors
    """

    # Standard factor names
    MARKET = "market"
    SIZE = "size"
    VALUE = "value"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    QUALITY = "quality"

    def __init__(self, risk_free_rate: float = 0.04):
        self.risk_free_rate = risk_free_rate
        self._factor_returns: pd.DataFrame | None = None

    def set_factor_returns(self, factor_returns: pd.DataFrame) -> None:
        """
        Set factor returns for the model.

        Args:
            factor_returns: DataFrame with factor returns (columns = factors)
        """
        self._factor_returns = factor_returns
        logger.info(f"Factor returns set: {list(factor_returns.columns)}")

    def calculate_exposures(
        self,
        portfolio_returns: pd.Series,
        factor_returns: pd.DataFrame | None = None,
    ) -> dict[str, FactorExposure]:
        """
        Calculate factor exposures (betas) for portfolio returns.

        Args:
            portfolio_returns: Series of portfolio returns
            factor_returns: DataFrame of factor returns (optional, uses stored)

        Returns:
            Dictionary of factor exposures
        """
        if factor_returns is None:
            factor_returns = self._factor_returns

        if factor_returns is None:
            raise ValueError("No factor returns available")

        # Align dates
        common_dates = portfolio_returns.index.intersection(factor_returns.index)
        port_ret = portfolio_returns.loc[common_dates].values
        factors = factor_returns.loc[common_dates]

        exposures = {}

        # Single factor regressions
        for factor_name in factors.columns:
            factor_ret = factors[factor_name].values

            # OLS regression
            X = np.column_stack([np.ones(len(port_ret)), factor_ret])
            try:
                beta, residuals, rank, s = np.linalg.lstsq(X, port_ret, rcond=None)
                _alpha, exposure = beta[0], beta[1]  # alpha unused in single-factor case

                # Statistics
                y_pred = X @ beta
                ss_res = np.sum((port_ret - y_pred) ** 2)
                ss_tot = np.sum((port_ret - np.mean(port_ret)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                # T-statistic
                n = len(port_ret)
                mse = ss_res / (n - 2) if n > 2 else 0
                var_beta = mse * np.linalg.inv(X.T @ X)[1, 1] if mse > 0 else 0
                se_beta = np.sqrt(var_beta) if var_beta > 0 else 1e-8
                t_stat = exposure / se_beta

                # P-value
                p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - 2))

                # Confidence interval
                ci = stats.t.interval(0.95, n - 2, loc=exposure, scale=se_beta)

                exposures[factor_name] = FactorExposure(
                    factor_name=factor_name,
                    exposure=float(exposure),
                    t_stat=float(t_stat),
                    p_value=float(p_value),
                    r_squared=float(r_squared),
                    confidence_interval=tuple(float(x) for x in ci),
                )

            except Exception as e:
                logger.warning(f"Failed to calculate exposure to {factor_name}: {e}")

        return exposures

    def calculate_multi_factor_exposure(
        self,
        portfolio_returns: pd.Series,
        factor_returns: pd.DataFrame | None = None,
    ) -> tuple[dict[str, float], float, float]:
        """
        Calculate exposures using multiple regression.

        Args:
            portfolio_returns: Series of portfolio returns
            factor_returns: DataFrame of factor returns

        Returns:
            Tuple of (exposures dict, alpha, r_squared)
        """
        if factor_returns is None:
            factor_returns = self._factor_returns

        if factor_returns is None:
            raise ValueError("No factor returns available")

        # Align dates
        common_dates = portfolio_returns.index.intersection(factor_returns.index)
        port_ret = portfolio_returns.loc[common_dates].values
        factors = factor_returns.loc[common_dates]

        # Multiple regression
        X = np.column_stack([np.ones(len(port_ret)), factors.values])

        try:
            beta, residuals, rank, s = np.linalg.lstsq(X, port_ret, rcond=None)

            alpha = float(beta[0]) * 252  # Annualize
            exposures = {col: float(beta[i + 1]) for i, col in enumerate(factors.columns)}

            # R-squared
            y_pred = X @ beta
            ss_res = np.sum((port_ret - y_pred) ** 2)
            ss_tot = np.sum((port_ret - np.mean(port_ret)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            return exposures, alpha, float(r_squared)

        except Exception as e:
            logger.error(f"Multi-factor regression failed: {e}")
            return {}, 0.0, 0.0

    def attribute_returns(
        self,
        portfolio_returns: pd.Series,
        factor_returns: pd.DataFrame | None = None,
    ) -> FactorAttributionResult:
        """
        Decompose portfolio returns into factor contributions.

        Args:
            portfolio_returns: Series of portfolio returns
            factor_returns: DataFrame of factor returns

        Returns:
            FactorAttributionResult with decomposition
        """
        if factor_returns is None:
            factor_returns = self._factor_returns

        if factor_returns is None:
            raise ValueError("No factor returns available")

        # Get exposures
        exposures, alpha, r_squared = self.calculate_multi_factor_exposure(
            portfolio_returns, factor_returns
        )

        # Align dates
        common_dates = portfolio_returns.index.intersection(factor_returns.index)
        factors = factor_returns.loc[common_dates]

        # Calculate factor contributions
        factor_contributions = {}
        for factor_name, exposure in exposures.items():
            factor_return = factors[factor_name].mean() * 252  # Annualize
            contribution = exposure * factor_return
            factor_contributions[factor_name] = float(contribution)

        # Total and residual
        total_return = float(portfolio_returns.mean() * 252)
        explained_return = sum(factor_contributions.values())
        residual_return = total_return - explained_return - alpha

        return FactorAttributionResult(
            total_return=total_return,
            factor_contributions=factor_contributions,
            alpha=alpha,
            residual_return=residual_return,
            r_squared=r_squared,
            factors_used=list(factors.columns),
            period_start=str(common_dates[0])[:10],
            period_end=str(common_dates[-1])[:10],
        )


class SyntheticFactorGenerator:
    """
    Generate synthetic factor returns from price data.

    Useful when actual factor data (e.g., from Ken French) is not available.
    """

    def __init__(self, lookback: int = 252):
        self.lookback = lookback

    def generate_market_factor(
        self,
        market_prices: pd.Series,
        risk_free_rate: float = 0.04,
    ) -> pd.Series:
        """Generate market excess return factor."""
        market_ret = market_prices.pct_change()
        rf_daily = risk_free_rate / 252
        excess_ret = market_ret - rf_daily
        excess_ret.name = FactorModel.MARKET
        return excess_ret

    def generate_momentum_factor(
        self,
        prices: pd.DataFrame,
        lookback: int = 252,
        skip: int = 21,
    ) -> pd.Series:
        """Generate cross-sectional momentum factor."""
        # Calculate momentum signal
        momentum = prices.pct_change(lookback - skip).shift(skip)

        # Long top quintile, short bottom quintile
        ranks = momentum.rank(axis=1, pct=True)
        long_mask = ranks > 0.8
        short_mask = ranks < 0.2

        returns = prices.pct_change()

        # Factor return = long portfolio - short portfolio
        long_ret = (returns * long_mask).mean(axis=1)
        short_ret = (returns * short_mask).mean(axis=1)
        factor_ret = long_ret - short_ret
        factor_ret.name = FactorModel.MOMENTUM

        return factor_ret

    def generate_volatility_factor(
        self,
        prices: pd.DataFrame,
        lookback: int = 60,
    ) -> pd.Series:
        """Generate low volatility factor (long low vol, short high vol)."""
        # Calculate volatility
        returns = prices.pct_change()
        vol = returns.rolling(lookback).std()

        # Long low vol, short high vol
        ranks = vol.rank(axis=1, pct=True)
        long_mask = ranks < 0.2  # Low vol
        short_mask = ranks > 0.8  # High vol

        long_ret = (returns * long_mask).mean(axis=1)
        short_ret = (returns * short_mask).mean(axis=1)
        factor_ret = long_ret - short_ret
        factor_ret.name = FactorModel.VOLATILITY

        return factor_ret

    def generate_all_factors(
        self,
        prices: pd.DataFrame,
        market_symbol: str = "SPY",
        risk_free_rate: float = 0.04,
    ) -> pd.DataFrame:
        """
        Generate all synthetic factors from price data.

        Args:
            prices: DataFrame of asset prices
            market_symbol: Symbol to use for market factor
            risk_free_rate: Annual risk-free rate

        Returns:
            DataFrame with factor returns
        """
        factors = {}

        # Market factor
        if market_symbol in prices.columns:
            factors[FactorModel.MARKET] = self.generate_market_factor(
                prices[market_symbol], risk_free_rate
            )

        # Momentum factor
        factors[FactorModel.MOMENTUM] = self.generate_momentum_factor(prices)

        # Volatility factor
        factors[FactorModel.VOLATILITY] = self.generate_volatility_factor(prices)

        return pd.DataFrame(factors).dropna()


class FactorRiskMonitor:
    """
    Monitor factor exposures over time for risk management.
    """

    def __init__(self, factor_model: FactorModel, lookback: int = 63):
        self.factor_model = factor_model
        self.lookback = lookback
        self._exposure_history: list[dict[str, Any]] = []

    def update(
        self,
        portfolio_returns: pd.Series,
        factor_returns: pd.DataFrame,
        timestamp: datetime | None = None,
    ) -> dict[str, FactorExposure]:
        """
        Update factor exposures with new data.

        Args:
            portfolio_returns: Recent portfolio returns
            factor_returns: Recent factor returns
            timestamp: Timestamp for this update

        Returns:
            Current factor exposures
        """
        # Use rolling window
        port_ret = portfolio_returns.tail(self.lookback)
        fact_ret = factor_returns.tail(self.lookback)

        exposures = self.factor_model.calculate_exposures(port_ret, fact_ret)

        # Record history
        self._exposure_history.append(
            {
                "timestamp": timestamp or datetime.now(),
                "exposures": {k: v.exposure for k, v in exposures.items()},
            }
        )

        return exposures

    def get_exposure_history(self, factor: str) -> pd.Series:
        """Get historical exposures for a factor."""
        data = [
            (h["timestamp"], h["exposures"].get(factor, np.nan)) for h in self._exposure_history
        ]
        return pd.Series(
            [d[1] for d in data],
            index=[d[0] for d in data],
            name=factor,
        )

    def check_exposure_limits(
        self,
        limits: dict[str, tuple[float, float]],
    ) -> list[dict[str, Any]]:
        """
        Check if current exposures breach limits.

        Args:
            limits: Dict of {factor: (min, max)} limits

        Returns:
            List of breached limits
        """
        if not self._exposure_history:
            return []

        current = self._exposure_history[-1]["exposures"]
        breaches = []

        for factor, (min_exp, max_exp) in limits.items():
            exp = current.get(factor)
            if exp is not None:
                if exp < min_exp:
                    breaches.append(
                        {
                            "factor": factor,
                            "exposure": exp,
                            "limit": min_exp,
                            "type": "below_minimum",
                        }
                    )
                elif exp > max_exp:
                    breaches.append(
                        {
                            "factor": factor,
                            "exposure": exp,
                            "limit": max_exp,
                            "type": "above_maximum",
                        }
                    )

        return breaches


class PCAFactorDiscovery:
    """
    Discover factors using Principal Component Analysis.
    """

    def __init__(self, n_components: int = 5):
        self.n_components = n_components
        self._components: np.ndarray | None = None
        self._explained_variance: np.ndarray | None = None
        self._mean: np.ndarray | None = None

    def fit(self, returns: pd.DataFrame) -> "PCAFactorDiscovery":
        """
        Fit PCA on returns data.

        Args:
            returns: DataFrame of asset returns

        Returns:
            Self
        """
        # Standardize
        self._mean = returns.mean().values
        std = returns.std().values
        standardized = (returns.values - self._mean) / (std + 1e-8)

        # PCA via SVD
        U, S, Vt = np.linalg.svd(standardized, full_matrices=False)

        # Store components
        self._components = Vt[: self.n_components].T
        self._explained_variance = (S**2)[: self.n_components] / (S**2).sum()
        self._feature_names = list(returns.columns)

        logger.info(
            f"PCA fit: {self.n_components} components explain "
            f"{self._explained_variance.sum():.1%} of variance"
        )

        return self

    def get_factor_returns(self, returns: pd.DataFrame) -> pd.DataFrame:
        """
        Project returns onto PCA factors.

        Args:
            returns: DataFrame of asset returns

        Returns:
            DataFrame of factor returns
        """
        if self._components is None:
            raise ValueError("Must call fit() first")

        standardized = (returns.values - self._mean) / (returns.std().values + 1e-8)
        factor_returns = standardized @ self._components

        return pd.DataFrame(
            factor_returns,
            index=returns.index,
            columns=[f"PC{i + 1}" for i in range(self.n_components)],
        )

    def get_factor_loadings(self) -> pd.DataFrame:
        """Get factor loadings (how each asset loads on each factor)."""
        if self._components is None:
            raise ValueError("Must call fit() first")

        return pd.DataFrame(
            self._components,
            index=self._feature_names,
            columns=[f"PC{i + 1}" for i in range(self.n_components)],
        )

    def get_explained_variance(self) -> pd.Series:
        """Get explained variance ratio for each component."""
        if self._explained_variance is None:
            raise ValueError("Must call fit() first")

        return pd.Series(
            self._explained_variance,
            index=[f"PC{i + 1}" for i in range(self.n_components)],
            name="explained_variance_ratio",
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("FACTOR ANALYSIS DEMO")
    print("=" * 80)

    # Create sample data
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=500, freq="D")

    # Generate correlated returns
    n_assets = 5
    asset_names = ["SPY", "QQQ", "IWM", "TLT", "GLD"]

    # Market factor
    market = np.random.randn(500) * 0.01

    # Generate asset returns with factor structure
    returns = pd.DataFrame(index=dates)
    returns["SPY"] = market + np.random.randn(500) * 0.005  # High beta
    returns["QQQ"] = 1.2 * market + np.random.randn(500) * 0.006  # Higher beta
    returns["IWM"] = 1.1 * market + np.random.randn(500) * 0.008  # Size tilt
    returns["TLT"] = -0.3 * market + np.random.randn(500) * 0.004  # Negative beta
    returns["GLD"] = 0.1 * market + np.random.randn(500) * 0.007  # Low beta

    # Create synthetic factors
    factor_gen = SyntheticFactorGenerator()
    prices = (1 + returns).cumprod() * 100

    factor_returns = factor_gen.generate_all_factors(prices, market_symbol="SPY")
    print(f"\nGenerated factors: {list(factor_returns.columns)}")

    # Create portfolio returns
    weights = pd.Series([0.4, 0.3, 0.1, 0.1, 0.1], index=asset_names)
    portfolio_returns = (returns * weights).sum(axis=1)

    # Factor model
    factor_model = FactorModel()
    factor_model.set_factor_returns(factor_returns)

    # Calculate exposures
    print("\nFactor Exposures:")
    exposures = factor_model.calculate_exposures(portfolio_returns)
    for name, exp in exposures.items():
        sig = "✓" if exp.is_significant() else "✗"
        print(f"  {name}: β={exp.exposure:.3f} (t={exp.t_stat:.2f}, p={exp.p_value:.4f}) {sig}")

    # Factor attribution
    print("\nFactor Attribution:")
    attribution = factor_model.attribute_returns(portfolio_returns)
    print(f"  Total Return: {attribution.total_return:.2%}")
    for factor, contrib in attribution.factor_contributions.items():
        print(f"  {factor} contribution: {contrib:.2%}")
    print(f"  Alpha: {attribution.alpha:.2%}")
    print(f"  R²: {attribution.r_squared:.1%}")

    # PCA factor discovery
    print("\nPCA Factor Discovery:")
    pca = PCAFactorDiscovery(n_components=3)
    pca.fit(returns)

    explained = pca.get_explained_variance()
    print(f"  Explained variance: {explained.to_dict()}")

    loadings = pca.get_factor_loadings()
    print("\n  Factor Loadings (PC1):")
    for asset, loading in loadings["PC1"].items():
        print(f"    {asset}: {loading:.3f}")

    print("\n" + "=" * 80)
