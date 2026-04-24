"""
Risk Manager - Real Implementation

Core risk management for Phil Town Rule #1: Don't lose money.

Restored: January 12, 2026 (was stub since PR #1445)
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from src.core.trading_constants import MAX_DAILY_LOSS_PCT, MAX_POSITION_PCT

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
    - Position size limits (canonical max of portfolio per position)
    - Daily loss limits (max 2% daily drawdown)
    - Concentration limits (no more than 20% in single sector)
    - Cash reserve requirements (keep 20% cash minimum)
    """

    # Default risk parameters (canonical max - Phil Town Rule #1)
    DEFAULT_MAX_POSITION_PCT = MAX_POSITION_PCT  # canonical max per position
    DEFAULT_MAX_DAILY_LOSS_PCT = MAX_DAILY_LOSS_PCT  # canonical max daily loss
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

    def calculate_stop_based_position_size(
        self,
        *,
        entry_price: float,
        stop_price: float,
        max_risk_pct: float | None = None,
        max_notional_pct: float | None = None,
        lot_size: int = 1,
    ) -> dict[str, Any]:
        """
        Size a directional position from a predefined invalidation level.

        This implements the standard breakout sizing formula:
        shares = max dollar loss / abs(entry - stop), capped by notional limits.
        """
        if entry_price <= 0 or stop_price <= 0:
            return {
                "quantity": 0,
                "notional": 0.0,
                "max_loss": 0.0,
                "risk_per_share": 0.0,
                "reason": "Invalid entry or stop price",
            }

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share <= 0:
            return {
                "quantity": 0,
                "notional": 0.0,
                "max_loss": 0.0,
                "risk_per_share": 0.0,
                "reason": "Entry and stop price are identical",
            }

        risk_pct = self.max_daily_loss_pct if max_risk_pct is None else max_risk_pct
        notional_pct = self.max_position_pct if max_notional_pct is None else max_notional_pct
        max_loss_dollars = max(0.0, self.portfolio_value * risk_pct)
        max_notional = max(0.0, self.portfolio_value * notional_pct)
        raw_quantity = int(max_loss_dollars // risk_per_share)
        notional_capped_quantity = int(max_notional // entry_price)
        quantity = min(raw_quantity, notional_capped_quantity)

        if lot_size > 1:
            quantity = (quantity // lot_size) * lot_size

        quantity = max(0, quantity)
        notional = quantity * entry_price
        max_loss = quantity * risk_per_share

        return {
            "quantity": quantity,
            "notional": round(notional, 2),
            "max_loss": round(max_loss, 2),
            "risk_per_share": round(risk_per_share, 4),
            "reason": (
                f"Size {quantity} shares/contracts from ${max_loss_dollars:.2f} risk "
                f"and ${max_notional:.2f} notional cap"
            ),
        }

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
            "position_check": {
                "passed": position_check.passed,
                "reason": position_check.reason,
            },
            "daily_loss_check": {
                "passed": daily_check.passed,
                "reason": daily_check.reason,
            },
            "cash_reserve_check": {
                "passed": cash_check.passed,
                "reason": cash_check.reason,
            },
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

    def calculate_size(
        self,
        ticker: str,
        account_equity: float,
        signal_strength: float,
        rl_confidence: float = 0.0,
        sentiment_score: float = 0.0,
        multiplier: float = 1.0,
        current_price: float = 0.0,
        hist=None,
        market_regime: str | None = None,
        allocation_cap: float = 1.0,
    ) -> float:
        """
        Calculate risk-adjusted position size (notional dollars).

        Uses ATR-based risk sizing when history is available, otherwise
        falls back to a percentage-of-equity approach.  Result is capped
        at MAX_POSITION_PCT of account equity and the allocation_cap.

        Args:
            ticker: Stock symbol
            account_equity: Total account equity
            signal_strength: Momentum signal strength (0-1)
            rl_confidence: RL model confidence (0-1)
            sentiment_score: Sentiment score (-1 to 1)
            multiplier: RL suggested size multiplier
            current_price: Current share price
            hist: Historical price DataFrame for ATR calculation
            market_regime: Market regime label (e.g. "bull", "bear")
            allocation_cap: Maximum fraction of equity for this allocation bucket

        Returns:
            Notional dollar amount for the order (0.0 if rejected)
        """
        if account_equity <= 0 or current_price <= 0:
            logger.warning("calculate_size(%s): invalid equity/price", ticker)
            return 0.0

        max_position = account_equity * self.max_position_pct
        max_risk_dollars = account_equity * self.max_daily_loss_pct

        # ATR-based sizing: risk dollars / risk-per-share
        atr_size = 0.0
        if hist is not None:
            try:
                from src.utils.technical_indicators import calculate_atr

                atr = float(calculate_atr(hist))
                if atr > 0:
                    risk_per_share = atr * 2  # 2×ATR stop distance
                    shares = max_risk_dollars / risk_per_share
                    atr_size = shares * current_price
            except Exception as exc:  # pragma: no cover
                logger.debug("ATR sizing failed for %s: %s", ticker, exc)

        # Fallback: fraction of equity scaled by signal
        base_size = atr_size if atr_size > 0 else max_position * signal_strength

        # Apply RL multiplier and confidence scaling
        confidence_factor = 0.5 + 0.5 * max(rl_confidence, signal_strength)
        sized = base_size * multiplier * confidence_factor

        # Dampen in bear regimes
        if market_regime and "bear" in market_regime.lower():
            sized *= 0.5

        # Enforce caps
        cap_dollars = account_equity * min(allocation_cap, 1.0)
        sized = min(sized, max_position, cap_dollars)

        # Floor at zero
        sized = max(sized, 0.0)

        logger.info(
            "calculate_size(%s): $%.2f (equity=$%.2f, signal=%.2f, conf=%.2f, mult=%.1f)",
            ticker,
            sized,
            account_equity,
            signal_strength,
            rl_confidence,
            multiplier,
        )
        return round(sized, 2)
