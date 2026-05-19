"""Tests for IronCondorRisk.calculate_quantity (was a commented-out stub).

The 50-lot SPY 2026-06-18 IC incident on 2026-05-19 showed that the
strategy layer had no quantity-sizing function — quantity was a literal
in the trader scripts. This locks in the correct behaviour.
"""

from src.strategies.iron_condor.risk import IronCondorRisk


class TestCalculateQuantity:
    def test_returns_zero_on_zero_equity(self):
        r = IronCondorRisk()
        assert r.calculate_quantity(equity=0, wing_width=10, credit_per_contract=2.0) == 0

    def test_returns_zero_on_zero_or_negative_wing(self):
        r = IronCondorRisk()
        assert r.calculate_quantity(equity=100_000, wing_width=0, credit_per_contract=2.0) == 0
        assert r.calculate_quantity(equity=100_000, wing_width=-1, credit_per_contract=2.0) == 0

    def test_returns_zero_when_credit_geq_wing(self):
        """Credit >= wing would imply zero or negative max loss — non-physical."""
        r = IronCondorRisk()
        assert r.calculate_quantity(equity=100_000, wing_width=10, credit_per_contract=10) == 0
        assert r.calculate_quantity(equity=100_000, wing_width=10, credit_per_contract=11) == 0

    def test_hard_cap_dominates_when_risk_room_is_larger(self):
        """On a $100K account, 2% = $2,000 / $800 per-IC = 2 ICs by risk.
        With explicit hard_cap=1 (controlled-experiment rule), result is 1."""
        r = IronCondorRisk()
        qty = r.calculate_quantity(
            equity=100_000,
            wing_width=10,
            credit_per_contract=2.0,
            max_risk_pct=0.02,
            hard_cap=1,
        )
        assert qty == 1

    def test_risk_pct_dominates_when_tighter_than_cap(self):
        """Tiny account: 1% of $5,000 = $50 / $800 per-IC = 0 ICs."""
        r = IronCondorRisk()
        qty = r.calculate_quantity(
            equity=5_000,
            wing_width=10,
            credit_per_contract=2.0,
            max_risk_pct=0.01,
            hard_cap=10,
        )
        assert qty == 0

    def test_blocks_the_historical_50_lot(self):
        """The actual incident: $95K paper account, $10 wing, ~$2 credit.
        Per-IC max loss = $800. 2% of $95K = $1,900. qty_from_risk = 2.
        With the default MAX_CONTRACTS_PER_TRADE hard cap (1 for the
        controlled-experiment profile), legal qty == 1, NOT 50."""
        r = IronCondorRisk()
        qty = r.calculate_quantity(
            equity=95_000,
            wing_width=10,
            credit_per_contract=2.0,
            hard_cap=1,
        )
        assert qty == 1
        assert qty != 50

    def test_quantity_is_non_negative_int(self):
        r = IronCondorRisk()
        qty = r.calculate_quantity(equity=100_000, wing_width=10, credit_per_contract=2.0)
        assert isinstance(qty, int)
        assert qty >= 0
