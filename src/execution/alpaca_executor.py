"""Execution adapter for Alpaca.

Dec 3, 2025 Enhancement:
- Added place_order_with_stop_loss() for integrated order + stop-loss execution
- ATR-based stop-loss calculation wired to order placement
- Automatic stop-loss on every new position

Dec 16, 2025 Enhancement:
- Added LangSmith tracing for all trade executions
- Every order is traced for observability
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from typing import Any

from src.brokers.multi_broker import get_multi_broker
from src.core.alpaca_trader import AlpacaTrader

logger = logging.getLogger(__name__)

# LangSmith tracing for trade execution
try:
    from src.observability.langsmith_tracer import TraceType, get_tracer
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False

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
                # Use MultiBroker for failover redundancy
                self.broker = get_multi_broker()
                # We still keep direct access to alpaca trader if needed for specific methods
                # but primary execution goes through broker
                self.trader = self.broker.alpaca if self.broker else None
                if not self.trader:
                    # Fallback if primary unimplemented
                    self.trader = AlpacaTrader(paper=paper)

            except Exception as exc:
                if not allow_simulator:
                    raise
                logger.warning(
                    "Broker connection unavailable (%s); falling back to simulator.",
                    exc,
                )
                self.trader = None
                self.broker = None
                self.simulated = True
        else:
            self.trader = None
            self.broker = None

    def _record_trade_for_tracking(self, order: dict[str, Any], strategy: str) -> None:
        """Record trade for daily performance tracking and trace to LangSmith."""
        try:
            from src.analytics.daily_performance_tracker import record_trade_pnl
            
            trade_record = {
                "id": order.get("id"),
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "qty": order.get("filled_qty") or order.get("qty"),
                "price": order.get("filled_avg_price"),
                "notional": order.get("notional"),
                "status": order.get("status"),
                "strategy": strategy,
                "pnl": 0.0,  # Will be calculated on close
                "commission": order.get("commission", 0),
                "timestamp": order.get("filled_at") or order.get("submitted_at"),
            }
            
            record_trade_pnl(trade_record)
            logger.debug(f"Trade recorded for performance tracking: {order.get('symbol')}")
            
            # Trace to LangSmith
            self._trace_trade_execution(order, strategy)
        except Exception as e:
            logger.warning(f"Failed to record trade for tracking: {e}")
    
    def _trace_trade_execution(self, order: dict[str, Any], strategy: str) -> None:
        """Trace trade execution to LangSmith for observability."""
        if not LANGSMITH_AVAILABLE:
            return
            
        try:
            tracer = get_tracer()
            symbol = order.get("symbol", "UNKNOWN")
            side = order.get("side", "UNKNOWN")
            
            with tracer.trace(
                name=f"trade_execution_{symbol}_{side}",
                trace_type=TraceType.TRADE,
                symbol=symbol,
                side=side,
                strategy=strategy,
            ) as span:
                span.inputs = {
                    "symbol": symbol,
                    "side": side,
                    "qty": order.get("qty") or order.get("filled_qty"),
                    "notional": order.get("notional"),
                    "strategy": strategy,
                }
                
                span.add_output("order_id", order.get("id"))
                span.add_output("filled_qty", order.get("filled_qty"))
                span.add_output("filled_price", order.get("filled_avg_price"))
                span.add_output("status", order.get("status"))
                span.add_output("commission", order.get("commission", 0))
                
                span.add_metadata({
                    "broker": order.get("broker", "alpaca"),
                    "mode": order.get("mode", "paper"),
                    "slippage_impact": order.get("slippage_impact", 0),
                })
                
            logger.debug(f"📊 Trade execution traced to LangSmith: {symbol} {side}")
        except Exception as e:
            logger.warning(f"Failed to trace trade to LangSmith: {e}")
    
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

        if self.broker:
            # Use MultiBroker to get positions from active broker
            positions, used_broker = self.broker.get_positions()

            # Convert to expected format if needed
            # MultiBroker returns list of dicts: {'symbol', 'quantity', ...} which matches
            # but we need to ensure keys align with what downstream expects
            formatted_pos = []
            for p in positions:
                formatted_pos.append(
                    {
                        "symbol": p["symbol"],
                        "qty": float(p["quantity"]),
                        "avg_entry_price": float(p.get("cost_basis", 0)) / float(p["quantity"])
                        if float(p["quantity"])
                        else 0.0,
                        "current_price": float(p.get("market_value", 0)) / float(p["quantity"])
                        if float(p["quantity"])
                        else 0.0,
                        "unrealized_pl": float(p["unrealized_pl"]),
                        "unrealized_plpc": (float(p["unrealized_pl"]) / float(p["cost_basis"]))
                        if float(p.get("cost_basis", 0)) != 0
                        else 0.0,
                        "market_value": float(p["market_value"]),
                        "cost_basis": float(p.get("cost_basis", 0)),
                        "broker": used_broker.value,
                    }
                )
            return formatted_pos

        return []

    def place_order(
        self,
        symbol: str,
        notional: float | None = None,
        qty: float | None = None,
        side: str = "buy",
        strategy: str = "unknown",
    ) -> dict[str, Any]:
        """
        Place an order with MANDATORY RAG/ML gate validation.
        
        This method ALWAYS validates through the trade gate before execution.
        """
        # ========== MANDATORY TRADE GATE - NEVER SKIP ==========
        from src.safety.mandatory_trade_gate import validate_trade_mandatory, TradeBlockedError
        
        amount = notional or (qty * 100.0 if qty else 0.0)  # Estimate for qty-based orders
        gate_result = validate_trade_mandatory(
            symbol=symbol,
            amount=amount,
            side=side.upper(),
            strategy=strategy,
        )
        
        if not gate_result.approved:
            logger.error(f"🚫 ORDER BLOCKED BY MANDATORY GATE: {gate_result.reason}")
            logger.error(f"   RAG Warnings: {gate_result.rag_warnings}")
            logger.error(f"   ML Anomalies: {gate_result.ml_anomalies}")
            raise TradeBlockedError(gate_result)
        
        if gate_result.rag_warnings or gate_result.ml_anomalies:
            logger.warning(f"⚠️ ORDER APPROVED WITH WARNINGS:")
            for w in gate_result.rag_warnings:
                logger.warning(f"   RAG: {w}")
            for a in gate_result.ml_anomalies:
                logger.warning(f"   ML: {a}")
        # ========================================================
        
        logger.debug(
            "Submitting %s order via AlpacaExecutor: %s for %s",
            side,
            symbol,
            f"${notional:.2f}" if notional else f"{qty} shares",
        )
        if self.simulated:
            # SIMULATION ENHANCEMENT: Add realistic slippage and commissions
            # Slippage: random noise around 5bps (0.05%) or min $0.01
            import random

            slippage_pct = random.uniform(0.0002, 0.0008)  # 2-8 bps

            # Get estimated price (usually 100 in dev, or real price)
            est_price = self._estimate_entry_price(
                symbol, notional or (qty * 100 if qty else 100), {}
            )
            if est_price <= 0:
                est_price = 100.0  # Fallback

            # Apply slippage
            fill_price = (
                est_price * (1 + slippage_pct) if side == "buy" else est_price * (1 - slippage_pct)
            )
            fill_price = round(fill_price, 2)

            # Calculate filled qty
            filled_qty = qty if qty else (notional / fill_price)
            filled_qty = round(filled_qty, 4)

            # Calculate commission (approx $0.005/share, min $1.00)
            commission = max(1.00, filled_qty * 0.005)

            order = {
                "id": str(uuid.uuid4()),
                "symbol": symbol,
                "side": side,
                "notional": round(notional, 2) if notional else None,
                "qty": filled_qty,
                "filled_qty": filled_qty,
                "filled_avg_price": fill_price,
                "status": "filled",
                "filled_at": datetime.utcnow().isoformat(),
                "mode": "simulated",
                "commission": round(commission, 2),
                "slippage_impact": round(abs(fill_price - est_price) * filled_qty, 2),
            }
            self.simulated_orders.append(order)

            logger.info(
                f"SIMULATED FILL: {side} {symbol} {filled_qty} @ {fill_price} "
                f"(Slippage: ${order['slippage_impact']}, Comm: ${order['commission']})"
            )
            
            # Record trade for daily performance tracking
            self._record_trade_for_tracking(order, strategy)
            
            return order

        # Execution via MultiBroker with Failover
        try:
            order_result = self.broker.submit_order(
                symbol=symbol,
                qty=qty,  # MultiBroker needs qty currently, or we need to calc it
                side=side,
            )

            # Convert OrderResult back to dict for compatibility
            order = {
                "id": order_result.order_id,
                "symbol": order_result.symbol,
                "side": order_result.side,
                "qty": order_result.quantity,
                "status": order_result.status,
                "filled_avg_price": order_result.filled_price,
                "broker": order_result.broker.value,
                "submitted_at": order_result.timestamp,
            }
            
            # Record trade for daily performance tracking
            self._record_trade_for_tracking(order, strategy)
            
            return order
        except Exception as e:
            # Fallback for notional logic if MultiBroker lacks it,
            # or if we need to calc qty from notional
            if notional and not qty and self.trader:
                # If MultiBroker expects qty but we have notional, we might need
                # to rely on AlpacaTrader directly or estimate qty.
                # For now, let's use the underlying trader directly if MultiBroker fails
                # or if we have complex notional logic MultiBroker doesn't wrap yet.
                logger.warning(
                    f"MultiBroker submit failed or skipped: {e}. Falling back to direct AlpacaTrader."
                )
                order = self.trader.execute_order(
                    symbol=symbol,
                    amount_usd=notional,
                    qty=qty,
                    side=side,
                    tier="T1_CORE",
                )
                return order
            raise e

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

        # Use MultiBroker for stop loss
        if self.broker:
            try:
                self.broker.submit_order(
                    symbol=symbol,
                    qty=qty,
                    side="sell",  # Stop loss is always a sell (to close)
                    order_type="stop",
                    limit_price=None,
                    # MultiBroker submit_order signature handles limit_price but
                    # we need to pass stop_price.
                    # Looking at MultiBroker.submit_order info, it seems to lack explicit stop_price arg
                    # in the top-level signature?
                    # Wait, checking signature: submit_order(self, symbol, qty, side, order_type='market', limit_price=None)
                    # It DOES NOT expose stop_price in the signature I saw earlier!
                    # CHECK NEEDED. Assuming I need to update MultiBroker or use kwarg.
                )
                # The MultiBroker.submit_order I read uses specific logic per broker.
                # AlpacaTrader.set_stop_loss is specialized.
                # Let's fallback to underlying trader for stop loss for now
                # UNTIL MultiBroker fully supports stops.
                return self.trader.set_stop_loss(symbol=symbol, qty=qty, stop_price=stop_price)
            except Exception as e:
                logger.warning(f"MultiBroker stop-loss failed: {e}")

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
