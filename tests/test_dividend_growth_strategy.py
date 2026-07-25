import pytest

from src.strategies.dividend_growth_strategy import DcaOrder, DividendGrowthStrategy


class TestDividendGrowthStrategy:
    def test_default_universe_is_schd(self):
        strategy = DividendGrowthStrategy()
        assert strategy.universe == ["SCHD"]

    def test_rejects_empty_universe(self):
        with pytest.raises(ValueError, match="universe"):
            DividendGrowthStrategy(universe=[])

    def test_plan_purchase_splits_cash_evenly_across_universe(self):
        strategy = DividendGrowthStrategy(universe=["SCHD", "VYM"])
        orders = strategy.plan_purchase(100.0)
        assert orders == [
            DcaOrder(symbol="SCHD", notional_usd=50.0),
            DcaOrder(symbol="VYM", notional_usd=50.0),
        ]

    def test_plan_purchase_returns_empty_for_zero_cash(self):
        strategy = DividendGrowthStrategy()
        assert strategy.plan_purchase(0.0) == []

    def test_plan_purchase_returns_empty_for_negative_cash(self):
        strategy = DividendGrowthStrategy()
        assert strategy.plan_purchase(-10.0) == []

    def test_plan_purchase_skips_when_per_symbol_notional_below_one_dollar(self):
        strategy = DividendGrowthStrategy(universe=["SCHD", "VYM", "DGRO"])
        # $2.50 / 3 symbols = $0.83 each, below the $1 minimum notional
        assert strategy.plan_purchase(2.5) == []

    def test_plan_purchase_single_symbol_uses_full_amount(self):
        strategy = DividendGrowthStrategy(universe=["SCHD"])
        orders = strategy.plan_purchase(42.0)
        assert orders == [DcaOrder(symbol="SCHD", notional_usd=42.0)]
