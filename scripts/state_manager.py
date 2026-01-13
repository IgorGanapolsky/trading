"""
State Manager - Centralized state management for trading system.

Manages system_state.json for:
- Trade recording (wins/losses)
- Performance metrics
- Win rate tracking

Created: Jan 13, 2026
Reason: CRITICAL - was imported but never created, causing silent failures
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Centralized path constant - per audit recommendations
SYSTEM_STATE_PATH = Path("data/system_state.json")


class StateManager:
    """
    Manages system state for trade tracking and performance metrics.

    Usage:
        state_manager = StateManager()
        state_manager.record_closed_trade(
            symbol="SOFI",
            entry_price=24.0,
            exit_price=25.0,
            quantity=100,
            entry_date="2026-01-13T10:00:00"
        )
        state_manager.save_state()
    """

    def __init__(self, state_file: Path | None = None):
        """Initialize state manager with optional custom state file path."""
        self.state_file = state_file or SYSTEM_STATE_PATH
        self.state = self._load_state()

        # Ensure performance section exists
        if "performance" not in self.state:
            self.state["performance"] = {
                "closed_trades": [],
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
            }

    def _load_state(self) -> dict[str, Any]:
        """Load state from file or return empty state."""
        try:
            if self.state_file.exists():
                with open(self.state_file, encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load state from {self.state_file}: {e}")

        return {
            "last_updated": datetime.now().isoformat(),
            "portfolio": {"equity": 0, "cash": 0},
            "performance": {
                "closed_trades": [],
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
            },
        }

    def save_state(self) -> bool:
        """Save current state to file."""
        try:
            self.state["last_updated"] = datetime.now().isoformat()
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)

            logger.info(f"State saved to {self.state_file}")
            return True
        except IOError as e:
            logger.error(f"Failed to save state: {e}")
            return False

    def record_closed_trade(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        entry_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Record a closed trade for win/loss tracking.

        Args:
            symbol: The ticker symbol
            entry_price: Price at entry
            exit_price: Price at exit
            quantity: Number of shares/contracts
            entry_date: ISO format date string for entry

        Returns:
            The recorded trade dictionary
        """
        pl = (exit_price - entry_price) * quantity
        pl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        is_winner = pl > 0

        trade = {
            "symbol": symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "entry_date": entry_date or datetime.now().isoformat(),
            "exit_date": datetime.now().isoformat(),
            "pl": round(pl, 2),
            "pl_pct": round(pl_pct, 2),
            "is_winner": is_winner,
        }

        # Ensure performance structure exists
        if "performance" not in self.state:
            self.state["performance"] = {
                "closed_trades": [],
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
            }

        self.state["performance"]["closed_trades"].append(trade)

        logger.info(
            f"Recorded trade: {symbol} {'WIN' if is_winner else 'LOSS'} "
            f"(${pl:.2f}, {pl_pct:.2f}%)"
        )

        return trade

    def get_win_rate(self) -> float:
        """Calculate current win rate from closed trades."""
        perf = self.state.get("performance", {})
        winning = perf.get("winning_trades", 0)
        losing = perf.get("losing_trades", 0)
        total = winning + losing

        if total == 0:
            return 0.0

        return (winning / total) * 100

    def get_total_pl(self) -> float:
        """Get total P/L from all closed trades."""
        closed_trades = self.state.get("performance", {}).get("closed_trades", [])
        return sum(trade.get("pl", 0) for trade in closed_trades)


if __name__ == "__main__":
    # Test the state manager
    logging.basicConfig(level=logging.INFO)

    sm = StateManager()
    print(f"Current state: {json.dumps(sm.state, indent=2)}")
    print(f"Win rate: {sm.get_win_rate():.1f}%")
    print(f"Total P/L: ${sm.get_total_pl():.2f}")
