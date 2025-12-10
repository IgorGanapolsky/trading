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
    # Options-specific sides
    BUY_TO_OPEN = "buy_to_open"
    BUY_TO_CLOSE = "buy_to_close"
    SELL_TO_OPEN = "sell_to_open"
    SELL_TO_CLOSE = "sell_to_close"


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

    # ========== OPTIONS TRADING METHODS ==========

    def get_option_expirations(self, symbol: str) -> list[str]:
        """
        Get available option expiration dates for a symbol.

        Args:
            symbol: Underlying stock symbol (e.g., 'SPY')

        Returns:
            List of expiration dates in 'YYYY-MM-DD' format
        """
        try:
            response = self._request(
                "GET",
                "/markets/options/expirations",
                params={"symbol": symbol.upper()},
            )

            expirations = response.get("expirations", {})
            if not expirations or expirations == "null":
                return []

            date_list = expirations.get("date", [])
            if isinstance(date_list, str):
                date_list = [date_list]

            return date_list
        except Exception as e:
            logger.warning(f"Failed to get option expirations for {symbol}: {e}")
            return []

    def get_option_chain(
        self,
        symbol: str,
        expiration: Optional[str] = None,
        option_type: Optional[str] = None,
    ) -> list[dict]:
        """
        Get option chain for a symbol.

        Args:
            symbol: Underlying stock symbol (e.g., 'SPY')
            expiration: Expiration date 'YYYY-MM-DD' (optional, returns nearest if not set)
            option_type: 'call', 'put', or None for both

        Returns:
            List of option contracts with greeks and quotes
        """
        try:
            params = {"symbol": symbol.upper(), "greeks": "true"}
            if expiration:
                params["expiration"] = expiration
            if option_type:
                params["option_type"] = option_type.lower()

            response = self._request("GET", "/markets/options/chains", params=params)

            options = response.get("options", {})
            if not options or options == "null":
                return []

            option_list = options.get("option", [])
            if isinstance(option_list, dict):
                option_list = [option_list]

            results = []
            for opt in option_list:
                greeks = opt.get("greeks", {}) or {}
                results.append({
                    "symbol": opt.get("symbol", ""),
                    "underlying": opt.get("underlying", symbol),
                    "strike": float(opt.get("strike", 0)),
                    "expiration_date": opt.get("expiration_date", ""),
                    "option_type": opt.get("option_type", ""),  # 'call' or 'put'
                    "bid": float(opt.get("bid", 0) or 0),
                    "ask": float(opt.get("ask", 0) or 0),
                    "last": float(opt.get("last", 0) or 0),
                    "volume": int(opt.get("volume", 0) or 0),
                    "open_interest": int(opt.get("open_interest", 0) or 0),
                    # Greeks
                    "delta": float(greeks.get("delta", 0) or 0),
                    "gamma": float(greeks.get("gamma", 0) or 0),
                    "theta": float(greeks.get("theta", 0) or 0),
                    "vega": float(greeks.get("vega", 0) or 0),
                    "rho": float(greeks.get("rho", 0) or 0),
                    "iv": float(greeks.get("mid_iv", 0) or greeks.get("smv_vol", 0) or 0),
                })

            return results
        except Exception as e:
            logger.warning(f"Failed to get option chain for {symbol}: {e}")
            return []

    def find_optimal_put(
        self,
        symbol: str,
        target_delta: float = 0.25,
        min_dte: int = 30,
        max_dte: int = 45,
    ) -> Optional[dict]:
        """
        Find optimal put option for cash-secured put strategy.

        Criteria (McMillan/TastyTrade):
        - OTM put (strike below current price)
        - Delta between -0.15 and -0.40
        - DTE between 30-45 days
        - Decent premium (>0.5% of underlying)

        Args:
            symbol: Underlying symbol
            target_delta: Target delta magnitude (default 0.25)
            min_dte: Minimum days to expiration
            max_dte: Maximum days to expiration

        Returns:
            Best put option dict or None
        """
        from datetime import date

        # Get current price
        quote = self.get_quote(symbol)
        current_price = quote.get("last", 0)
        if current_price <= 0:
            logger.warning(f"Could not get price for {symbol}")
            return None

        logger.info(f"🔍 Scanning Tradier option chain for {symbol}...")
        logger.info(f"   Current {symbol} price: ${current_price:.2f}")

        # Get expiration dates
        expirations = self.get_option_expirations(symbol)
        if not expirations:
            logger.warning(f"No expirations found for {symbol}")
            return None

        # Filter expirations by DTE
        target_expirations = []
        today = date.today()
        for exp_str in expirations:
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                dte = (exp_date - today).days
                if min_dte <= dte <= max_dte:
                    target_expirations.append(exp_str)
            except ValueError:
                continue

        if not target_expirations:
            logger.warning(f"No expirations in {min_dte}-{max_dte} DTE range for {symbol}")
            return None

        # Scan each expiration for optimal puts
        candidates = []
        for expiration in target_expirations:
            chain = self.get_option_chain(symbol, expiration=expiration, option_type="put")

            for opt in chain:
                strike = opt.get("strike", 0)
                delta = opt.get("delta", 0)
                bid = opt.get("bid", 0)
                ask = opt.get("ask", 0)
                mid = (bid + ask) / 2 if bid and ask else 0

                # Skip ITM puts (strike >= current price)
                if strike >= current_price:
                    continue

                # Check delta range (puts have negative delta)
                if delta > -0.15 or delta < -0.40:
                    continue

                # Calculate premium as % of underlying
                premium_pct = (mid / current_price) * 100 if current_price > 0 else 0

                # Skip if premium too low
                if premium_pct < 0.5:
                    continue

                exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()
                dte = (exp_date - today).days

                candidates.append({
                    "symbol": opt.get("symbol"),
                    "strike": strike,
                    "expiration": exp_date,
                    "dte": dte,
                    "delta": delta,
                    "bid": bid,
                    "ask": ask,
                    "mid": mid,
                    "premium_pct": premium_pct,
                    "iv": opt.get("iv", 0),
                })

        if not candidates:
            logger.warning(f"No suitable put options found for {symbol}")
            return None

        # Sort by delta closest to target
        candidates.sort(key=lambda x: abs(abs(x["delta"]) - target_delta))

        best = candidates[0]
        logger.info("✅ Found optimal put via Tradier:")
        logger.info(f"   Symbol: {best['symbol']}")
        logger.info(f"   Strike: ${best['strike']:.2f} ({((current_price - best['strike']) / current_price * 100):.1f}% OTM)")
        logger.info(f"   Expiration: {best['expiration']} ({best['dte']} DTE)")
        logger.info(f"   Delta: {best['delta']:.3f}")
        logger.info(f"   Premium: ${best['mid']:.2f} ({best['premium_pct']:.2f}%)")
        if best['iv']:
            logger.info(f"   IV: {best['iv']:.1%}")

        return best

    def submit_option_order(
        self,
        option_symbol: str,
        qty: int,
        side: str,
        order_type: str = "limit",
        limit_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> TradierOrder:
        """
        Submit an options order.

        Args:
            option_symbol: OCC option symbol (e.g., 'SPY251219P00580000')
            qty: Number of contracts
            side: 'buy_to_open', 'sell_to_open', 'buy_to_close', 'sell_to_close'
            order_type: 'market' or 'limit'
            limit_price: Limit price per contract (for limit orders)
            time_in_force: 'day' or 'gtc'

        Returns:
            TradierOrder with order details
        """
        if not self.is_configured():
            raise RuntimeError("Tradier client not configured")

        order_data = {
            "class": "option",
            "symbol": option_symbol,
            "side": side.lower(),
            "quantity": str(int(qty)),
            "type": order_type.lower(),
            "duration": time_in_force.lower(),
        }

        if limit_price and order_type == "limit":
            order_data["price"] = str(limit_price)

        logger.info(f"📤 Submitting Tradier option order: {side} {qty}x {option_symbol}")

        response = self._request(
            "POST",
            f"/accounts/{self.account_number}/orders",
            data=order_data,
        )

        order_info = response.get("order", {})
        order_id = str(order_info.get("id", ""))
        status = order_info.get("status", "pending")

        logger.info(f"✅ Tradier order submitted: ID={order_id}, status={status}")

        return TradierOrder(
            id=order_id,
            symbol=option_symbol,
            side=side,
            quantity=float(qty),
            filled_quantity=0.0,
            price=limit_price,
            avg_fill_price=None,
            status=status,
            created_at=datetime.now().isoformat(),
            order_type=order_type,
        )

    def execute_cash_secured_put(
        self,
        symbol: str,
        dry_run: bool = False,
    ) -> dict:
        """
        Execute a cash-secured put trade via Tradier.

        Strategy:
        1. Find optimal OTM put (delta ~0.25, 30-45 DTE)
        2. Verify cash for potential assignment
        3. Sell 1 put contract

        Args:
            symbol: Underlying symbol (e.g., 'SPY')
            dry_run: If True, don't actually execute

        Returns:
            Result dict with status and trade details
        """
        logger.info("=" * 60)
        logger.info("💰 TRADIER CASH-SECURED PUT STRATEGY")
        logger.info("=" * 60)

        # Get account info
        try:
            account = self.get_account()
            logger.info(f"Account cash: ${account.cash:,.2f}")
            logger.info(f"Buying power: ${account.buying_power:,.2f}")
        except Exception as e:
            logger.error(f"Failed to get Tradier account: {e}")
            return {"status": "ERROR", "error": f"Account error: {e}", "broker": "tradier"}

        # Find optimal put
        put_option = self.find_optimal_put(symbol)
        if not put_option:
            return {"status": "NO_TRADE", "reason": "No suitable options found", "broker": "tradier"}

        # Calculate cash required for assignment
        cash_required = put_option["strike"] * 100
        logger.info(f"\n💵 Cash required for assignment: ${cash_required:,.2f}")

        if account.cash < cash_required:
            logger.warning(f"❌ Insufficient cash! Need ${cash_required:,.2f}, have ${account.cash:,.2f}")
            return {"status": "NO_TRADE", "reason": "Insufficient cash", "broker": "tradier"}

        # Execute trade
        if dry_run:
            logger.info("\n🔶 DRY RUN - No actual trade executed")
            return {
                "status": "DRY_RUN",
                "option": put_option,
                "cash_required": cash_required,
                "potential_premium": put_option["mid"] * 100,
                "broker": "tradier",
            }

        # Place the order
        try:
            order = self.submit_option_order(
                option_symbol=put_option["symbol"],
                qty=1,
                side="sell_to_open",
                order_type="limit",
                limit_price=put_option["mid"],  # Use mid price for realistic fills
                time_in_force="day",
            )

            logger.info("\n✅ TRADIER ORDER SUBMITTED!")
            logger.info(f"   Order ID: {order.id}")
            logger.info(f"   Symbol: {put_option['symbol']}")
            logger.info("   Side: SELL TO OPEN")
            logger.info("   Qty: 1 contract")
            logger.info(f"   Limit Price: ${put_option['mid']:.2f}")
            logger.info(f"   Premium: ${put_option['mid'] * 100:.2f} (1 contract)")

            return {
                "status": "ORDER_SUBMITTED",
                "order_id": order.id,
                "option": put_option,
                "premium": put_option["mid"] * 100,
                "broker": "tradier",
            }

        except Exception as e:
            logger.error(f"❌ Tradier order failed: {e}")
            return {"status": "ERROR", "error": str(e), "broker": "tradier"}


# Singleton instance
_tradier_client: Optional[TradierClient] = None


def get_tradier_client(paper: bool = True) -> TradierClient:
    """Get or create singleton Tradier client."""
    global _tradier_client
    if _tradier_client is None:
        _tradier_client = TradierClient(paper=paper)
    return _tradier_client
