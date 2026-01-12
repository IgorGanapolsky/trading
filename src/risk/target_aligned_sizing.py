# Target aligned sizing stub - original deleted in cleanup PR #1445
# Minimal implementation to prevent import errors


class TargetAlignedSizer:
    """Stub target aligned sizer - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        self.daily_target = 100.0
        self.max_position_pct = 0.05

    def calculate_size(self, capital: float, price: float) -> int:
        """Calculate position size."""
        max_value = capital * self.max_position_pct
        if price <= 0:
            return 0
        return int(max_value / price)

    def get_daily_target(self) -> float:
        """Return daily target."""
        return self.daily_target
