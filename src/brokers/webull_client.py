"""
Webull Client - Tertiary broker for failover redundancy.

Webull provides an official OpenAPI for algorithmic trading.
Uses Apex Clearing for securities (different infrastructure from Alpaca/IBKR).

Features:
- Official API (not unofficial like Robinhood)
- Zero commission trading
- Stock Lending Income Program (via Apex)
- Paper trading support

API Docs: https://developer.webull.com/
SDK: https://github.com/webull-inc/openapi-python-sdk

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


class WebullOrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class WebullOrderType(Enum):
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP_LMT"


class WebullOrderStatus(Enum):
    PENDING = "Pending"
    WORKING = "Working"
    FILLED = "Filled"
    PARTIALLY_FILLED = "PartialFilled"
    CANCELLED = "Cancelled"
    REJECTED = "Failed"
    EXPIRED = "Expired"


@dataclass
class WebullOrder:
    """Order response from Webull."""

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
class WebullPosition:
    """Position from Webull."""

    symbol: str
    quantity: float
    cost_basis: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float


@dataclass
class WebullAccount:
    """Account info from Webull."""

    account_id: str
    equity: float
    cash: float
    buying_power: float
    status: str


class WebullClient:
    """
    Webull OpenAPI client for tertiary failover trading.

    The Webull OpenAPI provides official REST access to trading services.
    Uses Apex Clearing - different infrastructure from Alpaca (self-clearing)
    and IBKR, providing true redundancy.

    Environment Variables:
        WEBULL_APP_KEY: Your Webull app key
        WEBULL_APP_SECRET: Your Webull app secret
        WEBULL_ACCOUNT_ID: Your Webull account ID
        WEBULL_ACCESS_TOKEN: OAuth access token (after auth flow)

    For paper trading, use paper trading credentials.
    """

    # Webull OpenAPI endpoints
    BASE_URL = "https://api.webull.com/openapi"
    PAPER_URL = "https://paper-api.webull.com/openapi"

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        account_id: Optional[str] = None,
        access_token: Optional[str] = None,
        paper: bool = True,
    ):
        """
        Initialize Webull client.

        Args:
            app_key: Webull app key (or WEBULL_APP_KEY env var)
            app_secret: Webull app secret (or WEBULL_APP_SECRET env var)
            account_id: Webull account ID (or WEBULL_ACCOUNT_ID env var)
            access_token: OAuth access token (or WEBULL_ACCESS_TOKEN env var)
            paper: Use paper trading (default True for safety)
        """
        self.app_key = app_key or os.environ.get("WEBULL_APP_KEY")
        self.app_secret = app_secret or os.environ.get("WEBULL_APP_SECRET")
        self.account_id = account_id or os.environ.get("WEBULL_ACCOUNT_ID")
        self.access_token = access_token or os.environ.get("WEBULL_ACCESS_TOKEN")
        self.paper = paper

        self.base_url = self.PAPER_URL if paper else self.BASE_URL

        if not self.app_key:
            logger.warning("Webull app key not configured")
        if not self.access_token:
            logger.warning("Webull access token not configured")

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
    ) -> dict:
        """Make API request to Webull OpenAPI."""
        url = f"{self.base_url}{endpoint}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "app_key": self.app_key or "",
        }

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        body = json.dumps(data).encode() if data else None

        req = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            logger.error(f"Webull API error: {e.code} - {error_body}")
            raise
        except Exception as e:
            logger.error(f"Webull request failed: {e}")
            raise

    def is_configured(self) -> bool:
        """Check if Webull is properly configured."""
        return bool(self.app_key and self.access_token and self.account_id)

    def get_account(self) -> WebullAccount:
        """Get account information."""
        if not self.is_configured():
            raise RuntimeError("Webull client not configured")

        response = self._request("GET", f"/account/{self.account_id}")

        return WebullAccount(
            account_id=self.account_id or "",
            equity=float(response.get("netLiquidation", 0)),
            cash=float(response.get("cash", 0)),
            buying_power=float(response.get("dayBuyingPower", 0)),
            status="ACTIVE" if response.get("status") == "Active" else "UNKNOWN",
        )

    def get_positions(self) -> list[WebullPosition]:
        """Get all positions."""
        if not self.is_configured():
            return []

        response = self._request("GET", f"/account/{self.account_id}/positions")

        if not response or not isinstance(response, list):
            return []

        positions = []
        for pos in response:
            quantity = float(pos.get("quantity", 0))
            cost_basis = float(pos.get("costPrice", 0)) * quantity
            current_price = float(pos.get("lastPrice", 0))
            market_value = current_price * quantity
            unrealized_pl = market_value - cost_basis

            positions.append(
                WebullPosition(
                    symbol=pos.get("ticker", {}).get("symbol", ""),
                    quantity=quantity,
                    cost_basis=cost_basis,
                    current_price=current_price,
                    market_value=market_value,
                    unrealized_pl=unrealized_pl,
                    unrealized_pl_pct=(unrealized_pl / cost_basis * 100)
                    if cost_basis
                    else 0,
                )
            )

        return positions

    def _get_ticker_id(self, symbol: str) -> str:
        """Get ticker ID for a symbol (required for Webull orders)."""
        response = self._request("GET", f"/instruments/ticker?symbol={symbol}")

        if response and isinstance(response, dict):
            return str(response.get("tickerId", ""))

        raise ValueError(f"Could not find ticker ID for symbol: {symbol}")

    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "DAY",
    ) -> WebullOrder:
        """
        Submit an order.

        Args:
            symbol: Stock symbol
            qty: Quantity to trade
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop', 'stop_limit'
            limit_price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            time_in_force: 'DAY', 'GTC', 'IOC'
        """
        if not self.is_configured():
            raise RuntimeError("Webull client not configured")

        # Get ticker ID
        ticker_id = self._get_ticker_id(symbol)

        # Map order type
        webull_order_type = {
            "market": "MKT",
            "limit": "LMT",
            "stop": "STP",
            "stop_limit": "STP_LMT",
        }.get(order_type.lower(), "MKT")

        order_data = {
            "accountId": self.account_id,
            "tickerId": ticker_id,
            "orderType": webull_order_type,
            "action": side.upper(),
            "quantity": int(qty),
            "timeInForce": time_in_force,
        }

        if limit_price and order_type in ("limit", "stop_limit"):
            order_data["lmtPrice"] = limit_price

        if stop_price and order_type in ("stop", "stop_limit"):
            order_data["auxPrice"] = stop_price

        response = self._request(
            "POST",
            f"/account/{self.account_id}/orders",
            data=order_data,
        )

        order_id = str(response.get("orderId", ""))
        status = response.get("status", "Pending")

        return WebullOrder(
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

    def get_order(self, order_id: str) -> WebullOrder:
        """Get order by ID."""
        if not self.is_configured():
            raise RuntimeError("Webull client not configured")

        response = self._request(
            "GET", f"/account/{self.account_id}/orders/{order_id}"
        )

        return WebullOrder(
            id=str(response.get("orderId", "")),
            symbol=response.get("ticker", {}).get("symbol", ""),
            side=response.get("action", ""),
            quantity=float(response.get("totalQuantity", 0)),
            filled_quantity=float(response.get("filledQuantity", 0)),
            price=float(response.get("lmtPrice", 0))
            if response.get("lmtPrice")
            else None,
            avg_fill_price=float(response.get("avgFilledPrice", 0))
            if response.get("avgFilledPrice")
            else None,
            status=response.get("status", "unknown"),
            created_at=response.get("createTime", ""),
            order_type=response.get("orderType", ""),
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if not self.is_configured():
            return False

        try:
            self._request(
                "DELETE",
                f"/account/{self.account_id}/orders/{order_id}",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol."""
        try:
            response = self._request("GET", f"/market/quote?symbol={symbol}")

            if response and isinstance(response, dict):
                return {
                    "symbol": symbol,
                    "last": float(response.get("close", 0)),
                    "bid": float(response.get("bid", 0)),
                    "ask": float(response.get("ask", 0)),
                    "volume": int(response.get("volume", 0)),
                    "change": float(response.get("change", 0)),
                    "change_pct": float(response.get("changeRatio", 0)) * 100,
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
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        # NYSE hours: 9:30 AM - 4:00 PM ET (14:30 - 21:00 UTC)
        hour = now.hour
        weekday = now.weekday()

        is_open = weekday < 5 and 14 <= hour < 21

        return {
            "is_open": is_open,
            "next_open": "",
            "next_close": "",
        }

    def get_stock_lending_status(self) -> dict:
        """
        Get stock lending program status.

        Webull's Stock Lending Income Program is via Apex Clearing.
        Returns enrollment status and lending activity.
        """
        if not self.is_configured():
            return {"enrolled": False, "income": 0, "securities_on_loan": []}

        try:
            # Note: Actual endpoint may differ - this is a placeholder
            # Webull SLIP enrollment is typically managed through the app
            response = self._request(
                "GET", f"/account/{self.account_id}/securities-lending"
            )

            return {
                "enrolled": response.get("enrolled", False),
                "income": float(response.get("totalIncome", 0)),
                "securities_on_loan": response.get("lentSecurities", []),
            }
        except Exception as e:
            logger.debug(f"Stock lending status not available: {e}")
            return {"enrolled": False, "income": 0, "securities_on_loan": []}


# Singleton instance
_webull_client: Optional[WebullClient] = None


def get_webull_client(paper: bool = True) -> WebullClient:
    """Get or create singleton Webull client."""
    global _webull_client
    if _webull_client is None:
        _webull_client = WebullClient(paper=paper)
    return _webull_client
