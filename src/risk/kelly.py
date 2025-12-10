"""
Kelly sizing helpers for deterministic position sizing.
"""

from __future__ import annotations


def kelly_fraction(win_probability: float, payoff_ratio: float) -> float:
    """
    Compute the Kelly fraction for a single trade opportunity.
    """
    win_probability = max(0.0, min(1.0, win_probability))
    payoff_ratio = max(0.0, payoff_ratio)
    if payoff_ratio <= 0 or win_probability <= 0:
        return 0.0
    loss_probability = 1.0 - win_probability
    numerator = (win_probability * payoff_ratio) - loss_probability
    denominator = payoff_ratio
    if denominator == 0:
        return 0.0
    return max(0.0, numerator / denominator)
