import pytest

from src.adapters.equity_broker_adapter import AlpacaEquityBrokerAdapter, PaperEquityBrokerAdapter


class TestPaperEquityBrokerAdapter:
    def test_buy_records_position(self):
        broker = PaperEquityBrokerAdapter()
        result = broker.buy("SCHD", 100.0)
        assert result.success is True
        assert broker._positions["SCHD"] == 100.0

    def test_buy_accumulates_across_calls(self):
        broker = PaperEquityBrokerAdapter()
        broker.buy("SCHD", 100.0)
        broker.buy("SCHD", 50.0)
        assert broker._positions["SCHD"] == 150.0

    def test_buy_rejects_non_positive_notional(self):
        broker = PaperEquityBrokerAdapter()
        result = broker.buy("SCHD", 0.0)
        assert result.success is False
        assert "positive" in result.error
        assert "SCHD" not in broker._positions

    def test_collect_dividend_income_zero_with_no_accrual(self):
        broker = PaperEquityBrokerAdapter()
        income = broker.collect_dividend_income()
        assert income.total_usd == 0.0

    def test_accrue_dividends_scales_with_position_and_days(self):
        broker = PaperEquityBrokerAdapter(annual_dividend_yield_pct=3.65)  # 0.01/day for easy math
        broker.buy("SCHD", 10_000.0)
        broker.accrue_dividends_for_days(1)
        income = broker.collect_dividend_income()
        assert income.total_usd == pytest.approx(1.0, abs=0.01)

    def test_collect_dividend_income_resets_accrual(self):
        broker = PaperEquityBrokerAdapter()
        broker.buy("SCHD", 10_000.0)
        broker.accrue_dividends_for_days(10)
        first = broker.collect_dividend_income()
        second = broker.collect_dividend_income()
        assert first.total_usd > 0
        assert second.total_usd == 0.0

    def test_accrue_with_no_positions_yields_zero(self):
        broker = PaperEquityBrokerAdapter()
        broker.accrue_dividends_for_days(365)
        assert broker.collect_dividend_income().total_usd == 0.0


class TestAlpacaEquityBrokerAdapterSafety:
    def test_refuses_construction_without_credentials(self):
        with pytest.raises(ValueError, match="dedicated API credentials"):
            AlpacaEquityBrokerAdapter(api_key="", secret_key="", _live_enabled=True)

    def test_refuses_construction_without_live_flag(self):
        with pytest.raises(RuntimeError, match="DIVIDEND_GROWTH_ALPACA_ENABLED"):
            AlpacaEquityBrokerAdapter(api_key="k", secret_key="s", _live_enabled=False)

    def test_from_env_requires_both_credentials(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DIVIDEND_GROWTH_ALPACA_API_KEY", raising=False)
        monkeypatch.delenv("DIVIDEND_GROWTH_ALPACA_API_SECRET", raising=False)
        # Point the vault fallback at a missing file so a developer's real
        # ~/.resume_secrets/alpaca.json cannot satisfy from_env in this test.
        monkeypatch.setenv("ALPACA_SECRETS_PATH", str(tmp_path / "missing.json"))
        with pytest.raises(ValueError, match="DIVIDEND_GROWTH_ALPACA_API_KEY"):
            AlpacaEquityBrokerAdapter.from_env()

    def test_from_env_defaults_disabled(self, monkeypatch):
        monkeypatch.setenv("DIVIDEND_GROWTH_ALPACA_API_KEY", "k")
        monkeypatch.setenv("DIVIDEND_GROWTH_ALPACA_API_SECRET", "s")
        monkeypatch.delenv("DIVIDEND_GROWTH_ALPACA_ENABLED", raising=False)
        with pytest.raises(RuntimeError, match="DIVIDEND_GROWTH_ALPACA_ENABLED"):
            AlpacaEquityBrokerAdapter.from_env()

    def test_collect_dividend_income_sums_dividend_activities(self, monkeypatch):
        import requests

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return [{"net_amount": "1.25"}, {"net_amount": 2.75}, "not-a-dict"]

        monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse())
        adapter = AlpacaEquityBrokerAdapter(api_key="k", secret_key="s", _live_enabled=True)
        income = adapter.collect_dividend_income()
        assert income.total_usd == 4.0

    def test_collect_dividend_income_fails_closed_to_zero(self, monkeypatch):
        import requests

        def raise_error(*a, **k):
            raise requests.exceptions.ConnectionError("no network in tests")

        monkeypatch.setattr(requests, "get", raise_error)
        adapter = AlpacaEquityBrokerAdapter(api_key="k", secret_key="s", _live_enabled=True)
        income = adapter.collect_dividend_income()
        assert income.total_usd == 0.0
