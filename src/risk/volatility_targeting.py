"""
Volatility Targeting for Position Sizing

Based on Robert Carver's "Systematic Trading" (Chapter 11):
- Position size should be inversely proportional to instrument volatility
- This creates consistent risk exposure across all positions
- Adds ~0.3 to Sharpe ratio vs fixed position sizing

Formula:
    position_size = (target_portfolio_vol × capital) / (instrument_vol × price)

Where:
- target_portfolio_vol: Desired annual portfolio volatility (e.g., 0.15 = 15%)
- capital: Trading capital
- instrument_vol: Instrument's annualized volatility
- price: Current instrument price

Author: Trading System
Created: 2025-12-11
Reference: Carver, R. (2015). Systematic Trading. Harriman House.
"""

import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Default volatility estimates by asset class (annualized)
# These are conservative estimates used when live data unavailable
DEFAULT_VOLATILITY = {
    "SPY": 0.15,  # S&P 500 ~15% annual vol
    "QQQ": 0.20,  # Nasdaq ~20% annual vol
    "IWM": 0.20,  # Russell 2000 ~20% annual vol
    "DIA": 0.14,  # Dow ~14% annual vol
    # Treasuries (very low volatility)
    "BIL": 0.005,  # 1-3 month T-Bills ~0.5%
    "SHY": 0.02,  # 1-3 year Treasury ~2%
    "IEF": 0.08,  # 7-10 year Treasury ~8%
    "TLT": 0.15,  # 20+ year Treasury ~15%
    "GOVT": 0.06,  # All maturities ~6%
    # Bonds
    "AGG": 0.05,  # Aggregate bonds ~5%
    "BND": 0.05,  # Total bond ~5%
    "LQD": 0.08,  # Investment grade corp ~8%
    "HYG": 0.10,  # High yield ~10%
}

# Asset class default volatilities
ASSET_CLASS_VOLATILITY = {
    "treasury": 0.05,
    "bond": 0.07,
    "equity": 0.18,
}


@dataclass
class VolatilityTargetConfig:
    """Configuration for volatility targeting."""

    # Target portfolio volatility (annualized)
    # 10-15% is conservative, 20-25% is aggressive
    target_annual_vol: float = 0.15  # 15% target annual volatility

    # Volatility calculation parameters
    lookback_days: int = 20  # Days for volatility estimation
    vol_floor: float = 0.01  # Minimum 1% annualized vol (prevents division by tiny numbers)
    vol_ceiling: float = 1.0  # Maximum 100% annualized vol (prevents extreme reduction)

    # Position limits
    max_position_pct: float = 0.20  # Max 20% of capital in single position
    min_position_dollars: float = 50.0  # Minimum $50 position - ensures profit after 0.18% fees


@dataclass
class VolatilityTargetedPosition:
    """Result of volatility-targeted position sizing."""

    symbol: str
    position_dollars: float
    num_shares: float
    instrument_vol: float  # Annualized volatility used
    vol_source: str  # "calculated", "default", "asset_class"
    risk_contribution: float  # Expected contribution to portfolio vol
    reasoning: str


def calculate_annualized_volatility(
    returns: list[float] | np.ndarray,
    trading_days_per_year: int = 252,
) -> float:
    """
    Calculate annualized volatility from daily returns.

    Uses exponentially weighted moving average (EWMA) with half-life of 20 days
    as recommended by Carver for more responsive vol estimates.

    Args:
        returns: List or array of daily returns (as decimals, e.g., 0.01 = 1%)
        trading_days_per_year: Number of trading days per year

    Returns:
        Annualized volatility as decimal (e.g., 0.15 = 15%)
    """
    if len(returns) < 5:
        return 0.0

    returns_array = np.array(returns)

    # EWMA volatility with half-life of 20 days (Carver recommendation)
    # decay = 0.5^(1/20) ≈ 0.966
    decay = 0.5 ** (1 / 20)
    weights = np.array([decay**i for i in range(len(returns_array) - 1, -1, -1)])
    weights = weights / weights.sum()

    # Weighted variance
    weighted_mean = np.sum(weights * returns_array)
    weighted_var = np.sum(weights * (returns_array - weighted_mean) ** 2)

    # Daily vol to annual vol
    daily_vol = math.sqrt(weighted_var)
    annual_vol = daily_vol * math.sqrt(trading_days_per_year)

    return annual_vol


def get_instrument_volatility(
    symbol: str,
    price_history: list[float] | None = None,
    config: VolatilityTargetConfig | None = None,
) -> tuple[float, str]:
    """
    Get instrument volatility for position sizing.

    Priority:
    1. Calculate from price history if available
    2. Use symbol-specific default if known
    3. Use asset class default

    Args:
        symbol: Instrument symbol
        price_history: List of recent closing prices (newest last)
        config: Volatility target configuration

    Returns:
        Tuple of (annualized_volatility, source_description)
    """
    config = config or VolatilityTargetConfig()
    symbol_upper = symbol.upper()

    # Try to calculate from price history
    if price_history and len(price_history) >= 10:
        # Calculate daily returns
        prices = np.array(price_history)
        returns = np.diff(prices) / prices[:-1]

        vol = calculate_annualized_volatility(returns)
        if vol > 0:
            # Apply floor and ceiling
            vol = max(config.vol_floor, min(config.vol_ceiling, vol))
            return vol, "calculated"

    # Use symbol-specific default
    if symbol_upper in DEFAULT_VOLATILITY:
        return DEFAULT_VOLATILITY[symbol_upper], "default"

    # Use asset class default
    if symbol_upper in {"BIL", "SHY", "IEF", "TLT", "GOVT", "VGSH", "VGIT", "VGLT", "SCHO", "SCHR"}:
        return ASSET_CLASS_VOLATILITY["treasury"], "asset_class"
    if symbol_upper in {"AGG", "BND", "LQD", "HYG", "JNK", "TIP", "VCSH", "VCIT"}:
        return ASSET_CLASS_VOLATILITY["bond"], "asset_class"

    # Default to equity
    return ASSET_CLASS_VOLATILITY["equity"], "asset_class"


