import pytest

from src.adapters.equity_broker_adapter import (
    AlpacaEquityBrokerAdapter,
    PaperEquityBrokerAdapter,
)


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

    def test_buy_result_has_fill_fields(self):
        broker = PaperEquityBrokerAdapter()
        result = broker.buy("SCHD", 100.0)
        assert result.filled_qty is None  # paper doesn't track fills
        assert result.filled_avg_price is None
        assert result.order_id is None

    def test_collect_dividend_income_zero_with_no_accrual(self):
        broker = PaperEquityBrokerAdapter()
        income = broker.collect_dividend_income()
        assert income.total_usd == 0.0

    def test_collect_dividend_income_has_details(self):
        broker = PaperEquityBrokerAdapter()
        income = broker.collect_dividend_income()
        assert income.details == ()

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

    def test_from_env_requires_both_credentials(self, monkeypatch):
        monkeypatch.delenv("DIVIDEND_GROWTH_ALPACA_API_KEY", raising=False)
        monkeypatch.delenv("DIVIDEND_GROWTH_ALPACA_API_SECRET", raising=False)
        with pytest.raises(ValueError, match="DIVIDEND_GROWTH_ALPACA_API_KEY"):
            AlpacaEquityBrokerAdapter.from_env()

    def test_from_env_defaults_disabled(self, monkeypatch):
        monkeypatch.setenv("DIVIDEND_GROWTH_ALPACA_API_KEY", "k")
        monkeypatch.setenv("DIVIDEND_GROWTH_ALPACA_API_SECRET", "s")
        monkeypatch.delenv("DIVIDEND_GROWTH_ALPACA_ENABLED", raising=False)
        with pytest.raises(RuntimeError, match="DIVIDEND_GROWTH_ALPACA_ENABLED"):
            AlpacaEquityBrokerAdapter.from_env()

    def test_from_env_reads_paper_flag(self, monkeypatch):
        monkeypatch.setenv("DIVIDEND_GROWTH_ALPACA_API_KEY", "k")
        monkeypatch.setenv("DIVIDEND_GROWTH_ALPACA_API_SECRET", "s")
        monkeypatch.setenv("DIVIDEND_GROWTH_ALPACA_ENABLED", "1")
        monkeypatch.setenv("DIVIDEND_GROWTH_ALPACA_PAPER", "1")
        adapter = AlpacaEquityBrokerAdapter.from_env()
        assert adapter.paper is True

    def test_from_env_paper_defaults_false(self, monkeypatch):
        monkeypatch.setenv("DIVIDEND_GROWTH_ALPACA_API_KEY", "k")
        monkeypatch.setenv("DIVIDEND_GROWTH_ALPACA_API_SECRET", "s")
        monkeypatch.setenv("DIVIDEND_GROWTH_ALPACA_ENABLED", "1")
        monkeypatch.delenv("DIVIDEND_GROWTH_ALPACA_PAPER", raising=False)
        adapter = AlpacaEquityBrokerAdapter.from_env()
        assert adapter.paper is False

    def test_buy_rejects_non_positive_notional(self):
        adapter = AlpacaEquityBrokerAdapter(api_key="k", secret_key="s", _live_enabled=True)
        result = adapter.buy("SCHD", 0.0)
        assert result.success is False
        assert "positive" in result.error

    def test_buy_handles_api_error(self, monkeypatch):
        adapter = AlpacaEquityBrokerAdapter(api_key="k", secret_key="s", _live_enabled=True)

        class FakeClient:
            def submit_order(self, request):
                raise ConnectionError("simulated API failure")

        monkeypatch.setattr(adapter, "_get_client", lambda: FakeClient())
        result = adapter.buy("SCHD", 100.0)
        assert result.success is False
        assert "simulated API failure" in result.error


