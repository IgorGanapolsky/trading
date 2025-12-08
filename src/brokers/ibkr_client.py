"""
Interactive Brokers (IBKR) Client - Backup broker for failover.

IBKR is an enterprise-grade broker used by professional traders worldwide.
Used as backup when Alpaca is unavailable.

This client uses the IBKR Client Portal API (REST-based) for simpler integration.
For production, consider IB Gateway + TWS API for more robust connectivity.

API Docs: https://www.interactivebrokers.com/api/doc.html

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
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP_LMT"


class OrderStatus(Enum):
    PENDING = "PendingSubmit"
    SUBMITTED = "Submitted"
    FILLED = "Filled"
    PARTIALLY_FILLED = "PartiallyFilled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"
    EXPIRED = "Inactive"


@dataclass
class IBKROrder:
    """Order response from IBKR."""

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
class IBKRPosition:
    """Position from IBKR."""

    symbol: str
    quantity: float
    cost_basis: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float


@dataclass
class IBKRAccount:
    """Account info from IBKR."""

    account_id: str
    equity: float
    cash: float
    buying_power: float
    status: str


class IBKRClient:
    """
    Interactive Brokers Client Portal API client for backup trading.

    The Client Portal API provides REST access to IBKR services.
    Requires IBKR Gateway running locally or Client Portal session active.

    For paper trading, use paper trading account credentials.
    """

    # Client Portal Gateway URLs
    GATEWAY_URL = "https://localhost:5000/v1/api"
    PAPER_GATEWAY_URL = "https://localhost:5000/v1/api"  # Same endpoint, different account

    def __init__(
        self,
        account_id: Optional[str] = None,
        gateway_url: Optional[str] = None,
        paper: bool = True,
    ):
        """
        Initialize IBKR client.

        Args:
            account_id: IBKR account ID (or IBKR_ACCOUNT_ID env var)
            gateway_url: Gateway URL (or IBKR_GATEWAY_URL env var)
            paper: Use paper trading account (default True for safety)
        """
        self.account_id = account_id or os.environ.get("IBKR_ACCOUNT_ID")
        self.base_url = gateway_url or os.environ.get(
            "IBKR_GATEWAY_URL", self.GATEWAY_URL
        )
        self.paper = paper

        # SSL verification - IBKR Gateway uses self-signed certs by default
        self.verify_ssl = os.environ.get("IBKR_VERIFY_SSL", "false").lower() == "true"

        if not self.account_id:
            logger.warning("IBKR account ID not configured")

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
    ) -> dict:
        """Make API request to IBKR Client Portal."""
        url = f"{self.base_url}{endpoint}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        body = json.dumps(data).encode() if data else None

        req = Request(url, data=body, headers=headers, method=method)

        try:
            # Note: In production, handle SSL verification properly
            import ssl

            ctx = ssl.create_default_context()
            if not self.verify_ssl:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

            with urlopen(req, timeout=30, context=ctx) as response:
                return json.loads(response.read().decode())
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            logger.error(f"IBKR API error: {e.code} - {error_body}")
            raise
        except Exception as e:
            logger.error(f"IBKR request failed: {e}")
            raise

    def is_configured(self) -> bool:
        """Check if IBKR is properly configured."""
        return bool(self.account_id)

    def get_account(self) -> IBKRAccount:
        """Get account information."""
        response = self._request("GET", f"/portfolio/{self.account_id}/summary")

        return IBKRAccount(
            account_id=self.account_id,
            equity=float(response.get("netliquidationvalue", {}).get("amount", 0)),
            cash=float(response.get("totalcashvalue", {}).get("amount", 0)),
            buying_power=float(response.get("buyingpower", {}).get("amount", 0)),
            status="ACTIVE" if response else "UNKNOWN",
        )

    def get_positions(self) -> list[IBKRPosition]:
        """Get all positions."""
        response = self._request("GET", f"/portfolio/{self.account_id}/positions/0")

        if not response or not isinstance(response, list):
            return []

        positions = []
        for pos in response:
            market_value = float(pos.get("mktValue", 0))
            cost_basis = float(pos.get("avgCost", 0)) * float(pos.get("position", 0))
            unrealized_pl = float(pos.get("unrealizedPnl", 0))

            positions.append(
                IBKRPosition(
                    symbol=pos.get("contractDesc", "").split()[0],  # Extract symbol
                    quantity=float(pos.get("position", 0)),
                    cost_basis=cost_basis,
                    current_price=float(pos.get("mktPrice", 0)),
                    market_value=market_value,
                    unrealized_pl=unrealized_pl,
                    unrealized_pl_pct=(unrealized_pl / cost_basis * 100)
                    if cost_basis
                    else 0,
                )
            )

        return positions

    def _get_conid(self, symbol: str) -> int:
        """Get contract ID for a symbol (required for IBKR orders)."""
        response = self._request(
            "GET", f"/iserver/secdef/search?symbol={symbol}&secType=STK"
        )

        if response and isinstance(response, list) and len(response) > 0:
            # Return the first US stock match
            for item in response:
                if item.get("description", "").upper() in ["NASDAQ", "NYSE", "ARCA"]:
                    return int(item.get("conid", 0))
            # Fallback to first result
            return int(response[0].get("conid", 0))

        raise ValueError(f"Could not find contract ID for symbol: {symbol}")

    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "DAY",
    ) -> IBKROrder:
        """
        Submit an order.

        Args:
            symbol: Stock symbol
            qty: Quantity to trade
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', 'stop', 'stop_limit'
            limit_price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            time_in_force: 'DAY', 'GTC'
        """
        # Get contract ID
        conid = self._get_conid(symbol)

        # Map order type
        ibkr_order_type = {
            "market": "MKT",
            "limit": "LMT",
            "stop": "STP",
            "stop_limit": "STP_LMT",
        }.get(order_type.lower(), "MKT")

        order_data = {
            "orders": [
                {
                    "acctId": self.account_id,
                    "conid": conid,
                    "secType": f"{conid}:STK",
                    "orderType": ibkr_order_type,
                    "side": side.upper(),
                    "quantity": qty,
                    "tif": time_in_force,
                }
            ]
        }

        if limit_price and order_type in ("limit", "stop_limit"):
            order_data["orders"][0]["price"] = limit_price

        if stop_price and order_type in ("stop", "stop_limit"):
            order_data["orders"][0]["auxPrice"] = stop_price

        response = self._request(
            "POST",
            f"/iserver/account/{self.account_id}/orders",
            data=order_data,
        )

        # Handle order confirmation if needed
        if response and isinstance(response, list):
            first_response = response[0]

            # Check if confirmation needed
            if "id" in first_response and "message" in first_response:
                # Confirm the order
                confirm_response = self._request(
                    "POST",
                    f"/iserver/reply/{first_response['id']}",
                    data={"confirmed": True},
                )
                if confirm_response and isinstance(confirm_response, list):
                    first_response = confirm_response[0]

            order_id = str(first_response.get("order_id", first_response.get("id", "")))
            status = first_response.get("order_status", "PendingSubmit")
        else:
            order_id = ""
            status = "Failed"

        return IBKROrder(
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

    def get_order(self, order_id: str) -> IBKROrder:
        """Get order by ID."""
        response = self._request("GET", f"/iserver/account/orders")

        # Find the order in the list
        order = {}
        if response and isinstance(response, dict) and "orders" in response:
            for o in response["orders"]:
                if str(o.get("orderId")) == order_id:
                    order = o
                    break

        return IBKROrder(
            id=str(order.get("orderId", "")),
            symbol=order.get("ticker", ""),
            side=order.get("side", ""),
            quantity=float(order.get("totalSize", 0)),
            filled_quantity=float(order.get("filledQuantity", 0)),
            price=float(order.get("price", 0)) if order.get("price") else None,
            avg_fill_price=float(order.get("avgPrice", 0))
            if order.get("avgPrice")
            else None,
            status=order.get("status", "unknown"),
            created_at=order.get("lastExecutionTime", ""),
            order_type=order.get("orderType", ""),
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self._request(
                "DELETE",
                f"/iserver/account/{self.account_id}/order/{order_id}",
            )
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol."""
        try:
            conid = self._get_conid(symbol)
            response = self._request(
                "GET", f"/iserver/marketdata/snapshot?conids={conid}&fields=31,84,85,86"
            )

            if response and isinstance(response, list) and len(response) > 0:
                quote = response[0]
                return {
                    "symbol": symbol,
                    "last": float(quote.get("31", 0)),  # Last price
                    "bid": float(quote.get("84", 0)),  # Bid price
                    "ask": float(quote.get("85", 0)),  # Ask price
                    "volume": int(quote.get("87", 0)),  # Volume
                    "change": float(quote.get("82", 0)),  # Change
                    "change_pct": float(quote.get("83", 0)),  # Change %
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
        """Get market clock/status (approximation based on time)."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        # NYSE hours: 9:30 AM - 4:00 PM ET (14:30 - 21:00 UTC)
        hour = now.hour
        weekday = now.weekday()

        is_open = weekday < 5 and 14 <= hour < 21

        return {
            "is_open": is_open,
            "next_open": "",  # Would need separate market hours API
            "next_close": "",
        }


# Singleton instance
_ibkr_client: Optional[IBKRClient] = None


def get_ibkr_client(paper: bool = True) -> IBKRClient:
    """Get or create singleton IBKR client."""
    global _ibkr_client
    if _ibkr_client is None:
        _ibkr_client = IBKRClient(paper=paper)
    return _ibkr_client
