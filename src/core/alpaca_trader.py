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

import os
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
from decimal import Decimal

import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError, REST
from alpaca_trade_api.entity import Order, Position, Account, BarSet


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

    Environment Variables:
        ALPACA_API_KEY: API key for authentication
        ALPACA_SECRET_KEY: Secret key for authentication
        APCA_API_BASE_URL: Base URL for API (optional, defaults to paper/live URL)
    """

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

        # Get API credentials from environment variables
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            raise AlpacaTraderError(
                "Missing API credentials. Please set ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY environment variables."
            )

        # Set base URL based on trading mode
        base_url = os.getenv("APCA_API_BASE_URL")
        if not base_url:
            base_url = (
                "https://paper-api.alpaca.markets"
                if paper
                else "https://api.alpaca.markets"
            )

        try:
            # Initialize Alpaca API client
            self.api = tradeapi.REST(
                key_id=api_key,
                secret_key=secret_key,
                base_url=base_url,
                api_version="v2",
            )

            # Verify connection by fetching account
            account = self.api.get_account()

            logger.info(
                f"Successfully connected to Alpaca "
                f"({'paper' if paper else 'live'} trading)"
            )
            logger.info(f"Account status: {account.status}")

        except APIError as e:
            logger.error(f"Failed to connect to Alpaca API: {e}")
            raise AlpacaTraderError(f"API connection failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during initialization: {e}")
            raise AlpacaTraderError(f"Initialization failed: {e}") from e

    def get_account_info(self) -> Dict[str, Any]:
        """
        Retrieve account information including buying power, equity, and cash.

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
            account: Account = self.api.get_account()

            account_info = {
                "account_number": account.account_number,
                "status": account.status,
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

            logger.info(
                f"Retrieved account info: Portfolio value ${account_info['portfolio_value']:.2f}"
            )
            return account_info

        except APIError as e:
            logger.error(f"Failed to retrieve account information: {e}")
            raise AccountError(f"Account retrieval failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving account info: {e}")
            raise AccountError(f"Unexpected error: {e}") from e

    def execute_order(
        self, symbol: str, amount_usd: float, side: str = "buy"
    ) -> Dict[str, Any]:
        """
        Execute a market order with fractional shares based on USD amount.

        Args:
            symbol: Stock or ETF symbol (e.g., 'SPY', 'AAPL')
            amount_usd: Dollar amount to trade (e.g., 100.0 for $100)
            side: Order side - 'buy' or 'sell'. Default is 'buy'.

        Returns:
            Dictionary containing order information with keys:
                - id: Order ID
                - symbol: Asset symbol
                - notional: Dollar amount
                - side: Buy or sell
                - type: Order type (market)
                - status: Order status
                - submitted_at: Submission timestamp
                - filled_at: Fill timestamp (if filled)
                - filled_avg_price: Average fill price

        Raises:
            OrderExecutionError: If order execution fails.
            ValueError: If parameters are invalid.

        Example:
            >>> trader = AlpacaTrader()
            >>> order = trader.execute_order('SPY', 100.0, side='buy')
            >>> print(f"Order {order['id']} submitted for ${order['notional']}")
        """
        # Validate inputs
        if side not in ["buy", "sell"]:
            raise ValueError(f"Invalid side '{side}'. Must be 'buy' or 'sell'.")

        if amount_usd <= 0:
            raise ValueError(f"Amount must be positive. Got {amount_usd}")

        symbol = symbol.upper().strip()

        try:
            # Check account status before placing order
            account = self.api.get_account()

            if account.trading_blocked:
                raise OrderExecutionError("Trading is blocked for this account")

            if side == "buy" and float(account.buying_power) < amount_usd:
                raise OrderExecutionError(
                    f"Insufficient buying power. Available: ${account.buying_power}, "
                    f"Required: ${amount_usd}"
                )

            # Place market order with notional (dollar) amount
            logger.info(f"Executing {side} order: {symbol} for ${amount_usd:.2f}")

            order: Order = self.api.submit_order(
                symbol=symbol,
                notional=amount_usd,
                side=side,
                type="market",
                time_in_force="day",
            )

            order_info = {
                "id": order.id,
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "notional": float(order.notional) if order.notional else amount_usd,
                "side": order.side,
                "type": order.type,
                "time_in_force": order.time_in_force,
                "status": order.status,
                "submitted_at": str(order.submitted_at),
                "filled_at": str(order.filled_at) if order.filled_at else None,
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                "filled_avg_price": (
                    float(order.filled_avg_price) if order.filled_avg_price else None
                ),
            }

            logger.info(
                f"Order submitted successfully: {order.id} - "
                f"{side.upper()} {symbol} ${amount_usd:.2f}"
            )

            return order_info

        except APIError as e:
            logger.error(f"Order execution failed: {e}")
            raise OrderExecutionError(f"Failed to execute order: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error executing order: {e}")
            raise OrderExecutionError(f"Unexpected error: {e}") from e

    def set_stop_loss(
        self, symbol: str, qty: float, stop_price: float
    ) -> Dict[str, Any]:
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

            order: Order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side="sell",
                type="stop",
                time_in_force="gtc",  # Good 'til cancelled
                stop_price=stop_price,
            )

            order_info = {
                "id": order.id,
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": order.side,
                "type": order.type,
                "stop_price": float(order.stop_price),
                "time_in_force": order.time_in_force,
                "status": order.status,
                "submitted_at": str(order.submitted_at),
            }

            logger.info(f"Stop-loss order created: {order.id}")
            return order_info

        except APIError as e:
            logger.error(f"Failed to set stop-loss: {e}")
            raise OrderExecutionError(f"Stop-loss creation failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error setting stop-loss: {e}")
            raise OrderExecutionError(f"Unexpected error: {e}") from e

    def set_take_profit(
        self, symbol: str, qty: float, limit_price: float
    ) -> Dict[str, Any]:
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
            logger.info(
                f"Setting take-profit: {symbol} qty={qty} at ${limit_price:.2f}"
            )

            order: Order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side="sell",
                type="limit",
                time_in_force="gtc",  # Good 'til cancelled
                limit_price=limit_price,
            )

            order_info = {
                "id": order.id,
                "client_order_id": order.client_order_id,
                "symbol": order.symbol,
                "qty": float(order.qty),
                "side": order.side,
                "type": order.type,
                "limit_price": float(order.limit_price),
                "time_in_force": order.time_in_force,
                "status": order.status,
                "submitted_at": str(order.submitted_at),
            }

            logger.info(f"Take-profit order created: {order.id}")
            return order_info

        except APIError as e:
            logger.error(f"Failed to set take-profit: {e}")
            raise OrderExecutionError(f"Take-profit creation failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error setting take-profit: {e}")
            raise OrderExecutionError(f"Unexpected error: {e}") from e

    def get_portfolio_performance(self) -> Dict[str, Any]:
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
            account: Account = self.api.get_account()
            positions = self.api.list_positions()

            equity = float(account.equity)
            last_equity = float(account.last_equity)

            # Calculate profit/loss
            profit_loss = equity - last_equity
            profit_loss_pct = (
                (profit_loss / last_equity * 100) if last_equity > 0 else 0
            )

            # Calculate total return from initial investment
            # Using cash + equity vs just last_equity for more accurate return
            initial_value = float(account.last_equity)
            current_value = equity
            total_return = (
                ((current_value - initial_value) / initial_value * 100)
                if initial_value > 0
                else 0
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

        except APIError as e:
            logger.error(f"Failed to retrieve portfolio performance: {e}")
            raise AccountError(f"Portfolio performance retrieval failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving portfolio performance: {e}")
            raise AccountError(f"Unexpected error: {e}") from e

    def get_positions(self) -> List[Dict[str, Any]]:
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
            positions: List[Position] = self.api.list_positions()

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
                    "unrealized_plpc": float(pos.unrealized_plpc)
                    * 100,  # Convert to percentage
                    "unrealized_intraday_pl": float(pos.unrealized_intraday_pl),
                    "unrealized_intraday_plpc": float(pos.unrealized_intraday_plpc)
                    * 100,
                    "side": pos.side,
                    "exchange": pos.exchange,
                }
                positions_data.append(position_info)

            logger.info(f"Retrieved {len(positions_data)} positions")
            return positions_data

        except APIError as e:
            logger.error(f"Failed to retrieve positions: {e}")
            raise AccountError(f"Positions retrieval failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving positions: {e}")
            raise AccountError(f"Unexpected error: {e}") from e

    def get_historical_bars(
        self, symbol: str, timeframe: str = "1Day", limit: int = 100
    ) -> List[Dict[str, Any]]:
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
        valid_timeframes = ["1Min", "5Min", "15Min", "1Hour", "1Day"]
        if timeframe not in valid_timeframes:
            raise ValueError(
                f"Invalid timeframe '{timeframe}'. "
                f"Must be one of {valid_timeframes}"
            )

        if limit <= 0 or limit > 10000:
            raise ValueError(f"Limit must be between 1 and 10000. Got {limit}")

        symbol = symbol.upper().strip()

        try:
            logger.info(f"Fetching {limit} {timeframe} bars for {symbol}")

            # Get bars from Alpaca API
            barset: BarSet = self.api.get_bars(symbol, timeframe, limit=limit)

            bars_data = []
            if symbol in barset:
                for bar in barset[symbol]:
                    bar_info = {
                        "timestamp": str(bar.t),
                        "open": float(bar.o),
                        "high": float(bar.h),
                        "low": float(bar.l),
                        "close": float(bar.c),
                        "volume": int(bar.v),
                    }
                    bars_data.append(bar_info)

            logger.info(f"Retrieved {len(bars_data)} bars for {symbol}")
            return bars_data

        except APIError as e:
            logger.error(f"Failed to retrieve historical bars: {e}")
            raise MarketDataError(f"Historical data retrieval failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error retrieving historical bars: {e}")
            raise MarketDataError(f"Unexpected error: {e}") from e

    def cancel_all_orders(self) -> Dict[str, Any]:
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

            # Get all open orders before cancelling
            open_orders = self.api.list_orders(status="open")
            order_count = len(open_orders)

            # Cancel all orders
            self.api.cancel_all_orders()

            result = {
                "cancelled_count": order_count,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"Successfully cancelled {order_count} orders")
            return result

        except APIError as e:
            logger.error(f"Failed to cancel orders: {e}")
            raise OrderExecutionError(f"Order cancellation failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error cancelling orders: {e}")
            raise OrderExecutionError(f"Unexpected error: {e}") from e

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
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
            order: Order = self.api.get_order(order_id)

            order_info = {
                "id": order.id,
                "symbol": order.symbol,
                "qty": float(order.qty) if order.qty else None,
                "notional": float(order.notional) if order.notional else None,
                "side": order.side,
                "type": order.type,
                "status": order.status,
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                "filled_avg_price": (
                    float(order.filled_avg_price) if order.filled_avg_price else None
                ),
                "submitted_at": str(order.submitted_at),
                "filled_at": str(order.filled_at) if order.filled_at else None,
            }

            logger.info(f"Retrieved status for order {order_id}: {order.status}")
            return order_info

        except APIError as e:
            logger.error(f"Failed to get order status: {e}")
            raise OrderExecutionError(f"Order status retrieval failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting order status: {e}")
            raise OrderExecutionError(f"Unexpected error: {e}") from e

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
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
            self.api.cancel_order(order_id)

            result = {
                "order_id": order_id,
                "status": "cancelled",
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"Successfully cancelled order {order_id}")
            return result

        except APIError as e:
            logger.error(f"Failed to cancel order: {e}")
            raise OrderExecutionError(f"Order cancellation failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error cancelling order: {e}")
            raise OrderExecutionError(f"Unexpected error: {e}") from e

    def close_position(self, symbol: str) -> Dict[str, Any]:
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

            order: Order = self.api.close_position(symbol)

            order_info = {
                "id": order.id,
                "symbol": order.symbol,
                "qty": float(order.qty) if order.qty else None,
                "side": order.side,
                "type": order.type,
                "status": order.status,
                "submitted_at": str(order.submitted_at),
            }

            logger.info(f"Successfully closed position for {symbol}")
            return order_info

        except APIError as e:
            logger.error(f"Failed to close position: {e}")
            raise OrderExecutionError(f"Position closure failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error closing position: {e}")
            raise OrderExecutionError(f"Unexpected error: {e}") from e

    def close_all_positions(self) -> Dict[str, Any]:
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

            positions = self.api.list_positions()
            symbols = [pos.symbol for pos in positions]

            # Close all positions
            self.api.close_all_positions()

            result = {
                "closed_count": len(symbols),
                "closed_symbols": symbols,
                "status": "success",
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"Successfully closed {len(symbols)} positions: {symbols}")
            return result

        except APIError as e:
            logger.error(f"Failed to close all positions: {e}")
            raise OrderExecutionError(f"Position closure failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error closing all positions: {e}")
            raise OrderExecutionError(f"Unexpected error: {e}") from e