class TestAlpacaCollectDividendIncome:
    """Test collect_dividend_income() against a fake Alpaca client."""

    def _make_adapter(self, monkeypatch, activities):
        adapter = AlpacaEquityBrokerAdapter(api_key="k", secret_key="s", _live_enabled=True)

        class FakeClient:
            def get(self, path, data=None, **kwargs):
                assert path == "/account/activities"
                assert data.get("activity_type") == "DIV"
                return activities

        monkeypatch.setattr(adapter, "_get_client", lambda: FakeClient())
        return adapter

    def test_returns_zero_when_no_activities(self, monkeypatch):
        adapter = self._make_adapter(monkeypatch, [])
        income = adapter.collect_dividend_income()
        assert income.total_usd == 0.0
        assert income.details == ()

    def test_counts_cdiv_executed_only(self, monkeypatch):
        activities = [
            {
                "id": "div1",
                "activity_type": "DIV",
                "activity_sub_type": "CDIV",
                "symbol": "SCHD",
                "net_amount": "12.50",
                "per_share_amount": "0.125",
                "qty": "100",
                "date": "2026-07-15",
                "created_at": "2026-07-15T10:00:00+00:00",
                "status": "executed",
            },
            # SDIV (stock dividend) — should be skipped
            {
                "id": "div2",
                "activity_type": "DIV",
                "activity_sub_type": "SDIV",
                "symbol": "SCHD",
                "net_amount": "5.00",
                "status": "executed",
                "created_at": "2026-07-16T10:00:00+00:00",
            },
            # CDIV but not executed — should be skipped
            {
                "id": "div3",
                "activity_type": "DIV",
                "activity_sub_type": "CDIV",
                "symbol": "SCHD",
                "net_amount": "3.00",
                "status": "canceled",
                "created_at": "2026-07-17T10:00:00+00:00",
            },
        ]
        adapter = self._make_adapter(monkeypatch, activities)
        income = adapter.collect_dividend_income()
        assert income.total_usd == 12.50
        assert len(income.details) == 1
        assert income.details[0].symbol == "SCHD"
        assert income.details[0].net_amount_usd == 12.50
        assert income.details[0].per_share_amount == 0.125
        assert income.details[0].qty == 100

    def test_does_not_double_count_on_second_call(self, monkeypatch):
        activities = [
            {
                "id": "div1",
                "activity_type": "DIV",
                "activity_sub_type": "CDIV",
                "symbol": "SCHD",
                "net_amount": "10.00",
                "status": "executed",
                "created_at": "2026-07-15T10:00:00+00:00",
            },
        ]
        adapter = self._make_adapter(monkeypatch, activities)
        first = adapter.collect_dividend_income()
        assert first.total_usd == 10.00
        # Second call: the activity's created_at is now <= _last_checked_at
        second = adapter.collect_dividend_income()
        assert second.total_usd == 0.0
        assert second.details == ()

    def test_handles_api_error_gracefully(self, monkeypatch):
        adapter = AlpacaEquityBrokerAdapter(api_key="k", secret_key="s", _live_enabled=True)

        class FakeClient:
            def get(self, path, data=None, **kwargs):
                raise ConnectionError("API down")

        monkeypatch.setattr(adapter, "_get_client", lambda: FakeClient())
        income = adapter.collect_dividend_income()
        assert income.total_usd == 0.0
        assert income.details == ()

    def test_handles_non_numeric_net_amount(self, monkeypatch):
        activities = [
            {
                "id": "div1",
                "activity_type": "DIV",
                "activity_sub_type": "CDIV",
                "symbol": "SCHD",
                "net_amount": "not_a_number",
                "status": "executed",
                "created_at": "2026-07-15T10:00:00+00:00",
            },
            {
                "id": "div2",
                "activity_type": "DIV",
                "activity_sub_type": "CDIV",
                "symbol": "SCHD",
                "net_amount": "7.50",
                "status": "executed",
                "created_at": "2026-07-16T10:00:00+00:00",
            },
        ]
        adapter = self._make_adapter(monkeypatch, activities)
        income = adapter.collect_dividend_income()
        assert income.total_usd == 7.50
        assert len(income.details) == 1

    def test_handles_non_list_response(self, monkeypatch):
        adapter = AlpacaEquityBrokerAdapter(api_key="k", secret_key="s", _live_enabled=True)

        class FakeClient:
            def get(self, path, data=None, **kwargs):
                return {"unexpected": "dict"}

        monkeypatch.setattr(adapter, "_get_client", lambda: FakeClient())
        income = adapter.collect_dividend_income()
        assert income.total_usd == 0.0