class VolatilityTargeter:
    """
    Volatility-targeted position sizing.

    Implements Carver's formula:
        position_size = (target_vol × capital) / (instrument_vol × price)

    This ensures each position contributes roughly equal risk to the portfolio,
    regardless of the instrument's inherent volatility.
    """

    def __init__(self, config: VolatilityTargetConfig | None = None):
        """Initialize volatility targeter."""
        self.config = config or VolatilityTargetConfig()
        logger.info(
            f"VolatilityTargeter initialized: target_vol={self.config.target_annual_vol * 100:.1f}%"
        )

    def calculate_position_size(
        self,
        symbol: str,
        current_price: float,
        capital: float,
        price_history: list[float] | None = None,
        num_positions: int = 1,
    ) -> VolatilityTargetedPosition:
        """
        Calculate volatility-targeted position size.

        Args:
            symbol: Instrument symbol
            current_price: Current price per share
            capital: Total trading capital
            price_history: Recent price history for vol calculation
            num_positions: Expected number of positions in portfolio (for diversification)

        Returns:
            VolatilityTargetedPosition with sizing details
        """
        # Get instrument volatility
        instrument_vol, vol_source = get_instrument_volatility(symbol, price_history, self.config)

        # Carver's formula: position = (target_vol × capital) / (instrument_vol × price)
        # Adjusted for number of positions (diversification)
        position_target_vol = self.config.target_annual_vol / math.sqrt(max(1, num_positions))

        # Calculate notional position size
        if instrument_vol > 0 and current_price > 0:
            position_dollars = (position_target_vol * capital) / instrument_vol
        else:
            position_dollars = self.config.min_position_dollars

        # Apply position limits
        max_position = capital * self.config.max_position_pct
        position_dollars = min(position_dollars, max_position)
        position_dollars = max(position_dollars, self.config.min_position_dollars)

        # Calculate shares
        num_shares = position_dollars / current_price if current_price > 0 else 0.0

        # Calculate risk contribution
        risk_contribution = (position_dollars * instrument_vol) / capital

        # Generate reasoning
        reasoning = (
            f"Vol targeting: {symbol} vol={instrument_vol * 100:.1f}% ({vol_source}), "
            f"target={position_target_vol * 100:.1f}%, "
            f"position=${position_dollars:.2f} ({position_dollars / capital * 100:.1f}% of capital)"
        )

        return VolatilityTargetedPosition(
            symbol=symbol,
            position_dollars=position_dollars,
            num_shares=num_shares,
            instrument_vol=instrument_vol,
            vol_source=vol_source,
            risk_contribution=risk_contribution,
            reasoning=reasoning,
        )

    def calculate_portfolio_positions(
        self,
        positions: list[dict[str, Any]],
        capital: float,
    ) -> list[VolatilityTargetedPosition]:
        """
        Calculate volatility-targeted sizes for multiple positions.

        Args:
            positions: List of dicts with keys: symbol, price, price_history (optional)
            capital: Total trading capital

        Returns:
            List of VolatilityTargetedPosition for each position
        """
        num_positions = len(positions)
        results = []

        for pos in positions:
            result = self.calculate_position_size(
                symbol=pos["symbol"],
                current_price=pos["price"],
                capital=capital,
                price_history=pos.get("price_history"),
                num_positions=num_positions,
            )
            results.append(result)

        return results


# Default instance
DEFAULT_VOLATILITY_TARGETER = VolatilityTargeter()


def get_volatility_adjusted_size(
    symbol: str,
    current_price: float,
    capital: float,
    base_position_size: float,
    price_history: list[float] | None = None,
) -> tuple[float, str]:
    """
    Convenience function to adjust a base position size by volatility.

    This can be used to modify existing position sizing logic without
    replacing it entirely.

    Args:
        symbol: Instrument symbol
        current_price: Current price
        capital: Trading capital
        base_position_size: Base position size before vol adjustment
        price_history: Optional price history

    Returns:
        Tuple of (adjusted_position_size, reasoning)
    """
    vol_position = DEFAULT_VOLATILITY_TARGETER.calculate_position_size(
        symbol=symbol,
        current_price=current_price,
        capital=capital,
        price_history=price_history,
    )

    # Use the more conservative of base size and vol-targeted size
    adjusted_size = min(base_position_size, vol_position.position_dollars)

    reasoning = (
        f"Base: ${base_position_size:.2f}, "
        f"Vol-targeted: ${vol_position.position_dollars:.2f} "
        f"({vol_position.instrument_vol * 100:.1f}% vol), "
        f"Final: ${adjusted_size:.2f}"
    )

    return adjusted_size, reasoning
