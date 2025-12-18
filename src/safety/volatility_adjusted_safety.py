"""Stub module - original safety deleted in cleanup."""


class VolatilityAdjustedSafety:
    """Stub for deleted volatility safety."""

    def __init__(self, *args, **kwargs):
        pass

    def is_safe(self, *args, **kwargs) -> bool:
        return True

    def adjust_position_size(self, size: float, *args, **kwargs) -> float:
        return size


def get_volatility_safety(*args, **kwargs):
    """Return stub."""
    return VolatilityAdjustedSafety()
