# Slippage model stub - original deleted in cleanup PR #1445
# Minimal implementation to prevent import errors

from enum import Enum


class SlippageModelType(Enum):
    """Slippage model types."""
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    VOLUME_BASED = "volume_based"


class SlippageModel:
    """Stub slippage model - not used in Phil Town strategy."""

    def __init__(self, model_type: SlippageModelType = SlippageModelType.FIXED, *args, **kwargs):
        self.model_type = model_type
        self.fixed_slippage = 0.01  # 1 cent

    def calculate_slippage(self, price: float, qty: float) -> float:
        """Return minimal slippage."""
        return self.fixed_slippage * qty

    def adjust_price(self, price: float, side: str) -> float:
        """Adjust price for slippage."""
        if side == "buy":
            return price + self.fixed_slippage
        return price - self.fixed_slippage
