import importlib
import json
import sys
import types
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest


class DummyTrader:
    def __init__(self):
        self.orders = []

    def execute_order(self, symbol, amount_usd, side, tier):
        order_id = f"{symbol}-{len(self.orders)}"
        self.orders.append(
            {"symbol": symbol, "amount_usd": amount_usd, "side": side, "id": order_id}
        )
        return {"id": order_id, "filled_qty": amount_usd}

    def set_stop_loss(self, *args, **kwargs):
        return None

    def get_positions(self):
        return []

    def sync_portfolio_state(self):
        return None

    def get_historical_bars(self, *args, **kwargs):
        return []

    def get_historical_data(self, *args, **kwargs):
        return None


class DummyGuardrails:
    def __init__(self, symbols):
        self.symbols = symbols

    def summary(self):
        return {}

    def is_market_blocked(self):
        return False, None

    def is_symbol_blocked(self, symbol):
        return False, None


class BlockedGuardrails(DummyGuardrails):
    def is_market_blocked(self):
        return True, "FOMC"


def _mock_history() -> pd.DataFrame:
    idx = pd.date_range(end=pd.Timestamp.today(), periods=200, freq="B")
    import numpy as np

    rng = np.random.default_rng(42)
    changes = rng.normal(0, 0.3, len(idx))
    values = 100 + np.cumsum(changes)
    base = pd.Series(values, index=idx, dtype=float)
    data = pd.DataFrame(
        {
            "Open": base + 0.2,
            "High": base + 0.5,
            "Low": base - 0.5,
            "Close": base,
            "Volume": 1_000_000,
        }
    )
    return data


@pytest.fixture(autouse=True)
def disable_rl(monkeypatch):
    monkeypatch.setenv("ENABLE_RL_POLICY", "false")


def load_core(monkeypatch, guardrails_cls):
    install_alpaca_stubs(monkeypatch)
    module = importlib.import_module("src.strategies.core_strategy")
    module = importlib.reload(module)
    monkeypatch.setattr(module, "EconomicGuardrails", guardrails_cls)
    return module


def install_alpaca_stubs(monkeypatch):
    dummy_apierror = type("APIError", (Exception,), {})

    alpaca_mod = types.ModuleType("alpaca")
    trading_mod = types.ModuleType("alpaca.trading")
    client_mod = types.ModuleType("alpaca.trading.client")
    requests_mod = types.ModuleType("alpaca.trading.requests")
    enums_mod = types.ModuleType("alpaca.trading.enums")
    data_mod = types.ModuleType("alpaca.data")
    historical_mod = types.ModuleType("alpaca.data.historical")
    data_requests_mod = types.ModuleType("alpaca.data.requests")
    timeframe_mod = types.ModuleType("alpaca.data.timeframe")
    common_mod = types.ModuleType("alpaca.common")
    exceptions_mod = types.ModuleType("alpaca.common.exceptions")

    client_mod.TradingClient = object
    requests_mod.MarketOrderRequest = object
    requests_mod.LimitOrderRequest = object
    requests_mod.StopOrderRequest = object
    requests_mod.GetOrdersRequest = object
    enums_mod.OrderSide = type("OrderSide", (), {"BUY": "buy", "SELL": "sell"})
    enums_mod.TimeInForce = type("TimeInForce", (), {"DAY": "day"})
    enums_mod.OrderClass = type("OrderClass", (), {"BASIC": "basic"})
    enums_mod.OrderStatus = type("OrderStatus", (), {"FILLED": "filled"})
    historical_mod.StockHistoricalDataClient = object
    data_requests_mod.StockBarsRequest = object
    timeframe_mod.TimeFrame = type("TimeFrame", (), {"Day": "1Day"})
    exceptions_mod.APIError = dummy_apierror

    monkeypatch.setitem(sys.modules, "alpaca", alpaca_mod)
    monkeypatch.setitem(sys.modules, "alpaca.trading", trading_mod)
    monkeypatch.setitem(sys.modules, "alpaca.trading.client", client_mod)
    monkeypatch.setitem(sys.modules, "alpaca.trading.requests", requests_mod)
    monkeypatch.setitem(sys.modules, "alpaca.trading.enums", enums_mod)
    monkeypatch.setitem(sys.modules, "alpaca.data", data_mod)
    monkeypatch.setitem(sys.modules, "alpaca.data.historical", historical_mod)
    monkeypatch.setitem(sys.modules, "alpaca.data.requests", data_requests_mod)
    monkeypatch.setitem(sys.modules, "alpaca.data.timeframe", timeframe_mod)
    monkeypatch.setitem(sys.modules, "alpaca.common", common_mod)
    monkeypatch.setitem(sys.modules, "alpaca.common.exceptions", exceptions_mod)


