"""
Trailing Stop Manager

Implements dynamic trailing stop functionality that:
- Tracks peak price for each position
- Adjusts stop level as price moves in favor
- Locks in profits while allowing upside

This is a key risk management feature identified as missing in the Dec 2025 analysis.

Author: Trading System (Claude CTO)
Created: 2025-12-11
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TrailingStopState:
    """Tracks trailing stop state for a single position."""

    symbol: str
    entry_price: float
    entry_date: str
    peak_price: float  # Highest price since entry (for longs)
    trailing_stop_price: float
    trail_pct: float  # Trail distance as percentage
    trail_points: float | None  # Trail distance as fixed points (optional)
    side: str  # 'long' or 'short'
    last_updated: str
    triggered: bool = False
    trigger_price: float | None = None
    trigger_date: str | None = None


@dataclass
class TrailingStopSignal:
    """Signal indicating trailing stop status."""

    symbol: str
    should_exit: bool
    exit_type: str  # 'trailing_stop', 'hold'
    reason: str
    entry_price: float
    current_price: float
    peak_price: float
    trailing_stop_price: float
    trail_distance_pct: float
    pnl_pct: float
    pnl_from_peak_pct: float
    urgency: str  # 'immediate', 'none'


class TrailingStopManager:
    """
    Manages trailing stops for all positions.

    Key Features:
    - Tracks peak price for each position
    - Supports percentage-based and fixed-point trailing
    - Persists state to disk for crash recovery
    - Integrates with existing ATR exit manager

    Usage:
        manager = TrailingStopManager(trail_pct=2.0)
        manager.add_position('SPY', entry_price=600, side='long')
        signal = manager.update('SPY', current_price=620)  # Peak updates
        signal = manager.update('SPY', current_price=610)  # Check trail
    """

    DEFAULT_TRAIL_PCT = 2.0  # 2% trailing stop by default
    STATE_FILE = "data/trailing_stop_state.json"

    def __init__(
        self,
        trail_pct: float = DEFAULT_TRAIL_PCT,
        trail_points: float | None = None,
        use_atr_trail: bool = False,
        atr_multiplier: float = 1.5,
        state_file: str | None = None,
    ):
        """
        Initialize Trailing Stop Manager.

        Args:
            trail_pct: Trail distance as percentage (default: 2%)
            trail_points: Trail distance as fixed points (overrides pct if set)
            use_atr_trail: If True, use ATR-based trailing (dynamic)
            atr_multiplier: ATR multiplier for dynamic trail
            state_file: Path to state persistence file
        """
        self.trail_pct = trail_pct
        self.trail_points = trail_points
        self.use_atr_trail = use_atr_trail
        self.atr_multiplier = atr_multiplier
        self.state_file = Path(state_file or self.STATE_FILE)

        # Position states
        self.positions: dict[str, TrailingStopState] = {}

        # Load persisted state
        self._load_state()

        logger.info(
            f"Trailing Stop Manager initialized: "
            f"trail_pct={trail_pct}%, trail_points={trail_points}, "
            f"use_atr={use_atr_trail}"
        )

    def _load_state(self) -> None:
        """Load persisted state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                    for symbol, state_dict in data.get("positions", {}).items():
                        self.positions[symbol] = TrailingStopState(**state_dict)
                logger.info(f"Loaded {len(self.positions)} positions from state file")
            except Exception as e:
                logger.warning(f"Failed to load state file: {e}")

    def _save_state(self) -> None:
        """Persist state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "positions": {
                    symbol: asdict(state) for symbol, state in self.positions.items()
                },
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def add_position(
        self,
        symbol: str,
        entry_price: float,
        side: str = "long",
        trail_pct: float | None = None,
        trail_points: float | None = None,
        entry_date: str | None = None,
    ) -> TrailingStopState:
        """
        Add a new position to track.

        Args:
            symbol: Ticker symbol
            entry_price: Position entry price
            side: 'long' or 'short'
            trail_pct: Override default trail percentage
            trail_points: Override with fixed point trail
            entry_date: Entry date (defaults to now)

        Returns:
            TrailingStopState for the new position
        """
        now = datetime.now().isoformat()
        effective_trail_pct = trail_pct or self.trail_pct
        effective_trail_points = trail_points or self.trail_points

        # Calculate initial trailing stop
        if effective_trail_points is not None:
            if side == "long":
                trailing_stop = entry_price - effective_trail_points
            else:
                trailing_stop = entry_price + effective_trail_points
        else:
            trail_distance = entry_price * (effective_trail_pct / 100)
            if side == "long":
                trailing_stop = entry_price - trail_distance
            else:
                trailing_stop = entry_price + trail_distance

        state = TrailingStopState(
            symbol=symbol,
            entry_price=entry_price,
            entry_date=entry_date or now,
            peak_price=entry_price,  # Start at entry
            trailing_stop_price=trailing_stop,
            trail_pct=effective_trail_pct,
            trail_points=effective_trail_points,
            side=side,
            last_updated=now,
        )

        self.positions[symbol] = state
        self._save_state()

        logger.info(
            f"Added trailing stop for {symbol}: "
            f"entry=${entry_price:.2f}, stop=${trailing_stop:.2f}"
        )

        return state

    def remove_position(self, symbol: str) -> bool:
        """Remove a position from tracking."""
        if symbol in self.positions:
            del self.positions[symbol]
            self._save_state()
            logger.info(f"Removed trailing stop tracking for {symbol}")
            return True
        return False

    def update(
        self,
        symbol: str,
        current_price: float,
        atr: float | None = None,
    ) -> TrailingStopSignal:
        """
        Update trailing stop for a position and check for trigger.

        Args:
            symbol: Ticker symbol
            current_price: Current market price
            atr: Optional ATR value for dynamic trailing

        Returns:
            TrailingStopSignal with current status
        """
        if symbol not in self.positions:
            return TrailingStopSignal(
                symbol=symbol,
                should_exit=False,
                exit_type="not_tracked",
                reason=f"{symbol} not being tracked for trailing stop",
                entry_price=0,
                current_price=current_price,
                peak_price=0,
                trailing_stop_price=0,
                trail_distance_pct=0,
                pnl_pct=0,
                pnl_from_peak_pct=0,
                urgency="none",
            )

        state = self.positions[symbol]
        now = datetime.now().isoformat()

        # Update peak price if applicable
        if state.side == "long" and current_price > state.peak_price:
            state.peak_price = current_price
            state.last_updated = now

            # Recalculate trailing stop based on new peak
            if self.use_atr_trail and atr is not None:
                state.trailing_stop_price = current_price - (atr * self.atr_multiplier)
            elif state.trail_points is not None:
                state.trailing_stop_price = current_price - state.trail_points
            else:
                trail_distance = current_price * (state.trail_pct / 100)
                state.trailing_stop_price = current_price - trail_distance

            logger.debug(
                f"{symbol} new peak: ${current_price:.2f}, "
                f"trail stop: ${state.trailing_stop_price:.2f}"
            )

        elif state.side == "short" and current_price < state.peak_price:
            state.peak_price = current_price  # For shorts, peak is lowest price
            state.last_updated = now

            if self.use_atr_trail and atr is not None:
                state.trailing_stop_price = current_price + (atr * self.atr_multiplier)
            elif state.trail_points is not None:
                state.trailing_stop_price = current_price + state.trail_points
            else:
                trail_distance = current_price * (state.trail_pct / 100)
                state.trailing_stop_price = current_price + trail_distance

        # Calculate P/L metrics
        if state.side == "long":
            pnl_pct = ((current_price - state.entry_price) / state.entry_price) * 100
            pnl_from_peak_pct = (
                (current_price - state.peak_price) / state.peak_price
            ) * 100
        else:
            pnl_pct = ((state.entry_price - current_price) / state.entry_price) * 100
            pnl_from_peak_pct = (
                (state.peak_price - current_price) / state.peak_price
            ) * 100

        trail_distance_pct = abs(
            (state.trailing_stop_price - state.peak_price) / state.peak_price * 100
        )

        # Check for trailing stop trigger
        should_exit = False
        exit_type = "hold"
        reason = ""
        urgency = "none"

        if state.side == "long" and current_price <= state.trailing_stop_price:
            should_exit = True
            exit_type = "trailing_stop"
            reason = (
                f"Price ${current_price:.2f} hit trailing stop ${state.trailing_stop_price:.2f} "
                f"(peak was ${state.peak_price:.2f}, {state.trail_pct:.1f}% trail)"
            )
            urgency = "immediate"
            state.triggered = True
            state.trigger_price = current_price
            state.trigger_date = now

        elif state.side == "short" and current_price >= state.trailing_stop_price:
            should_exit = True
            exit_type = "trailing_stop"
            reason = (
                f"Price ${current_price:.2f} hit trailing stop ${state.trailing_stop_price:.2f} "
                f"(trough was ${state.peak_price:.2f}, {state.trail_pct:.1f}% trail)"
            )
            urgency = "immediate"
            state.triggered = True
            state.trigger_price = current_price
            state.trigger_date = now

        else:
            reason = (
                f"Holding: current=${current_price:.2f}, "
                f"peak=${state.peak_price:.2f}, "
                f"trail stop=${state.trailing_stop_price:.2f}"
            )

        self._save_state()

        return TrailingStopSignal(
            symbol=symbol,
            should_exit=should_exit,
            exit_type=exit_type,
            reason=reason,
            entry_price=state.entry_price,
            current_price=current_price,
            peak_price=state.peak_price,
            trailing_stop_price=state.trailing_stop_price,
            trail_distance_pct=trail_distance_pct,
            pnl_pct=pnl_pct,
            pnl_from_peak_pct=pnl_from_peak_pct,
            urgency=urgency,
        )

    def update_all(
        self,
        prices: dict[str, float],
        atrs: dict[str, float] | None = None,
    ) -> list[TrailingStopSignal]:
        """
        Update all tracked positions.

        Args:
            prices: Dict of symbol -> current price
            atrs: Optional dict of symbol -> ATR value

        Returns:
            List of TrailingStopSignals
        """
        signals = []
        atrs = atrs or {}

        for symbol, price in prices.items():
            if symbol in self.positions:
                signal = self.update(symbol, price, atrs.get(symbol))
                signals.append(signal)

        return signals

    def check_positions_from_list(
        self,
        positions: list[dict[str, Any]],
    ) -> list[TrailingStopSignal]:
        """
        Check positions from a list format (compatible with system_state.json).

        Args:
            positions: List of position dicts with symbol, entry_price, current_price

        Returns:
            List of TrailingStopSignals
        """
        signals = []

        for pos in positions:
            symbol = pos["symbol"]
            entry_price = pos.get("entry_price", pos.get("avg_cost", 0))
            current_price = pos["current_price"]
            entry_date = pos.get("entry_date")

            # Add if not tracked
            if symbol not in self.positions:
                self.add_position(
                    symbol=symbol,
                    entry_price=entry_price,
                    side=pos.get("side", "long"),
                    entry_date=entry_date,
                )

            # Update and check
            signal = self.update(symbol, current_price)
            signals.append(signal)

        return signals

    def get_status(self, symbol: str) -> dict[str, Any] | None:
        """Get current status for a symbol."""
        if symbol not in self.positions:
            return None
        return asdict(self.positions[symbol])

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get status for all tracked positions."""
        return {symbol: asdict(state) for symbol, state in self.positions.items()}

    def generate_report(self, signals: list[TrailingStopSignal]) -> str:
        """Generate human-readable trailing stop report."""
        report = []
        report.append("=" * 70)
        report.append("TRAILING STOP MANAGER REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report.append(f"Default Trail: {self.trail_pct}%")
        report.append("=" * 70)

        exits_needed = [s for s in signals if s.should_exit]
        holds = [s for s in signals if not s.should_exit]

        report.append(f"\nPositions to EXIT: {len(exits_needed)}")
        report.append(f"Positions to HOLD: {len(holds)}")

        if exits_needed:
            report.append("\n" + "-" * 70)
            report.append("TRAILING STOP TRIGGERED")
            report.append("-" * 70)

            for s in exits_needed:
                report.append(f"\n{s.symbol} - TRAILING STOP HIT")
                report.append(f"   Entry: ${s.entry_price:.2f}")
                report.append(f"   Peak: ${s.peak_price:.2f}")
                report.append(f"   Trail Stop: ${s.trailing_stop_price:.2f}")
                report.append(f"   Current: ${s.current_price:.2f}")
                report.append(f"   P/L: {s.pnl_pct:+.2f}%")
                report.append(f"   Drop from Peak: {s.pnl_from_peak_pct:.2f}%")
                report.append(f"   Urgency: {s.urgency.upper()}")

        if holds:
            report.append("\n" + "-" * 70)
            report.append("TRAILING - HOLDING")
            report.append("-" * 70)

            for s in holds:
                report.append(f"\n{s.symbol}:")
                report.append(
                    f"   Entry: ${s.entry_price:.2f} -> Peak: ${s.peak_price:.2f}"
                )
                report.append(f"   Current: ${s.current_price:.2f}")
                report.append(f"   Trail Stop: ${s.trailing_stop_price:.2f}")
                report.append(
                    f"   Distance to Stop: ${s.current_price - s.trailing_stop_price:.2f}"
                )
                report.append(f"   P/L: {s.pnl_pct:+.2f}%")

        report.append("\n" + "=" * 70)

        return "\n".join(report)


def get_trailing_stop_manager() -> TrailingStopManager:
    """Get default trailing stop manager with env overrides."""
    return TrailingStopManager(
        trail_pct=float(os.getenv("TRAILING_STOP_PCT", "2.0")),
        trail_points=float(os.getenv("TRAILING_STOP_POINTS", "0")) or None,
        use_atr_trail=os.getenv("TRAILING_USE_ATR", "false").lower() == "true",
        atr_multiplier=float(os.getenv("TRAILING_ATR_MULT", "1.5")),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Demo usage
    manager = TrailingStopManager(trail_pct=2.0)

    # Add a position
    manager.add_position("SPY", entry_price=600.00, side="long")

    # Simulate price movement
    print("\n--- Price rises to $620 (new peak) ---")
    signal = manager.update("SPY", current_price=620.00)
    print(f"Peak: ${signal.peak_price:.2f}, Stop: ${signal.trailing_stop_price:.2f}")

    print("\n--- Price rises to $650 (new peak) ---")
    signal = manager.update("SPY", current_price=650.00)
    print(f"Peak: ${signal.peak_price:.2f}, Stop: ${signal.trailing_stop_price:.2f}")

    print("\n--- Price drops to $640 (still above stop) ---")
    signal = manager.update("SPY", current_price=640.00)
    print(
        f"Should exit: {signal.should_exit}, Stop: ${signal.trailing_stop_price:.2f}"
    )

    print("\n--- Price drops to $635 (hits 2% trail from $650) ---")
    signal = manager.update("SPY", current_price=635.00)
    print(f"Should exit: {signal.should_exit}, Reason: {signal.reason}")

    # Generate report
    signals = [signal]
    print(manager.generate_report(signals))
