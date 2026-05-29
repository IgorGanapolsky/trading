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
                  closed: int = 0, unpaired_orders: int = 0,
                  trades: list | None = None) -> None:
    """Write a synthetic trades.json.

    If ``trades`` is supplied it is written verbatim and stats.total_pnl is
    treated as the sum of those trades' realized_pnl (caller's responsibility).
    If ``trades`` is None we synthesize a single closed trade with
    realized_pnl == total_pnl and exit_time inside the broker window used by
    the existing scenarios (2026-05-20..2026-05-29).
    """
    stats: dict = {
        "total_pnl": total_pnl,
        "closed_trades": closed,
        "unpaired_order_count": unpaired_orders,
    }
    if unpaired is not None:
        stats["unpaired_realized_pnl"] = unpaired
    if trades is None:
        trades = []
        if closed > 0:
            trades = [{
                "id": f"synth_{i}",
                "status": "closed",
                "entry_time": "2026-05-21 12:00:00+00:00",
                "exit_time": "2026-05-28 12:00:00+00:00",
                "realized_pnl": (total_pnl / closed) if closed else 0.0,
            } for i in range(closed)]
    path.write_text(json.dumps({"stats": stats, "trades": trades}))


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

    # Stamp every fill with a timestamp so the window-extraction code path
    # is also covered by this scenario.
    for i, row in enumerate(fills):
        row.setdefault("filled_at", f"2026-04-{1 + (i % 28):02d} 15:00:00+00:00")

    broker_realized, closed_count, win_start, win_end = recon_mod.compute_broker_realized(
        {"trade_history": fills}
    )

    # Closed sum = $200 + $400 + $200 = $800
    assert broker_realized == 800.0
    # 3 closed leg-groups; the 2 open ones contribute $0
    assert closed_count == 3
    # Window spans only the closed-group timestamps (open-group fills are
    # excluded — even though we still appended their timestamps to their own
    # group buckets, those groups never got selected as "closed").
    assert win_start is not None and win_end is not None
    assert win_start <= win_end


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


def _mleg_fills(legs: list[str], open_price: float, close_price: float,
                open_ts: str, close_ts: str, qty: int = 1) -> list[dict]:
    return [
        {"id": "open", "symbol": None, "side": "None", "qty": str(qty),
         "price": f"{open_price:.2f}", "filled_at": open_ts,
         "status": "OrderStatus.FILLED", "order_class": "OrderClass.MLEG",
         "legs": legs},
        {"id": "close", "symbol": None, "side": "None", "qty": str(qty),
         "price": f"{close_price:.2f}", "filled_at": close_ts,
         "status": "OrderStatus.FILLED", "order_class": "OrderClass.MLEG",
         "legs": legs},
    ]


