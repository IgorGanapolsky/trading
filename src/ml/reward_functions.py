"""
World-Class Risk-Adjusted Reward Functions for RL Trading
Based on 2024-2025 research on risk-aware reinforcement learning.
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class RiskAdjustedReward:
    """
    Multi-objective risk-adjusted reward function for RL trading.

    Components:
    1. Annualized Return (35% weight) - Prioritize returns
    2. Downside Risk Penalty (25% weight) - Minimize volatility of losses
    3. Sharpe Ratio (20% weight) - Risk-adjusted performance
    4. Drawdown Penalty (15% weight) - Heavy penalty for excessive drawdowns
    5. Transaction Cost Penalty (5% weight) - Discourage overtrading
    """

    def __init__(
        self,
        return_weight: float = 0.35,
        risk_weight: float = 0.25,
        sharpe_weight: float = 0.20,
        drawdown_weight: float = 0.15,
        cost_weight: float = 0.05,
        risk_free_rate: float = 0.02,  # 2% annual risk-free rate
        transaction_cost: float = 0.001,  # 0.1% per trade
    ):
        self.return_weight = return_weight
        self.risk_weight = risk_weight
        self.sharpe_weight = sharpe_weight
        self.drawdown_weight = drawdown_weight
        self.cost_weight = cost_weight
        self.risk_free_rate = risk_free_rate
        self.transaction_cost = transaction_cost

    def calculate(
        self,
        returns: float,
        volatility: float | None = None,
        drawdown: float | None = None,
        sharpe_ratio: float | None = None,
        holding_period_days: int = 1,
        transaction_costs: float | None = None,
        returns_series: np.ndarray | None = None,
        benchmark_returns: float | None = None,
    ) -> float:
        """
        Calculate risk-adjusted reward from trade result.

        Args:
            returns: Trade return (as decimal, e.g., 0.05 for 5%)
            volatility: Volatility of returns (if None, estimated from returns_series)
            drawdown: Maximum drawdown during trade (as decimal)
            sharpe_ratio: Sharpe ratio (if None, calculated from returns and volatility)
            holding_period_days: Number of days trade was held
            transaction_costs: Transaction costs (if None, uses default)
            returns_series: Series of returns for calculating statistics
            benchmark_returns: Benchmark return for comparison

        Returns:
            Risk-adjusted reward value (normalized to [-1, 1])
        """
        # Component 1: Annualized Return (35% weight)
        if holding_period_days > 0:
            annualized_return = (1 + returns) ** (252 / holding_period_days) - 1
        else:
            annualized_return = returns * 252  # Approximate

        return_component = self.return_weight * annualized_return

        # Component 2: Downside Risk Penalty (25% weight)
        if returns_series is not None and len(returns_series) > 0:
            negative_returns = returns_series[returns_series < 0]
            downside_risk = np.std(negative_returns) if len(negative_returns) > 0 else 0
        elif volatility is not None:
            # Estimate downside risk as volatility when returns are negative
            downside_risk = volatility * (1.0 if returns < 0 else 0.5)
        else:
            downside_risk = abs(returns) * 0.5  # Fallback estimate

        # Penalize downside risk (higher risk = lower reward)
        risk_component = -self.risk_weight * downside_risk * 10  # Scale for impact

        # Component 3: Sharpe Ratio (20% weight)
        if sharpe_ratio is None:
            if volatility is not None and volatility > 0:
                sharpe_ratio = (annualized_return - self.risk_free_rate) / volatility
            elif returns_series is not None and len(returns_series) > 0:
                vol = np.std(returns_series)
                if vol > 0:
                    sharpe_ratio = (np.mean(returns_series) * 252 - self.risk_free_rate) / (
                        vol * np.sqrt(252)
                    )
                else:
                    sharpe_ratio = 0.0
            else:
                sharpe_ratio = 0.0

        # Normalize Sharpe (typical range: -2 to 3, target: >1.0)
        sharpe_component = self.sharpe_weight * np.clip(sharpe_ratio / 2.0, -1.0, 1.0)

        # Component 4: Drawdown Penalty (15% weight)
        if drawdown is None:
            drawdown = abs(returns) if returns < 0 else 0.0

        if drawdown > 0.05:  # 5% threshold
            # Heavy penalty for drawdowns > 5%
            drawdown_penalty = -self.drawdown_weight * (drawdown - 0.05) * 20
        else:
            # Small bonus for low drawdown
            drawdown_penalty = self.drawdown_weight * (0.05 - drawdown) * 2

        # Component 5: Transaction Cost Penalty (5% weight)
        if transaction_costs is None:
            transaction_costs = self.transaction_cost

        cost_component = -self.cost_weight * transaction_costs * 100  # Scale for impact

        # Component 6: Benchmark Comparison (bonus if beating benchmark)
        if benchmark_returns is not None:
            diff_return = returns - benchmark_returns
            benchmark_bonus = 0.05 * np.clip(diff_return * 10, -1.0, 1.0)
        else:
            benchmark_bonus = 0.0

        # Composite reward
        reward = (
            return_component
            + risk_component
            + sharpe_component
            + drawdown_penalty
            + cost_component
            + benchmark_bonus
        )

        # Normalize to [-1, 1] range
        # Typical reward range: -0.5 to 0.5, so we scale by 2
        reward = np.clip(reward * 2.0, -1.0, 1.0)

        return reward

    def calculate_from_trade_result(
        self,
        trade_result: dict[str, Any],
        market_state: dict[str, Any] | None = None,
    ) -> float:
        """
        Calculate reward from trade result dictionary.

        Args:
            trade_result: Dictionary with trade information:
                - pl: Profit/loss in dollars
                - pl_pct: Profit/loss as percentage
                - holding_period_days: Days trade was held
                - max_drawdown: Maximum drawdown during trade
                - win_rate: Historical win rate
                - returns_series: Series of returns (optional)
            market_state: Optional market state with:
                - volatility: Market volatility
                - sharpe_ratio: Current Sharpe ratio
                - benchmark_return: Benchmark return

        Returns:
            Risk-adjusted reward value
        """
        pl_pct = trade_result.get("pl_pct", 0.0)
        holding_period = trade_result.get("holding_period_days", 1)
        drawdown = trade_result.get("max_drawdown", abs(pl_pct) if pl_pct < 0 else 0.0)
        returns_series = trade_result.get("returns_series")

        # Extract from market state if available
        volatility = None
        sharpe_ratio = None
        benchmark_return = None

        if market_state:
            volatility = market_state.get("volatility")
            sharpe_ratio = market_state.get("sharpe_ratio")
            benchmark_return = market_state.get("benchmark_return")

        return self.calculate(
            returns=pl_pct,
            volatility=volatility,
            drawdown=drawdown,
            sharpe_ratio=sharpe_ratio,
            holding_period_days=holding_period,
            returns_series=returns_series,
            benchmark_returns=benchmark_return,
        )


# Convenience function for backward compatibility
def calculate_risk_adjusted_reward(
    trade_result: dict[str, Any], market_state: dict[str, Any] | None = None
) -> float:
    """
    Calculate world-class risk-adjusted reward from trade result.

    This is the recommended reward function for RL trading systems.
    """
    reward_calculator = RiskAdjustedReward()
    return reward_calculator.calculate_from_trade_result(trade_result, market_state)
