"""
Broker Interface Abstraction Layer

Abstract base class for broker implementations.
Enables future flexibility to switch brokers without code changes.

As CTO: Architecture decision for maintainability and vendor flexibility.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class OrderResult:
    """Standardized order execution result."""

    order_id: str
    symbol: str
    side: str  # 'buy' or 'sell'
    amount_usd: float
    status: str
    filled_qty: float | None = None
    filled_avg_price: float | None = None
    submitted_at: str | None = None
    filled_at: str | None = None
    error: str | None = None


@dataclass
class AccountInfo:
    """Standardized account information."""

    account_number: str
    status: str
    buying_power: float
    cash: float
    portfolio_value: float
    equity: float
    trading_blocked: bool
    currency: str = "USD"


class BrokerInterface(ABC):
    """
    Abstract interface for broker implementations.

    All broker implementations must inherit from this class and implement
    all abstract methods to ensure compatibility with trading system.
    """

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        """
        Retrieve account information.

        Returns:
            AccountInfo with account details

        Raises:
            BrokerError: If account retrieval fails
        """
        pass

    @abstractmethod
    def execute_order(
        self, symbol: str, amount_usd: float, side: str = "buy", **kwargs
    ) -> OrderResult:
        """
        Execute a market order.

        Args:
            symbol: Stock/ETF symbol
            amount_usd: Dollar amount to trade
            side: 'buy' or 'sell'
            **kwargs: Additional broker-specific parameters

        Returns:
            OrderResult with order details

        Raises:
            BrokerError: If order execution fails
        """
        pass

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]:
        """
        Get current positions.

        Returns:
            List of position dictionaries with keys:
            - symbol: Stock symbol
            - quantity: Number of shares
            - avg_entry_price: Average entry price
            - market_value: Current market value
            - unrealized_pl: Unrealized profit/loss
        """
        pass

    @abstractmethod
    def get_orders(self, status: str | None = None) -> list[dict[str, Any]]:
        """
        Get order history.

        Args:
            status: Filter by order status (optional)

        Returns:
            List of order dictionaries
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancellation successful

        Raises:
            BrokerError: If cancellation fails
        """
        pass

    @abstractmethod
    def is_market_open(self) -> bool:
        """
        Check if market is currently open.

        Returns:
            True if market is open, False otherwise
        """
        pass

    @abstractmethod
    def get_historical_bars(
        self, symbol: str, timeframe: str = "1Day", limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        Get historical price bars.

        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe (e.g., '1Day', '1Hour')
            limit: Number of bars to retrieve

        Returns:
            List of bar dictionaries with keys:
            - timestamp: Bar timestamp
            - open: Open price
            - high: High price
            - low: Low price
            - close: Close price
            - volume: Trading volume
        """
        pass


class BrokerError(Exception):
    """Base exception for broker operations."""

    pass


class OrderExecutionError(BrokerError):
    """Exception raised when order execution fails."""

    pass


class AccountError(BrokerError):
    """Exception raised when account operations fail."""

    pass


class MarketDataError(BrokerError):
    """Exception raised when market data retrieval fails."""

    pass
