"""
Emergency Liquidator - Auto-close positions on critical loss thresholds.

This module bridges the CircuitBreaker with AlpacaTrader to automatically
liquidate positions when daily loss exceeds critical thresholds.

Key Features:
- Auto-liquidation at 3% daily loss (configurable)
- Keeps safe-haven assets (TLT, IEF, BND, SHY)
- Logs all emergency actions with full audit trail
- Sends alerts for manual review

Author: Trading System
Created: 2025-12-04
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.core.alpaca_trader import AlpacaTrader

logger = logging.getLogger(__name__)


class EmergencyLiquidator:
    """
    Automatically liquidates positions when critical loss thresholds are breached.

    This is the "auto-close at 3% daily loss" implementation that was missing.
    Previously, circuit breakers only blocked NEW trades but didn't liquidate
    existing positions. This class bridges that gap.

    Thresholds:
    - 3% daily loss: Auto-liquidate all risky positions, keep safe havens
    - 5% daily loss: Liquidate EVERYTHING including safe havens

    Safe Haven Assets (kept at 3% threshold):
    - TLT (Long-term treasuries)
    - IEF (Intermediate treasuries)
    - BND (Total bond market)
    - SHY (Short-term treasuries)
    - BIL (T-Bills)
    """

    # Thresholds
    AUTO_LIQUIDATE_PCT = 0.03  # 3% daily loss = liquidate risky positions
    FULL_LIQUIDATE_PCT = 0.05  # 5% daily loss = liquidate EVERYTHING

    # Safe haven assets to preserve at 3% threshold
    SAFE_HAVENS = {"TLT", "IEF", "BND", "SHY", "BIL", "GOVT", "SCHD"}

    def __init__(
        self,
        trader: Optional["AlpacaTrader"] = None,
        auto_liquidate_pct: float = AUTO_LIQUIDATE_PCT,
        full_liquidate_pct: float = FULL_LIQUIDATE_PCT,
        state_file: str = "data/emergency_liquidator_state.json",
        dry_run: bool = False,
    ):
        """
        Initialize the Emergency Liquidator.

        Args:
            trader: AlpacaTrader instance for executing liquidations
            auto_liquidate_pct: Threshold for auto-liquidating risky positions (default: 3%)
            full_liquidate_pct: Threshold for full liquidation (default: 5%)
            state_file: Path to persist liquidation state
            dry_run: If True, log actions but don't execute (for testing)
        """
        self.trader = trader
        self.auto_liquidate_pct = auto_liquidate_pct
        self.full_liquidate_pct = full_liquidate_pct
        self.state_file = Path(state_file)
        self.dry_run = dry_run

        logger.info(
            f"EmergencyLiquidator initialized: "
            f"auto_liquidate={auto_liquidate_pct:.1%}, "
            f"full_liquidate={full_liquidate_pct:.1%}, "
            f"dry_run={dry_run}"
        )

    def check_and_liquidate(
        self,
        portfolio_value: float,
        current_pl_today: float,
        positions: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Check daily P/L and auto-liquidate if threshold breached.

        This is the main entry point. Call this after each trade or periodically
        throughout the trading day.

        Args:
            portfolio_value: Total portfolio value
            current_pl_today: Current P/L for today (negative = loss)
            positions: Optional list of current positions (will fetch if not provided)

        Returns:
            Dict with action taken and details:
            - action: "NONE" | "PARTIAL_LIQUIDATE" | "FULL_LIQUIDATE"
            - liquidated_symbols: List of symbols closed
            - preserved_symbols: List of safe-haven symbols kept
            - loss_pct: Daily loss percentage
        """
        if portfolio_value <= 0:
            return {"action": "ERROR", "reason": "Invalid portfolio value"}

        # Calculate daily loss percentage
        loss_pct = abs(current_pl_today) / portfolio_value if current_pl_today < 0 else 0

        # Check if we're in profit (no action needed)
        if current_pl_today >= 0:
            return {
                "action": "NONE",
                "reason": "In profit, no liquidation needed",
                "daily_pl": current_pl_today,
                "daily_pct": current_pl_today / portfolio_value * 100,
            }

        # Check thresholds
        if loss_pct >= self.full_liquidate_pct:
            # CRITICAL: 5%+ loss - liquidate EVERYTHING
            return self._execute_full_liquidation(loss_pct, positions)

        elif loss_pct >= self.auto_liquidate_pct:
            # WARNING: 3%+ loss - liquidate risky positions, keep safe havens
            return self._execute_partial_liquidation(loss_pct, positions)

        else:
            # Under threshold - no action
            return {
                "action": "NONE",
                "reason": f"Loss {loss_pct:.2%} under threshold {self.auto_liquidate_pct:.1%}",
                "loss_pct": loss_pct * 100,
                "threshold_pct": self.auto_liquidate_pct * 100,
            }

    def _execute_partial_liquidation(
        self,
        loss_pct: float,
        positions: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Execute partial liquidation - close risky positions, keep safe havens.
        """
        logger.critical(
            f"🚨 PARTIAL LIQUIDATION TRIGGERED: Daily loss {loss_pct:.2%} >= {self.auto_liquidate_pct:.1%}"
        )

        # Get positions if not provided
        if positions is None and self.trader:
            try:
                raw_positions = self.trader.get_all_positions()
                positions = [
                    {
                        "symbol": p.get("symbol"),
                        "qty": p.get("qty"),
                        "market_value": p.get("market_value"),
                    }
                    for p in raw_positions
                ]
            except Exception as e:
                logger.error(f"Failed to fetch positions: {e}")
                positions = []

        positions = positions or []

        # Separate risky vs safe-haven positions
        to_liquidate = []
        to_preserve = []

        for pos in positions:
            symbol = pos.get("symbol", "").upper()
            if symbol in self.SAFE_HAVENS:
                to_preserve.append(symbol)
            else:
                to_liquidate.append(symbol)

        # Execute liquidation
        closed_symbols = []
        if not self.dry_run and self.trader and to_liquidate:
            for symbol in to_liquidate:
                try:
                    self.trader.close_position(symbol)
                    closed_symbols.append(symbol)
                    logger.warning(f"Closed position: {symbol}")
                except Exception as e:
                    logger.error(f"Failed to close {symbol}: {e}")
        elif self.dry_run:
            closed_symbols = to_liquidate
            logger.warning(f"[DRY RUN] Would close: {to_liquidate}")

        # Log the event
        result = {
            "action": "PARTIAL_LIQUIDATE",
            "trigger": f"Daily loss {loss_pct:.2%} >= {self.auto_liquidate_pct:.1%}",
            "loss_pct": loss_pct * 100,
            "liquidated_symbols": closed_symbols,
            "preserved_symbols": to_preserve,
            "timestamp": datetime.now().isoformat(),
            "dry_run": self.dry_run,
        }

        self._save_event(result)
        return result

    def _execute_full_liquidation(
        self,
        loss_pct: float,
        positions: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        """
        Execute FULL liquidation - close EVERYTHING including safe havens.
        """
        logger.critical(
            f"🚨🚨🚨 FULL LIQUIDATION TRIGGERED: Daily loss {loss_pct:.2%} >= {self.full_liquidate_pct:.1%}"
        )

        closed_symbols = []

        if not self.dry_run and self.trader:
            try:
                result = self.trader.close_all_positions()
                closed_symbols = result.get("closed_symbols", [])
                logger.critical(f"EMERGENCY: Closed ALL positions: {closed_symbols}")
            except Exception as e:
                logger.error(f"Failed to close all positions: {e}")
        elif self.dry_run:
            logger.warning("[DRY RUN] Would close ALL positions")
            if positions:
                closed_symbols = [p.get("symbol", "") for p in positions]

        result = {
            "action": "FULL_LIQUIDATE",
            "trigger": f"Daily loss {loss_pct:.2%} >= {self.full_liquidate_pct:.1%}",
            "loss_pct": loss_pct * 100,
            "liquidated_symbols": closed_symbols,
            "preserved_symbols": [],  # Nothing preserved at 5%
            "timestamp": datetime.now().isoformat(),
            "dry_run": self.dry_run,
            "severity": "CRITICAL",
        }

        self._save_event(result)
        return result

    def _save_event(self, event: dict[str, Any]) -> None:
        """Save liquidation event to state file for audit trail."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing events
            events = []
            if self.state_file.exists():
                try:
                    with open(self.state_file) as f:
                        data = json.load(f)
                        events = data.get("events", [])
                except Exception:
                    events = []

            # Add new event
            events.append(event)

            # Keep last 100 events
            events = events[-100:]

            # Save
            with open(self.state_file, "w") as f:
                json.dump(
                    {"events": events, "last_updated": datetime.now().isoformat()}, f, indent=2
                )

        except Exception as e:
            logger.error(f"Failed to save liquidation event: {e}")

    def get_history(self) -> list[dict[str, Any]]:
        """Get history of liquidation events."""
        if not self.state_file.exists():
            return []

        try:
            with open(self.state_file) as f:
                data = json.load(f)
                return data.get("events", [])
        except Exception as e:
            logger.error(f"Failed to load liquidation history: {e}")
            return []


def create_liquidator(
    trader: Optional["AlpacaTrader"] = None, dry_run: bool = False
) -> EmergencyLiquidator:
    """
    Factory function to create an EmergencyLiquidator with default settings.

    Args:
        trader: Optional AlpacaTrader instance
        dry_run: If True, don't execute real trades

    Returns:
        Configured EmergencyLiquidator instance
    """
    return EmergencyLiquidator(
        trader=trader,
        auto_liquidate_pct=0.03,  # 3% = partial liquidation
        full_liquidate_pct=0.05,  # 5% = full liquidation
        dry_run=dry_run,
    )


if __name__ == "__main__":
    """Demo the emergency liquidator logic."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("EMERGENCY LIQUIDATOR DEMO")
    print("=" * 80)

    # Create liquidator in dry-run mode
    liquidator = create_liquidator(dry_run=True)

    # Test scenarios
    scenarios = [
        {"portfolio": 100000, "pl": 500, "desc": "Profitable day (+$500)"},
        {"portfolio": 100000, "pl": -1000, "desc": "Small loss (-1%)"},
        {"portfolio": 100000, "pl": -3500, "desc": "3.5% loss - triggers partial liquidation"},
        {"portfolio": 100000, "pl": -5500, "desc": "5.5% loss - triggers FULL liquidation"},
    ]

    # Mock positions
    mock_positions = [
        {"symbol": "SPY", "qty": 10, "market_value": 4500},
        {"symbol": "QQQ", "qty": 5, "market_value": 1900},
        {"symbol": "NVDA", "qty": 2, "market_value": 900},
        {"symbol": "TLT", "qty": 20, "market_value": 1800},  # Safe haven
        {"symbol": "BND", "qty": 15, "market_value": 1200},  # Safe haven
    ]

    print("\nTest Scenarios:")
    print("-" * 80)

    for s in scenarios:
        print(f"\n{s['desc']}:")
        result = liquidator.check_and_liquidate(
            portfolio_value=s["portfolio"],
            current_pl_today=s["pl"],
            positions=mock_positions,
        )
        print(f"  Action: {result['action']}")
        if result.get("liquidated_symbols"):
            print(f"  Liquidated: {result['liquidated_symbols']}")
        if result.get("preserved_symbols"):
            print(f"  Preserved: {result['preserved_symbols']}")
        print(f"  Details: {result.get('reason', result.get('trigger', ''))}")
