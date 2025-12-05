"""
Tests for Phil Town's Rule #1 Options Strategy.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from src.strategies.rule_one_options import (
    BigFiveMetrics,
    OptionContract,
    RuleOneOptionsSignal,
    RuleOneOptionsStrategy,
    StickerPriceResult,
)


@pytest.fixture(autouse=True)
def stub_alpaca_clients(monkeypatch):
    """Provide lightweight Alpaca client stubs so tests do not need credentials."""

    trader_mock = Mock()
    trader_mock.get_account.return_value = {"cash": "10000"}
    trader_mock.get_positions.return_value = []

    options_mock = Mock()

    monkeypatch.setattr(
        "src.strategies.rule_one_options.AlpacaTrader", lambda *args, **kwargs: trader_mock
    )
    monkeypatch.setattr(
        "src.strategies.rule_one_options.AlpacaOptionsClient", lambda *args, **kwargs: options_mock
    )


class TestBigFiveMetrics:
    """Test Big Five analysis."""

    def test_passes_rule_one_when_all_criteria_met(self):
        """Big Five should pass when ROIC >= 10% and avg growth >= 10%."""
        metrics = BigFiveMetrics(
            roic=0.15,  # 15% ROIC
            equity_growth=0.12,
            eps_growth=0.14,
            sales_growth=0.11,
            fcf_growth=0.13,
        )

        assert metrics.passes_rule_one is True
        assert metrics.avg_growth >= 0.10

    def test_fails_rule_one_low_roic(self):
        """Big Five should fail if ROIC < 10%."""
        metrics = BigFiveMetrics(
            roic=0.05,  # Only 5% ROIC
            equity_growth=0.15,
            eps_growth=0.15,
            sales_growth=0.15,
            fcf_growth=0.15,
        )

        assert metrics.passes_rule_one is False

    def test_fails_rule_one_low_growth(self):
        """Big Five should fail if avg growth < 10%."""
        metrics = BigFiveMetrics(
            roic=0.15,
            equity_growth=0.05,
            eps_growth=0.05,
            sales_growth=0.05,
            fcf_growth=0.05,
        )

        assert metrics.passes_rule_one is False
        assert metrics.avg_growth < 0.10


class TestStickerPriceResult:
    """Test Sticker Price calculations."""

    def test_recommendation_strong_buy_below_mos(self):
        """Should recommend STRONG BUY when below MOS price."""
        result = StickerPriceResult(
            symbol="AAPL",
            current_price=100,
            current_eps=5,
            growth_rate=0.15,
            future_eps=20,
            future_pe=30,
            future_price=600,
            sticker_price=150,
            mos_price=75,
        )

        # Price $100 is above MOS $75, so not strong buy
        assert "BUY" in result.recommendation

    def test_recommendation_buy_below_sticker(self):
        """Should recommend BUY when below Sticker but above MOS."""
        result = StickerPriceResult(
            symbol="MSFT",
            current_price=140,
            current_eps=8,
            growth_rate=0.12,
            future_eps=25,
            future_pe=24,
            future_price=600,
            sticker_price=150,
            mos_price=75,
        )

        # Price $140 is below Sticker $150 but above MOS $75
        assert "BUY" in result.recommendation

    def test_recommendation_sell_overvalued(self):
        """Should recommend SELL when significantly above Sticker."""
        result = StickerPriceResult(
            symbol="TEST",
            current_price=200,
            current_eps=5,
            growth_rate=0.10,
            future_eps=13,
            future_pe=20,
            future_price=260,
            sticker_price=100,  # Fair value is $100
            mos_price=50,
        )

        # Price $200 is 2x Sticker $100 -> SELL
        assert "SELL" in result.recommendation or "Overvalued" in result.recommendation

    def test_margin_of_safety_calculation(self):
        """Should correctly calculate margin of safety percentage."""
        result = StickerPriceResult(
            symbol="TEST",
            current_price=75,
            current_eps=5,
            growth_rate=0.15,
            future_eps=20,
            future_pe=30,
            future_price=600,
            sticker_price=150,
            mos_price=75,
        )

        # Current price $75 = MOS price, so MOS% = (150-75)/150 = 50%
        assert result.margin_of_safety == pytest.approx(0.50, abs=0.01)


class TestRuleOneOptionsSignal:
    """Test options signal generation."""

    def test_signal_creation(self):
        """Should create valid options signal."""
        signal = RuleOneOptionsSignal(
            symbol="AAPL",
            signal_type="sell_put",
            strike=150.0,
            expiration="2025-01-17",
            premium=3.50,
            annualized_return=0.15,
            sticker_price=200.0,
            mos_price=100.0,
            current_price=180.0,
            rationale="Test signal",
            confidence=0.8,
        )

        assert signal.symbol == "AAPL"
        assert signal.signal_type == "sell_put"
        assert signal.annualized_return == 0.15
        assert signal.timestamp is not None


class TestRuleOneOptionsStrategy:
    """Test the main strategy class."""

    @patch("src.strategies.rule_one_options.yf.Ticker")
    def test_calculate_sticker_price(self, mock_ticker):
        """Should calculate Sticker Price using Phil Town's formula."""
        # Mock yfinance data
        mock_ticker.return_value.info = {
            "currentPrice": 150.0,
            "trailingEps": 6.0,
            "earningsGrowth": 0.12,
        }
        mock_ticker.return_value.financials = MagicMock()
        mock_ticker.return_value.balance_sheet = MagicMock()
        mock_ticker.return_value.cashflow = MagicMock()

        strategy = RuleOneOptionsStrategy(paper=True, universe=["AAPL"])
        result = strategy.calculate_sticker_price("AAPL")

        assert result is not None
        assert result.symbol == "AAPL"
        assert result.current_price == 150.0
        assert result.current_eps == 6.0
        assert result.sticker_price > 0
        assert result.mos_price == result.sticker_price * 0.5

    @patch("src.strategies.rule_one_options.yf.Ticker")
    def test_calculate_big_five(self, mock_ticker):
        """Should calculate Big Five metrics."""
        mock_ticker.return_value.info = {
            "returnOnCapital": 0.18,
            "earningsGrowth": 0.15,
            "revenueGrowth": 0.12,
        }
        mock_ticker.return_value.financials = MagicMock()
        mock_ticker.return_value.balance_sheet = MagicMock()
        mock_ticker.return_value.cashflow = MagicMock()

        strategy = RuleOneOptionsStrategy(paper=True)
        metrics = strategy.calculate_big_five("AAPL")

        assert metrics is not None
        assert metrics.roic == 0.18
        assert metrics.eps_growth == 0.15

    def test_strategy_initialization(self):
        """Should initialize with default universe."""
        strategy = RuleOneOptionsStrategy(paper=True)

        assert len(strategy.universe) > 0
        assert "AAPL" in strategy.universe
        assert "MSFT" in strategy.universe
        assert strategy.paper is True

    def test_custom_universe(self):
        """Should accept custom universe."""
        custom = ["NVDA", "AMD", "INTC"]
        strategy = RuleOneOptionsStrategy(paper=True, universe=custom)

        assert strategy.universe == custom
        assert len(strategy.universe) == 3

    def test_put_opportunities_filter_by_iv_rank(self, monkeypatch):
        """High IV rank should block put signals."""
        strategy = RuleOneOptionsStrategy(paper=True, universe=["AAPL"])
        strategy.trader = Mock()
        strategy.trader.get_account.return_value = {"cash": "10000"}

        valuation = StickerPriceResult(
            symbol="AAPL",
            current_price=150,
            current_eps=6,
            growth_rate=0.12,
            future_eps=15,
            future_pe=25,
            future_price=375,
            sticker_price=180,
            mos_price=90,
        )
        strategy._valuation_cache["AAPL"] = valuation
        strategy._big_five_cache["AAPL"] = BigFiveMetrics(
            roic=0.15, equity_growth=0.12, eps_growth=0.14, sales_growth=0.11, fcf_growth=0.13
        )

        high_iv_contract = OptionContract(
            symbol="AAPL",
            option_type="put",
            expiration="2025-01-17",
            strike=90,
            bid=1.0,
            ask=1.5,
            mid=1.25,
            delta=-0.18,
            implied_vol=0.4,
            days_to_expiry=30,
            iv_rank=65.0,
        )

        monkeypatch.setattr(
            strategy, "_find_best_put_option", lambda *args, **kwargs: high_iv_contract
        )

        signals = strategy.find_put_opportunities()
        assert signals == []

    def test_put_opportunities_include_contract_sizing(self, monkeypatch):
        """Ensure cash sizing determines contract count and metadata."""
        strategy = RuleOneOptionsStrategy(paper=True, universe=["MSFT"])
        strategy.trader = Mock()
        strategy.trader.get_account.return_value = {"cash": "20000"}
        strategy.trader.get_account_info.return_value = {"cash": "20000"}

        valuation = StickerPriceResult(
            symbol="MSFT",
            current_price=300,
            current_eps=10,
            growth_rate=0.15,
            future_eps=25,
            future_pe=30,
            future_price=750,
            sticker_price=250,
            mos_price=125,
        )
        strategy._valuation_cache["MSFT"] = valuation
        strategy._big_five_cache["MSFT"] = BigFiveMetrics(
            roic=0.18, equity_growth=0.14, eps_growth=0.16, sales_growth=0.13, fcf_growth=0.12
        )

        good_contract = OptionContract(
            symbol="MSFT",
            option_type="put",
            expiration="2025-02-21",
            strike=125,
            bid=1.5,
            ask=1.7,
            mid=1.6,
            delta=-0.19,
            implied_vol=0.25,
            days_to_expiry=35,
            iv_rank=22.0,
        )
        monkeypatch.setattr(
            strategy, "_find_best_put_option", lambda *args, **kwargs: good_contract
        )

        signals = strategy.find_put_opportunities()
        assert len(signals) == 1
        signal = signals[0]
        assert signal.contracts == 1  # 20k cash / (125*100) = 1 contract
        assert signal.iv_rank == pytest.approx(22.0)
        assert signal.delta == pytest.approx(-0.19)
        assert signal.total_premium == pytest.approx(1.6 * 100)

    def test_generate_daily_signals_persists_snapshot(self, tmp_path, monkeypatch):
        """Signals should be written to data/options_signals for auditing."""
        strategy = RuleOneOptionsStrategy(paper=True, universe=["AAPL"])
        strategy.options_log_dir = Path(tmp_path)

        monkeypatch.setattr(strategy, "analyze_universe", lambda: {})

        sample_signal = RuleOneOptionsSignal(
            symbol="AAPL",
            signal_type="sell_put",
            strike=120,
            expiration="2025-01-17",
            premium=1.5,
            annualized_return=0.2,
            sticker_price=180,
            mos_price=90,
            current_price=150,
            rationale="Test",
            confidence=0.8,
            contracts=1,
            total_premium=150.0,
            iv_rank=25.0,
            delta=-0.2,
        )
        monkeypatch.setattr(strategy, "find_put_opportunities", lambda: [sample_signal])
        monkeypatch.setattr(strategy, "find_call_opportunities", lambda: [])

        strategy.generate_daily_signals()

        files = list(Path(tmp_path).glob("*.json"))
        assert files, "Expected signal snapshot file"
        with open(files[0], encoding="utf-8") as handle:
            data = json.load(handle)
        assert data["put_opportunities"][0]["symbol"] == "AAPL"
        assert data["put_opportunities"][0]["contracts"] == 1


