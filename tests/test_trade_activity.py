from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.utils.trade_activity import reconcile_filled_trade_activity


def _write_fallback_trades(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries), encoding="utf-8")


def test_trade_history_overrides_stale_state_trade_summary(tmp_path: Path) -> None:
    system_state = {
        "trades": {
            "last_trade_date": "2026-02-10",
            "today_trades": 4,
        },
        "trade_history": [
            {"order_id": "old-fill", "filled_at": "2026-02-10T14:00:00Z", "status": "FILLED"},
            {"order_id": "new-fill", "filled_at": "2026-02-20T14:59:23Z"},
        ],
    }

    summary = reconcile_filled_trade_activity(
        system_state,
        data_dir=tmp_path / "data",
        today=date(2026, 2, 20),
    )

    assert summary["last_trade_date"] == "2026-02-20"
    assert summary["trades_today"] == 1
    assert summary["total_fills"] == 2


def test_fallback_file_counts_only_real_fills(tmp_path: Path) -> None:
    fallback_file = tmp_path / "data" / "trades_2026-02-25.json"
    _write_fallback_trades(
        fallback_file,
        [
            {"order_id": "sim-1", "status": "SIMULATED", "timestamp": "2026-02-25T09:30:00Z"},
            {
                "order_id": "submitted-1",
                "status": "LIVE_SUBMITTED",
                "timestamp": "2026-02-25T10:00:00Z",
            },
            {"order_id": "fill-1", "status": "FILLED", "timestamp": "2026-02-25T12:00:00+00:00"},
            {"order_id": "fill-2", "activity_type": "FILL", "timestamp": "2026-02-24T15:00:00Z"},
            {"order_id": "fill-3", "filled_at": "2026-02-25"},
        ],
    )

    summary = reconcile_filled_trade_activity({}, data_dir=tmp_path / "data", today=date(2026, 2, 25))

    assert summary["last_trade_date"] == "2026-02-25"
    assert summary["trades_today"] == 2
    assert summary["total_fills"] == 3


def test_duplicate_order_id_is_deduplicated(tmp_path: Path) -> None:
    system_state = {
        "trade_history": [
            {"order_id": "dup-1", "filled_at": "2026-02-25T14:59:23Z"},
            {"order_id": "uniq-1", "filled_at": "2026-02-26T10:30:00Z"},
        ]
    }
    fallback_file = tmp_path / "data" / "trades_2026-02-26.json"
    _write_fallback_trades(
        fallback_file,
        [
            {"order_id": "dup-1", "status": "FILLED", "timestamp": "2026-02-25T14:59:23+00:00"},
            {"order_id": "uniq-2", "status": "FILLED", "timestamp": "2026-02-26T11:00:00Z"},
        ],
    )

    summary = reconcile_filled_trade_activity(
        system_state,
        data_dir=tmp_path / "data",
        today=date(2026, 2, 26),
    )

    assert summary["last_trade_date"] == "2026-02-26"
    assert summary["trades_today"] == 2
    assert summary["total_fills"] == 3
