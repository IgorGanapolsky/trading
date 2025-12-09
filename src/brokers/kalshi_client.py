"""
Kalshi Prediction Markets Client - Event-based trading integration.

Kalshi is a CFTC-regulated prediction market platform allowing trading on
binary outcomes for events like elections, weather, crypto, sports, etc.

This client implements the Kalshi REST API for:
- Account management (balance, positions)
- Market data (events, markets, order books)
- Trading (order placement, cancellation)

API Docs: https://docs.kalshi.com/
Demo API: https://demo-api.kalshi.co/trade-api/v2
Prod API: https://trading-api.kalshi.com/trade-api/v2

Author: Trading System
Created: 2025-12-09
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class KalshiOrderSide(Enum):
    """Order side for Kalshi markets."""
    YES = "yes"
    NO = "no"


class KalshiOrderType(Enum):
    """Order types available on Kalshi."""
    MARKET = "market"
    LIMIT = "limit"


class KalshiOrderStatus(Enum):
    """Order status on Kalshi."""
    PENDING = "pending"
    ACTIVE = "active"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "canceled"
    EXPIRED = "expired"


@dataclass
class KalshiMarket:
    """Represents a Kalshi prediction market."""
    ticker: str
    title: str
    subtitle: str
    status: str  # open, closed, settled
    yes_price: float  # Price in cents (0-100)
    no_price: float
    volume: int
    open_interest: int
    close_time: Optional[str] = None
    result: Optional[str] = None  # yes, no, or None if unsettled
    category: str = ""

    @property
    def yes_probability(self) -> float:
        """Convert yes price to implied probability (0-1)."""
        return self.yes_price / 100.0

    @property
    def no_probability(self) -> float:
        """Convert no price to implied probability (0-1)."""
        return self.no_price / 100.0


@dataclass
class KalshiPosition:
    """Position in a Kalshi market."""
    market_ticker: str
    market_title: str
    side: str  # "yes" or "no"
    quantity: int  # Number of contracts
    cost_basis: float  # Total cost in USD
    market_value: float  # Current value in USD
    unrealized_pl: float  # Unrealized P/L in USD
    avg_price: float  # Average entry price (cents)


@dataclass
class KalshiOrder:
    """Order on Kalshi."""
    id: str
    market_ticker: str
    side: str  # "yes" or "no"
    type: str  # "market" or "limit"
    quantity: int
    price: Optional[float]  # Limit price in cents
    filled_quantity: int
    status: str
    created_at: str
    avg_fill_price: Optional[float] = None


@dataclass
class KalshiAccount:
    """Kalshi account information."""
    user_id: str
    balance: float  # Available balance in USD
    portfolio_value: float  # Total portfolio value
    total_deposits: float
    total_withdrawals: float
    status: str = "active"


@dataclass
class KalshiAuth:
    """Authentication state for Kalshi API."""
    token: str
    user_id: str
    expires_at: datetime

    def is_expired(self) -> bool:
        """Check if token is expired (with 1 min buffer)."""
        return datetime.now(timezone.utc) >= self.expires_at


class KalshiClient:
    """
    Kalshi Prediction Markets API client.

    Kalshi offers CFTC-regulated event contracts on outcomes like:
    - Elections and politics
    - Economic indicators (Fed rates, inflation)
    - Weather and climate
    - Crypto prices
    - Sports and entertainment

    Each contract pays $1 if the outcome occurs, $0 otherwise.
    Prices are quoted in cents (0-100 representing probability).

    Usage:
        client = KalshiClient()

        # Get markets
        markets = client.get_markets(category="elections")

        # Check portfolio
        positions = client.get_positions()

        # Place order
        order = client.place_order("TRUMP-24", "yes", 10, limit_price=55)
    """

    # API endpoints
    PROD_URL = "https://trading-api.kalshi.com/trade-api/v2"
    DEMO_URL = "https://demo-api.kalshi.co/trade-api/v2"

    # Token expires after 30 minutes per Kalshi docs
    TOKEN_LIFETIME_SECONDS = 30 * 60

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        api_key: Optional[str] = None,
        private_key_path: Optional[str] = None,
        paper: bool = True,
    ):
        """
        Initialize Kalshi client.

        Args:
            email: Kalshi account email (or KALSHI_EMAIL env var)
            password: Kalshi account password (or KALSHI_PASSWORD env var)
            api_key: Optional API key ID for key-based auth (KALSHI_API_KEY env var)
            private_key_path: Path to private key PEM file (KALSHI_PRIVATE_KEY_PATH env var)
            paper: Use demo API (default True for safety)
        """
        self.email = email or os.environ.get("KALSHI_EMAIL")
        self.password = password or os.environ.get("KALSHI_PASSWORD")
        self.api_key = api_key or os.environ.get("KALSHI_API_KEY")
        self.private_key_path = private_key_path or os.environ.get("KALSHI_PRIVATE_KEY_PATH")
        self.paper = paper

        self.base_url = self.DEMO_URL if paper else self.PROD_URL

        # Auth state
        self._auth: Optional[KalshiAuth] = None

        if not self._has_credentials():
            logger.warning("Kalshi credentials not configured")

    def _has_credentials(self) -> bool:
        """Check if credentials are available."""
        return bool(
            (self.email and self.password) or
            (self.api_key and self.private_key_path)
        )

    def is_configured(self) -> bool:
        """Check if client is properly configured."""
        return self._has_credentials()

    def _login(self) -> KalshiAuth:
        """
        Authenticate with Kalshi and get session token.

        Returns:
            KalshiAuth with token and user_id
        """
        if not self.email or not self.password:
            raise ValueError("Email and password required for login")

        url = f"{self.base_url}/login"

        data = json.dumps({
            "email": self.email,
            "password": self.password,
        }).encode()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        req = Request(url, data=data, headers=headers, method="POST")

        try:
            with urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())

                # Extract token and user_id from response
                token = result.get("token", "")
                member = result.get("member", {})
                user_id = member.get("user_id", "")

                expires_at = datetime.now(timezone.utc).replace(
                    second=0, microsecond=0
                )
                # Token valid for 30 minutes
                from datetime import timedelta
                expires_at += timedelta(seconds=self.TOKEN_LIFETIME_SECONDS - 60)  # 1 min buffer

                self._auth = KalshiAuth(
                    token=token,
                    user_id=user_id,
                    expires_at=expires_at,
                )

                logger.info(f"Kalshi login successful, user_id={user_id[:8]}...")
                return self._auth

        except HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            logger.error(f"Kalshi login failed: {e.code} - {error_body}")
            raise
        except Exception as e:
            logger.error(f"Kalshi login failed: {e}")
            raise

    def _ensure_auth(self) -> KalshiAuth:
        """Ensure we have a valid auth token, refreshing if needed."""
        if self._auth is None or self._auth.is_expired():
            return self._login()
        return self._auth

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """
        Make authenticated API request to Kalshi.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            data: Request body (for POST/PUT)
            params: Query parameters

        Returns:
            Parsed JSON response
        """
        auth = self._ensure_auth()

        # Build URL with query params
        url = f"{self.base_url}{endpoint}"
        if params:
            query_string = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            if query_string:
                url = f"{url}?{query_string}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {auth.token}",
        }

        body = json.dumps(data).encode() if data else None

        req = Request(url, data=body, headers=headers, method=method)

        try:
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode())
        except HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            logger.error(f"Kalshi API error: {e.code} - {error_body}")

            # Handle token expiry
            if e.code == 401:
                self._auth = None
                # Retry once with fresh token
                auth = self._ensure_auth()
                headers["Authorization"] = f"Bearer {auth.token}"
                req = Request(url, data=body, headers=headers, method=method)
                with urlopen(req, timeout=30) as response:
                    return json.loads(response.read().decode())
            raise
        except Exception as e:
            logger.error(f"Kalshi request failed: {e}")
            raise

    def get_account(self) -> KalshiAccount:
        """Get account balance and info."""
        auth = self._ensure_auth()

        response = self._request("GET", f"/portfolio/balance")

        return KalshiAccount(
            user_id=auth.user_id,
            balance=float(response.get("balance", 0)) / 100.0,  # Convert cents to USD
            portfolio_value=float(response.get("portfolio_value", 0)) / 100.0,
            total_deposits=float(response.get("total_deposits", 0)) / 100.0,
            total_withdrawals=float(response.get("total_withdrawals", 0)) / 100.0,
            status="active",
        )

    def get_positions(self) -> list[KalshiPosition]:
        """Get all current positions."""
        response = self._request("GET", "/portfolio/positions")

        positions_data = response.get("market_positions", [])

        positions = []
        for pos in positions_data:
            quantity = pos.get("position", 0)
            if quantity == 0:
                continue

            # Determine side based on position sign
            side = "yes" if quantity > 0 else "no"
            quantity = abs(quantity)

            # Prices are in cents
            avg_price = float(pos.get("average_price", 0))
            market_price = float(pos.get("market_price", 0))
            cost_basis = (avg_price * quantity) / 100.0  # Convert to USD
            market_value = (market_price * quantity) / 100.0

            positions.append(KalshiPosition(
                market_ticker=pos.get("ticker", ""),
                market_title=pos.get("title", pos.get("ticker", "")),
                side=side,
                quantity=quantity,
                cost_basis=cost_basis,
                market_value=market_value,
                unrealized_pl=market_value - cost_basis,
                avg_price=avg_price,
            ))

        return positions

    def get_markets(
        self,
        category: Optional[str] = None,
        status: str = "open",
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> list[KalshiMarket]:
        """
        Get available prediction markets.

        Args:
            category: Filter by category (elections, economics, weather, etc.)
            status: Market status filter (open, closed, settled)
            limit: Max results (1-1000)
            cursor: Pagination cursor

        Returns:
            List of KalshiMarket objects
        """
        params = {
            "status": status,
            "limit": min(limit, 1000),
        }
        if category:
            params["series_ticker"] = category
        if cursor:
            params["cursor"] = cursor

        response = self._request("GET", "/markets", params=params)

        markets = []
        for m in response.get("markets", []):
            markets.append(KalshiMarket(
                ticker=m.get("ticker", ""),
                title=m.get("title", ""),
                subtitle=m.get("subtitle", ""),
                status=m.get("status", ""),
                yes_price=float(m.get("yes_bid", 0) + m.get("yes_ask", 0)) / 2,
                no_price=float(m.get("no_bid", 0) + m.get("no_ask", 0)) / 2,
                volume=int(m.get("volume", 0)),
                open_interest=int(m.get("open_interest", 0)),
                close_time=m.get("close_time"),
                result=m.get("result"),
                category=m.get("category", ""),
            ))

        return markets

    def get_market(self, ticker: str) -> KalshiMarket:
        """Get details for a specific market."""
        response = self._request("GET", f"/markets/{ticker}")

        m = response.get("market", {})
        return KalshiMarket(
            ticker=m.get("ticker", ticker),
            title=m.get("title", ""),
            subtitle=m.get("subtitle", ""),
            status=m.get("status", ""),
            yes_price=float(m.get("yes_bid", 0) + m.get("yes_ask", 0)) / 2,
            no_price=float(m.get("no_bid", 0) + m.get("no_ask", 0)) / 2,
            volume=int(m.get("volume", 0)),
            open_interest=int(m.get("open_interest", 0)),
            close_time=m.get("close_time"),
            result=m.get("result"),
            category=m.get("category", ""),
        )

    def get_orderbook(self, ticker: str) -> dict[str, Any]:
        """
        Get order book for a market.

        Returns:
            Dict with 'yes' and 'no' order book sides,
            each containing 'bids' and 'asks' lists.
        """
        response = self._request("GET", f"/markets/{ticker}/orderbook")

        return {
            "ticker": ticker,
            "yes": {
                "bids": response.get("yes", {}).get("bids", []),
                "asks": response.get("yes", {}).get("asks", []),
            },
            "no": {
                "bids": response.get("no", {}).get("bids", []),
                "asks": response.get("no", {}).get("asks", []),
            },
        }

    def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        limit_price: Optional[float] = None,
        expiration_time: Optional[str] = None,
    ) -> KalshiOrder:
        """
        Place an order on a prediction market.

        Args:
            ticker: Market ticker
            side: "yes" or "no"
            quantity: Number of contracts
            limit_price: Limit price in cents (1-99). If None, market order.
            expiration_time: ISO timestamp for order expiry (optional)

        Returns:
            KalshiOrder with order details
        """
        if side not in ("yes", "no"):
            raise ValueError(f"Invalid side: {side}. Must be 'yes' or 'no'")

        order_type = "limit" if limit_price is not None else "market"

        order_data = {
            "ticker": ticker,
            "side": side,
            "count": quantity,
            "type": order_type,
            "action": "buy",  # buy contracts
        }

        if limit_price is not None:
            # Price in cents (1-99)
            order_data["yes_price"] = int(limit_price) if side == "yes" else 100 - int(limit_price)

        if expiration_time:
            order_data["expiration_time"] = expiration_time

        response = self._request("POST", "/portfolio/orders", data=order_data)

        order = response.get("order", {})
        return KalshiOrder(
            id=order.get("order_id", ""),
            market_ticker=ticker,
            side=side,
            type=order_type,
            quantity=quantity,
            price=limit_price,
            filled_quantity=order.get("filled_count", 0),
            status=order.get("status", "pending"),
            created_at=order.get("created_time", datetime.now().isoformat()),
            avg_fill_price=order.get("avg_fill_price"),
        )

    def sell_position(
        self,
        ticker: str,
        side: str,
        quantity: int,
        limit_price: Optional[float] = None,
    ) -> KalshiOrder:
        """
        Sell contracts from an existing position.

        Args:
            ticker: Market ticker
            side: "yes" or "no" - the side you currently hold
            quantity: Number of contracts to sell
            limit_price: Limit price in cents. If None, market order.

        Returns:
            KalshiOrder with order details
        """
        if side not in ("yes", "no"):
            raise ValueError(f"Invalid side: {side}. Must be 'yes' or 'no'")

        order_type = "limit" if limit_price is not None else "market"

        order_data = {
            "ticker": ticker,
            "side": side,
            "count": quantity,
            "type": order_type,
            "action": "sell",  # sell contracts
        }

        if limit_price is not None:
            order_data["yes_price"] = int(limit_price) if side == "yes" else 100 - int(limit_price)

        response = self._request("POST", "/portfolio/orders", data=order_data)

        order = response.get("order", {})
        return KalshiOrder(
            id=order.get("order_id", ""),
            market_ticker=ticker,
            side=side,
            type=order_type,
            quantity=quantity,
            price=limit_price,
            filled_quantity=order.get("filled_count", 0),
            status=order.get("status", "pending"),
            created_at=order.get("created_time", datetime.now().isoformat()),
            avg_fill_price=order.get("avg_fill_price"),
        )

    def get_orders(
        self,
        ticker: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[KalshiOrder]:
        """
        Get orders.

        Args:
            ticker: Filter by market ticker
            status: Filter by status (pending, active, filled, canceled)

        Returns:
            List of KalshiOrder objects
        """
        params = {}
        if ticker:
            params["ticker"] = ticker
        if status:
            params["status"] = status

        response = self._request("GET", "/portfolio/orders", params=params)

        orders = []
        for o in response.get("orders", []):
            orders.append(KalshiOrder(
                id=o.get("order_id", ""),
                market_ticker=o.get("ticker", ""),
                side=o.get("side", ""),
                type=o.get("type", ""),
                quantity=o.get("count", 0),
                price=o.get("yes_price") if o.get("side") == "yes" else o.get("no_price"),
                filled_quantity=o.get("filled_count", 0),
                status=o.get("status", ""),
                created_at=o.get("created_time", ""),
                avg_fill_price=o.get("avg_fill_price"),
            ))

        return orders

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancellation successful
        """
        try:
            self._request("DELETE", f"/portfolio/orders/{order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def get_events(
        self,
        category: Optional[str] = None,
        status: str = "open",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get events (groups of related markets).

        Args:
            category: Filter by category
            status: Event status (open, closed)
            limit: Max results

        Returns:
            List of event dictionaries
        """
        params = {
            "status": status,
            "limit": limit,
        }
        if category:
            params["series_ticker"] = category

        response = self._request("GET", "/events", params=params)
        return response.get("events", [])

    def get_market_history(
        self,
        ticker: str,
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Get historical price data for a market.

        Args:
            ticker: Market ticker
            min_ts: Minimum timestamp (unix seconds)
            max_ts: Maximum timestamp (unix seconds)

        Returns:
            List of historical data points
        """
        params = {}
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts

        response = self._request(
            "GET", f"/markets/{ticker}/candlesticks/1h", params=params
        )
        return response.get("candlesticks", [])

    def is_market_open(self) -> bool:
        """
        Check if Kalshi markets are tradable.

        Kalshi markets trade 24/7 but may have maintenance windows.
        """
        try:
            # Try to get any market as a health check
            markets = self.get_markets(limit=1)
            return len(markets) > 0
        except Exception:
            return False

    def get_quote(self, ticker: str) -> dict:
        """
        Get current quote for a market.

        Returns:
            Dict with bid/ask for yes and no sides
        """
        market = self.get_market(ticker)
        orderbook = self.get_orderbook(ticker)

        yes_bids = orderbook.get("yes", {}).get("bids", [])
        yes_asks = orderbook.get("yes", {}).get("asks", [])

        return {
            "ticker": ticker,
            "yes_bid": yes_bids[0][0] if yes_bids else market.yes_price,
            "yes_ask": yes_asks[0][0] if yes_asks else market.yes_price,
            "no_bid": 100 - (yes_asks[0][0] if yes_asks else market.yes_price),
            "no_ask": 100 - (yes_bids[0][0] if yes_bids else market.yes_price),
            "volume": market.volume,
            "open_interest": market.open_interest,
        }


# Singleton instance
_kalshi_client: Optional[KalshiClient] = None


def get_kalshi_client(paper: bool = True) -> KalshiClient:
    """Get or create singleton Kalshi client."""
    global _kalshi_client
    if _kalshi_client is None:
        _kalshi_client = KalshiClient(paper=paper)
    return _kalshi_client