def test_core_strategy_executes_with_mocked_deps(monkeypatch, tmp_path):
    hist = _mock_history()
    core_strategy = load_core(monkeypatch, DummyGuardrails)

    monkeypatch.setattr(
        core_strategy.yf,
        "Ticker",
        lambda symbol: type("T", (), {"history": lambda self, *_, **__: hist.copy()})(),
    )
    monkeypatch.setattr(
        core_strategy,
        "load_latest_sentiment",
        lambda: {
            "meta": {"freshness": "fresh", "days_old": 0},
            "sentiment_by_ticker": {
                "SPY": {"score": 60, "confidence": "high", "market_regime": "risk_on"}
            },
        },
    )
    monkeypatch.setattr(core_strategy, "EconomicGuardrails", DummyGuardrails)

    strategy = core_strategy.CoreStrategy(daily_allocation=20.0, use_sentiment=False)
    strategy.alpaca_trader = DummyTrader()
    strategy.gemini3_enabled = False
    strategy._gemini3_integration = None
    strategy.langchain_guard_enabled = False

    dummy_scores = [
        core_strategy.MomentumScore(
            symbol="SPY",
            score=80.0,
            returns_1m=0.02,
            returns_3m=0.03,
            returns_6m=0.05,
            volatility=0.1,
            sharpe_ratio=1.2,
            rsi=55.0,
            macd_value=0.1,
            macd_signal=0.05,
            macd_histogram=0.02,
            volume_ratio=1.1,
            sentiment_boost=0.0,
            timestamp=datetime.now(),
        ),
        core_strategy.MomentumScore(
            symbol="QQQ",
            score=70.0,
            returns_1m=0.01,
            returns_3m=0.02,
            returns_6m=0.03,
            volatility=0.1,
            sharpe_ratio=1.0,
            rsi=53.0,
            macd_value=0.08,
            macd_signal=0.04,
            macd_histogram=0.015,
            volume_ratio=1.0,
            sentiment_boost=0.0,
            timestamp=datetime.now(),
        ),
    ]

    monkeypatch.setattr(
        core_strategy.CoreStrategy,
        "_calculate_all_momentum_scores",
        lambda self, sentiment, relaxed_filters=False: dummy_scores,
    )

    def stub_snapshot(self, extra_symbols=None):
        symbols = ["SPY", "QQQ", "VOO", "BND", "VNQ", "TLT"]
        snapshot = {"generated_at": datetime.utcnow().isoformat(), "symbols": {}}
        metrics_map = {}
        for sym in symbols:
            metrics = core_strategy.TrendMetrics(
                symbol=sym,
                price=100.0,
                sma20=100.0,
                sma50=99.5,
                sma200=98.0,
                return_5d=0.5,
                return_21d=1.5,
                gate_open=True,
                regime_bias="uptrend",
            )
            metrics_map[sym] = metrics
            snapshot["symbols"][sym] = metrics.__dict__
        self._trend_snapshot = metrics_map
        path = Path("data/trend_snapshot.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(snapshot, fh)

    monkeypatch.setattr(core_strategy.CoreStrategy, "_update_trend_snapshot", stub_snapshot)

    order = strategy.execute_daily()

    assert order is not None
    assert strategy.alpaca_trader.orders, "order should have been submitted"

    snapshot_path = Path("data/trend_snapshot.json")
    assert snapshot_path.exists()
    with open(snapshot_path) as fh:
        snapshot = json.load(fh)
    assert snapshot.get("symbols")


def test_guardrails_block_trade(monkeypatch):
    core_strategy = load_core(monkeypatch, BlockedGuardrails)
    monkeypatch.setattr(
        core_strategy.yf,
        "Ticker",
        lambda symbol: type("T", (), {"history": lambda self, *_, **__: _mock_history()})(),
    )
    monkeypatch.setattr(
        core_strategy,
        "load_latest_sentiment",
        lambda: {
            "meta": {},
            "sentiment_by_ticker": {
                "SPY": {"score": 40, "confidence": "medium", "market_regime": "neutral"}
            },
        },
    )

    strategy = core_strategy.CoreStrategy(daily_allocation=20.0, use_sentiment=False)
    strategy.alpaca_trader = DummyTrader()

    assert strategy.execute_daily() is None
    assert not strategy.alpaca_trader.orders
