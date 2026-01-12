# Capital efficiency stub - original deleted in cleanup PR #1445
# Minimal implementation to prevent import errors


class CapitalCalculator:
    """Stub capital calculator."""

    def __init__(self, *args, **kwargs):
        pass

    def calculate(self, capital: float) -> dict:
        """Return stub calculation."""
        return {"efficiency": 1.0, "status": "stub"}


def get_capital_calculator(*args, **kwargs) -> CapitalCalculator:
    """Return stub calculator instance."""
    return CapitalCalculator()
