"""
Tradier Client - Tertiary broker for failover redundancy.

Tradier is an API-first brokerage designed specifically for algorithmic trading.
One of the cleanest broker APIs available with excellent documentation.

Features:
- Official REST API (production-grade)
- Cloud-based (no desktop client required)
- Low commissions ($0 stock trades, competitive options)
- Real-time streaming quotes
- Paper trading (sandbox environment)

API Docs: https://documentation.tradier.com/
Sandbox: https://sandbox.tradier.com/

Author: Trading System
Created: 2025-12-09
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


class TradierOrderSide(Enum):
    BUY = "buy"
    SELL = "sell"
    BUY_TO_COVER = "buy_to_cover"
    SELL_SHORT = "sell_short"


class TradierOrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TradierOrderStatus(Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TradierDuration(Enum):
    DAY = "day"
    GTC = "gtc"
    PRE = "pre"
    POST = "post"


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

    account_id: str
    equity: float
    cash: float
    buying_power: float
    status: str


class TradierClient:
    """
    Tradier Brokerage API client for tertiary failover trading.

    Tradier is an API-first cloud brokerage with one of the best REST APIs
    in the industry. Uses standard OAuth bearer token authentication.

    Environment Variables:
        TRADIER_ACCOUNT_NUMBER: Your Tradier account number
        TRADIER_API_KEY: Your Tradier API access token

    For paper trading, use sandbox credentials and set paper=True.
    """

    # Tradier API endpoints
    BASE_URL = "https://api.tradier.com/v1"
    SANDBOX_URL = "https://sandbox.tradier.com/v1"

    def __init__(
        self,
        account_number: Optional[str] = None,
        api_key: Optional[str] = None,
        paper: bool = True,
    ):
        """
        Initialize Tradier client.

        Args:
            account_number: Tradier account number (or TRADIER_ACCOUNT_NUMBER env var)
            api_key: Tradier API key/token (or TRADIER_API_KEY env var)
            paper: Use sandbox/paper trading (default True for safety)
        """
        self.account_number = account_number or os.environ.get("TRADIER_ACCOUNT_NUMBER")
        self.api_key = api_key or os.environ.get("TRADIER_API_KEY")
        self.paper = paper

        self.base_url = self.SANDBOX_URL if paper else self.BASE_URL

        if not self.account_number:
            logger.warning("Tradier account number not configured")
        if not self.api_key:
            logger.warning("Tradier API key not configured")

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """Make API request to Tradier."""
        url = f"{self.base_url}{endpoint}"

        # Add query params if provided
        if params:
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query_string}"

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        body = None
        if data:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            body = "&".join(f"{k}={v}" for k, v in data.items()).encode()

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
        return bool(self.account_number and self.api_key)

    def get_account(self) -> TradierAccount:
        """Get account information."""
        if not self.is_configured():
            raise RuntimeError("Tradier client not configured")

        response = self._request("GET", f"/accounts/{self.account_number}/balances")

        balances = response.get("balances", {})

        return TradierAccount(
            account_id=self.account_number or "",
            equity=float(balances.get("equity", 0) or balances.get("total_equity", 0)),
            cash=float(
                balances.get("cash", {}).get("cash_available", 0)
                if isinstance(balances.get("cash"), dict)
                else balances.get("total_cash", 0)
            ),
            buying_power=float(
                balances.get("buying_power", 0)
                or balances.get("margin", {}).get("stock_buying_power", 0)
            ),
            status="ACTIVE" if balances.get("account_type") else "UNKNOWN",
        )

    def get_positions(self) -> list[TradierPosition]:
        """Get all positions."""
        if not self.is_configured():
            return []

        response = self._request("GET", f"/accounts/{self.account_number}/positions")

        positions_data = response.get("positions", {})
        if not positions_data or positions_data == "null":
            return []

        # Positions can be a single dict or list
        position_list = positions_data.get("position", [])
        if isinstance(position_list, dict):
            position_list = [position_list]

        positions = []
        for pos in position_list:
            quantity = float(pos.get("quantity", 0))
            cost_basis = float(pos.get("cost_basis", 0))
            current_price = cost_basis / quantity if quantity else 0
            market_value = current_price * quantity
            unrealized_pl = market_value - cost_basis

            positions.append(
                TradierPosition(
                    symbol=pos.get("symbol", ""),
                    quantity=quantity,
                    cost_basis=cost_basis,
                    current_price=current_price,
                    market_value=market_value,
                    unrealized_pl=unrealized_pl,
                    unrealized_pl_pct=(unrealized_pl / cost_basis * 100) if cost_basis else 0,
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
        if not self.is_configured():
            raise RuntimeError("Tradier client not configured")

        order_data = {
            "class": "equity",
            "symbol": symbol.upper(),
            "side": side.lower(),
            "quantity": str(int(qty)),
            "type": order_type.lower(),
            "duration": time_in_force.lower(),
        }

        if limit_price and order_type in ("limit", "stop_limit"):
            order_data["price"] = str(limit_price)

        if stop_price and order_type in ("stop", "stop_limit"):
            order_data["stop"] = str(stop_price)

        response = self._request(
            "POST",
            f"/accounts/{self.account_number}/orders",
            data=order_data,
        )

        order_info = response.get("order", {})
        order_id = str(order_info.get("id", ""))
        status = order_info.get("status", "pending")

        return TradierOrder(
            id=order_id,
            symbol=symbol,
            side=side,
            quantity=qty,
            filled_quantity=0.0,
            price=limit_price,
            avg_fill_price=None,
            status=status,
            created_at=datetime.now().isoformat(),
            order_type=order_type,
        )

    def get_order(self, order_id: str) -> TradierOrder:
        """Get order by ID."""
        if not self.is_configured():
            raise RuntimeError("Tradier client not configured")

        response = self._request("GET", f"/accounts/{self.account_number}/orders/{order_id}")

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

    def get_orders(self) -> list[TradierOrder]:
        """Get all orders."""
        if not self.is_configured():
            return []

        response = self._request("GET", f"/accounts/{self.account_number}/orders")

        orders_data = response.get("orders", {})
        if not orders_data or orders_data == "null":
            return []

        order_list = orders_data.get("order", [])
        if isinstance(order_list, dict):
            order_list = [order_list]

        orders = []
        for order in order_list:
            orders.append(
                TradierOrder(
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
            )

        return orders

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if not self.is_configured():
            return False

        try:
            self._request(
                "DELETE",
                f"/accounts/{self.account_number}/orders/{order_id}",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol."""
        try:
            response = self._request("GET", "/markets/quotes", params={"symbols": symbol.upper()})

            quotes = response.get("quotes", {})
            quote = quotes.get("quote", {})

            if isinstance(quote, list):
                quote = quote[0] if quote else {}

            return {
                "symbol": symbol,
                "last": float(quote.get("last", 0)),
                "bid": float(quote.get("bid", 0)),
                "ask": float(quote.get("ask", 0)),
                "volume": int(quote.get("volume", 0)),
                "change": float(quote.get("change", 0)),
                "change_pct": float(quote.get("change_percentage", 0)),
            }
        except Exception as e:
            logger.warning(f"Failed to get quote for {symbol}: {e}")

        return {
            "symbol": symbol,
            "last": 0,
            "bid": 0,
            "ask": 0,
            "volume": 0,
            "change": 0,
            "change_pct": 0,
        }

    def get_market_clock(self) -> dict:
        """Get market clock/status."""
        try:
            response = self._request("GET", "/markets/clock")

            clock = response.get("clock", {})

            return {
                "is_open": clock.get("state", "").lower() == "open",
                "next_open": clock.get("next_open", ""),
                "next_close": clock.get("next_close", ""),
            }
        except Exception as e:
            logger.warning(f"Failed to get market clock: {e}")

        # Fallback to time-based approximation
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        hour = now.hour
        weekday = now.weekday()

        is_open = weekday < 5 and 14 <= hour < 21

        return {
            "is_open": is_open,
            "next_open": "",
            "next_close": "",
        }

    def get_history(
        self, symbol: str, interval: str = "daily", start: str = "", end: str = ""
    ) -> list[dict]:
        """
        Get historical price data.

        Args:
            symbol: Stock symbol
            interval: 'daily', 'weekly', 'monthly'
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
        """
        try:
            params = {"symbol": symbol.upper(), "interval": interval}
            if start:
                params["start"] = start
            if end:
                params["end"] = end

            response = self._request("GET", "/markets/history", params=params)

            history = response.get("history", {})
            if not history or history == "null":
                return []

            day_data = history.get("day", [])
            if isinstance(day_data, dict):
                day_data = [day_data]

            return [
                {
                    "date": day.get("date"),
                    "open": float(day.get("open", 0)),
                    "high": float(day.get("high", 0)),
                    "low": float(day.get("low", 0)),
                    "close": float(day.get("close", 0)),
                    "volume": int(day.get("volume", 0)),
                }
                for day in day_data
            ]
        except Exception as e:
            logger.warning(f"Failed to get history for {symbol}: {e}")
            return []


# Singleton instance
_tradier_client: Optional[TradierClient] = None


def get_tradier_client(paper: bool = True) -> TradierClient:
    """Get or create singleton Tradier client."""
    global _tradier_client
    if _tradier_client is None:
        _tradier_client = TradierClient(paper=paper)
    return _tradier_client
