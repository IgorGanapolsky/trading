"""Black-Scholes Options Greeks & Delta Analyzer.

Calculates exact Delta, Theta, Gamma, and Vega for SPY/XSP option contracts
to optimize 0.15-delta short put strike selection and 50% profit target exits.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def _n_prime(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _cnd(x: float) -> float:
    """Cumulative normal distribution function approximation."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass(frozen=True)
class OptionGreeks:
    underlying_price: float
    strike_price: float
    dte: int
    iv: float
    option_type: str  # "call" or "put"
    delta: float
    gamma: float
    theta: float
    vega: float


class OptionsGreeksAnalyzer:
    """Calculates Black-Scholes Greeks for options risk management."""

    def __init__(self, risk_free_rate: float = 0.045):
        self.r = risk_free_rate

    def calculate_greeks(
        self,
        underlying_price: float,
        strike_price: float,
        dte: int,
        iv: float,
        option_type: str = "put",
    ) -> OptionGreeks:
        S = max(0.01, float(underlying_price))
        K = max(0.01, float(strike_price))
        T = max(1 / 365.0, float(dte) / 365.0)
        sigma = max(0.01, float(iv))
        is_put = option_type.lower() == "put"

        d1 = (math.log(S / K) + (self.r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if is_put:
            delta = _cnd(d1) - 1.0
        else:
            delta = _cnd(d1)

        gamma = _n_prime(d1) / (S * sigma * math.sqrt(T))

        if is_put:
            theta = (
                -(S * sigma * _n_prime(d1)) / (2.0 * math.sqrt(T))
                + self.r * K * math.exp(-self.r * T) * _cnd(-d2)
            ) / 365.0
        else:
            theta = (
                -(S * sigma * _n_prime(d1)) / (2.0 * math.sqrt(T))
                - self.r * K * math.exp(-self.r * T) * _cnd(d2)
            ) / 365.0

        vega = (S * math.sqrt(T) * _n_prime(d1)) / 100.0

        return OptionGreeks(
            underlying_price=S,
            strike_price=K,
            dte=dte,
            iv=sigma,
            option_type="put" if is_put else "call",
            delta=round(delta, 4),
            gamma=round(gamma, 6),
            theta=round(theta, 4),
            vega=round(vega, 4),
        )
