"""
Broker clients for multi-broker trading with automatic failover.

Primary: Alpaca (self-clearing)
Secondary: Interactive Brokers (IBKR) - enterprise-grade
Tertiary: Tradier (API-first cloud brokerage)
Quaternary: Kalshi (CFTC-regulated prediction markets)

True redundancy with four different trading infrastructures.

Usage:
    from src.brokers import get_multi_broker

    broker = get_multi_broker()
    result = broker.submit_order("AAPL", 10, "buy")
    print(f"Order placed on {result.broker.value}")

    # For prediction markets
    from src.brokers import get_kalshi_client
    kalshi = get_kalshi_client()
    markets = kalshi.get_markets(category="elections")
"""

from .ibkr_client import (
    IBKRClient,
    get_ibkr_client,
)
from .kalshi_client import (
    KalshiAccount,
    KalshiClient,
    KalshiMarket,
    KalshiOrder,
    KalshiPosition,
    get_kalshi_client,
)
from .multi_broker import (
    BrokerType,
    MultiBroker,
    OrderResult,
    get_multi_broker,
)
from .tradier_client import (
    TradierClient,
    get_tradier_client,
)

__all__ = [
    "MultiBroker",
    "get_multi_broker",
    "BrokerType",
    "OrderResult",
    "IBKRClient",
    "get_ibkr_client",
    "TradierClient",
    "get_tradier_client",
    "KalshiClient",
    "KalshiMarket",
    "KalshiPosition",
    "KalshiOrder",
    "KalshiAccount",
    "get_kalshi_client",
]
