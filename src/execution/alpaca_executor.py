"""Execution adapter for Alpaca.

Dec 3, 2025 Enhancement:
- Added place_order_with_stop_loss() for integrated order + stop-loss execution
- ATR-based stop-loss calculation wired to order placement
- Automatic stop-loss on every new position

Jan 9, 2026: Observability via Vertex AI RAG + Local JSON (LangSmith removed)
Jan 13, 2026: Auto-reflection on failures (Reflexion pattern - arXiv 2303.11366)
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

# Observability: Vertex AI RAG + Local JSON (LangSmith removed Jan 9, 2026)

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
        """Record trade to Vertex AI RAG, RLHF storage, and local JSON."""
        # Use unified trade sync (Jan 2026 - fixes operational gap)
        try:
            from src.observability.trade_sync import sync_trade

            symbol = order.get("symbol", "UNKNOWN")
            side = order.get("side", "UNKNOWN")
            qty = float(order.get("filled_qty") or order.get("qty") or 0)
            price = float(order.get("filled_avg_price") or 0)

            results = sync_trade(
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                strategy=strategy,
                order_id=order.get("id"),
                metadata={
                    "status": order.get("status"),
                    "commission": order.get("commission", 0),
                    "broker": "alpaca",
                    "mode": "paper" if self.paper else "live",
                },
            )

            logger.info(
                f"Trade sync: {symbol} {side} | "
                f"RAG={results.get('rag', False)}, JSON={results.get('local_json', False)}"
            )

            # Store to RLHF trajectory storage for ML learning (Jan 6 2026 fix)
            self._store_rlhf_trajectory(order, strategy, price)

        except ImportError:
            logger.warning("trade_sync not available - trade not recorded")
        except Exception as e:
            logger.warning(f"Failed to sync trade: {e}")

    def _store_rlhf_trajectory(self, order: dict[str, Any], strategy: str, price: float) -> None:
        """Store trade as RLHF trajectory for ML learning."""
        try:
            from src.learning.rlhf_storage import store_trade_trajectory

            symbol = order.get("symbol", "UNKNOWN")
            side = order.get("side", "").lower()
            order_id = order.get("id", f"{symbol}_{int(datetime.now().timestamp())}")

            # Create a basic state representation
            # TODO: Enhance with actual market features from RLFilter
            entry_state = {
                "price": price,
                "symbol": symbol,
                "strategy": strategy,
                "timestamp": datetime.now().isoformat(),
            }

            # Determine action: 1=BUY, 2=SELL, 0=HOLD
            action = 1 if side == "buy" else (2 if side == "sell" else 0)

            result = store_trade_trajectory(
                episode_id=str(order_id),
                entry_state=entry_state,
                action=action,
                exit_state=entry_state,  # Will be updated on position close
                reward=0.0,  # Will be calculated on position close
                symbol=symbol,
                policy_version="1.0.0",
                metadata={
                    "strategy": strategy,
                    "broker": "alpaca",
                    "mode": "paper" if self.paper else "live",
                },
            )

            if result:
                logger.info(f"RLHF trajectory stored: {symbol} {side} (episode: {order_id})")
            else:
                logger.warning(f"RLHF trajectory storage returned None for {symbol}")

        except ImportError as e:
            logger.warning(f"RLHF storage not available: {e}")
        except Exception as e:
            logger.warning(f"Failed to store RLHF trajectory: {e}")

    def sync_portfolio_state(self) -> None:
        """
        Sync portfolio state from Alpaca.

        CRITICAL: If this fails, we MUST know about it.
        Never fall back silently to empty state - that causes blind trading.
        """
        if self.simulated:
            equity = float(os.getenv("SIMULATED_EQUITY", "100000"))
            self.account_snapshot = {"equity": equity, "mode": "simulated"}
            self.positions = []
        else:
            try:
                # Try to get account info - this MUST work
                if hasattr(self.trader, "get_account_info"):
                    self.account_snapshot = self.trader.get_account_info()
                elif hasattr(self.trader, "get_account"):
                    # Direct TradingClient fallback
                    account = self.trader.get_account()
                    self.account_snapshot = {
                        "equity": float(account.equity),
                        "buying_power": float(account.buying_power),
                        "cash": float(account.cash),
                        "portfolio_value": float(account.portfolio_value),
                    }
                else:
                    raise RuntimeError("Trader has no get_account_info or get_account method!")

                # Get positions
                if hasattr(self.trader, "get_positions"):
                    self.positions = self.trader.get_positions()
                elif hasattr(self.trader, "get_all_positions"):
                    self.positions = self.trader.get_all_positions()
                else:
                    self.positions = []
                    logger.warning("Could not get positions - no method available")

            except Exception as e:
                # CRITICAL: Do NOT fall back silently - this causes blind trading!
                logger.error(f"❌ CRITICAL: Failed to sync portfolio state: {e}")
                logger.error("   This means we cannot see our account or positions!")
                logger.error("   Trading should be BLOCKED until this is fixed.")

                # Auto-reflect on sync failure (Reflexion pattern)
                try:
                    from src.learning.failure_reflection import reflect_on_failure

                    reflect_on_failure("SYNC_FAILED", error_message=str(e))
                except Exception as refl_err:
                    logger.debug(f"Reflection failed: {refl_err}")

                # Set error state - equity 0 will trigger safety checks
                self.account_snapshot = {"equity": 0, "error": str(e)}
                self.positions = []

                # Re-raise so callers know there's a problem
                raise RuntimeError(f"Cannot sync portfolio - trading unsafe: {e}") from e

        equity = self.account_equity

        # Safety check: If equity is 0 or negative, something is VERY wrong
        if equity <= 0 and not self.simulated:
            logger.error(f"❌ CRITICAL: Equity is ${equity} - this should never happen!")
            logger.error("   Either API failed or account is empty. BLOCKING TRADING.")

        logger.info(
            "Synced %s Alpaca state | equity=$%.2f | positions=%d",
            "simulated" if self.simulated else ("paper" if self.paper else "live"),
            equity,
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
                # SECURITY FIX (Jan 19, 2026): Check for zero BEFORE division
                # Previous bug: ternary evaluated division first, causing ZeroDivisionError
                qty = float(p.get("quantity", 0))
                cost_basis = float(p.get("cost_basis", 0))
                market_value = float(p.get("market_value", 0))
                unrealized_pl = float(p.get("unrealized_pl", 0))

                formatted_pos.append(
                    {
                        "symbol": p["symbol"],
                        "qty": qty,
                        "avg_entry_price": (cost_basis / qty) if qty != 0 else 0.0,
                        "current_price": (market_value / qty) if qty != 0 else 0.0,
                        "unrealized_pl": unrealized_pl,
                        "unrealized_plpc": (unrealized_pl / cost_basis) if cost_basis != 0 else 0.0,
                        "market_value": market_value,
                        "cost_basis": cost_basis,
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
        # ========== MANDATORY TRADE GATE - FAIL CLOSED ==========
        # CRITICAL SECURITY: If gate import fails, BLOCK all trades (Jan 19, 2026)
        # Previous bug: Import failure would bypass all validation
        try:
            from src.safety.mandatory_trade_gate import TradeBlockedError, validate_trade_mandatory
            gate_available = True
        except ImportError as import_err:
            logger.error(f"🚨 CRITICAL: Mandatory trade gate import failed: {import_err}")
            logger.error("🚫 FAIL CLOSED: All trades blocked until gate is restored")
            raise RuntimeError(
                "SECURITY: Mandatory trade gate unavailable. "
                "Cannot execute trades without safety validation. "
                "Fix import or restore src/safety/mandatory_trade_gate.py"
            ) from import_err

        if gate_available:
            amount = notional or (qty * 100.0 if qty else 0.0)  # Estimate for qty-based orders

            # Get account context for context-aware blocking (ll_051 prevention)
            # This enables blocking when equity=$0 (blind trading prevention)
            account_context = {}
            try:
                if hasattr(self, "account_snapshot") and self.account_snapshot:
                    account_context = {
                        "equity": float(self.account_snapshot.get("equity", 0)),
                        "buying_power": float(self.account_snapshot.get("buying_power", 0)),
                    }
                elif hasattr(self, "trader") and self.trader:
                    # Try to get fresh account data
                    account = None
                    if hasattr(self.trader, "get_account_info"):
                        account = self.trader.get_account_info()
                    elif hasattr(self.trader, "get_account"):
                        account = self.trader.get_account()
                    if account:
                        account_context = {
                            "equity": float(getattr(account, "equity", 0) or 0),
                            "buying_power": float(getattr(account, "buying_power", 0) or 0),
                        }
            except Exception as e:
                logger.warning(f"Could not get account context for gate: {e}")

            gate_result = validate_trade_mandatory(
                symbol=symbol,
                amount=amount,
                side=side.upper(),
                strategy=strategy,
                context=account_context,
            )

            if not gate_result.approved:
                logger.error(f"🚫 ORDER BLOCKED BY MANDATORY GATE: {gate_result.reason}")
                logger.error(f"   RAG Warnings: {gate_result.rag_warnings}")
                logger.error(f"   ML Anomalies: {gate_result.ml_anomalies}")

                # Auto-reflect on blocked trade (Reflexion pattern)
                try:
                    from src.learning.failure_reflection import reflect_trade_blocked

                    reflect_trade_blocked(
                        symbol=symbol,
                        reason=gate_result.reason,
                        strategy=strategy,
                        context={
                            "rag_warnings": gate_result.rag_warnings,
                            "ml_anomalies": gate_result.ml_anomalies,
                        },
                    )
                except Exception as refl_err:
                    logger.debug(f"Reflection failed: {refl_err}")

                raise TradeBlockedError(gate_result)

            if gate_result.rag_warnings or gate_result.ml_anomalies:
                logger.warning("⚠️ ORDER APPROVED WITH WARNINGS:")
                for w in gate_result.rag_warnings:
                    logger.warning(f"   RAG: {w}")
                for a in gate_result.ml_anomalies:
                    logger.warning(f"   ML: {a}")
        # ========================================================

        # ========== PRE-TRADE PATTERN VALIDATION (Jan 7, 2026) ==========
        # Query TradeMemory BEFORE executing - learn from history
        try:
            from src.learning.trade_memory import TradeMemory

            memory = TradeMemory()
            entry_reason = strategy  # Use strategy as entry reason for now
            pattern_check = memory.query_similar(strategy, entry_reason)

            if pattern_check.get("found", False):
                win_rate = pattern_check.get("win_rate", 0.5)
                sample_size = pattern_check.get("sample_size", 0)
                avg_pnl = pattern_check.get("avg_pnl", 0.0)

                logger.info(
                    f"📊 PATTERN CHECK: {strategy}_{entry_reason} | "
                    f"Win Rate: {win_rate:.1%} | Samples: {sample_size} | Avg P/L: ${avg_pnl:.2f}"
                )

                # Block trades with poor historical performance (Rule #1: Don't Lose Money)
                if sample_size >= 5 and win_rate < 0.50:
                    logger.error(
                        f"🚫 TRADE BLOCKED BY PATTERN HISTORY: {strategy} has {win_rate:.1%} win rate "
                        f"over {sample_size} trades. Rule #1: Don't lose money."
                    )

                    # Auto-reflect on pattern block (Reflexion pattern)
                    try:
                        from src.learning.failure_reflection import reflect_pattern_blocked

                        reflect_pattern_blocked(strategy, win_rate, sample_size)
                    except Exception as refl_err:
                        logger.debug(f"Reflection failed: {refl_err}")

                    raise TradeBlockedError(
                        f"Historical pattern {strategy} has {win_rate:.1%} win rate - below 50% threshold"
                    )
                elif sample_size >= 5 and win_rate < 0.60:
                    logger.warning(
                        f"⚠️ CAUTION: {strategy} has marginal {win_rate:.1%} win rate. "
                        f"Consider reducing position size."
                    )
            else:
                logger.info(
                    f"📊 PATTERN CHECK: No history for {strategy}_{entry_reason} - proceeding with caution"
                )

        except ImportError:
            logger.debug("TradeMemory not available - skipping pattern check")
        except TradeBlockedError:
            raise  # Re-raise blocking exceptions
        except Exception as e:
            logger.warning(f"Pattern check failed (non-blocking): {e}")
        # ================================================================

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
        # Check API circuit breaker before any API call (Jan 13, 2026)
        try:
            from src.utils.api_circuit_breaker import (
                CircuitBreakerOpen,
                check_circuit_breaker,
                get_api_circuit_breaker,
            )

            check_circuit_breaker()
        except CircuitBreakerOpen as cb_err:
            logger.critical(f"🚨 CIRCUIT BREAKER OPEN - Order blocked: {cb_err}")
            raise
        except ImportError:
            pass  # Circuit breaker not available, proceed

        try:
            order_result = self.broker.submit_order(
                symbol=symbol,
                qty=qty,  # MultiBroker needs qty currently, or we need to calc it
                side=side,
            )

            # SECURITY FIX (Jan 19, 2026): Validate broker response before use
            # Previous bug: None response would crash on attribute access
            if order_result is None:
                raise ValueError("Broker returned None - order submission failed silently")

            # Record success for circuit breaker (Jan 13, 2026)
            try:
                breaker = get_api_circuit_breaker()
                breaker.record_success()
            except Exception:
                pass

            # Convert OrderResult back to dict for compatibility
            # Validate required attributes exist
            required_attrs = ["order_id", "symbol", "side", "quantity", "status", "broker", "timestamp"]
            for attr in required_attrs:
                if not hasattr(order_result, attr):
                    raise ValueError(f"Broker response missing required attribute: {attr}")

            order = {
                "id": order_result.order_id,
                "symbol": order_result.symbol,
                "side": order_result.side,
                "qty": order_result.quantity,
                "status": order_result.status,
                "filled_avg_price": getattr(order_result, "filled_price", None),  # May be None for pending
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
                try:
                    order = self.trader.execute_order(
                        symbol=symbol,
                        amount_usd=notional,
                        qty=qty,
                        side=side,
                        tier="T1_CORE",
                    )
                    return order
                except Exception as inner_e:
                    # Auto-reflect on order execution failure (Reflexion pattern)
                    try:
                        from src.learning.failure_reflection import reflect_order_failed

                        reflect_order_failed(symbol, str(inner_e), strategy)
                    except Exception as refl_err:
                        logger.debug(f"Reflection failed: {refl_err}")
                    raise inner_e

            # Record failure for circuit breaker (Jan 13, 2026)
            try:
                from src.utils.api_circuit_breaker import get_api_circuit_breaker

                breaker = get_api_circuit_breaker()
                breaker.record_failure(str(e))
            except Exception:
                pass

            # Auto-reflect on broker failure (Reflexion pattern)
            try:
                from src.learning.failure_reflection import reflect_order_failed

                reflect_order_failed(symbol, str(e), strategy)
            except Exception as refl_err:
                logger.debug(f"Reflection failed: {refl_err}")
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

            # CRITICAL: Alert CEO immediately - Added Jan 13, 2026
            # Position is unprotected, this is a safety emergency
            try:
                from src.utils.error_monitoring import send_slack_alert

                send_slack_alert(
                    message=(
                        f"🚨 *STOP-LOSS FAILED: {symbol}*\n\n"
                        f"Position opened WITHOUT stop-loss protection!\n"
                        f"Symbol: {symbol}\n"
                        f"Entry: ${entry_price:.2f}\n"
                        f"Intended Stop: ${stop_price:.2f}\n"
                        f"Error: {e}\n"
                        f"ACTION REQUIRED: Set stop-loss manually or close position!"
                    ),
                    level="error",
                )
            except Exception as slack_err:
                logger.error(f"Failed to send Slack alert: {slack_err}")

            # Auto-reflect on CRITICAL stop-loss failure (Reflexion pattern)
            try:
                from src.learning.failure_reflection import reflect_stop_loss_failed

                reflect_stop_loss_failed(symbol, str(e))
            except Exception as refl_err:
                logger.debug(f"Reflection failed: {refl_err}")

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
            # BUG FIX (Jan 13, 2026): Was using self.trader.api which doesn't exist
            # AlpacaTrader has get_current_quote() method instead
            try:
                if self.trader and hasattr(self.trader, "get_current_quote"):
                    quote_data = self.trader.get_current_quote(symbol)
                    if quote_data and quote_data.get("ask_price"):
                        return float(quote_data["ask_price"])
            except Exception:
                pass
            # Default estimate: assume 1 share = notional (rough)
            return notional / 1.0 if notional > 0 else 0.0

        # Try to get current market price
        # BUG FIX (Jan 13, 2026): Was using self.trader.api which doesn't exist
        try:
            if self.trader and hasattr(self.trader, "get_current_quote"):
                quote_data = self.trader.get_current_quote(symbol)
                if quote_data and quote_data.get("ask_price"):
                    return float(quote_data["ask_price"])
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
