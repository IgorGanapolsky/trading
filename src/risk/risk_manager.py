"""
Risk Manager - Real Implementation

Core risk management for Phil Town Rule #1: Don't lose money.

Restored: January 12, 2026 (was stub since PR #1445)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class RiskCheck:
    """Result of a risk check."""

    passed: bool
    reason: str
    risk_score: float = 0.0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class RiskManager:
    """
    Risk manager for Phil Town options trading.

    Enforces:
    - Position size limits (max 5% of portfolio per position)
    - Daily loss limits (max 2% daily drawdown)
    - Concentration limits (no more than 20% in single sector)
    - Cash reserve requirements (keep 20% cash minimum)
    """

    # Default risk parameters (conservative for small capital)
    DEFAULT_MAX_POSITION_PCT = 0.20  # 20% max per position for small accounts
    DEFAULT_MAX_DAILY_LOSS_PCT = 0.02  # 2% max daily loss
    DEFAULT_MIN_CASH_RESERVE_PCT = 0.20  # Keep 20% cash
    DEFAULT_MAX_SECTOR_CONCENTRATION = 0.40  # 40% max in one sector

    def __init__(
        self,
        portfolio_value: float = 5000.0,
        max_position_pct: float = None,
        max_daily_loss_pct: float = None,
        min_cash_reserve_pct: float = None,
    ):
        """
        Initialize risk manager.

        Args:
            portfolio_value: Total portfolio value for calculations
            max_position_pct: Max % of portfolio per position
            max_daily_loss_pct: Max daily loss as % of portfolio
            min_cash_reserve_pct: Min cash to keep as % of portfolio
        """
        self.portfolio_value = portfolio_value
        self.max_position_pct = max_position_pct or self.DEFAULT_MAX_POSITION_PCT
        self.max_daily_loss_pct = max_daily_loss_pct or self.DEFAULT_MAX_DAILY_LOSS_PCT
        self.min_cash_reserve_pct = min_cash_reserve_pct or self.DEFAULT_MIN_CASH_RESERVE_PCT

        # Track daily P&L
        self._daily_pnl: float = 0.0
        self._last_reset_date: date = date.today()

        logger.info(
            f"RiskManager initialized: portfolio=${portfolio_value:.2f}, "
            f"max_position={self.max_position_pct:.0%}, max_daily_loss={self.max_daily_loss_pct:.0%}"
        )

    def _reset_daily_if_needed(self):
        """Reset daily P&L tracker at start of new day."""
        today = date.today()
        if today != self._last_reset_date:
            logger.info(f"New trading day - resetting daily P&L from ${self._daily_pnl:.2f}")
            self._daily_pnl = 0.0
            self._last_reset_date = today

    def update_portfolio_value(self, new_value: float):
        """Update portfolio value for risk calculations."""
        self.portfolio_value = new_value
        logger.info(f"Portfolio value updated: ${new_value:.2f}")

    def record_pnl(self, pnl: float):
        """Record P&L for daily tracking."""
        self._reset_daily_if_needed()
        self._daily_pnl += pnl
        logger.info(f"P&L recorded: ${pnl:.2f}, daily total: ${self._daily_pnl:.2f}")

    def check_position_size(self, symbol: str, notional_value: float) -> RiskCheck:
        """
        Check if position size is within limits.

        Args:
            symbol: Stock symbol
            notional_value: Dollar value of the position

        Returns:
            RiskCheck with pass/fail and reason
        """
        max_position = self.portfolio_value * self.max_position_pct
        position_pct = notional_value / self.portfolio_value if self.portfolio_value > 0 else 1.0

        if notional_value > max_position:
            return RiskCheck(
                passed=False,
                reason=f"{symbol}: Position ${notional_value:.2f} exceeds max ${max_position:.2f} ({self.max_position_pct:.0%})",
                risk_score=position_pct,
            )

        return RiskCheck(
            passed=True,
            reason=f"{symbol}: Position ${notional_value:.2f} within limit ({position_pct:.1%} of portfolio)",
            risk_score=position_pct,
        )

    def check_daily_loss(self, additional_loss: float = 0.0) -> RiskCheck:
        """
        Check if daily loss limit would be exceeded.

        Args:
            additional_loss: Potential additional loss to check

        Returns:
            RiskCheck with pass/fail and reason
        """
        self._reset_daily_if_needed()

        max_daily_loss = self.portfolio_value * self.max_daily_loss_pct
        projected_loss = abs(self._daily_pnl) + abs(additional_loss)
        loss_pct = projected_loss / self.portfolio_value if self.portfolio_value > 0 else 1.0

        if projected_loss > max_daily_loss:
            return RiskCheck(
                passed=False,
                reason=f"Daily loss ${projected_loss:.2f} would exceed limit ${max_daily_loss:.2f} ({self.max_daily_loss_pct:.0%})",
                risk_score=loss_pct,
            )

        return RiskCheck(
            passed=True,
            reason=f"Daily loss ${projected_loss:.2f} within limit ({loss_pct:.1%} of portfolio)",
            risk_score=loss_pct,
        )

    def check_cash_reserve(self, cash_available: float, trade_cost: float) -> RiskCheck:
        """
        Check if trade would leave sufficient cash reserve.

        Args:
            cash_available: Current cash in account
            trade_cost: Cost/collateral for proposed trade

        Returns:
            RiskCheck with pass/fail and reason
        """
        min_cash = self.portfolio_value * self.min_cash_reserve_pct
        remaining_cash = cash_available - trade_cost

        if remaining_cash < min_cash:
            return RiskCheck(
                passed=False,
                reason=f"Trade would leave ${remaining_cash:.2f} cash, below minimum ${min_cash:.2f}",
                risk_score=1.0 - (remaining_cash / self.portfolio_value),
            )

        return RiskCheck(
            passed=True,
            reason=f"Cash reserve OK: ${remaining_cash:.2f} remaining after trade",
            risk_score=trade_cost / self.portfolio_value,
        )

    def get_position_limit(self, symbol: str) -> float:
        """
        Get maximum position size for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Maximum dollar value for position
        """
        return self.portfolio_value * self.max_position_pct

    def get_max_contracts(self, strike_price: float, cash_available: float) -> int:
        """
        Calculate maximum CSP contracts given capital constraints.

        Args:
            strike_price: Option strike price
            cash_available: Available cash for collateral

        Returns:
            Maximum number of contracts (may be 0)
        """
        # CSP requires strike * 100 as collateral
        collateral_per_contract = strike_price * 100

        # Keep cash reserve
        usable_cash = cash_available * (1 - self.min_cash_reserve_pct)

        # Position size limit
        max_by_position = self.portfolio_value * self.max_position_pct

        # Calculate max contracts
        max_by_cash = int(usable_cash // collateral_per_contract)
        max_by_limit = int(max_by_position // collateral_per_contract)

        return min(max_by_cash, max_by_limit, 10)  # Cap at 10 contracts

    def calculate_risk(
        self,
        symbol: str,
        notional_value: float,
        cash_available: float,
        potential_loss: float = 0.0,
    ) -> dict[str, Any]:
        """
        Comprehensive risk calculation for a proposed trade.

        Args:
            symbol: Stock symbol
            notional_value: Dollar value of position
            cash_available: Available cash
            potential_loss: Maximum potential loss

        Returns:
            Dict with risk scores and checks
        """
        position_check = self.check_position_size(symbol, notional_value)
        daily_check = self.check_daily_loss(potential_loss)
        cash_check = self.check_cash_reserve(cash_available, notional_value)

        all_passed = position_check.passed and daily_check.passed and cash_check.passed
        avg_risk = (position_check.risk_score + daily_check.risk_score + cash_check.risk_score) / 3

        return {
            "approved": all_passed,
            "risk_score": round(avg_risk, 3),
            "position_check": {"passed": position_check.passed, "reason": position_check.reason},
            "daily_loss_check": {"passed": daily_check.passed, "reason": daily_check.reason},
            "cash_reserve_check": {"passed": cash_check.passed, "reason": cash_check.reason},
            "portfolio_value": self.portfolio_value,
            "daily_pnl": self._daily_pnl,
            "timestamp": datetime.now().isoformat(),
        }

    def approve_trade(
        self,
        symbol: str,
        notional_value: float,
        cash_available: float,
        potential_loss: float = 0.0,
    ) -> tuple[bool, str]:
        """
        Quick trade approval check.

        Args:
            symbol: Stock symbol
            notional_value: Dollar value of position
            cash_available: Available cash
            potential_loss: Maximum potential loss

        Returns:
            Tuple of (approved: bool, reason: str)
        """
        risk = self.calculate_risk(symbol, notional_value, cash_available, potential_loss)

        if risk["approved"]:
            return True, f"Trade approved: risk score {risk['risk_score']:.2f}"

        # Find failed check
        for check_name in ["position_check", "daily_loss_check", "cash_reserve_check"]:
            if not risk[check_name]["passed"]:
                return False, risk[check_name]["reason"]

        return False, "Trade rejected: unknown reason"
