"""
ATR-Based Exit Manager

Implements the top AI trader exit strategy:
- Take Profit: +3× ATR from entry
- Stop Loss: -2× ATR from entry
- Time Limit: 5 days max holding

Based on research from Renaissance, Two Sigma, and academic papers showing
that signal-based exits with ATR adjustment outperform time-based exits.

Author: Trading System
Created: 2025-12-10
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ExitSignal:
    """Exit signal with reason and details."""

    symbol: str
    should_exit: bool
    exit_type: str  # 'take_profit', 'stop_loss', 'time_limit', 'hold'
    reason: str
    entry_price: float
    current_price: float
    stop_loss_price: float
    take_profit_price: float
    days_held: int
    pnl_pct: float
    urgency: str  # 'immediate', 'end_of_day', 'none'


class ATRExitManager:
    """
    Manages position exits using ATR-based stop loss and take profit levels.

    Based on research findings:
    - Renaissance: 50.75% win rate → 66% returns (risk-reward matters more than win rate)
    - Top quant funds: 1-5 day holding periods, signal-based exits
    - Academic research: ATR adapts to volatility, reduces whipsaws

    Exit Rules:
    1. Take Profit: +3× ATR (lock in wins)
    2. Stop Loss: -2× ATR (cut losses)
    3. Time Limit: 5 days max (force data generation for win rate)
    """

    # Default ATR values for common assets (14-day estimates)
    DEFAULT_ATR = {
        # Equity ETFs
        "SPY": 8.50,  # S&P 500 (~1.2% daily)
        "QQQ": 12.00,  # Nasdaq (~2% daily)
        "IWM": 4.50,  # Russell 2000
        "VOO": 8.50,  # Vanguard S&P 500
        "VTI": 5.50,  # Total Market
        # Bond ETFs (lower volatility)
        "BIL": 0.02,  # T-Bills (very stable)
        "SHY": 0.08,  # Short-term treasuries
        "IEF": 0.45,  # Intermediate treasuries
        "TLT": 1.20,  # Long-term treasuries
        "BND": 0.35,  # Total Bond
    }

    def __init__(
        self,
        stop_loss_atr_mult: float = 2.0,
        take_profit_atr_mult: float = 3.0,
        max_holding_days: int = 5,
        default_atr_pct: float = 0.015,  # 1.5% if unknown
    ):
        """
        Initialize ATR Exit Manager.

        Args:
            stop_loss_atr_mult: ATR multiplier for stop loss (default: 2×)
            take_profit_atr_mult: ATR multiplier for take profit (default: 3×)
            max_holding_days: Maximum days to hold position (default: 5)
            default_atr_pct: Default ATR as % of price if unknown (default: 1.5%)
        """
        self.stop_loss_mult = stop_loss_atr_mult
        self.take_profit_mult = take_profit_atr_mult
        self.max_holding_days = max_holding_days
        self.default_atr_pct = default_atr_pct

        logger.info(
            f"ATR Exit Manager initialized: "
            f"SL={stop_loss_atr_mult}×ATR, TP={take_profit_atr_mult}×ATR, "
            f"MaxDays={max_holding_days}"
        )

    def get_atr(self, symbol: str, hist: pd.DataFrame | None = None) -> float:
        """
        Get ATR for a symbol.

        Args:
            symbol: Ticker symbol
            hist: Optional historical OHLC data for calculation

        Returns:
            ATR value in dollars
        """
        # If we have historical data, calculate actual ATR
        if hist is not None and len(hist) >= 14:
            try:
                return self._calculate_atr(hist, period=14)
            except Exception as e:
                logger.warning(f"ATR calculation failed for {symbol}: {e}")

        # Use default ATR if available
        if symbol.upper() in self.DEFAULT_ATR:
            return self.DEFAULT_ATR[symbol.upper()]

        # Fallback: estimate as percentage of typical price
        # This is a rough estimate - better to use actual data
        logger.warning(f"Using estimated ATR for {symbol}")
        return 100.0 * self.default_atr_pct  # Assume $100 price

    def _calculate_atr(self, hist: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range from OHLC data."""
        high = hist["High"].values
        low = hist["Low"].values
        close = hist["Close"].values

        # True Range components
        tr1 = high - low
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])

        # True Range (max of the three)
        tr = np.maximum(tr1[1:], np.maximum(tr2, tr3))

        # ATR is the moving average of TR
        atr = np.mean(tr[-period:])

        return float(atr)

    def calculate_exit_levels(
        self,
        symbol: str,
        entry_price: float,
        side: str = "long",
        hist: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        """
        Calculate stop loss and take profit levels.

        Args:
            symbol: Ticker symbol
            entry_price: Position entry price
            side: 'long' or 'short'
            hist: Optional historical data for ATR calculation

        Returns:
            Dict with stop_loss, take_profit, and atr values
        """
        atr = self.get_atr(symbol, hist)

        if side.lower() == "long":
            stop_loss = entry_price - (self.stop_loss_mult * atr)
            take_profit = entry_price + (self.take_profit_mult * atr)
        else:  # short
            stop_loss = entry_price + (self.stop_loss_mult * atr)
            take_profit = entry_price - (self.take_profit_mult * atr)

        return {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "atr": atr,
            "stop_distance_pct": (self.stop_loss_mult * atr / entry_price) * 100,
            "target_distance_pct": (self.take_profit_mult * atr / entry_price) * 100,
        }

    def check_exit(
        self,
        symbol: str,
        entry_price: float,
        current_price: float,
        entry_date: datetime | str,
        side: str = "long",
        hist: pd.DataFrame | None = None,
    ) -> ExitSignal:
        """
        Check if position should be exited.

        Args:
            symbol: Ticker symbol
            entry_price: Position entry price
            current_price: Current market price
            entry_date: When position was opened
            side: 'long' or 'short'
            hist: Optional historical data for ATR calculation

        Returns:
            ExitSignal with recommendation
        """
        # Parse entry date
        if isinstance(entry_date, str):
            try:
                entry_date = datetime.fromisoformat(entry_date.replace("Z", "+00:00"))
                if entry_date.tzinfo:
                    entry_date = entry_date.replace(tzinfo=None)
            except Exception:
                entry_date = datetime.now() - timedelta(days=1)

        # Calculate days held
        days_held = (datetime.now() - entry_date).days

        # Calculate exit levels
        levels = self.calculate_exit_levels(symbol, entry_price, side, hist)
        stop_loss = levels["stop_loss"]
        take_profit = levels["take_profit"]
        levels["atr"]

        # Calculate P/L
        if side.lower() == "long":
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - current_price) / entry_price) * 100

        # Check exit conditions (in priority order)

        # 1. Stop Loss
        if (
            side.lower() == "long"
            and current_price <= stop_loss
            or side.lower() == "short"
            and current_price >= stop_loss
        ):
            return ExitSignal(
                symbol=symbol,
                should_exit=True,
                exit_type="stop_loss",
                reason=f"Price ${current_price:.2f} hit stop loss ${stop_loss:.2f} (2×ATR)",
                entry_price=entry_price,
                current_price=current_price,
                stop_loss_price=stop_loss,
                take_profit_price=take_profit,
                days_held=days_held,
                pnl_pct=pnl_pct,
                urgency="immediate",
            )

        # 2. Take Profit
        if (
            side.lower() == "long"
            and current_price >= take_profit
            or side.lower() == "short"
            and current_price <= take_profit
        ):
            return ExitSignal(
                symbol=symbol,
                should_exit=True,
                exit_type="take_profit",
                reason=f"Price ${current_price:.2f} hit take profit ${take_profit:.2f} (3×ATR)",
                entry_price=entry_price,
                current_price=current_price,
                stop_loss_price=stop_loss,
                take_profit_price=take_profit,
                days_held=days_held,
                pnl_pct=pnl_pct,
                urgency="immediate",
            )

        # 3. Time Limit
        if days_held >= self.max_holding_days:
            return ExitSignal(
                symbol=symbol,
                should_exit=True,
                exit_type="time_limit",
                reason=f"Position held {days_held} days (max {self.max_holding_days})",
                entry_price=entry_price,
                current_price=current_price,
                stop_loss_price=stop_loss,
                take_profit_price=take_profit,
                days_held=days_held,
                pnl_pct=pnl_pct,
                urgency="end_of_day",
            )

        # 4. Hold
        return ExitSignal(
            symbol=symbol,
            should_exit=False,
            exit_type="hold",
            reason=f"Within targets (SL: ${stop_loss:.2f}, TP: ${take_profit:.2f}, Days: {days_held}/{self.max_holding_days})",
            entry_price=entry_price,
            current_price=current_price,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            days_held=days_held,
            pnl_pct=pnl_pct,
            urgency="none",
        )

    def check_all_positions(
        self,
        positions: list[dict[str, Any]],
    ) -> list[ExitSignal]:
        """
        Check all positions for exit signals.

        Args:
            positions: List of position dicts with symbol, entry_price,
                      current_price, entry_date fields

        Returns:
            List of ExitSignals for all positions
        """
        signals = []

        for pos in positions:
            signal = self.check_exit(
                symbol=pos["symbol"],
                entry_price=pos.get("entry_price", pos.get("avg_cost", 0)),
                current_price=pos["current_price"],
                entry_date=pos.get("entry_date", datetime.now()),
                side=pos.get("side", "long"),
            )
            signals.append(signal)

        return signals

    def generate_exit_report(self, signals: list[ExitSignal]) -> str:
        """Generate human-readable exit report."""
        report = []
        report.append("=" * 70)
        report.append("ATR EXIT MANAGER REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append("=" * 70)

        # Count by type
        exits_needed = [s for s in signals if s.should_exit]
        holds = [s for s in signals if not s.should_exit]

        report.append(f"\nPositions to EXIT: {len(exits_needed)}")
        report.append(f"Positions to HOLD: {len(holds)}")

        if exits_needed:
            report.append("\n" + "-" * 70)
            report.append("🚨 EXIT REQUIRED")
            report.append("-" * 70)

            for s in exits_needed:
                emoji = (
                    "🔴"
                    if s.exit_type == "stop_loss"
                    else "🟢"
                    if s.exit_type == "take_profit"
                    else "⏰"
                )
                report.append(f"\n{emoji} {s.symbol} - {s.exit_type.upper()}")
                report.append(f"   Reason: {s.reason}")
                report.append(f"   P/L: {s.pnl_pct:+.2f}%")
                report.append(f"   Urgency: {s.urgency.upper()}")

        if holds:
            report.append("\n" + "-" * 70)
            report.append("⚪ HOLDING")
            report.append("-" * 70)

            for s in holds:
                report.append(f"\n{s.symbol}:")
                report.append(f"   Days: {s.days_held}/{self.max_holding_days}")
                report.append(f"   P/L: {s.pnl_pct:+.2f}%")
                report.append(
                    f"   Stop: ${s.stop_loss_price:.2f} | Target: ${s.take_profit_price:.2f}"
                )

        report.append("\n" + "=" * 70)

        return "\n".join(report)


def get_exit_manager() -> ATRExitManager:
    """Get default exit manager with env overrides."""
    return ATRExitManager(
        stop_loss_atr_mult=float(os.getenv("EXIT_STOP_LOSS_ATR", "2.0")),
        take_profit_atr_mult=float(os.getenv("EXIT_TAKE_PROFIT_ATR", "3.0")),
        max_holding_days=int(os.getenv("EXIT_MAX_DAYS", "5")),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Demo with sample positions
    manager = ATRExitManager()

    # Sample positions from system state
    positions = [
        {
            "symbol": "SPY",
            "entry_price": 686.38,
            "current_price": 685.69,
            "entry_date": "2025-12-07T18:16:23",
        },
        {
            "symbol": "BIL",
            "entry_price": 91.53,
            "current_price": 91.52,
            "entry_date": "2025-12-07T18:16:23",
        },
    ]

    signals = manager.check_all_positions(positions)
    print(manager.generate_exit_report(signals))
