"""
Portfolio Risk Layer - Position Sizing Aligned to $100/day Goal

This module provides portfolio-level risk management with position sizing
that aligns to the $100/day net income target.

Author: Trading System
Created: 2025-12-02
"""

import logging
from dataclasses import dataclass

from src.target_model import TARGET_DAILY_NET_INCOME, TargetModel, TargetModelConfig

logger = logging.getLogger(__name__)


@dataclass
class PositionSizingConfig:
    """Configuration for position sizing."""

    target_daily_net_income: float = TARGET_DAILY_NET_INCOME
    capital: float = 100000.0
    max_position_pct: float = 5.0  # Max 5% per position
    max_daily_exposure_pct: float = 20.0  # Max 20% total exposure
    volatility_scaling: bool = True
    kelly_fraction: float = 0.25  # Use 25% of Kelly criterion
    min_position_size: float = 10.0  # Minimum $10 position


@dataclass
class PositionSizingResult:
    """Result of position sizing calculation."""

    position_size: float
    notional_value: float
    num_shares: float
    reasoning: str
    risk_adjusted: bool


class PortfolioRiskLayer:
    """
    Portfolio-level risk management with $100/day target alignment.

    Provides:
    - Position sizing based on target daily income
    - Volatility-aware scaling
    - Exposure limits per strategy
    - Daily loss limits
    """

    def __init__(self, config: PositionSizingConfig | None = None):
        """
        Initialize portfolio risk layer.

        Args:
            config: Position sizing configuration
        """
        self.config = config or PositionSizingConfig()
        self.target_model = TargetModel(TargetModelConfig(capital=self.config.capital))

    def calculate_position_size(
        self,
        signal_strength: float,
        volatility: float,
        current_price: float,
        account_equity: float | None = None,
        current_exposure: float = 0.0,
    ) -> PositionSizingResult:
        """
        Calculate position size aligned to $100/day target.

        Args:
            signal_strength: Signal strength (0-1)
            volatility: Annual volatility (0-1, e.g., 0.15 = 15%)
            current_price: Current price per share
            account_equity: Current account equity (defaults to config.capital)
            current_exposure: Current total exposure in dollars

        Returns:
            PositionSizingResult with sizing details
        """
        equity = account_equity or self.config.capital
        metrics = self.target_model.compute_metrics()

        # Base position size from target daily income
        # If we need $100/day and expect 1% daily return, we need $10k exposure
        # But we scale by signal strength and risk
        target_daily_return_pct = metrics.required_daily_return_pct / 100
        base_exposure_needed = self.config.target_daily_net_income / target_daily_return_pct

        # Scale by signal strength
        signal_scaled_exposure = base_exposure_needed * signal_strength

        # Apply volatility scaling if enabled
        if self.config.volatility_scaling:
            # Reduce size for high volatility
            volatility_multiplier = 1.0 / (1.0 + volatility * 2)  # Reduce by up to 50% at 25% vol
            signal_scaled_exposure *= volatility_multiplier

        # Apply Kelly fraction
        kelly_size = signal_scaled_exposure * self.config.kelly_fraction

        # Apply position limits
        max_position_dollars = equity * (self.config.max_position_pct / 100)
        max_exposure_dollars = equity * (self.config.max_daily_exposure_pct / 100)
        remaining_exposure = max(0, max_exposure_dollars - current_exposure)

        # Final position size
        position_size = min(kelly_size, max_position_dollars, remaining_exposure)
        position_size = max(position_size, self.config.min_position_size)

        # Calculate shares
        num_shares = position_size / current_price if current_price > 0 else 0.0
        notional_value = num_shares * current_price

        # Generate reasoning
        reasoning_parts = [
            f"Target: ${self.config.target_daily_net_income:.2f}/day",
            f"Signal strength: {signal_strength:.2f}",
            f"Volatility: {volatility * 100:.1f}%",
        ]
        if self.config.volatility_scaling:
            reasoning_parts.append(f"Volatility scaling: {volatility_multiplier:.2f}x")
        reasoning = " | ".join(reasoning_parts)

        return PositionSizingResult(
            position_size=position_size,
            notional_value=notional_value,
            num_shares=num_shares,
            reasoning=reasoning,
            risk_adjusted=True,
        )

    def check_daily_loss_limit(
        self,
        daily_pnl: float,
        account_equity: float | None = None,
    ) -> tuple[bool, str]:
        """
        Check if daily loss exceeds limits.

        Args:
            daily_pnl: Today's P&L
            account_equity: Current account equity

        Returns:
            Tuple of (within_limit, message)
        """
        equity = account_equity or self.config.capital
        metrics = self.target_model.compute_metrics()

        daily_loss_pct = abs(daily_pnl) / equity * 100 if daily_pnl < 0 else 0.0
        max_daily_loss_pct = 2.0  # 2% max daily loss

        if daily_pnl < 0 and abs(daily_pnl) > metrics.worst_5day_drawdown_limit / 5:
            return (
                False,
                f"Daily loss ${abs(daily_pnl):.2f} exceeds 5-day drawdown limit",
            )

        if daily_loss_pct > max_daily_loss_pct:
            return (
                False,
                f"Daily loss {daily_loss_pct:.2f}% exceeds limit {max_daily_loss_pct:.2f}%",
            )

        return True, "Within daily loss limits"

    def allocate_across_strategies(
        self,
        strategy_signals: dict[str, dict[str, float]],
        account_equity: float | None = None,
    ) -> dict[str, PositionSizingResult]:
        """
        Allocate capital across multiple strategies.

        Args:
            strategy_signals: Dict mapping strategy name to signal dict
                Example: {
                    "core": {"signal_strength": 0.8, "volatility": 0.15, "price": 450.0},
                    "growth": {"signal_strength": 0.6, "volatility": 0.20, "price": 150.0},
                }
            account_equity: Current account equity

        Returns:
            Dict mapping strategy name to PositionSizingResult
        """
        equity = account_equity or self.config.capital
        allocations = {}

        # Calculate total signal strength
        total_signal = sum(s["signal_strength"] for s in strategy_signals.values())
        if total_signal == 0:
            logger.warning("No signals provided for allocation")
            return allocations

        # Allocate proportionally to signal strength
        current_exposure = 0.0
        for strategy_name, signal_dict in strategy_signals.items():
            signal_strength = signal_dict["signal_strength"]
            volatility = signal_dict.get("volatility", 0.15)
            price = signal_dict.get("price", 1.0)

            # Proportional allocation
            allocation_pct = signal_strength / total_signal if total_signal > 0 else 0.0
            max_allocation = equity * (self.config.max_daily_exposure_pct / 100) * allocation_pct

            result = self.calculate_position_size(
                signal_strength=signal_strength,
                volatility=volatility,
                current_price=price,
                account_equity=equity,
                current_exposure=current_exposure,
            )

            # Cap at proportional allocation
            if result.notional_value > max_allocation:
                result.notional_value = max_allocation
                result.position_size = max_allocation
                result.num_shares = max_allocation / price

            allocations[strategy_name] = result
            current_exposure += result.notional_value

        return allocations

    def get_target_alignment_report(
        self,
        current_avg_daily_pnl: float,
        current_sharpe: float,
    ) -> str:
        """
        Generate report on alignment with $100/day target.

        Args:
            current_avg_daily_pnl: Current average daily P&L
            current_sharpe: Current Sharpe ratio

        Returns:
            Formatted report string
        """
        analysis = self.target_model.analyze_backtest_vs_target(
            avg_daily_pnl=current_avg_daily_pnl,
            pct_days_above_target=50.0,  # Placeholder
            worst_5day_drawdown=0.0,  # Placeholder
            worst_20day_drawdown=0.0,  # Placeholder
            sharpe_ratio=current_sharpe,
        )

        return self.target_model.generate_target_report(analysis)
