"""Centralized configuration with validation.

Uses pydantic-settings to parse environment variables and enforce basic ranges.
"""

from __future__ import annotations

from pydantic import Field, field_validator

try:  # pragma: no cover - test sandboxes may lack the nested provider module
    from pydantic_settings import BaseSettings
except Exception:  # noqa: BLE001
    from pydantic import BaseModel as BaseSettings  # type: ignore

# =============================================================================
# OPTIMIZED $10/DAY ALLOCATION CONFIGURATION
# =============================================================================
# Strategy: Maximize compound growth through diversified allocation
# Target: Build foundation for $100+/day profitability by Month 6
#
# Allocation Breakdown:
# - Core ETFs (40%): Momentum-selected SPY/QQQ for stable growth
# - Bonds + Treasuries (15%): Risk mitigation via BND + SHY/IEF/TLT ladder
# - REITs (15%): Dividend income via VNQ
# - Crypto (10%): Weekend BTC/ETH volatility capture
# - Growth Stocks (15%): High-conviction NVDA/GOOGL/AMZN
# - Options Reserve (5%): Premium accumulation for covered calls
#
# Benefits over legacy allocation:
# 1. Risk-adjusted: Bonds + REITs provide stability (30% defensive)
# 2. Income-focused: REITs + future options generate cash flow
# 3. Volatility capture: Crypto on weekends = 7-day trading
# 4. Compound-ready: Options reserve builds for yield generation
# =============================================================================

OPTIMIZED_DAILY_INVESTMENT = 10.0  # Base daily investment amount

# Optimized allocation percentages (with enhanced treasury exposure)
# Updated 2025-12-03: Increased treasury allocation for stable carry income
OPTIMIZED_ALLOCATION = {
    # Fixed GOVT core (intermediate treasury for stable 4.5% carry)
    # Purpose: Cash-plus yield with near-zero credit risk
    "treasury_core": 0.25,  # $2.50/day - GOVT ETF, bypasses all gates
    # Core momentum ETFs (SPY/QQQ selection based on technicals)
    # Reduced from 40% to make room for treasury core
    "core_etfs": 0.35,  # $3.50/day
    # Dynamic treasury ladder (SHY/IEF/TLT or ZROZ)
    # Purpose: Yield curve positioning, steepener trades
    "treasury_dynamic": 0.10,  # $1.00/day - subject to momentum gates
    # REITs (VNQ - Vanguard Real Estate ETF)
    # Purpose: Dividend income, real estate exposure, inflation hedge
    "reits": 0.10,  # $1.00/day
    # Crypto (BTC/ETH weekend trading)
    # Purpose: 24/7 market access, volatility capture
    "crypto": 0.05,  # $0.50/day
    # Growth stocks (NVDA/GOOGL/AMZN)
    # Purpose: High-conviction tech exposure
    "growth_stocks": 0.10,  # $1.00/day
    # Options premium reserve (for covered calls)
    # Purpose: Accumulate capital for yield generation strategy
    "options_reserve": 0.05,  # $0.50/day
}

# Treasury-specific configuration
TREASURY_CONFIG = {
    # Fixed core allocation - always invested regardless of signals
    "govt_core_pct": 0.25,
    "govt_ticker": "GOVT",
    # Dynamic long ETF selection thresholds
    "yield_10y_zroz_threshold": 4.05,  # Switch to ZROZ when 10Y < 4.05%
    "default_long_etf": "TLT",
    "low_yield_long_etf": "ZROZ",
    # Steepener override (2s10s spread)
    "steepener_threshold": 0.20,  # Trigger when spread < 0.2%
    "steepener_extra_allocation": 0.15,  # Add 15% extra to long
    # MOVE Index thresholds
    "move_low_vol": 70,
    "move_high_vol": 120,
    # T-Bill ladder for idle cash
    "tbill_ticker": "BIL",
    "tbill_cash_reserve_pct": 0.05,  # Keep 5% as true cash
}

# Calculate dollar amounts for clarity
OPTIMIZED_AMOUNTS = {
    tier: OPTIMIZED_DAILY_INVESTMENT * pct for tier, pct in OPTIMIZED_ALLOCATION.items()
}

# Validation: Ensure allocations sum to 100%
assert abs(sum(OPTIMIZED_ALLOCATION.values()) - 1.0) < 0.001, (
    f"Optimized allocations must sum to 100%, got {sum(OPTIMIZED_ALLOCATION.values()) * 100:.1f}%"
)


class AppConfig(BaseSettings):
    # Trading
    DAILY_INVESTMENT: float = Field(default=10.0, ge=0.01, description="Daily budget in USD")
    USE_OPTIMIZED_ALLOCATION: bool = Field(
        default=False,
        description="Use optimized $10/day allocation (bonds, REITs, crypto, options reserve)",
    )
    ALPACA_SIMULATED: bool = Field(default=True)
    SIMULATED_EQUITY: float = Field(default=100000.0, ge=0.0)

    # LLM/Budget
    HYBRID_LLM_MODEL: str = Field(default="claude-3-5-haiku-20241022")
    RL_CONFIDENCE_THRESHOLD: float = Field(default=0.6, ge=0.0, le=1.0)
    LLM_NEGATIVE_SENTIMENT_THRESHOLD: float = Field(default=-0.2, le=0.0, ge=-1.0)

    # Risk
    RISK_USE_ATR_SCALING: bool = Field(default=True)
    ATR_STOP_MULTIPLIER: float = Field(default=2.0, gt=0.0)

    # Order Execution
    USE_LIMIT_ORDERS: bool = Field(
        default=True, description="Use limit orders instead of market orders to reduce slippage"
    )
    LIMIT_ORDER_BUFFER_PCT: float = Field(
        default=0.1, ge=0.0, le=5.0, description="Buffer percentage for limit orders (0.1 = 0.1%)"
    )
    LIMIT_ORDER_TIMEOUT_SECONDS: int = Field(
        default=60, ge=10, le=300, description="Timeout before canceling unfilled limit order"
    )

    @field_validator("DAILY_INVESTMENT")
    @classmethod
    def _validate_budget(cls, v: float) -> float:
        if v > 1000.0:
            raise ValueError("DAILY_INVESTMENT too high for safety; cap at $1000")
        return v

    def get_tier_allocations(self) -> dict[str, float]:
        """
        Get tier allocations based on USE_OPTIMIZED_ALLOCATION flag.

        Returns:
            Dictionary mapping tier names to dollar amounts
        """
        if self.USE_OPTIMIZED_ALLOCATION:
            # Use optimized allocation with current DAILY_INVESTMENT amount
            scale_factor = self.DAILY_INVESTMENT / OPTIMIZED_DAILY_INVESTMENT
            return {tier: amount * scale_factor for tier, amount in OPTIMIZED_AMOUNTS.items()}
        else:
            # Legacy allocation (backwards compatibility)
            # Tier 1: 60%, Tier 2: 20%, Tier 3: 10%, Tier 4: 10%
            return {
                "tier1_core": self.DAILY_INVESTMENT * 0.60,
                "tier2_growth": self.DAILY_INVESTMENT * 0.20,
                "tier3_ipo": self.DAILY_INVESTMENT * 0.10,
                "tier4_crowdfunding": self.DAILY_INVESTMENT * 0.10,
            }

    class Config:
        env_file = ".env"
        extra = "ignore"


def load_config() -> AppConfig:
    return AppConfig()  # type: ignore[call-arg]
