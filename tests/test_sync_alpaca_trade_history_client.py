from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import sync_alpaca_state


class _GetOrdersRequest:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _install_fake_alpaca_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    alpaca_mod = types.ModuleType("alpaca")
    trading_mod = types.ModuleType("alpaca.trading")
    enums_mod = types.ModuleType("alpaca.trading.enums")
    requests_mod = types.ModuleType("alpaca.trading.requests")

    enums_mod.QueryOrderStatus = SimpleNamespace(CLOSED="closed")
    requests_mod.GetOrdersRequest = _GetOrdersRequest

    monkeypatch.setitem(sys.modules, "alpaca", alpaca_mod)
    monkeypatch.setitem(sys.modules, "alpaca.trading", trading_mod)
    monkeypatch.setitem(sys.modules, "alpaca.trading.enums", enums_mod)
    monkeypatch.setitem(sys.modules, "alpaca.trading.requests", requests_mod)


@pytest.fixture
def fake_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.utils.alpaca_client.get_alpaca_credentials",
        lambda: ("paper_key", "paper_secret"),
    )


@pytest.fixture
def no_live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPACA_BROKERAGE_TRADING_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_BROKERAGE_TRADING_API_SECRET", raising=False)


def test_sync_from_alpaca_uses_trader_wrapped_trading_client(
    monkeypatch: pytest.MonkeyPatch,
    fake_credentials: None,
    no_live_env: None,
) -> None:
    _install_fake_alpaca_imports(monkeypatch)

    order = SimpleNamespace(
        id="ord-1",
        symbol="SPY",
        side="buy",
        filled_qty="1",
        filled_avg_price="500.10",
        filled_at="2026-03-05T14:00:00Z",
        status="filled",
        order_class="simple",
        legs=[],
    )

    class _OrdersClient:
        def get_orders(self, filter):  # noqa: A002 - follows alpaca signature
            return [order]

    class _TraderWrapper:
        def __init__(self) -> None:
            self.trading_client = _OrdersClient()

    class _Executor:
        def __init__(self, paper=True, allow_simulator=False):  # noqa: ARG002
            self.trader = _TraderWrapper()
            self.account_snapshot = {"cash": 1000.0, "buying_power": 2000.0, "last_equity": 950.0}
            self.account_equity = 1000.0

        def sync_portfolio_state(self) -> None:
            return None

        def get_positions(self):
            return []

    fake_executor_mod = types.ModuleType("src.execution.alpaca_executor")
    fake_executor_mod.AlpacaExecutor = _Executor
    monkeypatch.setitem(sys.modules, "src.execution.alpaca_executor", fake_executor_mod)

    result = sync_alpaca_state.sync_from_alpaca()

    assert result is not None
    paper = result["paper"]
    assert paper["trades_loaded"] == 1
    assert paper["trade_history"][0]["symbol"] == "SPY"


def test_sync_from_alpaca_falls_back_to_get_alpaca_client_for_orders(
    monkeypatch: pytest.MonkeyPatch,
    fake_credentials: None,
    no_live_env: None,
) -> None:
    _install_fake_alpaca_imports(monkeypatch)

    order = SimpleNamespace(
        id="ord-2",
        symbol="AAPL",
        side="sell",
        filled_qty="2",
        filled_avg_price="220.00",
        filled_at="2026-03-05T15:00:00Z",
        status="filled",
        order_class="simple",
        legs=[],
    )

    class _FallbackOrdersClient:
        def get_orders(self, filter):  # noqa: A002 - follows alpaca signature
            return [order]

    class _ExecutorNoTrader:
        def __init__(self, paper=True, allow_simulator=False):  # noqa: ARG002
            self.trader = None
            self.account_snapshot = {"cash": 3000.0, "buying_power": 4000.0, "last_equity": 3050.0}
            self.account_equity = 3000.0

        def sync_portfolio_state(self) -> None:
            return None

        def get_positions(self):
            return []

    fake_executor_mod = types.ModuleType("src.execution.alpaca_executor")
    fake_executor_mod.AlpacaExecutor = _ExecutorNoTrader
    monkeypatch.setitem(sys.modules, "src.execution.alpaca_executor", fake_executor_mod)

    monkeypatch.setattr(
        "src.utils.alpaca_client.get_alpaca_client",
        lambda paper=True: _FallbackOrdersClient(),
    )

    result = sync_alpaca_state.sync_from_alpaca()

    assert result is not None
    paper = result["paper"]
    assert paper["trades_loaded"] == 1
    assert paper["trade_history"][0]["symbol"] == "AAPL"
