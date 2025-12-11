"""
Tradier Broker Client - Backup broker for failover.

Tradier is an API-first brokerage with similar REST API to Alpaca.
Used as backup when Alpaca is unavailable.

API Docs: https://documentation.tradier.com/

Author: Trading System
Created: 2025-12-08
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"
    BUY_TO_COVER = "buy_to_cover"
    SELL_SHORT = "sell_short"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class TradierOrder:
    """Order response from Tradier."""

    id: str
    symbol: str
    side: str
    quantity: float
    filled_quantity: float
    price: Optional[float]
    avg_fill_price: Optional[float]
    status: str
    created_at: str
    order_type: str


@dataclass
class TradierPosition:
    """Position from Tradier."""

    symbol: str
    quantity: float
    cost_basis: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float


@dataclass
class TradierAccount:
    """Account info from Tradier."""

    account_number: str
    equity: float
    cash: float
    buying_power: float
    status: str


class TradierClient:
    """
    Tradier API client for backup trading.

    Mirrors Alpaca client interface for easy failover.
    """

    # API endpoints
    SANDBOX_URL = "https://sandbox.tradier.com/v1"
    PRODUCTION_URL = "https://api.tradier.com/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        account_id: Optional[str] = None,
        sandbox: bool = True,
    ):
        """
        Initialize Tradier client.

        Args:
            api_key: Tradier API key (or TRADIER_API_KEY env var)
            account_id: Tradier account ID (or TRADIER_ACCOUNT_ID env var)
            sandbox: Use sandbox environment (default True for safety)
        """
        self.api_key = api_key or os.environ.get("TRADIER_API_KEY")
        self.account_id = account_id or os.environ.get("TRADIER_ACCOUNT_ID")
        self.sandbox = sandbox

        self.base_url = self.SANDBOX_URL if sandbox else self.PRODUCTION_URL

        if not self.api_key:
            logger.warning("Tradier API key not configured")
        if not self.account_id:
            logger.warning("Tradier account ID not configured")

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
    ) -> dict:
        """Make API request to Tradier."""
        url = f"{self.base_url}{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        if data:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = "&".join(f"{k}={v}" for k, v in data.items()).encode()
        else:
            body = None

        req = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            logger.error(f"Tradier API error: {e.code} - {error_body}")
            raise
        except Exception as e:
            logger.error(f"Tradier request failed: {e}")
            raise

    def is_configured(self) -> bool:
        """Check if Tradier is properly configured."""
        return bool(self.api_key and self.account_id)

    def get_account(self) -> TradierAccount:
        """Get account information."""
        response = self._request("GET", f"/accounts/{self.account_id}/balances")

        balances = response.get("balances", {})

        return TradierAccount(
            account_number=self.account_id,
            equity=float(balances.get("total_equity", 0)),
            cash=float(balances.get("total_cash", 0)),
            buying_power=float(balances.get("stock_buying_power", 0)),
            status="ACTIVE" if balances else "UNKNOWN",
        )

    def get_positions(self) -> list[TradierPosition]:
        """Get all positions."""
        response = self._request("GET", f"/accounts/{self.account_id}/positions")

        positions_data = response.get("positions", {})
        if positions_data == "null" or not positions_data:
            return []

        position_list = positions_data.get("position", [])
        if isinstance(position_list, dict):
            position_list = [position_list]

        positions = []
        for pos in position_list:
            positions.append(
                TradierPosition(
                    symbol=pos.get("symbol", ""),
                    quantity=float(pos.get("quantity", 0)),
                    cost_basis=float(pos.get("cost_basis", 0)),
                    current_price=0.0,  # Need separate quote call
                    market_value=float(pos.get("market_value", 0)),
                    unrealized_pl=float(pos.get("unrealized_pl", 0)),
                    unrealized_pl_pct=float(pos.get("unrealized_plpc", 0)),
                )
            )

        return positions

    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> TradierOrder:
        """
        Submit an order.

        Args:
            symbol: Stock symbol
            qty: Quantity to trade
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop', 'stop_limit'
            limit_price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            time_in_force: 'day', 'gtc', 'pre', 'post'
        """
        data = {
            "class": "equity",
            "symbol": symbol,
            "side": side.lower(),
            "quantity": str(int(qty)) if qty == int(qty) else str(qty),
            "type": order_type,
            "duration": time_in_force,
        }

        if limit_price and order_type in ("limit", "stop_limit"):
            data["price"] = str(limit_price)

        if stop_price and order_type in ("stop", "stop_limit"):
            data["stop"] = str(stop_price)

        response = self._request(
            "POST",
            f"/accounts/{self.account_id}/orders",
            data=data,
        )

        order_data = response.get("order", {})

        return TradierOrder(
            id=str(order_data.get("id", "")),
            symbol=symbol,
            side=side,
            quantity=qty,
            filled_quantity=0.0,
            price=limit_price,
            avg_fill_price=None,
            status=order_data.get("status", "pending"),
            created_at=datetime.now().isoformat(),
            order_type=order_type,
        )

    def get_order(self, order_id: str) -> TradierOrder:
        """Get order by ID."""
        response = self._request(
            "GET",
            f"/accounts/{self.account_id}/orders/{order_id}",
        )

        order = response.get("order", {})

        return TradierOrder(
            id=str(order.get("id", "")),
            symbol=order.get("symbol", ""),
            side=order.get("side", ""),
            quantity=float(order.get("quantity", 0)),
            filled_quantity=float(order.get("exec_quantity", 0)),
            price=float(order.get("price", 0)) if order.get("price") else None,
            avg_fill_price=float(order.get("avg_fill_price", 0))
            if order.get("avg_fill_price")
            else None,
            status=order.get("status", "unknown"),
            created_at=order.get("create_date", ""),
            order_type=order.get("type", ""),
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self._request(
                "DELETE",
                f"/accounts/{self.account_id}/orders/{order_id}",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol."""
        response = self._request("GET", f"/markets/quotes?symbols={symbol}")

        quotes = response.get("quotes", {})
        quote = quotes.get("quote", {})

        if isinstance(quote, list):
            quote = quote[0] if quote else {}

        return {
            "symbol": quote.get("symbol", symbol),
            "last": float(quote.get("last", 0)),
            "bid": float(quote.get("bid", 0)),
            "ask": float(quote.get("ask", 0)),
            "volume": int(quote.get("volume", 0)),
            "change": float(quote.get("change", 0)),
            "change_pct": float(quote.get("change_percentage", 0)),
        }

    def get_market_clock(self) -> dict:
        """Get market clock/status."""
        response = self._request("GET", "/markets/clock")

        clock = response.get("clock", {})

        return {
            "is_open": clock.get("state", "") == "open",
            "next_open": clock.get("next_open", ""),
            "next_close": clock.get("next_close", ""),
        }


# Singleton instance
_tradier_client: Optional[TradierClient] = None


def get_tradier_client(sandbox: bool = True) -> TradierClient:
    """Get or create singleton Tradier client."""
    global _tradier_client
    if _tradier_client is None:
        _tradier_client = TradierClient(sandbox=sandbox)
    return _tradier_client
