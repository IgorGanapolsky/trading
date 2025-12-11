"""
Position Manager - Active Position Management with Multi-Condition Exits

This module provides comprehensive position management to ensure trades are
actively closed rather than held indefinitely. It addresses the core problem
of positions never being closed (win rate = 0%).

Exit Conditions:
1. Take-Profit: Close when profit target reached (default: 3%)
2. Stop-Loss: Close when loss limit breached (default: 3%)
3. Time-Decay: Close after max holding period (default: 10 days)
4. Momentum Reversal: Close when MACD crosses bearish
5. ATR Stop: Dynamic stop based on volatility

Author: Claude CTO
Created: 2025-12-03
Updated: 2025-12-04 - Added persistence for position entry dates
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default path for persisting position state
DEFAULT_STATE_FILE = Path(__file__).parent.parent.parent / "data" / "system_state.json"

# Asset class definitions for exit threshold tuning
TREASURY_ETFS = {"BIL", "SHY", "IEF", "TLT", "GOVT", "ZROZ", "VGSH", "VGIT", "VGLT", "SCHO", "SCHR"}
CRYPTO_ASSETS = {"BTCUSD", "ETHUSD", "BTC", "ETH", "BITO", "GBTC", "ETHE"}
BOND_ETFS = {"AGG", "BND", "LQD", "HYG", "JNK", "TIP", "VCSH", "VCIT"}


class AssetClass(Enum):
    """Asset class for threshold selection."""

    TREASURY = "treasury"
    BOND = "bond"
    CRYPTO = "crypto"
    EQUITY = "equity"


def get_asset_class(symbol: str) -> AssetClass:
    """Determine asset class from symbol for appropriate exit thresholds."""
    symbol_upper = symbol.upper()
    if symbol_upper in TREASURY_ETFS:
        return AssetClass.TREASURY
    if symbol_upper in CRYPTO_ASSETS:
        return AssetClass.CRYPTO
    if symbol_upper in BOND_ETFS:
        return AssetClass.BOND
    return AssetClass.EQUITY


class ExitReason(Enum):
    """Enumeration of position exit reasons."""

    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    TIME_DECAY = "time_decay"
    MOMENTUM_REVERSAL = "momentum_reversal"
    ATR_STOP = "atr_stop"
    CIRCUIT_BREAKER = "circuit_breaker"
    MANUAL = "manual"


@dataclass
class ExitConditions:
    """
    Configuration for position exit conditions.

    These are tighter than typical buy-and-hold strategies to ensure
    active position management and generate closed trade data for win rate.

    Asset-class-specific thresholds (as of Dec 11, 2025):
    - Treasuries: 0.1% (barely move, need very tight thresholds)
    - Bonds: 1.0% (moderate volatility)
    - Equities: 0.5% (tighter for active trading)
    - Crypto: 3.0% (high volatility, tightened from 5%)

    Attributes:
        take_profit_pct: Profit target percentage (default: 3%)
        stop_loss_pct: Maximum loss percentage (default: 3%)
        max_holding_days: Maximum days to hold position (default: 10)
        enable_momentum_exit: Whether to exit on MACD bearish cross
        enable_atr_stop: Whether to use ATR-based dynamic stops
        atr_multiplier: ATR multiplier for dynamic stop calculation
    """

    take_profit_pct: float = 0.005  # 0.5% profit target (tighter for active trading)
    stop_loss_pct: float = 0.005  # 0.5% stop loss (tighter for active trading)
    max_holding_days: int = 5  # Close after 5 days regardless
    enable_momentum_exit: bool = True  # Exit on MACD bearish cross
    enable_atr_stop: bool = True  # Use ATR-based stops
    atr_multiplier: float = 2.0  # 2x ATR for stop distance

    # Asset-class-specific overrides
    treasury_take_profit_pct: float = 0.001  # 0.1% for treasuries (they move 0.02-0.05%/day)
    treasury_stop_loss_pct: float = 0.001  # 0.1% for treasuries (they move 0.02-0.05%/day)
    treasury_max_holding_days: int = 2  # 2 days for treasuries - force exits faster

    bond_take_profit_pct: float = 0.01  # 1.0% for bonds
    bond_stop_loss_pct: float = 0.01  # 1.0% for bonds
    bond_max_holding_days: int = 5  # 5 days for bonds

    crypto_take_profit_pct: float = 0.03  # 3.0% for crypto (tightened from 5%)
    crypto_stop_loss_pct: float = 0.03  # 3.0% for crypto (tightened from 5%)
    crypto_max_holding_days: int = 5  # 5 days for crypto (tightened from 7)

    def get_thresholds_for_asset(self, asset_class: AssetClass) -> tuple[float, float, int]:
        """
        Get take_profit, stop_loss, and max_holding_days for an asset class.

        Returns:
            Tuple of (take_profit_pct, stop_loss_pct, max_holding_days)
        """
        if asset_class == AssetClass.TREASURY:
            return (
                self.treasury_take_profit_pct,
                self.treasury_stop_loss_pct,
                self.treasury_max_holding_days,
            )
        if asset_class == AssetClass.BOND:
            return (self.bond_take_profit_pct, self.bond_stop_loss_pct, self.bond_max_holding_days)
        if asset_class == AssetClass.CRYPTO:
            return (
                self.crypto_take_profit_pct,
                self.crypto_stop_loss_pct,
                self.crypto_max_holding_days,
            )
        # Default: equity
        return (self.take_profit_pct, self.stop_loss_pct, self.max_holding_days)


@dataclass
class PositionInfo:
    """Information about an open position for exit evaluation."""

    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    entry_date: datetime
    unrealized_pl: float
    unrealized_plpc: float
    market_value: float


@dataclass
class ExitSignal:
    """Signal to exit a position with reason and details."""

    symbol: str
    should_exit: bool
    reason: ExitReason
    details: str
    urgency: int  # 1-5, 5 being most urgent


class PositionManager:
    """
    Active position manager that ensures trades are closed properly.

    This class solves the core problem of positions never being closed,
    which results in 0% win rate and no performance data.
    """

    def __init__(
        self,
        conditions: ExitConditions | None = None,
        alpaca_trader: Any | None = None,
        state_file: Path | None = None,
    ):
        """
        Initialize position manager.

        Args:
            conditions: Exit conditions configuration
            alpaca_trader: AlpacaTrader instance for position data
            state_file: Path to system state file for persistence
        """
        self.conditions = conditions or ExitConditions()
        self.alpaca_trader = alpaca_trader
        self.state_file = state_file or DEFAULT_STATE_FILE
        self._position_entry_dates: dict[str, datetime] = {}

        # Load persisted entry dates on init
        self._load_entry_dates()

        logger.info("Position Manager initialized with conditions:")
        logger.info(f"  Take-profit: {self.conditions.take_profit_pct * 100:.1f}%")
        logger.info(f"  Stop-loss: {self.conditions.stop_loss_pct * 100:.1f}%")
        logger.info(f"  Max holding: {self.conditions.max_holding_days} days")
        logger.info(f"  Momentum exit: {self.conditions.enable_momentum_exit}")
        logger.info(f"  ATR stop: {self.conditions.enable_atr_stop}")
        logger.info(f"  Loaded {len(self._position_entry_dates)} persisted entry dates")

    def track_entry(self, symbol: str, entry_date: datetime | None = None) -> None:
        """
        Track when a position was entered for time-based exits.
        Persists to system_state.json to survive restarts.

        Args:
            symbol: Stock symbol
            entry_date: Entry timestamp (defaults to now)
        """
        self._position_entry_dates[symbol] = entry_date or datetime.now()
        logger.info(f"Tracking entry for {symbol} at {self._position_entry_dates[symbol]}")
        self._save_entry_dates()  # Persist immediately

    def get_entry_date(self, symbol: str) -> datetime | None:
        """Get the entry date for a position."""
        return self._position_entry_dates.get(symbol)

    def clear_entry(self, symbol: str) -> None:
        """Clear entry tracking when position is closed. Persists change."""
        if symbol in self._position_entry_dates:
            del self._position_entry_dates[symbol]
            logger.info(f"Cleared entry tracking for {symbol}")
            self._save_entry_dates()  # Persist immediately

    def _load_entry_dates(self) -> None:
        """Load persisted entry dates from system_state.json."""
        try:
            if not self.state_file.exists():
                logger.debug(f"State file not found at {self.state_file}")
                return

            with open(self.state_file, encoding="utf-8") as f:
                state = json.load(f)

            position_entries = state.get("position_entries", {})
            for symbol, date_str in position_entries.items():
                try:
                    self._position_entry_dates[symbol] = datetime.fromisoformat(date_str)
                except ValueError as e:
                    logger.warning(f"Invalid date format for {symbol}: {e}")

            logger.info(f"Loaded {len(self._position_entry_dates)} position entry dates from state")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse state file: {e}")
        except Exception as e:
            logger.error(f"Failed to load entry dates: {e}")

    def _save_entry_dates(self) -> None:
        """Save entry dates to system_state.json."""
        try:
            # Load existing state
            if self.state_file.exists():
                with open(self.state_file, encoding="utf-8") as f:
                    state = json.load(f)
            else:
                state = {}

            # Update position_entries section
            state["position_entries"] = {
                symbol: dt.isoformat() for symbol, dt in self._position_entry_dates.items()
            }

            # Update meta timestamp
            if "meta" not in state:
                state["meta"] = {}
            state["meta"]["last_updated"] = datetime.now().isoformat()

            # Write atomically (write to temp, then rename)
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            temp_file.replace(self.state_file)

            logger.debug(f"Saved {len(self._position_entry_dates)} position entry dates to state")
        except Exception as e:
            logger.error(f"Failed to save entry dates: {e}")

    def evaluate_position(self, position: PositionInfo) -> ExitSignal:
        """
        Evaluate a position against all exit conditions.

        This is the core method that determines if a position should be closed
        and why. It checks all exit conditions in priority order.

        Uses ASSET-CLASS-SPECIFIC thresholds:
        - Treasuries (BIL, SHY, IEF, TLT): 0.5% thresholds, 3 day max hold
        - Bonds (AGG, BND, etc.): 1.0% thresholds, 5 day max hold
        - Crypto (BTCUSD, ETHUSD): 5.0% thresholds, 7 day max hold
        - Equities (SPY, QQQ, etc.): 3.0% thresholds, 10 day max hold

        Args:
            position: Position information to evaluate

        Returns:
            ExitSignal indicating whether to exit and why
        """
        symbol = position.symbol
        unrealized_plpc = position.unrealized_plpc

        # Get asset-class-specific thresholds
        asset_class = get_asset_class(symbol)
        take_profit_pct, stop_loss_pct, max_holding_days = self.conditions.get_thresholds_for_asset(
            asset_class
        )

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Evaluating position: {symbol} ({asset_class.value.upper()})")
        logger.info(f"  Entry: ${position.entry_price:.2f}")
        logger.info(f"  Current: ${position.current_price:.2f}")
        logger.info(f"  P/L: {unrealized_plpc * 100:.2f}%")
        logger.info(
            f"  Thresholds: TP={take_profit_pct * 100:.1f}%, SL={stop_loss_pct * 100:.1f}%, MaxDays={max_holding_days}"
        )

        # 1. Check STOP-LOSS (highest priority - protect capital)
        if unrealized_plpc <= -stop_loss_pct:
            logger.warning(
                f"  🛑 STOP-LOSS TRIGGERED: {unrealized_plpc * 100:.2f}% <= "
                f"-{stop_loss_pct * 100:.1f}%"
            )
            return ExitSignal(
                symbol=symbol,
                should_exit=True,
                reason=ExitReason.STOP_LOSS,
                details=f"Loss of {unrealized_plpc * 100:.2f}% exceeds {stop_loss_pct * 100:.1f}% limit ({asset_class.value})",
                urgency=5,
            )

        # 2. Check TAKE-PROFIT
        if unrealized_plpc >= take_profit_pct:
            logger.info(
                f"  🎯 TAKE-PROFIT TRIGGERED: {unrealized_plpc * 100:.2f}% >= "
                f"{take_profit_pct * 100:.1f}%"
            )
            return ExitSignal(
                symbol=symbol,
                should_exit=True,
                reason=ExitReason.TAKE_PROFIT,
                details=f"Profit of {unrealized_plpc * 100:.2f}% reached {take_profit_pct * 100:.1f}% target ({asset_class.value})",
                urgency=4,
            )

        # 3. Check TIME-DECAY (close stale positions)
        entry_date = self.get_entry_date(symbol)
        if entry_date:
            days_held = (datetime.now() - entry_date).days
            if days_held >= max_holding_days:
                logger.info(
                    f"  ⏰ TIME-DECAY TRIGGERED: Held {days_held} days >= "
                    f"{max_holding_days} day limit ({asset_class.value})"
                )
                return ExitSignal(
                    symbol=symbol,
                    should_exit=True,
                    reason=ExitReason.TIME_DECAY,
                    details=f"Position held {days_held} days exceeds {max_holding_days} day limit ({asset_class.value})",
                    urgency=3,
                )
            else:
                logger.info(f"  Days held: {days_held}/{max_holding_days}")
        else:
            logger.warning(f"  ⚠️ No entry date tracked for {symbol} - cannot check time decay")

        # 4. Check MOMENTUM REVERSAL (if enabled)
        if self.conditions.enable_momentum_exit:
            momentum_exit = self._check_momentum_reversal(symbol)
            if momentum_exit:
                logger.info(f"  📉 MOMENTUM REVERSAL: MACD crossed bearish for {symbol}")
                return ExitSignal(
                    symbol=symbol,
                    should_exit=True,
                    reason=ExitReason.MOMENTUM_REVERSAL,
                    details="MACD crossed below signal line (bearish)",
                    urgency=3,
                )

        # 5. Check ATR-based stop (if enabled)
        if self.conditions.enable_atr_stop:
            atr_exit = self._check_atr_stop(symbol, position.entry_price, position.current_price)
            if atr_exit:
                return atr_exit

        # No exit condition met - hold position
        logger.info("  ✅ HOLD: No exit conditions met")
        return ExitSignal(
            symbol=symbol,
            should_exit=False,
            reason=ExitReason.MANUAL,
            details="No exit conditions met - continuing to hold",
            urgency=0,
        )

    def _check_momentum_reversal(self, symbol: str) -> bool:
        """
        Check if MACD has crossed bearish (momentum reversal).

        Args:
            symbol: Stock symbol

        Returns:
            True if momentum has reversed bearish, False otherwise
        """
        try:
            import yfinance as yf

            # Get recent price data
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")

            if hist.empty or len(hist) < 26:  # Need enough data for MACD
                logger.debug(f"Insufficient data for MACD calculation on {symbol}")
                return False

            # Calculate MACD
            close = hist["Close"]
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            histogram = macd_line - signal_line

            # Check for bearish crossover (MACD crossing below signal)
            if len(histogram) >= 2:
                current_hist = histogram.iloc[-1]
                prev_hist = histogram.iloc[-2]

                # Bearish cross: histogram went from positive to negative
                if prev_hist > 0 and current_hist < 0:
                    logger.info(f"  MACD bearish cross detected for {symbol}")
                    logger.info(f"    Previous histogram: {prev_hist:.4f}")
                    logger.info(f"    Current histogram: {current_hist:.4f}")
                    return True

            return False

        except Exception as e:
            logger.debug(f"Error checking momentum for {symbol}: {e}")
            return False

    def _check_atr_stop(
        self, symbol: str, entry_price: float, current_price: float
    ) -> ExitSignal | None:
        """
        Check if ATR-based stop has been triggered.

        Args:
            symbol: Stock symbol
            entry_price: Position entry price
            current_price: Current market price

        Returns:
            ExitSignal if ATR stop triggered, None otherwise
        """
        try:
            import yfinance as yf

            from src.utils.technical_indicators import calculate_atr

            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")

            if hist.empty or len(hist) < 15:
                return None

            atr = calculate_atr(hist)
            if atr <= 0:
                return None

            # Calculate ATR-based stop price
            atr_stop_price = entry_price - (atr * self.conditions.atr_multiplier)

            logger.info(f"  ATR: ${atr:.2f}, Stop: ${atr_stop_price:.2f}")

            if current_price <= atr_stop_price:
                logger.warning(
                    f"  🛑 ATR STOP TRIGGERED: ${current_price:.2f} <= ${atr_stop_price:.2f}"
                )
                return ExitSignal(
                    symbol=symbol,
                    should_exit=True,
                    reason=ExitReason.ATR_STOP,
                    details=f"Price ${current_price:.2f} breached ATR stop ${atr_stop_price:.2f}",
                    urgency=5,
                )

            return None

        except ImportError:
            logger.debug("technical_indicators not available for ATR calculation")
            return None
        except Exception as e:
            logger.debug(f"Error calculating ATR for {symbol}: {e}")
            return None

    def manage_all_positions(
        self, positions: list[dict], state_manager: Any | None = None
    ) -> list[dict]:
        """
        Evaluate all positions and return list of exits to execute.

        This is the main entry point for the daily position management routine.

        Args:
            positions: List of position dictionaries from Alpaca
            state_manager: Optional StateManager for tracking

        Returns:
            List of exit signals for positions that should be closed
        """
        logger.info("=" * 80)
        logger.info("POSITION MANAGER - ACTIVE EXIT EVALUATION")
        logger.info(f"Evaluating {len(positions)} positions with tighter conditions:")
        logger.info(f"  Take-profit: {self.conditions.take_profit_pct * 100:.1f}%")
        logger.info(f"  Stop-loss: {self.conditions.stop_loss_pct * 100:.1f}%")
        logger.info(f"  Max holding: {self.conditions.max_holding_days} days")
        logger.info("=" * 80)

        exits_to_execute = []

        for pos_dict in positions:
            try:
                position = PositionInfo(
                    symbol=pos_dict.get("symbol", ""),
                    quantity=float(pos_dict.get("qty", 0)),
                    entry_price=float(pos_dict.get("avg_entry_price", 0)),
                    current_price=float(pos_dict.get("current_price", 0)),
                    entry_date=self.get_entry_date(pos_dict.get("symbol", ""))
                    or datetime.now() - timedelta(days=30),  # Assume old if not tracked
                    unrealized_pl=float(pos_dict.get("unrealized_pl", 0)),
                    unrealized_plpc=float(pos_dict.get("unrealized_plpc", 0)),
                    market_value=float(pos_dict.get("market_value", 0)),
                )

                signal = self.evaluate_position(position)

                if signal.should_exit:
                    exits_to_execute.append(
                        {
                            "symbol": signal.symbol,
                            "reason": signal.reason.value,
                            "details": signal.details,
                            "urgency": signal.urgency,
                            "position": position,
                        }
                    )

            except Exception as e:
                logger.error(f"Error evaluating position {pos_dict}: {e}")
                continue

        # Sort by urgency (highest first)
        exits_to_execute.sort(key=lambda x: x["urgency"], reverse=True)

        logger.info("=" * 80)
        logger.info(f"SUMMARY: {len(exits_to_execute)} positions flagged for exit")
        for exit_info in exits_to_execute:
            logger.info(
                f"  [{exit_info['urgency']}] {exit_info['symbol']}: {exit_info['reason']} - {exit_info['details']}"
            )
        logger.info("=" * 80)

        return exits_to_execute


# Default instance with tighter conditions for active trading
DEFAULT_POSITION_MANAGER = PositionManager(
    conditions=ExitConditions(
        take_profit_pct=0.005,  # 0.5% take-profit (tightened Dec 11, 2025)
        stop_loss_pct=0.005,  # 0.5% stop-loss (tightened Dec 11, 2025)
        max_holding_days=5,  # Max 5 days (tightened from 10)
        enable_momentum_exit=True,
        enable_atr_stop=True,
    )
)


def get_position_manager(conditions: ExitConditions | None = None) -> PositionManager:
    """
    Get a position manager instance.

    Args:
        conditions: Optional custom exit conditions

    Returns:
        PositionManager instance
    """
    if conditions:
        return PositionManager(conditions=conditions)
    return DEFAULT_POSITION_MANAGER
