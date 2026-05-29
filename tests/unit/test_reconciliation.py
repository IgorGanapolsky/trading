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
    """Broker = -$1000 net cash from one MLEG debit; paired ledger reports
    -$1030. Delta $30 < $150 -> no alert, exit 0."""
    state = tmp_path / "system_state.json"
    trades = tmp_path / "trades.json"
    reports = tmp_path / "reports"

    # Single MLEG fill: 1 contract @ price -10.00 (net debit) -> -$1000.
    fills = [
        {
            "id": "abc",
            "symbol": None,
            "side": "None",
            "qty": "1",
            "price": "-10.00",
            "filled_at": "2026-05-29 19:00:00+00:00",
            "status": "OrderStatus.FILLED",
            "order_class": "OrderClass.MLEG",
            "legs": ["A", "B", "C", "D"],
        }
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
    assert report["broker_fill_count"] == 1
    assert report["paired_trade_count"] == 1


def test_breach_threshold_exit_two_alert_fired(tmp_path: Path, recon_mod,
                                                monkeypatch, caplog):
    """Broker = +$500 (SIMPLE SELL 1 @ $5.00); paired reports +$200.
    Delta = $300 > $150 -> alert fired, exit 2."""
    state = tmp_path / "system_state.json"
    trades = tmp_path / "trades.json"
    reports = tmp_path / "reports"

    fills = [
        {
            "id": "x1",
            "symbol": "SPY260618C00500000",
            "side": "OrderSide.SELL",
            "qty": "1",
            "price": "5.00",
            "filled_at": "2026-05-29 18:00:00+00:00",
            "status": "OrderStatus.FILLED",
            "order_class": "OrderClass.SIMPLE",
            "legs": [],
        }
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
