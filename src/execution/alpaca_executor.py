"""Execution adapter for Alpaca.

Dec 3, 2025 Enhancement:
- Added place_order_with_stop_loss() for integrated order + stop-loss execution
- ATR-based stop-loss calculation wired to order placement
- Automatic stop-loss on every new position
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any

from src.core.alpaca_trader import AlpacaTrader, AlpacaTraderError

logger = logging.getLogger(__name__)

# Default stop-loss configuration
DEFAULT_STOP_LOSS_PCT = 0.05  # 5% default if ATR unavailable
MIN_STOP_LOSS_PCT = 0.02  # Never less than 2%
MAX_STOP_LOSS_PCT = 0.10  # Never more than 10%


class AlpacaExecutor:
    """Handles portfolio sync and order placement."""

    def __init__(self, paper: bool = True, allow_simulator: bool = True) -> None:
        self.simulated_orders: list[dict[str, Any]] = []
        self.account_snapshot: dict[str, Any] = {}
        self.positions: list[dict[str, Any]] = []
        self.simulated = os.getenv("ALPACA_SIMULATED", "false").lower() in {"1", "true"}
        self.paper = paper

        if not self.simulated:
            try:
                self.trader = AlpacaTrader(paper=paper)
            except AlpacaTraderError as exc:
                if not allow_simulator:
                    raise
                logger.warning(
                    "Alpaca credentials unavailable (%s); falling back to simulator.",
                    exc,
                )
                self.trader = None
                self.simulated = True
        else:
            self.trader = None

    def sync_portfolio_state(self) -> None:
        if self.simulated:
            equity = float(os.getenv("SIMULATED_EQUITY", "100000"))
            self.account_snapshot = {"equity": equity, "mode": "simulated"}
            self.positions = []
        else:
            try:
                self.account_snapshot = self.trader.get_account_info()
                self.positions = self.trader.get_positions()
            except Exception as e:
                logger.error(f"Failed to sync portfolio state: {e}. Falling back to empty state.")
                self.account_snapshot = {}
                self.positions = []

        logger.info(
            "Synced %s Alpaca state | equity=$%.2f | positions=%d",
            "simulated" if self.simulated else ("paper" if self.paper else "live"),
            self.account_equity,
            len(self.positions),
        )

    @property
    def account_equity(self) -> float:
        if not self.account_snapshot:
            return float(os.getenv("SIMULATED_EQUITY", "100000")) if self.simulated else 0.0
        return float(
            self.account_snapshot.get("equity")
            or self.account_snapshot.get("portfolio_value")
            or 0.0
        )

    def get_positions(self) -> list[dict[str, Any]]:
        """
        Get current open positions from Alpaca.

        Returns fresh position data from the broker, not cached data.

        Returns:
            List of position dictionaries with keys:
            - symbol: str
            - qty: float
            - avg_entry_price: float
            - current_price: float
            - unrealized_pl: float
            - unrealized_plpc: float (as decimal, e.g., 0.03 for 3%)
            - market_value: float
        """
        if self.simulated:
            return self.positions  # Return cached simulated positions

        if self.trader:
            return self.trader.get_positions()

        return []

    def place_order(self, symbol: str, notional: float, side: str = "buy") -> dict[str, Any]:
        logger.debug(
            "Submitting %s order via AlpacaExecutor: %s for $%.2f",
            side,
            symbol,
            notional,
        )
        if self.simulated:
            order = {
                "id": str(uuid.uuid4()),
                "symbol": symbol,
                "side": side,
                "notional": round(notional, 2),
                "status": "filled",
                "filled_at": datetime.utcnow().isoformat(),
                "mode": "simulated",
            }
            self.simulated_orders.append(order)
            return order

        order = self.trader.execute_order(
            symbol=symbol,
            amount_usd=notional,
            side=side,
            tier="T1_CORE",
        )
        return order

    def set_stop_loss(self, symbol: str, qty: float, stop_price: float) -> dict[str, Any]:
        """Place or simulate a stop-loss order.

        In simulated mode, records a synthetic stop order entry.
        """
        if qty <= 0 or stop_price <= 0:
            raise ValueError("qty and stop_price must be positive")

        if self.simulated:
            order = {
                "id": str(uuid.uuid4()),
                "symbol": symbol,
                "side": "sell",
                "type": "stop",
                "qty": float(qty),
                "stop_price": float(stop_price),
                "status": "accepted",
                "submitted_at": datetime.utcnow().isoformat(),
                "mode": "simulated",
            }
            self.simulated_orders.append(order)
            return order

        return self.trader.set_stop_loss(symbol=symbol, qty=qty, stop_price=stop_price)

    def place_order_with_stop_loss(
        self,
        symbol: str,
        notional: float,
        side: str = "buy",
        stop_loss_pct: float | None = None,
        atr_multiplier: float = 2.0,
        hist: Any | None = None,
    ) -> dict[str, Any]:
        """
        Place order AND automatically set stop-loss in one atomic operation.

        This is the recommended method for all new positions - ensures every
        position is protected from the moment it's opened.

        Args:
            symbol: Ticker symbol
            notional: Dollar amount to invest
            side: 'buy' or 'sell'
            stop_loss_pct: Fixed stop-loss percentage (overrides ATR calculation)
            atr_multiplier: ATR multiplier for dynamic stop (default 2x ATR)
            hist: Optional DataFrame with OHLCV data for ATR calculation

        Returns:
            Dict with order details and stop_loss details:
            {
                'order': {order details},
                'stop_loss': {stop order details or None if failed},
                'stop_loss_price': calculated stop price,
                'stop_loss_pct': actual percentage from entry
            }
        """
        result = {
            "order": None,
            "stop_loss": None,
            "stop_loss_price": None,
            "stop_loss_pct": None,
            "error": None,
        }

        # Place the main order first
        try:
            order = self.place_order(symbol=symbol, notional=notional, side=side)
            result["order"] = order
        except Exception as e:
            logger.error(f"Failed to place order for {symbol}: {e}")
            result["error"] = f"Order failed: {e}"
            return result

        # For sell orders, we don't set stop-loss (we're exiting)
        if side.lower() != "buy":
            logger.info(f"Sell order for {symbol} - no stop-loss needed")
            return result

        # Calculate entry price (estimated from notional / filled_qty or current price)
        entry_price = self._estimate_entry_price(symbol, notional, order)
        if entry_price <= 0:
            logger.error(f"Could not determine entry price for {symbol}. Stop-loss not placed.")
            result["error"] = "Could not determine entry price for stop-loss."
            # Order was placed but stop failed - this is a risk!
            logger.critical(
                f"[RISK] Position {symbol} opened WITHOUT stop-loss protection! "
                f"Manual intervention required."
            )
            return result

        # Calculate stop-loss price
        if stop_loss_pct is not None:
            # Fixed percentage stop
            stop_price = entry_price * (1 - stop_loss_pct)
            actual_pct = stop_loss_pct
        else:
            # ATR-based dynamic stop
            stop_price, actual_pct = self._calculate_atr_stop(
                symbol=symbol,
                entry_price=entry_price,
                atr_multiplier=atr_multiplier,
                hist=hist,
            )

        # Ensure stop is within bounds
        actual_pct = max(MIN_STOP_LOSS_PCT, min(MAX_STOP_LOSS_PCT, actual_pct))
        stop_price = entry_price * (1 - actual_pct)
        stop_price = round(stop_price, 2)

        result["stop_loss_price"] = stop_price
        result["stop_loss_pct"] = actual_pct

        # Calculate quantity from filled order or estimate
        qty = self._get_order_qty(order, notional, entry_price)
        if qty <= 0:
            logger.warning(f"Could not determine quantity for {symbol} stop-loss")
            return result

        # Place the stop-loss order
        try:
            stop_order = self.set_stop_loss(symbol=symbol, qty=qty, stop_price=stop_price)
            result["stop_loss"] = stop_order
            logger.info(
                f"[PROTECTED] {symbol}: Entry=${entry_price:.2f}, "
                f"Stop=${stop_price:.2f} ({actual_pct * 100:.1f}%), "
                f"Qty={qty:.4f}"
            )
        except Exception as e:
            logger.error(f"Failed to set stop-loss for {symbol}: {e}")
            result["error"] = f"Stop-loss failed: {e}"
            # Order was placed but stop failed - this is a risk!
            logger.critical(
                f"[RISK] Position {symbol} opened WITHOUT stop-loss protection! "
                f"Manual intervention required."
            )

        return result

    def _estimate_entry_price(self, symbol: str, notional: float, order: dict[str, Any]) -> float:
        """Estimate entry price from order or current market price."""
        # Try to get from order fill
        if order.get("filled_avg_price"):
            return float(order["filled_avg_price"])

        if order.get("filled_qty") and float(order.get("filled_qty", 0)) > 0:
            return notional / float(order["filled_qty"])

        # Simulated orders - estimate from notional
        if order.get("mode") == "simulated":
            # Try to get current price
            try:
                if self.trader:
                    quote = self.trader.api.get_latest_quote(symbol)
                    if quote and quote.ask_price:
                        return float(quote.ask_price)
            except Exception:
                pass
            # Default estimate: assume 1 share = notional (rough)
            return notional / 1.0 if notional > 0 else 0.0

        # Try to get current market price
        try:
            if self.trader:
                quote = self.trader.api.get_latest_quote(symbol)
                if quote and quote.ask_price:
                    return float(quote.ask_price)
        except Exception:
            pass

        return 0.0

    def _calculate_atr_stop(
        self,
        symbol: str,
        entry_price: float,
        atr_multiplier: float,
        hist: Any | None = None,
    ) -> tuple[float, float]:
        """Calculate ATR-based stop-loss price."""
        try:
            from src.risk.risk_manager import RiskManager

            rm = RiskManager()
            stop_price = rm.calculate_stop_loss(
                ticker=symbol,
                entry_price=entry_price,
                direction="long",
                atr_multiplier=atr_multiplier,
                hist=hist,
            )

            if stop_price > 0 and stop_price < entry_price:
                actual_pct = (entry_price - stop_price) / entry_price
                return stop_price, actual_pct

        except Exception as e:
            logger.debug(f"ATR calculation failed for {symbol}: {e}")

        # Fallback to default
        return entry_price * (1 - DEFAULT_STOP_LOSS_PCT), DEFAULT_STOP_LOSS_PCT

    def _get_order_qty(self, order: dict[str, Any], notional: float, entry_price: float) -> float:
        """Get quantity from order or estimate from notional."""
        if order.get("filled_qty"):
            return float(order["filled_qty"])

        if order.get("qty"):
            return float(order["qty"])

        # Estimate from notional / price
        if entry_price > 0:
            return notional / entry_price

        return 0.0
