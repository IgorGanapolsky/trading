"""
Multi-Broker Failover System

Automatically fails over between brokers when one is unavailable.
Primary: Alpaca (self-clearing)
Secondary: Interactive Brokers (IBKR) - enterprise-grade
Tertiary: Webull (via Apex Clearing) - zero commission

The system tries brokers in priority order, automatically
switching to the next available broker if one fails.

True redundancy: Three different clearing infrastructures.

Author: Trading System
Created: 2025-12-08
Updated: 2025-12-09 - Added Webull as tertiary failover
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

from src.safety.failover_system import CircuitBreakerPattern

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BrokerType(Enum):
    """Available broker types."""

    ALPACA = "alpaca"
    IBKR = "ibkr"
    WEBULL = "webull"


@dataclass
class BrokerHealth:
    """Health status of a broker."""

    broker: BrokerType
    is_healthy: bool
    last_check: datetime
    consecutive_failures: int
    last_error: Optional[str] = None


@dataclass
class OrderResult:
    """Unified order result across brokers."""

    broker: BrokerType
    order_id: str
    symbol: str
    side: str
    quantity: float
    status: str
    filled_price: Optional[float] = None
    timestamp: str = ""


class MultiBroker:
    """
    Multi-broker trading system with automatic failover.

    Usage:
        broker = MultiBroker()

        # Automatically tries Alpaca first, then Tradier
        result = broker.submit_order("AAPL", 10, "buy")

        # Check which broker was used
        print(f"Order placed on {result.broker.value}")
    """

    def __init__(
        self,
        primary: BrokerType = BrokerType.ALPACA,
        enable_failover: bool = True,
    ):
        """
        Initialize multi-broker system.

        Args:
            primary: Primary broker to use
            enable_failover: Whether to failover to backup on failure
        """
        self.primary = primary
        self.enable_failover = enable_failover

        # Circuit breakers for each broker
        self.circuit_breakers: dict[BrokerType, CircuitBreakerPattern] = {
            BrokerType.ALPACA: CircuitBreakerPattern(failure_threshold=3),
            BrokerType.IBKR: CircuitBreakerPattern(failure_threshold=3),
            BrokerType.WEBULL: CircuitBreakerPattern(failure_threshold=3),
        }

        # Health status
        self.health: dict[BrokerType, BrokerHealth] = {}

        # Initialize broker clients lazily
        self._alpaca_client = None
        self._ibkr_client = None
        self._webull_client = None

        logger.info(
            f"MultiBroker initialized with primary={primary.value}, failover={enable_failover}"
        )

    @property
    def alpaca(self):
        """Lazy-load Alpaca client."""
        if self._alpaca_client is None:
            try:
                from alpaca.trading.client import TradingClient

                api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("APCA_API_KEY_ID")
                secret_key = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get(
                    "APCA_API_SECRET_KEY"
                )

                if api_key and secret_key:
                    self._alpaca_client = TradingClient(api_key, secret_key, paper=True)
                    logger.info("Alpaca client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Alpaca: {e}")
        return self._alpaca_client

    @property
    def ibkr(self):
        """Lazy-load IBKR client."""
        if self._ibkr_client is None:
            try:
                from src.brokers.ibkr_client import IBKRClient

                client = IBKRClient(paper=True)
                if client.is_configured():
                    self._ibkr_client = client
                    logger.info("IBKR client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize IBKR: {e}")
        return self._ibkr_client

    @property
    def webull(self):
        """Lazy-load Webull client."""
        if self._webull_client is None:
            try:
                from src.brokers.webull_client import WebullClient

                client = WebullClient(paper=True)
                if client.is_configured():
                    self._webull_client = client
                    logger.info("Webull client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Webull: {e}")
        return self._webull_client

    def _get_broker_order(self) -> list[BrokerType]:
        """Get order of brokers to try based on circuit breaker state."""
        brokers = []

        # Define failover priority order
        # Primary: Alpaca (self-clearing, best API)
        # Secondary: IBKR (enterprise-grade, battle-tested)
        # Tertiary: Webull (zero commission, Apex clearing)
        priority_order = [BrokerType.ALPACA, BrokerType.IBKR, BrokerType.WEBULL]

        # Start with primary
        if self.circuit_breakers[self.primary].can_execute():
            brokers.append(self.primary)

        # Add backups if failover enabled
        if self.enable_failover:
            for broker in priority_order:
                if broker != self.primary and self.circuit_breakers[broker].can_execute():
                    brokers.append(broker)

        return brokers

    def _execute_with_failover(
        self,
        alpaca_func: Callable[[], T],
        ibkr_func: Callable[[], T],
        operation_name: str,
        webull_func: Optional[Callable[[], T]] = None,
    ) -> tuple[T, BrokerType]:
        """
        Execute operation with automatic failover.

        Args:
            alpaca_func: Function to call for Alpaca
            ibkr_func: Function to call for IBKR
            operation_name: Name of operation for logging
            webull_func: Optional function to call for Webull

        Returns:
            Tuple of (result, broker_used)
        """
        brokers_to_try = self._get_broker_order()

        if not brokers_to_try:
            raise RuntimeError("All brokers are unavailable (circuit breakers open)")

        last_error = None

        for broker in brokers_to_try:
            circuit = self.circuit_breakers[broker]

            try:
                if broker == BrokerType.ALPACA and self.alpaca:
                    result = alpaca_func()
                elif broker == BrokerType.IBKR and self.ibkr:
                    result = ibkr_func()
                elif broker == BrokerType.WEBULL and self.webull and webull_func:
                    result = webull_func()
                else:
                    continue

                # Success - record and return
                circuit.record_success()
                logger.info(f"{operation_name} succeeded on {broker.value}")
                return result, broker

            except Exception as e:
                circuit.record_failure()
                last_error = e
                logger.warning(f"{operation_name} failed on {broker.value}: {e}")

                # Update health
                self.health[broker] = BrokerHealth(
                    broker=broker,
                    is_healthy=False,
                    last_check=datetime.now(),
                    consecutive_failures=circuit.failure_count,
                    last_error=str(e),
                )

        # All brokers failed
        raise RuntimeError(f"All brokers failed for {operation_name}: {last_error}")

    def get_account(self) -> tuple[dict, BrokerType]:
        """Get account info from available broker."""

        def alpaca_call():
            account = self.alpaca.get_account()
            return {
                "equity": float(account.equity),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "status": account.status,
            }

        def ibkr_call():
            account = self.ibkr.get_account()
            return {
                "equity": account.equity,
                "cash": account.cash,
                "buying_power": account.buying_power,
                "status": account.status,
            }

        def webull_call():
            account = self.webull.get_account()
            return {
                "equity": account.equity,
                "cash": account.cash,
                "buying_power": account.buying_power,
                "status": account.status,
            }

        return self._execute_with_failover(
            alpaca_call, ibkr_call, "get_account", webull_call
        )

    def get_positions(self) -> tuple[list[dict], BrokerType]:
        """Get positions from available broker."""

        def alpaca_call():
            positions = self.alpaca.get_all_positions()
            return [
                {
                    "symbol": pos.symbol,
                    "quantity": float(pos.qty),
                    "market_value": float(pos.market_value),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "cost_basis": float(pos.cost_basis),
                }
                for pos in positions
            ]

        def ibkr_call():
            positions = self.ibkr.get_positions()
            return [
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "market_value": pos.market_value,
                    "unrealized_pl": pos.unrealized_pl,
                    "cost_basis": pos.cost_basis,
                }
                for pos in positions
            ]

        def webull_call():
            positions = self.webull.get_positions()
            return [
                {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "market_value": pos.market_value,
                    "unrealized_pl": pos.unrealized_pl,
                    "cost_basis": pos.cost_basis,
                }
                for pos in positions
            ]

        return self._execute_with_failover(
            alpaca_call, ibkr_call, "get_positions", webull_call
        )

    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> OrderResult:
        """
        Submit order with automatic failover.

        Args:
            symbol: Stock symbol
            qty: Quantity
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            limit_price: Price for limit orders

        Returns:
            OrderResult with broker info
        """
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

        def alpaca_call():
            alpaca_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

            if order_type == "limit" and limit_price:
                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price,
                )
            else:
                request = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                )

            order = self.alpaca.submit_order(request)
            return order

        def ibkr_call():
            return self.ibkr.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type=order_type,
                limit_price=limit_price,
            )

        def webull_call():
            return self.webull.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type=order_type,
                limit_price=limit_price,
            )

        result, broker = self._execute_with_failover(
            alpaca_call, ibkr_call, f"submit_order({symbol})", webull_call
        )

        # Convert to unified OrderResult
        if broker == BrokerType.ALPACA:
            return OrderResult(
                broker=broker,
                order_id=str(result.id),
                symbol=symbol,
                side=side,
                quantity=qty,
                status=result.status.value
                if hasattr(result.status, "value")
                else str(result.status),
                filled_price=float(result.filled_avg_price) if result.filled_avg_price else None,
                timestamp=datetime.now().isoformat(),
            )
        elif broker == BrokerType.IBKR:
            return OrderResult(
                broker=broker,
                order_id=result.id,
                symbol=symbol,
                side=side,
                quantity=qty,
                status=result.status,
                filled_price=result.avg_fill_price,
                timestamp=datetime.now().isoformat(),
            )
        else:  # Webull
            return OrderResult(
                broker=broker,
                order_id=result.id,
                symbol=symbol,
                side=side,
                quantity=qty,
                status=result.status,
                filled_price=result.avg_fill_price,
                timestamp=datetime.now().isoformat(),
            )

    def get_quote(self, symbol: str) -> tuple[dict, BrokerType]:
        """Get quote from available broker."""
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest

        def alpaca_call():
            api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("APCA_API_KEY_ID")
            secret_key = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get(
                "APCA_API_SECRET_KEY"
            )

            client = StockHistoricalDataClient(api_key, secret_key)
            request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
            quotes = client.get_stock_latest_quote(request)

            quote = quotes.get(symbol)
            return {
                "symbol": symbol,
                "bid": float(quote.bid_price) if quote else 0,
                "ask": float(quote.ask_price) if quote else 0,
                "last": (float(quote.bid_price) + float(quote.ask_price)) / 2 if quote else 0,
            }

        def ibkr_call():
            return self.ibkr.get_quote(symbol)

        def webull_call():
            return self.webull.get_quote(symbol)

        return self._execute_with_failover(
            alpaca_call, ibkr_call, f"get_quote({symbol})", webull_call
        )

    def health_check(self) -> dict[str, Any]:
        """Check health of all brokers."""
        results = {}

        # Check Alpaca
        try:
            if self.alpaca:
                account = self.alpaca.get_account()
                results["alpaca"] = {
                    "status": "healthy",
                    "equity": float(account.equity),
                    "circuit_breaker": self.circuit_breakers[BrokerType.ALPACA].state.value,
                }
                self.circuit_breakers[BrokerType.ALPACA].record_success()
        except Exception as e:
            results["alpaca"] = {
                "status": "unhealthy",
                "error": str(e),
                "circuit_breaker": self.circuit_breakers[BrokerType.ALPACA].state.value,
            }
            self.circuit_breakers[BrokerType.ALPACA].record_failure()

        # Check IBKR
        try:
            if self.ibkr and self.ibkr.is_configured():
                account = self.ibkr.get_account()
                results["ibkr"] = {
                    "status": "healthy",
                    "equity": account.equity,
                    "circuit_breaker": self.circuit_breakers[BrokerType.IBKR].state.value,
                }
                self.circuit_breakers[BrokerType.IBKR].record_success()
            else:
                results["ibkr"] = {
                    "status": "not_configured",
                    "circuit_breaker": self.circuit_breakers[BrokerType.IBKR].state.value,
                }
        except Exception as e:
            results["ibkr"] = {
                "status": "unhealthy",
                "error": str(e),
                "circuit_breaker": self.circuit_breakers[BrokerType.IBKR].state.value,
            }
            self.circuit_breakers[BrokerType.IBKR].record_failure()

        # Check Webull
        try:
            if self.webull and self.webull.is_configured():
                account = self.webull.get_account()
                results["webull"] = {
                    "status": "healthy",
                    "equity": account.equity,
                    "circuit_breaker": self.circuit_breakers[BrokerType.WEBULL].state.value,
                }
                self.circuit_breakers[BrokerType.WEBULL].record_success()
            else:
                results["webull"] = {
                    "status": "not_configured",
                    "circuit_breaker": self.circuit_breakers[BrokerType.WEBULL].state.value,
                }
        except Exception as e:
            results["webull"] = {
                "status": "unhealthy",
                "error": str(e),
                "circuit_breaker": self.circuit_breakers[BrokerType.WEBULL].state.value,
            }
            self.circuit_breakers[BrokerType.WEBULL].record_failure()

        return results


# Singleton instance
_multi_broker: Optional[MultiBroker] = None


def get_multi_broker() -> MultiBroker:
    """Get or create singleton multi-broker instance."""
    global _multi_broker
    if _multi_broker is None:
        _multi_broker = MultiBroker()
    return _multi_broker


# CLI interface
if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO)

    broker = get_multi_broker()

    if len(sys.argv) < 2:
        print("Usage: python multi_broker.py [health|account|positions]")
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "health":
        health = broker.health_check()
        print(json.dumps(health, indent=2))

    elif command == "account":
        try:
            account, used_broker = broker.get_account()
            print(f"Broker: {used_broker.value}")
            print(json.dumps(account, indent=2))
        except Exception as e:
            print(f"Error: {e}")

    elif command == "positions":
        try:
            positions, used_broker = broker.get_positions()
            print(f"Broker: {used_broker.value}")
            print(json.dumps(positions, indent=2))
        except Exception as e:
            print(f"Error: {e}")

    else:
        print(f"Unknown command: {command}")
