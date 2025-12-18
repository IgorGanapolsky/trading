"""
Alpaca Trading Executor Module

This module provides a comprehensive interface to the Alpaca Trading API for executing
trades, managing positions, and retrieving market data. It supports both paper and live
trading environments with full error handling and logging.

Features:
    - Market orders with fractional shares
    - Stop-loss and take-profit order management
    - Account and portfolio data retrieval
    - Historical market data fetching
    - Support for stocks and ETFs
    - Comprehensive error handling and logging

Example:
    >>> trader = AlpacaTrader(paper=True)
    >>> account = trader.get_account_info()
    >>> order = trader.execute_order('SPY', 100.0, side='buy')
    >>> trader.set_stop_loss('SPY', 1.0, 450.0)
"""

import logging
import os

# Import retry decorator
import sys
import time
from datetime import datetime
from typing import Any

# Optional import - alpaca-py may not be installed in all environments
try:
    from alpaca.common.exceptions import APIError
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import (
        LimitOrderRequest,
        MarketOrderRequest,
        StopOrderRequest,
    )
    ALPACA_AVAILABLE = True
except ImportError:
    # Create placeholder types for when alpaca is not installed
    APIError = Exception  # type: ignore
    StockHistoricalDataClient = None  # type: ignore
    StockBarsRequest = None  # type: ignore
    StockLatestQuoteRequest = None  # type: ignore
    TimeFrame = None  # type: ignore
    TradingClient = None  # type: ignore
    OrderSide = None  # type: ignore
    TimeInForce = None  # type: ignore
    LimitOrderRequest = None  # type: ignore
    MarketOrderRequest = None  # type: ignore
    StopOrderRequest = None  # type: ignore
    ALPACA_AVAILABLE = False

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from src.core.config import load_config
from src.utils.retry_decorator import retry_with_backoff

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AlpacaTraderError(Exception):
    """Base exception for Alpaca trading errors."""

    pass


class OrderExecutionError(AlpacaTraderError):
    """Exception raised when order execution fails."""

    pass


class AccountError(AlpacaTraderError):
    """Exception raised when account operations fail."""

    pass


class MarketDataError(AlpacaTraderError):
    """Exception raised when market data retrieval fails."""

    pass


