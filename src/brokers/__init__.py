"""
Broker clients for multi-broker trading with automatic failover.

Primary: Alpaca (self-clearing)
Secondary: Interactive Brokers (IBKR) - enterprise-grade
Tertiary: Webull (via Apex Clearing) - zero commission

True redundancy with three different clearing infrastructures.

Usage:
    from src.brokers import get_multi_broker

    broker = get_multi_broker()
    result = broker.submit_order("AAPL", 10, "buy")
    print(f"Order placed on {result.broker.value}")
"""

from .multi_broker import (
    BrokerType,
    MultiBroker,
    OrderResult,
    get_multi_broker,
)
from .ibkr_client import (
    IBKRClient,
    get_ibkr_client,
)
from .webull_client import (
    WebullClient,
    get_webull_client,
)

__all__ = [
    "MultiBroker",
    "get_multi_broker",
    "BrokerType",
    "OrderResult",
    "IBKRClient",
    "get_ibkr_client",
    "WebullClient",
    "get_webull_client",
]