def test_paired_window_clip_excludes_out_of_window(tmp_path: Path, recon_mod,
                                                    monkeypatch):
    """Paired ledger has 5 closed trades: 2 outside broker window, 3 inside.
    Only the 3 inside count toward delta. broker_realized is +$200, the 3 in
    window paired trades sum to +$210 (delta -$10 < $150)."""
    state = tmp_path / "system_state.json"
    trades_path = tmp_path / "trades.json"
    reports = tmp_path / "reports"

    # Broker: one closed MLEG, +$3 credit -> -$1 debit = +$200, window
    # 2026-05-20..2026-05-29. (Close-side price must be NEGATIVE so the
    # MLEG signed_qty convention nets to zero.)
    fills = _mleg_fills(
        legs=["A", "B", "C", "D"],
        open_price=3.0,
        close_price=-1.0,
        open_ts="2026-05-20 19:00:00+00:00",
        close_ts="2026-05-29 19:00:00+00:00",
    )
    _write_state(state, fills)

    # Paired: 3 inside (sum +$210), 2 outside (sum +$5000 — must be ignored).
    paired_trades = [
        {"id": "in1", "status": "closed", "entry_time": "2026-05-21T10:00:00+00:00",
         "exit_time": "2026-05-22T10:00:00+00:00", "realized_pnl": 70.0},
        {"id": "in2", "status": "closed", "entry_time": "2026-05-23T10:00:00+00:00",
         "exit_time": "2026-05-24T10:00:00+00:00", "realized_pnl": 70.0},
        {"id": "in3", "status": "closed", "entry_time": "2026-05-25T10:00:00+00:00",
         "exit_time": "2026-05-26T10:00:00+00:00", "realized_pnl": 70.0},
        {"id": "out_before", "status": "closed", "entry_time": "2026-01-10T10:00:00+00:00",
         "exit_time": "2026-01-20T10:00:00+00:00", "realized_pnl": 2500.0},
        {"id": "out_after", "status": "closed", "entry_time": "2026-06-10T10:00:00+00:00",
         "exit_time": "2026-06-20T10:00:00+00:00", "realized_pnl": 2500.0},
    ]
    # stats.total_pnl is the FULL-history paired number (pre-clip). We must
    # demonstrate the clip ignores it in favor of per-trade exit-time filter.
    trades_path.write_text(json.dumps({
        "stats": {"total_pnl": 5210.0, "closed_trades": 5,
                  "unpaired_realized_pnl": 0.0, "unpaired_order_count": 0},
        "trades": paired_trades,
    }))

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    code = recon_mod.main([
        "--system-state", str(state),
        "--trades", str(trades_path),
        "--report-dir", str(reports),
        "--date", "2026-05-29",
    ])
    assert code == 0  # delta = 200 - 210 = -10, within threshold

    report = json.loads((reports / "reconciliation_2026-05-29.json").read_text())
    assert report["broker_realized_pnl"] == 200.0
    assert report["paired_realized_in_window"] == 210.0
    assert report["paired_realized_outside_window"] == 5000.0
    assert report["paired_trade_count_in_window"] == 3
    assert report["paired_trade_count_outside_window"] == 2
    assert report["delta_dollars"] == -10.0
    assert report["alert_fired"] is False
    assert report["window_clipped"] is True
    assert report["window_start"] is not None
    assert report["window_end"] is not None


def test_paired_entirely_outside_window(tmp_path: Path, recon_mod, monkeypatch):
    """All paired trades exit before broker window opens. paired_in_window=0,
    delta = broker_realized alone. Broker +$500 > $150 -> alert fires."""
    state = tmp_path / "system_state.json"
    trades_path = tmp_path / "trades.json"
    reports = tmp_path / "reports"

    # Broker: +$500 net realized inside the window. Close price negative
    # so MLEG net_qty hits zero (the IC is fully unwound).
    fills = _mleg_fills(
        legs=["W", "X", "Y", "Z"],
        open_price=6.0,
        close_price=-1.0,
        open_ts="2026-05-20 18:00:00+00:00",
        close_ts="2026-05-29 18:00:00+00:00",
    )
    _write_state(state, fills)

    # Every paired trade exited BEFORE the broker window opened.
    paired_trades = [
        {"id": f"old{i}", "status": "closed",
         "entry_time": "2026-01-05T10:00:00+00:00",
         "exit_time": "2026-01-15T10:00:00+00:00",
         "realized_pnl": 100.0}
        for i in range(4)
    ]
    trades_path.write_text(json.dumps({
        "stats": {"total_pnl": 400.0, "closed_trades": 4,
                  "unpaired_realized_pnl": 0.0, "unpaired_order_count": 0},
        "trades": paired_trades,
    }))

    monkeypatch.delenv("SENTRY_DSN", raising=False)
    code = recon_mod.main([
        "--system-state", str(state),
        "--trades", str(trades_path),
        "--report-dir", str(reports),
        "--date", "2026-05-29",
    ])
    # broker $500, paired_in $0 -> delta $500 > $150 -> alert -> exit 2.
    assert code == 2

    report = json.loads((reports / "reconciliation_2026-05-29.json").read_text())
    assert report["broker_realized_pnl"] == 500.0
    assert report["paired_realized_in_window"] == 0.0
    assert report["paired_trade_count_in_window"] == 0
    assert report["paired_realized_outside_window"] == 400.0
    assert report["paired_trade_count_outside_window"] == 4
    assert report["delta_dollars"] == 500.0
    assert report["alert_fired"] is True
