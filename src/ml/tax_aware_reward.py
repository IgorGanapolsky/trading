"""
Tax-Aware Reward Function for RL Pipeline

Integrates tax optimization into reinforcement learning reward function.
This ensures the RL agent optimizes for after-tax returns, not just gross returns.
"""

import logging
from datetime import datetime
from typing import Any

from src.utils.tax_optimization import (
    LONG_TERM_THRESHOLD_DAYS,
    PDT_DAY_TRADE_THRESHOLD,
    TaxOptimizer,
)

logger = logging.getLogger(__name__)


class TaxAwareRewardFunction:
    """
    Tax-aware reward function for RL training.

    Adjusts rewards based on:
    - Holding period (penalize short-term, reward long-term)
    - Wash sale violations (penalize heavily)
    - Day trading frequency (penalize if approaching PDT threshold)
    - Tax efficiency (reward tax-optimized trades)
    """

    def __init__(self, tax_optimizer: TaxOptimizer | None = None):
        self.tax_optimizer = tax_optimizer or TaxOptimizer()

    def calculate_reward(
        self,
        trade_result: dict[str, Any],
        base_reward: float,
        current_equity: float,
    ) -> float:
        """
        Calculate tax-aware reward for RL agent.

        Args:
            trade_result: Dict with trade details:
                - symbol: str
                - entry_date: datetime
                - exit_date: datetime
                - entry_price: float
                - exit_price: float
                - quantity: float
                - pl: float (profit/loss)
                - trade_id: str
            base_reward: Base reward from RL agent (pre-tax)
            current_equity: Current account equity

        Returns:
            Tax-adjusted reward
        """
        # Extract trade details
        symbol = trade_result.get("symbol", "UNKNOWN")
        entry_date = trade_result.get("entry_date")
        exit_date = trade_result.get("exit_date")
        pl = trade_result.get("pl", 0.0)

        if not entry_date or not exit_date:
            logger.warning("Missing entry/exit dates for tax calculation")
            return base_reward

        # Calculate holding period
        if isinstance(entry_date, str):
            entry_date = datetime.fromisoformat(entry_date.replace("Z", "+00:00"))
        if isinstance(exit_date, str):
            exit_date = datetime.fromisoformat(exit_date.replace("Z", "+00:00"))

        holding_period_days = (exit_date - entry_date).days
        is_long_term = holding_period_days >= LONG_TERM_THRESHOLD_DAYS
        is_day_trade = holding_period_days == 0

        # Start with base reward
        adjusted_reward = base_reward

        # Tax adjustment based on holding period
        if pl > 0:  # Profitable trade
            if is_long_term:
                # Reward long-term gains (lower tax rate)
                tax_savings = pl * (0.37 - 0.20)  # 17% tax savings
                adjusted_reward += tax_savings * 0.5  # Scale down for RL stability
                logger.debug(f"Long-term gain bonus: {symbol} +${tax_savings:.2f} tax savings")
            elif holding_period_days < 30:
                # Penalize very short-term gains (highest tax rate)
                tax_penalty = pl * (0.37 - 0.20) * 0.3  # 17% tax penalty, scaled
                adjusted_reward -= tax_penalty
                logger.debug(f"Short-term gain penalty: {symbol} -${tax_penalty:.2f} tax penalty")
            elif holding_period_days < 90:
                # Moderate penalty for short-term gains
                tax_penalty = pl * (0.37 - 0.20) * 0.15
                adjusted_reward -= tax_penalty

        # Penalize day trading if approaching PDT threshold
        if is_day_trade:
            pdt_status = self.tax_optimizer.check_pdt_status(current_equity)
            if pdt_status["day_trades_count"] >= 3:
                # Heavy penalty if close to PDT threshold
                pdt_penalty = base_reward * 0.2  # 20% penalty
                adjusted_reward -= pdt_penalty
                logger.warning(f"Day trade penalty (PDT risk): {symbol} -${pdt_penalty:.2f}")
            elif pdt_status["day_trades_count"] >= 2:
                # Moderate penalty
                pdt_penalty = base_reward * 0.1
                adjusted_reward -= pdt_penalty

        # Check for wash sale (if we have trade history)
        if self.tax_optimizer.tax_events:
            # Simulate wash sale check
            recent_sales = [
                e
                for e in self.tax_optimizer.tax_events
                if e.symbol == symbol
                and (exit_date - e.sale_date).days <= 30
                and (exit_date - e.sale_date).days > 0
            ]
            if recent_sales and pl < 0:
                # Heavy penalty for wash sale losses (can't deduct)
                wash_sale_penalty = abs(pl) * 0.5  # 50% penalty
                adjusted_reward -= wash_sale_penalty
                logger.warning(
                    f"Wash sale penalty: {symbol} -${wash_sale_penalty:.2f} (loss disallowed)"
                )

        # Reward tax-loss harvesting (realizing losses to offset gains)
        if pl < 0 and len(self.tax_optimizer.tax_events) >= 3:
            # Check if we have gains to offset
            recent_gains = sum(
                e.gain_loss for e in self.tax_optimizer.tax_events[-10:] if e.gain_loss > 0
            )
            if recent_gains > abs(pl):
                # Small bonus for tax-loss harvesting
                tax_loss_bonus = abs(pl) * 0.1  # 10% bonus
                adjusted_reward += tax_loss_bonus
                logger.debug(f"Tax-loss harvesting bonus: {symbol} +${tax_loss_bonus:.2f}")

        return adjusted_reward

    def get_tax_constraints(self, current_equity: float) -> dict[str, Any]:
        """
        Get tax constraints for RL agent action space.

        Returns constraints that should be applied to prevent tax-inefficient actions.
        """
        pdt_status = self.tax_optimizer.check_pdt_status(current_equity)

        constraints = {
            "max_day_trades_per_5days": (
                PDT_DAY_TRADE_THRESHOLD - 1
                if not pdt_status["meets_equity_requirement"]
                else None  # No limit if equity requirement met
            ),
            "min_holding_period_days": (
                30  # Encourage holding >30 days for better tax treatment
                if pdt_status["day_trades_count"] >= 2
                else 0  # No constraint if not approaching PDT
            ),
            "wash_sale_symbols": [
                e.symbol
                for e in self.tax_optimizer.tax_events
                if (datetime.now() - e.sale_date).days <= 30
            ],
        }

        return constraints