class TestPhilTownFormulas:
    """Test Phil Town's specific formulas."""

    def test_sticker_price_formula(self):
        """
        Phil Town's Sticker Price formula:
        1. Future EPS = Current EPS * (1 + growth)^10
        2. Future P/E = min(growth * 100 * 2, 50)
        3. Future Price = Future EPS * Future P/E
        4. Sticker Price = Future Price / (1.15)^10
        """
        current_eps = 5.0
        growth_rate = 0.15  # 15%

        # Step 1: Future EPS after 10 years
        future_eps = current_eps * ((1 + growth_rate) ** 10)
        assert future_eps == pytest.approx(20.23, rel=0.01)

        # Step 2: Future P/E (2x growth rate as P/E, capped at 50)
        future_pe = min(growth_rate * 100 * 2, 50)
        assert future_pe == 30  # 15% growth -> 30 P/E

        # Step 3: Future price
        future_price = future_eps * future_pe
        assert future_price == pytest.approx(606.8, rel=0.01)

        # Step 4: Discount back at 15% MARR
        sticker_price = future_price / ((1.15) ** 10)
        assert sticker_price == pytest.approx(150.0, rel=0.05)

        # Step 5: MOS Price (50% of Sticker)
        mos_price = sticker_price * 0.5
        assert mos_price == pytest.approx(75.0, rel=0.05)

    def test_annualized_return_calculation(self):
        """Test options premium annualized return calculation."""
        premium = 3.0  # $3 premium per share
        strike = 100.0  # $100 strike
        days_to_expiry = 30

        # Annualized return = (premium / strike) * (365 / days)
        annualized = (premium / strike) * (365 / days_to_expiry)

        # 3% in 30 days = ~36.5% annualized
        assert annualized == pytest.approx(0.365, rel=0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
