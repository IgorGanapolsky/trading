"""Tests for canonical iron-condor trading profiles."""

from __future__ import annotations

from src.core import trading_constants
from src.core.trading_profiles import (
    get_iron_condor_profile,
    get_iron_condor_strategy_config,
)


def test_default_iron_condor_profile_values():
    profile = get_iron_condor_profile()

    assert profile.name == "spy-core"
    assert profile.underlying == "SPY"
    assert profile.target_dte == 30
    assert profile.min_dte == 30
    assert profile.max_dte == 45
    assert profile.short_delta == 0.15
    assert profile.delta_band_min == 0.10
    assert profile.delta_band_max == 0.22
    assert profile.wing_width == 10.0
    assert profile.take_profit_pct == 0.50
    assert profile.stop_loss_pct == 1.0
    assert profile.exit_dte == 7
    assert profile.min_hold_hours == 24
    assert profile.position_size_pct == 0.05
    assert profile.max_contracts_per_trade == 2
    assert profile.max_concurrent_positions == 4
    assert profile.max_daily_structures == 1


def test_strategy_config_bridge_matches_profile():
    config = get_iron_condor_strategy_config()

    assert config["underlying"] == "SPY"
    assert config["target_dte"] == 30
    assert config["min_dte"] == 30
    assert config["max_dte"] == 45
    assert config["short_delta"] == 0.15
    assert config["wing_width"] == 10.0
    assert config["take_profit_pct"] == 0.50
    assert config["stop_loss_pct"] == 1.0
    assert config["exit_dte"] == 7
    assert config["min_hold_hours"] == 24
    assert config["position_size_pct"] == 0.05
    assert config["max_contracts_per_trade"] == 2
    assert config["max_positions"] == 4


def test_trading_constants_derive_from_active_profile():
    profile = get_iron_condor_profile()

    assert profile.underlying == trading_constants.IRON_CONDOR_UNDERLYING
    assert profile.target_dte == trading_constants.IRON_CONDOR_TARGET_DTE
    assert profile.short_delta == trading_constants.IRON_CONDOR_TARGET_DELTA
    assert profile.delta_band_min == trading_constants.IRON_CONDOR_DELTA_MIN
    assert profile.delta_band_max == trading_constants.IRON_CONDOR_DELTA_MAX
    assert profile.wing_width == trading_constants.IRON_CONDOR_WING_WIDTH
    assert profile.take_profit_pct == trading_constants.IC_PROFIT_TARGET_PCT
    assert profile.stop_loss_pct == trading_constants.IRON_CONDOR_STOP_LOSS_MULTIPLIER
    assert profile.exit_dte == trading_constants.IRON_CONDOR_EXIT_DTE
    assert profile.min_hold_hours == trading_constants.IRON_CONDOR_MIN_HOLD_HOURS
    assert profile.position_size_pct == trading_constants.MAX_POSITION_PCT
    assert profile.max_contracts_per_trade == trading_constants.MAX_CONTRACTS_PER_TRADE
    assert profile.max_concurrent_positions == trading_constants.MAX_CONCURRENT_IRON_CONDORS
    assert profile.max_daily_structures == trading_constants.MAX_DAILY_STRUCTURES
    assert profile.min_dte == trading_constants.MIN_DTE
    assert profile.max_dte == trading_constants.MAX_DTE
