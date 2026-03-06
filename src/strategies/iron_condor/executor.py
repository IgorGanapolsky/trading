"""
Iron Condor Execution Layer
Role: Handle atomic order submission via MLEG.
"""

import logging
from typing import Any

from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest
from src.safety.mandatory_trade_gate import safe_submit_order

logger = logging.getLogger(__name__)


class IronCondorExecutor:
    """
    Execution Engine for Iron Condors.
    """

    def __init__(self, client):
        self.client = client

    def build_mleg_order(
        self, underlying: str, legs: dict[str, str], net_credit: float, qty: int = 1
    ) -> LimitOrderRequest:
        """
        Build a 4-leg Limit MLEG order with net credit limit price.
        """
        option_legs = [
            OptionLegRequest(symbol=legs["long_put"], side=OrderSide.BUY, ratio_qty=1),
            OptionLegRequest(symbol=legs["short_put"], side=OrderSide.SELL, ratio_qty=1),
            OptionLegRequest(symbol=legs["short_call"], side=OrderSide.SELL, ratio_qty=1),
            OptionLegRequest(symbol=legs["long_call"], side=OrderSide.BUY, ratio_qty=1),
        ]

        return LimitOrderRequest(
            qty=qty,
            order_class=OrderClass.MLEG,
            legs=option_legs,
            time_in_force=TimeInForce.DAY,
            limit_price=round(net_credit, 2),
        )

    def execute(self, order_req: LimitOrderRequest) -> Any:
        """
        Submit order via the mandatory safety gate.
        """
        logger.info("Submitting 4-leg Iron Condor MLEG order...")
        return safe_submit_order(self.client, order_req)
