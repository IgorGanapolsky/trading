from __future__ import annotations

import pytest

from src.strategies.iron_condor.risk import IronCondorRisk


def test_get_stop_prices_uses_credit_times_multiplier() -> None:
    risk = IronCondorRisk(max_positions=1)
    risk.stop_multiplier = 1.0

    stops = risk.get_stop_prices(credit_received=1.25, short_put=3.10, short_call=2.90)

    assert stops["put_stop"] == pytest.approx(4.35)
    assert stops["call_stop"] == pytest.approx(4.15)
