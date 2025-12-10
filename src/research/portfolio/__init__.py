"""
Portfolio optimization and construction module.

Provides position sizing algorithms and portfolio construction methods:
- Mean-variance optimization (Markowitz)
- Risk parity (equal risk contribution)
- Hierarchical Risk Parity (HRP)
- Kelly Criterion sizing
- Volatility scaling
- Constraints: sector caps, concentration limits, turnover
"""

from src.research.portfolio.kelly import (
    calculate_half_kelly,
    calculate_kelly_fraction,
)
from src.research.portfolio.optimizer import (
    OptimizationMethod,
    OptimizationResult,
    PortfolioConstraints,
    PortfolioOptimizer,
)
from src.research.portfolio.risk_parity import (
    calculate_equal_risk_contribution,
    calculate_risk_parity_weights,
)


# Placeholder result type for compatibility
class PortfolioResult(dict):
    """Placeholder portfolio result container."""


def calculate_portfolio_stats(weights, returns=None):
    """Placeholder portfolio statistics calculator."""
    return {"weights": weights, "returns": returns}


__all__ = [
    "PortfolioOptimizer",
    "OptimizationMethod",
    "PortfolioConstraints",
    "OptimizationResult",
    "PortfolioResult",
    "calculate_risk_parity_weights",
    "calculate_equal_risk_contribution",
    "calculate_kelly_fraction",
    "calculate_half_kelly",
    "calculate_portfolio_stats",
]
