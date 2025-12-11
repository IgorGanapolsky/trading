"""
Broker clients for multi-broker trading.

Primary: Alpaca
Backup: Tradier

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
from .tradier_client import (
    TradierClient,
    get_tradier_client,
)

__all__ = [
    "MultiBroker",
    "get_multi_broker",
    "BrokerType",
    "OrderResult",
    "TradierClient",
    "get_tradier_client",
]
