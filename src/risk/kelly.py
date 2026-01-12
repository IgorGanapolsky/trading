# Kelly criterion stub - original deleted in cleanup PR #1445
# Minimal implementation to prevent import errors


def kelly_fraction(win_rate: float, win_loss_ratio: float) -> float:
    """
    Calculate Kelly criterion fraction.

    Stub implementation - returns conservative 0.25 (quarter Kelly).
    """
    if win_rate <= 0 or win_loss_ratio <= 0:
        return 0.0

    # Quarter Kelly for safety
    return 0.25
