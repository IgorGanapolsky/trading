"""SPY put credit entry."""

from gateway import TradeGateway


def plan_put_credit() -> None:
    TradeGateway().reject_unclean()
