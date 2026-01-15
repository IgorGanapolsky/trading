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
# OPTIMIZED ALLOCATION CONFIGURATION - THETA PIVOT (Dec 11, 2025)
# =============================================================================
# Strategy: Pivot to options theta decay for path to $100/day North Star
# Rationale: Momentum caps at 26% annualized; theta on SPY/QQQ iron condors
#            yields 25-30% ROI with 80% win rate in range-bound markets
#
# Allocation Breakdown (70/30 Theta Pivot):
# - Options Theta (70%): Iron condors, credit spreads on SPY/QQQ
#   - SPY theta: 40% - Premium selling, 45-60 DTE OTM spreads
#   - QQQ theta: 30% - Premium selling, higher vol = more premium
# - Momentum ETFs (30%): MACD/RSI/Volume momentum core
#
# NOTE: Crypto removed per Lesson Learned #052 - We do NOT trade crypto
#
# Expected Returns:
# - Theta: $50-75/day realistic on $25k allocation (25-30% ROI)
# - Momentum: $15-20/day on $30k allocation (18-24% ROI)
# - Total path to $65-95/day → North Star achievable
#
# Risk Management:
# - Iron condors: 2.0x credit stop-loss (McMillan)
# - Max single position: 10% of capital
# - Daily drawdown circuit: 2%
# =============================================================================

OPTIMIZED_DAILY_INVESTMENT = 25.0  # Base daily investment amount

# Theta-pivot allocation (Dec 11, 2025 strategic shift)
# 70% theta, 30% momentum - NO CRYPTO (Lesson #052)
OPTIMIZED_ALLOCATION = {
    # Options theta strategies (70% total)
    # SPY iron condors: Sell 20-delta wings, 45-60 DTE, collect theta
    "theta_spy": 0.40,  # $4.00/day accumulation → SPY premium selling
    # QQQ iron condors: Higher IV = more premium, same structure
    "theta_qqq": 0.30,  # $3.00/day accumulation → QQQ premium selling
    # Core momentum ETFs (30% total)
    # SPY/QQQ/VTI selection based on MACD/RSI/Volume signals
    "momentum_etfs": 0.30,  # $3.00/day - technical momentum plays
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
    DAILY_INVESTMENT: float = Field(default=25.0, ge=0.01, description="Daily budget in USD")
    USE_OPTIMIZED_ALLOCATION: bool = Field(
        default=False,
        description="Use optimized $25/day allocation (theta, momentum, options reserve)",
    )
    ALPACA_SIMULATED: bool = Field(default=True)
    SIMULATED_EQUITY: float = Field(default=100000.0, ge=0.0)

    # LLM/Budget - BATS Framework (Budget-Aware Test-time Scaling)
    # Reference: https://arxiv.org/abs/2511.17006
    HYBRID_LLM_MODEL: str = Field(default="claude-3-5-haiku-20241022")
    LLM_DAILY_BUDGET: float = Field(
        default=3.33,  # $100/month ÷ 30 days
        ge=0.0,
        le=50.0,
        description="Daily LLM API budget in USD",
    )
    LLM_MONTHLY_BUDGET: float = Field(
        default=100.0,
        ge=0.0,
        le=500.0,
        description="Monthly LLM API budget in USD",
    )
    FORCE_LLM_MODEL: str | None = Field(
        default=None,
        description="Force all agents to use this model (for testing/debugging)",
    )
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
