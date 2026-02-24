from types import SimpleNamespace

from src.safety import position_enforcer


class FakeTrader:
    def __init__(self, symbols):
        self._positions = [SimpleNamespace(symbol=s) for s in symbols]

    def get_all_positions(self):
        return self._positions


def test_enforce_positions_uses_safe_close_wrapper(monkeypatch):
    calls = []

    def fake_safe_close_position(trader, symbol, **kwargs):
        calls.append((symbol, kwargs))

    monkeypatch.setattr(position_enforcer, "safe_close_position", fake_safe_close_position)

    trader = FakeTrader(["AAPL260320C00150000"])
    result = position_enforcer.enforce_positions(trader)

    assert result.violations_found == 1
    assert result.positions_closed == 1
    assert result.closed_symbols == ["AAPL260320C00150000"]
    assert calls == [("AAPL260320C00150000", {})]


def test_enforce_positions_keeps_allowed_underlyings_open(monkeypatch):
    calls = []

    def fake_safe_close_position(trader, symbol, **kwargs):
        calls.append((symbol, kwargs))

    monkeypatch.setattr(position_enforcer, "safe_close_position", fake_safe_close_position)

    trader = FakeTrader(["SPY260320C00500000"])
    result = position_enforcer.enforce_positions(trader)

    assert result.violations_found == 0
    assert result.positions_closed == 0
    assert result.closed_symbols == []
    assert calls == []
