#!/usr/bin/env python3
"""Micro-cap deployment gate tests (feat/live-micro-trade-cap).

Pure-function tests only: compute_micro_cap is deterministic and has no I/O,
so these never touch the network, the kill-switch, or real creds. They assert
the "deposit more, trade more as small as possible" curve it encodes.
"""

import pytest

from src.micro.micro_capital_gate import (
    compute_micro_cap,
    options_require_larger_capital,
)


@pytest.mark.parametrize(
    "balance,hard_floor,deploy_fraction,live_cap,exp_deploy,exp_can",
    [
        # Non-positive balance -> nothing.
        (0.0, 25.0, 0.10, 50.0, 0.0, False),
        (-5.0, 25.0, 0.10, 50.0, 0.0, False),
        # At/below the hard floor -> deploy nothing, keep buffer.
        (25.0, 25.0, 0.10, 50.0, 0.0, False),
        # "As small as possible": (balance-floor)*fraction.
        (100.0, 25.0, 0.10, 50.0, 7.50, True),
        # Live cap binds: surplus*frac (97.5) would exceed $50 cap.
        (1000.0, 25.0, 0.10, 50.0, 50.0, True),
        # Fraction scales with deposits ("more in -> more trade").
        (250.0, 25.0, 0.10, 50.0, 22.50, True),
        (500.0, 25.0, 0.10, 50.0, 47.50, True),
    ],
)
def test_compute_micro_cap_deployable(
    balance, hard_floor, deploy_fraction, live_cap, exp_deploy, exp_can
):
    dec = compute_micro_cap(
        balance,
        hard_floor_usd=hard_floor,
        deploy_fraction=deploy_fraction,
        live_cap_usd=live_cap,
    )
    assert dec.deployable_usd == pytest.approx(exp_deploy)
    assert dec.can_deploy == exp_can


def test_income_loop_can_consume_gate():
    """A $100 balance (Igor's current) deploys exactly ~$7.50 and is > $0."""
    dec = compute_micro_cap(100.0)
    assert dec.can_deploy is True
    assert dec.deployable_usd == pytest.approx(7.50)


def test_balance_below_floor_blocks_and_records_reason():
    dec = compute_micro_cap(10.0)
    assert dec.can_deploy is False
    assert dec.deployable_usd == 0.0
    assert dec.blocked_reason is not None
    assert "hard floor" in dec.blocked_reason


def test_options_excluded_with_explanation():
    reason = options_require_larger_capital()
    assert "500" in reason
    assert "option" in reason.lower()