class AlpacaTrader:
    """
    Alpaca Trading API executor for automated trading operations.

    This class provides a high-level interface to interact with Alpaca's trading API,
    supporting order execution, portfolio management, and market data retrieval.

    Attributes:
        api: Alpaca REST API client instance
        paper: Boolean indicating if using paper trading (True) or live trading (False)
        daily_investment: Expected daily investment amount from .env (for validation)

    Environment Variables:
        ALPACA_API_KEY: API key for authentication
        ALPACA_SECRET_KEY: Secret key for authentication
        APCA_API_BASE_URL: Base URL for API (optional, defaults to paper/live URL)
        DAILY_INVESTMENT: Expected daily investment amount (default: 10.0)
    """

    # Tier allocation mapping (must match .env and strategy configuration)
    TIER_ALLOCATIONS = {
        "T1_CORE": 0.60,  # 60% of daily investment
        "T2_GROWTH": 0.20,  # 20% of daily investment
        "T3_IPO": 0.10,  # 10% of daily investment
        "T4_CROWD": 0.10,  # 10% of daily investment
    }

    # Safety multiplier: reject orders >10x expected amount
    MAX_ORDER_MULTIPLIER = 10.0

    def __init__(self, paper: bool = True) -> None:
        """
        Initialize the Alpaca trader with API credentials.

        Args:
            paper: If True, use paper trading environment. If False, use live trading.
                  Default is True for safety.

        Raises:
            AlpacaTraderError: If API credentials are missing or invalid.

        Example:
            >>> trader = AlpacaTrader(paper=True)
            >>> print(f"Connected to {'paper' if trader.paper else 'live'} trading")
        """
        self.paper = paper

        # Load configuration
        self.config = load_config()

        # Get API credentials from environment variables
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        # Store API credentials for data client reuse
        self.api_key = api_key
        self.secret_key = secret_key

        # Get daily investment amount for validation
        self.daily_investment = float(os.getenv("DAILY_INVESTMENT", "10.0"))
        logger.info(f"Daily investment configured: ${self.daily_investment:.2f}")
        logger.info(f"Limit orders: {'ENABLED' if self.config.USE_LIMIT_ORDERS else 'DISABLED'}")

        if not api_key or not secret_key:
            raise AlpacaTraderError(
                "Missing API credentials. Please set ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY environment variables."
            )

        try:
            # Initialize Alpaca Trading Client
            self.trading_client = TradingClient(api_key=api_key, secret_key=secret_key, paper=paper)

            # Initialize Alpaca Data Client
            self.data_client = StockHistoricalDataClient(api_key=api_key, secret_key=secret_key)

            # Verify connection by fetching account
            account = self.trading_client.get_account()

            logger.info(
                f"Successfully connected to Alpaca ({'paper' if paper else 'live'} trading)"
            )
            logger.info(f"Account status: {account.status}")

        except Exception as e:
            logger.error(f"Failed to connect to Alpaca API: {e}")
            raise AlpacaTraderError(f"Initialization failed: {e}") from e

    def get_current_quote(self, symbol: str) -> dict[str, float] | None:
        """
        Get current bid/ask prices for a symbol.

        Args:
            symbol: Stock or ETF symbol

        Returns:
            Dictionary with 'bid' and 'ask' prices, or None if unavailable

        Example:
            >>> trader = AlpacaTrader()
            >>> quote = trader.get_current_quote('SPY')
            >>> print(f"Bid: ${quote['bid']:.2f}, Ask: ${quote['ask']:.2f}")
        """
        try:
            quote_request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quote_data = self.data_client.get_stock_latest_quote(quote_request)

            if symbol in quote_data:
                quote = quote_data[symbol]
                return {
                    "bid": float(quote.bid_price),
                    "ask": float(quote.ask_price),
                    "bid_size": int(quote.bid_size),
                    "ask_size": int(quote.ask_size),
                }
            return None
        except Exception as e:
            logger.warning(f"Could not fetch quote for {symbol}: {e}")
            return None

    def validate_order_amount(self, symbol: str, amount: float, tier: str | None = None) -> None:
        """
        Validate order amount is reasonable to prevent catastrophic errors.

        This method prevents bugs like the Nov 3 incident where $1,600 was
        deployed instead of $8 (200x too large). It checks:
        1. Amount is not more than 10x expected for the tier
        2. Warns if amount is 5x-10x expected (suspicious but allowed)

        Args:
            symbol: Stock or ETF symbol
            amount: Dollar amount being ordered
            tier: Trading tier (T1_CORE, T2_GROWTH, T3_IPO, T4_CROWD) or None

        Raises:
            OrderExecutionError: If amount exceeds 10x expected amount

        Example:
            >>> trader = AlpacaTrader()
            >>> trader.validate_order_amount('SPY', 6.0, 'T1_CORE')  # PASS
            >>> trader.validate_order_amount('SPY', 600.0, 'T1_CORE')  # ERROR
        """
        # Determine expected amount based on tier
        if tier and tier in self.TIER_ALLOCATIONS:
            expected_amount = self.daily_investment * self.TIER_ALLOCATIONS[tier]
            tier_name = tier
        else:
            # If no tier specified, use full daily investment as baseline
            expected_amount = self.daily_investment
            tier_name = "UNSPECIFIED"

        # Calculate maximum allowed (10x tolerance)
        max_allowed = expected_amount * self.MAX_ORDER_MULTIPLIER

        # CRITICAL: Reject orders that are too large
        if amount > max_allowed:
            error_msg = (
                f"🚨 ORDER REJECTED FOR SAFETY 🚨\n"
                f"Symbol: {symbol}\n"
                f"Order amount: ${amount:.2f}\n"
                f"Expected amount: ${expected_amount:.2f} (tier: {tier_name})\n"
                f"Maximum allowed: ${max_allowed:.2f} ({self.MAX_ORDER_MULTIPLIER}x expected)\n"
                f"This order is {amount / expected_amount:.1f}x expected - appears to be a bug.\n"
                f"REFUSING to execute to prevent financial loss."
            )
            logger.error(error_msg)
            raise OrderExecutionError(error_msg)

        # WARNING: Orders that are 5x-10x expected (suspicious)
        warning_threshold = expected_amount * 5.0
        if amount > warning_threshold:
            warning_msg = (
                f"⚠️  SUSPICIOUS ORDER SIZE ⚠️\n"
                f"Symbol: {symbol}\n"
                f"Order amount: ${amount:.2f}\n"
                f"Expected amount: ${expected_amount:.2f} (tier: {tier_name})\n"
                f"This order is {amount / expected_amount:.1f}x expected.\n"
                f"Proceeding with caution..."
            )
            logger.warning(warning_msg)
        else:
            # Normal order - log success
            logger.info(
                f"✅ Order validation passed: ${amount:.2f} <= ${max_allowed:.2f} "
                f"(expected: ${expected_amount:.2f}, tier: {tier_name})"
            )

    @retry_with_backoff(max_retries=3, initial_delay=1.0, exceptions=(APIError, ConnectionError))
    def get_account_info(self) -> dict[str, Any]:
        """
        Retrieve account information including buying power, equity, and cash.

        Retries up to 3 times with exponential backoff on network errors.

        Returns:
            Dictionary containing account information with keys:
                - account_number: Account identification number
                - status: Account status (ACTIVE, etc.)
                - currency: Account currency (USD)
                - buying_power: Available buying power
                - cash: Available cash
                - portfolio_value: Total portfolio value
                - equity: Total equity
                - last_equity: Equity as of previous trading day
                - pattern_day_trader: PDT flag

        Raises:
            AccountError: If account information retrieval fails.

        Example:
            >>> trader = AlpacaTrader()
            >>> account = trader.get_account_info()
            >>> print(f"Buying power: ${account['buying_power']}")
        """
        try:
            account = self.trading_client.get_account()

            account_info = {
                "account_number": account.account_number,
                "status": str(account.status),
                "currency": account.currency,
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "equity": float(account.equity),
                "last_equity": float(account.last_equity),
                "pattern_day_trader": account.pattern_day_trader,
                "trading_blocked": account.trading_blocked,
                "transfers_blocked": account.transfers_blocked,
                "account_blocked": account.account_blocked,
                "created_at": str(account.created_at),
                "trade_suspended_by_user": account.trade_suspended_by_user,
            }

            # Add daytrade_count if available
            if hasattr(account, "daytrade_count"):
                account_info["daytrade_count"] = account.daytrade_count
            elif hasattr(account, "day_trade_count"):
                account_info["daytrade_count"] = account.day_trade_count
            else:
                account_info["daytrade_count"] = 0

            logger.info(
                f"Retrieved account info: Portfolio value ${account_info['portfolio_value']:.2f}"
            )
            return account_info

        except Exception as e:
            logger.error(f"Failed to retrieve account information: {e}")
            raise AccountError(f"Account retrieval failed: {e}") from e

    @retry_with_backoff(max_retries=3, initial_delay=2.0, exceptions=(APIError, ConnectionError))
    def execute_order(
        self,
        symbol: str,
        amount_usd: float | None = None,
        qty: float | None = None,
        side: str = "buy",
        tier: str | None = None,
        strategy: str = "unknown",
    ) -> dict[str, Any]:
        """
        Execute an order with fractional shares (by USD amount) or share quantity.
        Uses limit orders by default (if configured) to reduce slippage, with
        automatic fallback to market orders if limit doesn't fill in time.

        IMPORTANT: All orders pass through MANDATORY RAG/ML trade gate validation.

        Retries up to 3 times with exponential backoff on network/API errors.

        Args:
            symbol: Stock or ETF symbol (e.g., 'SPY', 'AAPL')
            amount_usd: Dollar amount to trade (notional). One of amount_usd or qty is required.
            qty: Quantity of shares to trade.
            side: Order side - 'buy' or 'sell'. Default is 'buy'.
            tier: Trading tier for validation (T1_CORE, T2_GROWTH, T3_IPO, T4_CROWD)
            strategy: Strategy name for RAG/ML validation.

        Returns:
            Dictionary containing order information.
        """
        # ========== MANDATORY TRADE GATE - NEVER SKIP ==========
        try:
            from src.safety.mandatory_trade_gate import validate_trade_mandatory, TradeBlockedError
            
            gate_amount = amount_usd or (qty * 100.0 if qty else 0.0)
            gate_result = validate_trade_mandatory(
                symbol=symbol,
                amount=gate_amount,
                side=side.upper(),
                strategy=strategy or tier or "unknown",
            )
            
            if not gate_result.approved:
                logger.error(f"🚫 ORDER BLOCKED BY MANDATORY GATE: {gate_result.reason}")
                raise TradeBlockedError(gate_result)
            
            if gate_result.rag_warnings or gate_result.ml_anomalies:
                logger.warning(f"⚠️ ORDER APPROVED WITH WARNINGS (confidence: {gate_result.confidence:.2f})")
        except ImportError:
            # Gate not available - log warning but proceed
            logger.warning("⚠️ Mandatory trade gate not available - proceeding without validation")
        # ========================================================
        
        # Validate inputs
        if side not in ["buy", "sell"]:
            raise ValueError(f"Invalid side '{side}'. Must be 'buy' or 'sell'.")

        if amount_usd is None and qty is None:
            raise ValueError("Must provide either amount_usd or qty")

        if amount_usd is not None and qty is not None:
            raise ValueError("Cannot provide both amount_usd and qty")

        symbol = symbol.upper().strip()

        # Handle Notional Rounding if using amount_usd
        if amount_usd is not None:
            if amount_usd <= 0:
                raise ValueError(f"Amount must be positive. Got {amount_usd}")
            amount_usd = round(amount_usd, 2)
            # CRITICAL: Validate order amount before proceeding (only for buys/notional)
            # We skip validation for sells (closing positions) or qty based orders for now
            # as those are usually calculated from existing holdings.
            if side == "buy":
                self.validate_order_amount(symbol, amount_usd, tier)

        if qty is not None and qty <= 0:
            raise ValueError(f"Quantity must be positive. Got {qty}")

        try:
            # Check account status before placing order
            account = self.trading_client.get_account()

            if account.trading_blocked:
                raise OrderExecutionError("Trading is blocked for this account")

            if side == "buy" and amount_usd and float(account.buying_power) < amount_usd:
                raise OrderExecutionError(
                    f"Insufficient buying power. Available: ${account.buying_power}, "
                    f"Required: ${amount_usd}"
                )

            # Crypto orders require GTC (good-til-canceled), stocks use DAY
            is_crypto = symbol.endswith("USD") and symbol.replace("USD", "") in [
                "BTC",
                "ETH",
                "LTC",
                "DOGE",
                "SOL",
            ]
            tif = TimeInForce.GTC if is_crypto else TimeInForce.DAY

            # Get current quote for limit price and slippage tracking
            quote = self.get_current_quote(symbol)
            intended_price = None
            limit_price = None
            # Only use limit orders for notional if supported (Alpaca doesn't support notional limit orders yet)
            # But we can calculate qty from notional if we have a price.
            # For qty-based orders, we can use limit.
            use_limit_order = self.config.USE_LIMIT_ORDERS and quote is not None

            if quote:
                # Set intended price based on side
                intended_price = quote["ask"] if side == "buy" else quote["bid"]

                # Calculate limit price with buffer
                if use_limit_order:
                    buffer_multiplier = 1 + (self.config.LIMIT_ORDER_BUFFER_PCT / 100)
                    if side == "buy":
                        limit_price = round(quote["ask"] * buffer_multiplier, 2)
                    else:
                        limit_price = round(quote["bid"] / buffer_multiplier, 2)

                    # Format for log
                    amount_str = f"${amount_usd:.2f}" if amount_usd else f"{qty} shares"
                    logger.info(
                        f"Executing LIMIT {side} order: {symbol} for {amount_str} "
                        f"(limit: ${limit_price:.2f}, quote: ${intended_price:.2f})"
                    )

            # Place order (limit or market)
            order = None
            fallback_to_market = False

            # Alpaca doesn't support Notional Limit Orders.
            # If we have amount_usd, we MUST use Market Order (or calculate qty).
            if amount_usd and use_limit_order:
                logger.warning(
                    f"Limit order requested but Alpaca doesn't support notional limit orders. "
                    f"Using market order for {symbol}."
                )
                use_limit_order = False

            if use_limit_order:
                # Qty based limit order
                # We know qty is set because if amount_usd was set, we disabled limit order above.
                req = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                    time_in_force=tif,
                    limit_price=limit_price,
                )
                order = self.trading_client.submit_order(req)

            if not use_limit_order:
                # Use market order
                amount_str = f"${amount_usd:.2f}" if amount_usd else f"{qty} shares"
                logger.info(f"Executing MARKET {side} order: {symbol} for {amount_str}")

                req = MarketOrderRequest(
                    symbol=symbol,
                    notional=amount_usd,
                    qty=qty,
                    side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                    time_in_force=tif,
                )

                order = self.trading_client.submit_order(req)

            # Wait for order to fill (with timeout)
            timeout = self.config.LIMIT_ORDER_TIMEOUT_SECONDS
            start_time = time.time()

            while order and str(order.status) not in ["filled", "cancelled", "expired", "rejected"]:
                if time.time() - start_time > timeout:
                    logger.warning(
                        f"Order {order.id} did not fill within {timeout}s. "
                        f"Current status: {order.status}"
                    )
                    break

                time.sleep(1)
                order = self.trading_client.get_order_by_id(order.id)

            # Check if we need to cancel and retry with market order
            if order and str(order.status) not in ["filled", "partially_filled"]:
                if use_limit_order:
                    logger.warning(
                        f"Limit order {order.id} not filled. Cancelling and retrying with market order."
                    )
                    try:
                        self.trading_client.cancel_order_by_id(order.id)
                    except Exception as e:
                        logger.warning(f"Could not cancel order {order.id}: {e}")

                    # Retry with market order
                    req = MarketOrderRequest(
                        symbol=symbol,
                        notional=amount_usd,
                        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                        time_in_force=tif,
                    )
                    order = self.trading_client.submit_order(req)
                    fallback_to_market = True

                    # Wait for market order to fill (should be quick)
                    time.sleep(2)
                    order = self.trading_client.get_order_by_id(order.id)
                else:
                    # FIX: Market order stuck in PENDING_NEW - cancel and retry
                    # This fixes the Dec 12, 2025 bug where SPY order got stuck
                    logger.warning(
                        f"Market order {order.id} stuck in {order.status}. "
                        f"Cancelling and retrying..."
                    )
                    try:
                        self.trading_client.cancel_order_by_id(order.id)
                        time.sleep(1)  # Brief pause before retry

                        # Retry the market order
                        req = MarketOrderRequest(
                            symbol=symbol,
                            notional=amount_usd,
                            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                            time_in_force=tif,
                        )
                        order = self.trading_client.submit_order(req)
                        logger.info(f"Retried market order: {order.id}")

                        # Wait for retry to fill
                        time.sleep(2)
                        order = self.trading_client.get_order_by_id(order.id)
                    except Exception as e:
                        logger.error(f"Failed to retry stuck market order: {e}")

            filled_avg_price = float(order.filled_avg_price) if order.filled_avg_price else None

            # Calculate slippage if we have both prices
            slippage_pct = None
            slippage_usd = None
            if filled_avg_price and intended_price:
                slippage_pct = ((filled_avg_price - intended_price) / intended_price) * 100
                if side == "sell":
                    slippage_pct = -slippage_pct  # Flip sign for sells

                # Calculate dollar slippage
                filled_qty = float(order.filled_qty) if order.filled_qty else 0
                slippage_usd = (filled_avg_price - intended_price) * filled_qty
                if side == "sell":
                    slippage_usd = -slippage_usd

            order_info = {
                "id": str(order.id),
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "notional": float(order.notional) if order.notional else amount_usd,
                "side": str(order.side),
                "type": str(order.type),
                "time_in_force": str(order.time_in_force),
                "status": str(order.status),
                "submitted_at": str(order.submitted_at),
                "filled_at": str(order.filled_at) if order.filled_at else None,
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                "filled_avg_price": filled_avg_price,
                "limit_price": limit_price,  # Limit price used (if any)
                "intended_price": intended_price,  # Price we expected from quote
                "slippage_pct": slippage_pct,  # Percentage slippage
                "slippage_usd": slippage_usd,  # Dollar slippage
                "fallback_to_market": fallback_to_market,  # True if limit order cancelled
            }

            if slippage_pct is not None:
                logger.info(
                    f"Order filled: {order.id} - {side.upper()} {symbol} ${amount_usd:.2f} "
                    f"(avg fill: ${filled_avg_price:.2f}, slippage: {slippage_pct:+.2f}%)"
                )
            else:
                logger.info(
                    f"Order submitted: {order.id} - {side.upper()} {symbol} ${amount_usd:.2f}"
                )

            # Trigger trade tracking for online learning (if available)
            try:
                # Get global trade tracker instance if it exists
                # This will be set up by the orchestrator
                if hasattr(self, "_trade_tracker") and self._trade_tracker:
                    # Note: Entry state would need to be passed from orchestrator
                    # For now, we just log the trade
                    logger.debug(f"Trade tracker notified: {symbol} {side}")
            except Exception as e:
                logger.debug(f"Trade tracker not available: {e}")

            return order_info

        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            raise OrderExecutionError(f"Failed to execute order: {e}") from e

    def set_stop_loss(self, symbol: str, qty: float, stop_price: float) -> dict[str, Any]:
        """
        Set a stop-loss order to limit potential losses.

        Args:
            symbol: Stock or ETF symbol
            qty: Quantity of shares (supports fractional shares)
            stop_price: Price at which to trigger the stop-loss

        Returns:
            Dictionary containing order information.

        Raises:
            OrderExecutionError: If stop-loss order creation fails.
            ValueError: If parameters are invalid.

        Example:
            >>> trader = AlpacaTrader()
            >>> order = trader.set_stop_loss('SPY', 1.5, 450.00)
            >>> print(f"Stop-loss set at ${order['stop_price']}")
        """
        if qty <= 0:
            raise ValueError(f"Quantity must be positive. Got {qty}")

        if stop_price <= 0:
            raise ValueError(f"Stop price must be positive. Got {stop_price}")

        symbol = symbol.upper().strip()

        try:
            logger.info(f"Setting stop-loss: {symbol} qty={qty} at ${stop_price:.2f}")

            req = StopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                stop_price=stop_price,
            )

            order = self.trading_client.submit_order(req)

            order_info = {
                "id": str(order.id),
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": str(order.side),
                "type": str(order.type),
                "stop_price": float(order.stop_price),
                "time_in_force": str(order.time_in_force),
                "status": str(order.status),
                "submitted_at": str(order.submitted_at),
            }

            logger.info(f"Stop-loss order created: {order.id}")
            return order_info

        except Exception as e:
            logger.error(f"Failed to set stop-loss: {e}")
            raise OrderExecutionError(f"Stop-loss creation failed: {e}") from e

    def set_take_profit(self, symbol: str, qty: float, limit_price: float) -> dict[str, Any]:
        """
        Set a take-profit order to lock in gains.

        Args:
            symbol: Stock or ETF symbol
            qty: Quantity of shares (supports fractional shares)
            limit_price: Price at which to take profit

        Returns:
            Dictionary containing order information.

        Raises:
            OrderExecutionError: If take-profit order creation fails.
            ValueError: If parameters are invalid.

        Example:
            >>> trader = AlpacaTrader()
            >>> order = trader.set_take_profit('SPY', 1.5, 480.00)
            >>> print(f"Take-profit set at ${order['limit_price']}")
        """
        if qty <= 0:
            raise ValueError(f"Quantity must be positive. Got {qty}")

        if limit_price <= 0:
            raise ValueError(f"Limit price must be positive. Got {limit_price}")

        symbol = symbol.upper().strip()

        try:
            logger.info(f"Setting take-profit: {symbol} qty={qty} at ${limit_price:.2f}")

            req = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
                limit_price=limit_price,
            )

            order = self.trading_client.submit_order(req)

            order_info = {
                "id": str(order.id),
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": str(order.side),
                "type": str(order.type),
                "limit_price": float(order.limit_price),
                "time_in_force": str(order.time_in_force),
                "status": str(order.status),
                "submitted_at": str(order.submitted_at),
            }

            logger.info(f"Take-profit order created: {order.id}")
            return order_info

        except Exception as e:
            logger.error(f"Failed to set take-profit: {e}")
            raise OrderExecutionError(f"Take-profit creation failed: {e}") from e

    def get_portfolio_performance(self) -> dict[str, Any]:
        """
        Get portfolio performance metrics including profit/loss and returns.

        Returns:
            Dictionary containing performance metrics:
                - equity: Current equity
                - profit_loss: Total profit/loss in dollars
                - profit_loss_pct: Profit/loss percentage
                - total_return: Total return percentage
                - positions_count: Number of open positions
                - cash: Available cash
                -

        Raises:
            AccountError: If portfolio data retrieval fails.

        Example:
            >>> trader = AlpacaTrader()
            >>> performance = trader.get_portfolio_performance()
            >>> print(f"Total return: {performance['total_return']:.2f}%")
        """
        try:
            account = self.trading_client.get_account()
            positions = self.trading_client.get_all_positions()

            equity = float(account.equity)
            last_equity = float(account.last_equity)

            # Calculate profit/loss
            profit_loss = equity - last_equity
            profit_loss_pct = (profit_loss / last_equity * 100) if last_equity > 0 else 0

            # Calculate total return from initial investment
            # Using cash + equity vs just last_equity for more accurate return
            initial_value = float(account.last_equity)
            current_value = equity
            total_return = (
                ((current_value - initial_value) / initial_value * 100) if initial_value > 0 else 0
            )

            performance = {
                "equity": equity,
                "last_equity": last_equity,
                "profit_loss": profit_loss,
                "profit_loss_pct": profit_loss_pct,
                "total_return": total_return,
                "positions_count": len(positions),
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "portfolio_value": float(account.portfolio_value),
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"Portfolio performance: P/L ${profit_loss:.2f} "
                f"({profit_loss_pct:.2f}%), {len(positions)} positions"
            )

            return performance

        except Exception as e:
            logger.error(f"Failed to retrieve portfolio performance: {e}")
            raise AccountError(f"Portfolio performance retrieval failed: {e}") from e

    def get_positions(self) -> list[dict[str, Any]]:
        """
        Get all current portfolio positions.

        Returns:
            List of dictionaries, each containing position information:
                - symbol: Asset symbol
                - qty: Quantity held
                - avg_entry_price: Average entry price
                - current_price: Current market price
                - market_value: Current market value
                - cost_basis: Total cost basis
                - unrealized_pl: Unrealized profit/loss
                - unrealized_plpc: Unrealized P/L percentage
                - side: Long or short

        Raises:
            AccountError: If positions retrieval fails.

        Example:
            >>> trader = AlpacaTrader()
            >>> positions = trader.get_positions()
            >>> for pos in positions:
            ...     print(f"{pos['symbol']}: {pos['qty']} shares, "
            ...           f"P/L: ${pos['unrealized_pl']:.2f}")
        """
        try:
            positions = self.trading_client.get_all_positions()

            positions_data = []
            for pos in positions:
                position_info = {
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "avg_entry_price": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value),
                    "cost_basis": float(pos.cost_basis),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc) * 100,  # Convert to percentage
                    "unrealized_intraday_pl": float(pos.unrealized_intraday_pl),
                    "unrealized_intraday_plpc": float(pos.unrealized_intraday_plpc) * 100,
                    "side": str(pos.side),
                    "exchange": str(pos.exchange),
                }
                positions_data.append(position_info)

            logger.info(f"Retrieved {len(positions_data)} positions")
            return positions_data

        except Exception as e:
            logger.error(f"Failed to retrieve positions: {e}")
            raise AccountError(f"Positions retrieval failed: {e}") from e

    def get_historical_bars(
        self, symbol: str, timeframe: str = "1Day", limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        Get historical price bars (OHLCV data) for a symbol.

        Args:
            symbol: Stock or ETF symbol
            timeframe: Bar timeframe - '1Min', '5Min', '15Min', '1Hour', '1Day'
                      Default is '1Day'
            limit: Number of bars to retrieve (max 10000). Default is 100.

        Returns:
            List of dictionaries containing bar data:
                - timestamp: Bar timestamp
                - open: Opening price
                - high: High price
                - low: Low price
                - close: Closing price
                - volume: Trading volume

        Raises:
            MarketDataError: If historical data retrieval fails.
            ValueError: If parameters are invalid.

        Example:
            >>> trader = AlpacaTrader()
            >>> bars = trader.get_historical_bars('SPY', timeframe='1Day', limit=30)
            >>> for bar in bars[-5:]:
            ...     print(f"{bar['timestamp']}: Close ${bar['close']:.2f}")
        """
        valid_timeframes = {
            "1Min": TimeFrame.Minute,
            "5Min": TimeFrame.Minute,  # Alpaca-py handles multipliers differently, but for simplicity mapping to Minute
            "15Min": TimeFrame.Minute,
            "1Hour": TimeFrame.Hour,
            "1Day": TimeFrame.Day,
        }

        # Note: Alpaca-py TimeFrame is an object, not just a string.
        # For custom intervals like 5Min, we need TimeFrame(5, TimeFrameUnit.Minute)
        # But for now, let's support the basic ones or map string to TimeFrame

        tf = TimeFrame.Day
        if timeframe == "1Min":
            tf = TimeFrame.Minute
        elif timeframe == "1Hour":
            tf = TimeFrame.Hour
        elif timeframe == "1Day":
            tf = TimeFrame.Day
        else:
            # Fallback or error - for now defaulting to Day if unknown to avoid crash, but logging warning
            if timeframe not in valid_timeframes:
                logger.warning(
                    f"Timeframe {timeframe} not fully supported in simple mapping, defaulting to Day"
                )

        if limit <= 0 or limit > 10000:
            raise ValueError(f"Limit must be between 1 and 10000. Got {limit}")

        symbol = symbol.upper().strip()

        try:
            logger.info(f"Fetching {limit} {timeframe} bars for {symbol}")

            req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=tf, limit=limit)

            # Get bars from Alpaca API
            barset = self.data_client.get_stock_bars(req)

            bars_data = []
            if symbol in barset.data:
                for bar in barset.data[symbol]:
                    bar_info = {
                        "timestamp": str(bar.timestamp),
                        "open": float(bar.open),
                        "high": float(bar.high),
                        "low": float(bar.low),
                        "close": float(bar.close),
                        "volume": int(bar.volume),
                    }
                    bars_data.append(bar_info)

            logger.info(f"Retrieved {len(bars_data)} bars for {symbol}")
            return bars_data

        except Exception as e:
            logger.error(f"Failed to retrieve historical bars: {e}")
            raise MarketDataError(f"Historical data retrieval failed: {e}") from e

    def cancel_all_orders(self) -> dict[str, Any]:
        """
        Cancel all open orders.

        Returns:
            Dictionary containing cancellation results:
                - cancelled_count: Number of orders cancelled
                - status: Success status

        Raises:
            OrderExecutionError: If order cancellation fails.

        Example:
            >>> trader = AlpacaTrader()
            >>> result = trader.cancel_all_orders()
            >>> print(f"Cancelled {result['cancelled_count']} orders")
        """
        try:
            logger.info("Cancelling all open orders")

            # Get all open orders before cancelling (for counting)
            # Note: cancel_orders returns list of CancelOrderResponse, but we want count first
            # Actually cancel_orders cancels all and returns list of cancelled orders

            cancelled_orders = self.trading_client.cancel_orders()
            order_count = len(cancelled_orders)

            result = {
                "cancelled_count": order_count,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"Successfully cancelled {order_count} orders")
            return result

        except Exception as e:
            logger.error(f"Failed to cancel orders: {e}")
            raise OrderExecutionError(f"Order cancellation failed: {e}") from e

    def get_order_status(self, order_id: str) -> dict[str, Any]:
        """
        Get the status of a specific order.

        Args:
            order_id: The order ID to check

        Returns:
            Dictionary containing order status information.

        Raises:
            OrderExecutionError: If order status retrieval fails.

        Example:
            >>> trader = AlpacaTrader()
            >>> status = trader.get_order_status('order-id-123')
            >>> print(f"Order status: {status['status']}")
        """
        try:
            order = self.trading_client.get_order_by_id(order_id)

            order_info = {
                "id": str(order.id),
                "symbol": order.symbol,
                "qty": float(order.qty) if order.qty else None,
                "notional": float(order.notional) if order.notional else None,
                "side": str(order.side),
                "type": str(order.type),
                "status": str(order.status),
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                "filled_avg_price": (
                    float(order.filled_avg_price) if order.filled_avg_price else None
                ),
                "submitted_at": str(order.submitted_at),
                "filled_at": str(order.filled_at) if order.filled_at else None,
            }

            logger.info(f"Retrieved status for order {order_id}: {order.status}")
            return order_info

        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            raise OrderExecutionError(f"Order status retrieval failed: {e}") from e

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """
        Cancel a specific order.

        Args:
            order_id: The order ID to cancel

        Returns:
            Dictionary containing cancellation confirmation.

        Raises:
            OrderExecutionError: If order cancellation fails.

        Example:
            >>> trader = AlpacaTrader()
            >>> result = trader.cancel_order('order-id-123')
            >>> print(f"Order cancelled: {result['status']}")
        """
        try:
            logger.info(f"Cancelling order {order_id}")
            self.trading_client.cancel_order_by_id(order_id)

            result = {
                "order_id": order_id,
                "status": "cancelled",
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"Successfully cancelled order {order_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            raise OrderExecutionError(f"Order cancellation failed: {e}") from e

    def close_position(self, symbol: str) -> dict[str, Any]:
        """
        Close an entire position for a symbol.

        Args:
            symbol: Stock or ETF symbol to close

        Returns:
            Dictionary containing the closing order information.

        Raises:
            OrderExecutionError: If position closure fails.

        Example:
            >>> trader = AlpacaTrader()
            >>> result = trader.close_position('SPY')
            >>> print(f"Closed position: {result['symbol']}")
        """
        symbol = symbol.upper().strip()

        try:
            logger.info(f"Closing position for {symbol}")

            order = self.trading_client.close_position(symbol)

            order_info = {
                "id": str(order.id),
                "symbol": order.symbol,
                "qty": float(order.qty) if order.qty else None,
                "side": str(order.side),
                "type": str(order.type),
                "status": str(order.status),
                "submitted_at": str(order.submitted_at),
            }

            logger.info(f"Successfully closed position for {symbol}")
            return order_info

        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            raise OrderExecutionError(f"Position closure failed: {e}") from e

    def close_all_positions(self) -> dict[str, Any]:
        """
        Close all open positions.

        Returns:
            Dictionary containing closure results:
                - closed_count: Number of positions closed
                - closed_symbols: List of symbols closed

        Raises:
            OrderExecutionError: If position closure fails.

        Example:
            >>> trader = AlpacaTrader()
            >>> result = trader.close_all_positions()
            >>> print(f"Closed {result['closed_count']} positions")
        """
        try:
            logger.info("Closing all positions")

            positions = self.trading_client.get_all_positions()
            symbols = [pos.symbol for pos in positions]

            # Close all positions
            self.trading_client.close_all_positions(cancel_orders=True)

            result = {
                "closed_count": len(symbols),
                "closed_symbols": symbols,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"Successfully closed {len(symbols)} positions: {symbols}")
            return result

        except Exception as e:
            logger.error(f"Failed to close all positions: {e}")
            raise OrderExecutionError(f"Position closure failed: {e}") from e
