"""
Broker System - Alpaca Trading Integration.

Simple wrapper around Alpaca for trading operations.
No over-engineered failover - just clean Alpaca integration.

Primary (and only) broker: Alpaca (paper trading)

Author: Trading System
Created: 2025-12-08
Updated: 2025-12-23 - Simplified to Alpaca-only (removed dead code)
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BrokerType(Enum):
    """Available broker types."""

    ALPACA = "alpaca"


@dataclass
class OrderResult:
    """Unified order result."""

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
    Broker trading system using Alpaca.

    Usage:
        broker = MultiBroker()
        result = broker.submit_order("AAPL", 10, "buy")
    """

    def __init__(self):
        """Initialize broker system with Alpaca."""
        self._alpaca_client = None
        logger.info("MultiBroker initialized with Alpaca")

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

    def get_account(self) -> tuple[dict, BrokerType]:
        """Get account info from Alpaca."""
        account = self.alpaca.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "status": account.status,
        }, BrokerType.ALPACA

    def get_positions(self) -> tuple[list[dict], BrokerType]:
        """Get positions from Alpaca."""
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
        ], BrokerType.ALPACA

    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> OrderResult:
        """
        Submit order to Alpaca.

        Args:
            symbol: Stock symbol
            qty: Quantity
            side: 'buy' or 'sell'
            order_type: 'market' or 'limit'
            limit_price: Price for limit orders

        Returns:
            OrderResult with order info
        """
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

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

        return OrderResult(
            broker=BrokerType.ALPACA,
            order_id=str(order.id),
            symbol=symbol,
            side=side,
            quantity=qty,
            status=order.status.value if hasattr(order.status, "value") else str(order.status),
            filled_price=float(order.filled_avg_price) if order.filled_avg_price else None,
            timestamp=datetime.now().isoformat(),
        )

    def get_quote(self, symbol: str) -> tuple[dict, BrokerType]:
        """Get quote from Alpaca."""
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest

        api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("APCA_API_KEY_ID")
        secret_key = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("APCA_API_SECRET_KEY")

        client = StockHistoricalDataClient(api_key, secret_key)
        request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
        quotes = client.get_stock_latest_quote(request)

        quote = quotes.get(symbol)
        return {
            "symbol": symbol,
            "bid": float(quote.bid_price) if quote else 0,
            "ask": float(quote.ask_price) if quote else 0,
            "last": (float(quote.bid_price) + float(quote.ask_price)) / 2 if quote else 0,
        }, BrokerType.ALPACA

    def health_check(self) -> dict[str, Any]:
        """Check health of Alpaca."""
        results = {}

        try:
            if self.alpaca:
                account = self.alpaca.get_account()
                results["alpaca"] = {
                    "status": "healthy",
                    "equity": float(account.equity),
                }
        except Exception as e:
            results["alpaca"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        return results


# Singleton instance
_multi_broker: Optional[MultiBroker] = None


def get_multi_broker() -> MultiBroker:
    """Get or create singleton broker instance."""
    global _multi_broker
    if _multi_broker is None:
        _multi_broker = MultiBroker()
    return _multi_broker
