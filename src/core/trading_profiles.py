"""Canonical trading profiles for live strategy execution paths."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, replace
from functools import cache
from typing import Any


@dataclass(frozen=True)
class IronCondorProfile:
    """Canonical iron-condor policy shared by entry, execution, and exits."""

    name: str
    underlying: str
    target_dte: int
    min_dte: int
    max_dte: int
    short_delta: float
    delta_band_min: float
    delta_band_max: float
    wing_width: float
    take_profit_pct: float
    stop_loss_pct: float
    exit_dte: int
    min_hold_hours: int
    position_size_pct: float
    max_contracts_per_trade: int
    max_concurrent_positions: int
    max_daily_structures: int

    def as_strategy_config(self) -> dict[str, Any]:
        """Bridge to legacy dict-based strategy config callers."""
        data = asdict(self)
        data["underlying"] = self.underlying.upper()
        data["max_positions"] = self.max_concurrent_positions
        return data

    def with_underlying(self, underlying: str) -> IronCondorProfile:
        """Preserve the policy while routing to a different underlying."""
        return replace(self, underlying=underlying.upper().strip())


_BASELINE_IRON_CONDOR_PROFILE = IronCondorProfile(
    name="spy-core",
    underlying="SPY",
    target_dte=30,
    min_dte=30,
    max_dte=45,
    short_delta=0.15,
    delta_band_min=0.10,
    delta_band_max=0.22,
    # Validation hypothesis (data/runtime/strategy_validation_hypothesis.json)
    # rejects 10-wide wings from the failed 144-trade ledger; the fresh cohort
    # must use narrower defined-risk wings until kill criteria are cleared.
    wing_width=5.0,
    # CEO-approved 2026-07-02: 25% TP + 200% stop validation package.
    # Evidence: 138/144 failed-ledger losses stopped out <1h at the 100%
    # multiplier; avg win captured only 22% of premium. Kill criteria in
    # data/runtime/strategy_validation_hypothesis.json remain binding.
    take_profit_pct=0.25,
    stop_loss_pct=2.0,
    exit_dte=7,
    min_hold_hours=24,
    position_size_pct=0.02,  # 2% — industry standard for defined risk (was 5% scaling, 1% validation)
    # Validation phase: prove edge with one-lot sizing before scaling.
    max_contracts_per_trade=1,
    max_concurrent_positions=2,  # CLAUDE.md mandate: 2 ICs max (8 legs)
    max_daily_structures=1,
)

# Product-specific tuning can diverge later; for now the live policy is the same
# baseline routed to a different underlying symbol.
IRON_CONDOR_PROFILE_REGISTRY: dict[str, IronCondorProfile] = {
    "spy-core": _BASELINE_IRON_CONDOR_PROFILE,
    "spx-core": _BASELINE_IRON_CONDOR_PROFILE.with_underlying("SPX"),
    "xsp-core": _BASELINE_IRON_CONDOR_PROFILE.with_underlying("XSP"),
}

DEFAULT_IRON_CONDOR_PROFILE_NAME = "spy-core"


@cache
def get_iron_condor_profile(
    profile_name: str | None = None,
    underlying: str | None = None,
) -> IronCondorProfile:
    """Return the active iron-condor profile, optionally routed to another symbol."""
    resolved_name = (profile_name or os.getenv("IRON_CONDOR_PROFILE") or DEFAULT_IRON_CONDOR_PROFILE_NAME).lower()
    profile = IRON_CONDOR_PROFILE_REGISTRY.get(resolved_name, _BASELINE_IRON_CONDOR_PROFILE)
    if underlying:
        return profile.with_underlying(underlying)
    return profile


def get_iron_condor_strategy_config(underlying: str | None = None) -> dict[str, Any]:
    """Compatibility helper for dict-based scripts."""
    return get_iron_condor_profile(underlying=underlying).as_strategy_config()


@dataclass(frozen=True)
class PutCreditProfile:
    """Canonical SPY bull-put (credit vertical) policy — successor to killed IC Simple."""

    name: str
    underlying: str
    target_dte: int
    min_dte: int
    max_dte: int
    short_delta: float
    delta_band_min: float
    delta_band_max: float
    wing_width: float
    take_profit_pct: float
    stop_loss_pct: float
    exit_dte: int
    min_hold_hours: int
    position_size_pct: float
    max_contracts_per_trade: int
    max_concurrent_positions: int
    max_daily_structures: int
    min_credit: float

    def as_strategy_config(self) -> dict[str, Any]:
        data = asdict(self)
        data["underlying"] = self.underlying.upper()
        data["max_positions"] = self.max_concurrent_positions
        data["strategy_family"] = "spy_put_credit"
        data["structure"] = "bull_put_credit"
        return data


_BASELINE_PUT_CREDIT_PROFILE = PutCreditProfile(
    name="spy-put-credit",
    underlying="SPY",
    target_dte=30,
    min_dte=30,
    max_dte=45,
    short_delta=0.15,
    delta_band_min=0.10,
    delta_band_max=0.22,
    wing_width=5.0,
    take_profit_pct=0.25,
    stop_loss_pct=2.0,
    exit_dte=7,
    min_hold_hours=24,
    position_size_pct=0.02,
    max_contracts_per_trade=1,
    max_concurrent_positions=2,
    max_daily_structures=1,
    min_credit=0.50,
)

PUT_CREDIT_PROFILE_REGISTRY: dict[str, PutCreditProfile] = {
    "spy-put-credit": _BASELINE_PUT_CREDIT_PROFILE,
}

DEFAULT_PUT_CREDIT_PROFILE_NAME = "spy-put-credit"


@cache
def get_put_credit_profile(profile_name: str | None = None) -> PutCreditProfile:
    resolved = (
        profile_name
        or os.getenv("PUT_CREDIT_PROFILE")
        or DEFAULT_PUT_CREDIT_PROFILE_NAME
    ).lower()
    return PUT_CREDIT_PROFILE_REGISTRY.get(resolved, _BASELINE_PUT_CREDIT_PROFILE)


def get_active_strategy_config() -> dict[str, Any]:
    """Config for the active validation family (post IC kill: put credit)."""
    try:
        from src.core.active_strategy import load_kill_state

        state = load_kill_state()
        if state.active_family in {"spy_put_credit", "bull_put", "put_credit"}:
            return get_put_credit_profile().as_strategy_config()
    except Exception:
        pass
    return get_put_credit_profile().as_strategy_config()
