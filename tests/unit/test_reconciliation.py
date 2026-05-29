"""Tests for scripts/reconcile_broker_vs_paired.py.

Two scenarios per spec:
  1. Synthetic state where broker and paired reconcile within $50
     -> exit 0, no alert.
  2. Synthetic state with $300 delta -> exit 2, alert fired,
     report contents correct.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reconcile_broker_vs_paired.py"


@pytest.fixture(scope="module")
def recon_mod():
    spec = importlib.util.spec_from_file_location("reconcile_mod", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["reconcile_mod"] = module
    spec.loader.exec_module(module)
    return module


def _write_state(path: Path, fills: list[dict]) -> None:
    path.write_text(json.dumps({"trade_history": fills}))


def _write_trades(path: Path, total_pnl: float, unpaired: float | None,
                  closed: int = 0, unpaired_orders: int = 0) -> None:
    stats: dict = {
        "total_pnl": total_pnl,
        "closed_trades": closed,
        "unpaired_order_count": unpaired_orders,
    }
    if unpaired is not None:
        stats["unpaired_realized_pnl"] = unpaired
    path.write_text(json.dumps({"stats": stats, "trades": []}))


def test_within_threshold_exit_zero(tmp_path: Path, recon_mod, monkeypatch):
    """Closed IC: opened for +$1500 credit, closed for -$2500 debit.
    Net realized = -$1000. Paired ledger reports -$1030.
    Delta $30 < $150 -> no alert, exit 0."""
    state = tmp_path / "system_state.json"
    trades = tmp_path / "trades.json"
    reports = tmp_path / "reports"

    legs = ["A", "B", "C", "D"]
    fills = [
        # Open: sell-to-open IC for +$15.00 credit x 1 contract = +$1500
        {
            "id": "open",
            "symbol": None,
            "side": "None",
            "qty": "1",
            "price": "15.00",
            "filled_at": "2026-05-20 19:00:00+00:00",
            "status": "OrderStatus.FILLED",
            "order_class": "OrderClass.MLEG",
            "legs": legs,
        },
        # Close: buy-to-close same IC at -$25.00 debit x 1 contract = -$2500
        {
            "id": "close",
            "symbol": None,
            "side": "None",
            "qty": "1",
            "price": "-25.00",
            "filled_at": "2026-05-29 19:00:00+00:00",
            "status": "OrderStatus.FILLED",
            "order_class": "OrderClass.MLEG",
            "legs": legs,
        },
    ]
    _write_state(state, fills)
    _write_trades(trades, total_pnl=-1030.0, unpaired=0.0, closed=1)

    monkeypatch.delenv("SENTRY_DSN", raising=False)

    code = recon_mod.main([
        "--system-state", str(state),
        "--trades", str(trades),
        "--report-dir", str(reports),
        "--date", "2026-05-29",
    ])
    assert code == 0

    report = json.loads((reports / "reconciliation_2026-05-29.json").read_text())
    assert report["broker_realized_pnl"] == -1000.0
    assert report["paired_realized_pnl"] == -1030.0
    assert report["delta_dollars"] == 30.0
    assert report["alert_fired"] is False
    assert report["threshold_dollars"] == 150
    # broker_fill_count now counts CLOSED leg-groups, not raw fills
    assert report["broker_fill_count"] == 1
    assert report["paired_trade_count"] == 1


def test_breach_threshold_exit_two_alert_fired(tmp_path: Path, recon_mod,
                                                monkeypatch, caplog):
    """Closed single-leg short: SELL 1 @ $5.00 then BUY 1 @ $0.00 to close.
    Net realized = +$500. Paired reports +$200. Delta $300 > $150 -> alert."""
    state = tmp_path / "system_state.json"
    trades = tmp_path / "trades.json"
    reports = tmp_path / "reports"

    symbol = "SPY260618C00500000"
    fills = [
        {
            "id": "open",
            "symbol": symbol,
            "side": "OrderSide.SELL",
            "qty": "1",
            "price": "5.00",
            "filled_at": "2026-05-20 18:00:00+00:00",
            "status": "OrderStatus.FILLED",
            "order_class": "OrderClass.SIMPLE",
            "legs": [],
        },
        {
            "id": "close",
            "symbol": symbol,
            "side": "OrderSide.BUY",
            "qty": "1",
            "price": "0.00",
            "filled_at": "2026-05-29 18:00:00+00:00",
            "status": "OrderStatus.FILLED",
            "order_class": "OrderClass.SIMPLE",
            "legs": [],
        },
    ]
    _write_state(state, fills)
    _write_trades(trades, total_pnl=200.0, unpaired=0.0, closed=1)

    # No SENTRY_DSN -> CRITICAL log path, no crash.
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    caplog.set_level("CRITICAL")

    code = recon_mod.main([
        "--system-state", str(state),
        "--trades", str(trades),
        "--report-dir", str(reports),
        "--date", "2026-05-29",
    ])
    assert code == 2

    report = json.loads((reports / "reconciliation_2026-05-29.json").read_text())
    assert report["broker_realized_pnl"] == 500.0
    assert report["paired_realized_pnl"] == 200.0
    assert report["delta_dollars"] == 300.0
    assert report["alert_fired"] is True
    assert any("reconciliation breach" in rec.message.lower() for rec in caplog.records)


def test_open_positions_excluded_from_broker_realized(recon_mod):
    """Synthetic snapshot: 3 closed legs + 2 still-open legs. broker_realized
    must include only the 3 closed groups and exclude the 2 open ones.

    Bug being prevented: v1 summed every signed_cash including entry fills of
    still-open positions, producing a $50K+ phantom delta against the paired
    ledger (LL-354 reconciliation noise floor).
    """
    fills = []

    # Closed group 1: SIMPLE leg, SELL 1@$3 then BUY 1@$1 -> net +$200
    fills += [
        {"id": "c1o", "symbol": "S1", "side": "OrderSide.SELL", "qty": "1",
         "price": "3.00", "status": "OrderStatus.FILLED",
         "order_class": "OrderClass.SIMPLE", "legs": []},
        {"id": "c1c", "symbol": "S1", "side": "OrderSide.BUY", "qty": "1",
         "price": "1.00", "status": "OrderStatus.FILLED",
         "order_class": "OrderClass.SIMPLE", "legs": []},
    ]
    # Closed group 2: SIMPLE leg, SELL 2@$4 then BUY 2@$2 -> net +$400
    fills += [
        {"id": "c2o", "symbol": "S2", "side": "OrderSide.SELL", "qty": "2",
         "price": "4.00", "status": "OrderStatus.FILLED",
         "order_class": "OrderClass.SIMPLE", "legs": []},
        {"id": "c2c", "symbol": "S2", "side": "OrderSide.BUY", "qty": "2",
         "price": "2.00", "status": "OrderStatus.FILLED",
         "order_class": "OrderClass.SIMPLE", "legs": []},
    ]
    # Closed group 3: MLEG IC, open +$10 credit then close -$8 debit -> net +$200
    legs = ["L1", "L2", "L3", "L4"]
    fills += [
        {"id": "c3o", "symbol": None, "side": "None", "qty": "1",
         "price": "10.00", "status": "OrderStatus.FILLED",
         "order_class": "OrderClass.MLEG", "legs": legs},
        {"id": "c3c", "symbol": None, "side": "None", "qty": "1",
         "price": "-8.00", "status": "OrderStatus.FILLED",
         "order_class": "OrderClass.MLEG", "legs": legs},
    ]
    # Open group A: SIMPLE leg still short, SELL 5@$100 = +$50,000 entry cash
    fills += [
        {"id": "oA", "symbol": "OPEN1", "side": "OrderSide.SELL", "qty": "5",
         "price": "100.00", "status": "OrderStatus.FILLED",
         "order_class": "OrderClass.SIMPLE", "legs": []},
    ]
    # Open group B: MLEG IC still on, opened for +$20 credit x 10 = +$20,000
    fills += [
        {"id": "oB", "symbol": None, "side": "None", "qty": "10",
         "price": "20.00", "status": "OrderStatus.FILLED",
         "order_class": "OrderClass.MLEG",
         "legs": ["X1", "X2", "X3", "X4"]},
    ]

    broker_realized, closed_count = recon_mod.compute_broker_realized(
        {"trade_history": fills}
    )

    # Closed sum = $200 + $400 + $200 = $800
    assert broker_realized == 800.0
    # 3 closed leg-groups; the 2 open ones contribute $0
    assert closed_count == 3


def test_missing_unpaired_field_is_tolerated(tmp_path: Path, recon_mod, monkeypatch):
    """Older ledgers without stats.unpaired_realized_pnl must default to 0."""
    state = tmp_path / "system_state.json"
    trades = tmp_path / "trades.json"
    reports = tmp_path / "reports"

    _write_state(state, [])
    _write_trades(trades, total_pnl=0.0, unpaired=None, closed=0)

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    code = recon_mod.main([
        "--system-state", str(state),
        "--trades", str(trades),
        "--report-dir", str(reports),
        "--date", "2026-05-29",
    ])
    assert code == 0
    report = json.loads((reports / "reconciliation_2026-05-29.json").read_text())
    assert report["paired_realized_pnl"] == 0.0
    assert report["delta_dollars"] == 0.0
