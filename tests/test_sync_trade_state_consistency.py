import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        fixed = cls(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)
        if tz is None:
            return fixed.replace(tzinfo=None)
        return fixed.astimezone(tz)


def test_sync_alpaca_state_derives_trades_from_canonical_fill_times(tmp_path):
    state_file = tmp_path / "data" / "system_state.json"
    runtime_dir = tmp_path / "data" / "runtime"
    history_file = runtime_dir / "intraday_pnl_history.json"
    latest_file = runtime_dir / "intraday_pnl_latest.json"

    state_file.parent.mkdir(parents=True)
    state_file.write_text(json.dumps({"meta": {}, "account": {}, "paper_account": {}}))

    alpaca_data = {
        "paper": {
            "equity": 100000.0,
            "cash": 90000.0,
            "buying_power": 90000.0,
            "positions": [],
            "positions_count": 0,
            "mode": "paper",
            "synced_at": "2026-03-02T12:00:00+00:00",
            "trade_history": [
                {
                    "id": "older-fill",
                    "symbol": "QQQ",
                    "filled_at": "2026-02-28T12:00:00+00:00",
                },
                {
                    "id": "today-fill-offset-1",
                    "symbol": "SPY",
                    "filled_at": "2026-03-01T23:30:00-05:00",
                },
                {
                    "id": "today-fill-offset-2",
                    "symbol": None,
                    "filled_at": "2026-03-02T00:10:00-05:00",
                },
            ],
        },
        "live": None,
    }

    with (
        patch("sync_alpaca_state.SYSTEM_STATE_FILE", state_file),
        patch("sync_alpaca_state.RUNTIME_DIR", runtime_dir),
        patch("sync_alpaca_state.INTRADAY_PNL_HISTORY_FILE", history_file),
        patch("sync_alpaca_state.INTRADAY_PNL_LATEST_FILE", latest_file),
        patch("sync_alpaca_state.datetime", _FixedDateTime),
    ):
        from sync_alpaca_state import update_system_state

        update_system_state(alpaca_data)

    state = json.loads(state_file.read_text())
    trades = state["trades"]

    assert trades["today_trades"] == 2
    assert trades["total_trades_today"] == 2
    assert trades["last_trade_date"] == "2026-03-02"
    assert trades["last_trade_symbol"] == "SPY"


def test_update_system_state_trades_preserves_last_trade_date_when_no_fills(tmp_path):
    data_dir = tmp_path / "data"
    state_file = data_dir / "system_state.json"
    data_dir.mkdir(parents=True)
    state_file.write_text(
        json.dumps(
            {
                "trades": {
                    "last_trade_date": "2026-02-27",
                    "last_trade_symbol": "SPY",
                    "today_trades": 3,
                    "total_trades_today": 3,
                },
                "meta": {},
            }
        )
    )

    with patch("sync_trades_from_alpaca.DATA_DIR", data_dir):
        from sync_trades_from_alpaca import update_system_state_trades

        assert update_system_state_trades(0, "2026-03-02") is True

    state = json.loads(state_file.read_text())
    trades = state["trades"]

    assert trades["last_trade_date"] == "2026-02-27"
    assert trades["last_trade_symbol"] == "SPY"
    assert trades["today_trades"] == 0
    assert trades["total_trades_today"] == 0


def test_update_system_state_trades_sets_last_trade_date_when_fills_exist(tmp_path):
    data_dir = tmp_path / "data"
    state_file = data_dir / "system_state.json"
    data_dir.mkdir(parents=True)
    state_file.write_text(json.dumps({"trades": {"last_trade_date": "2026-02-27"}, "meta": {}}))

    with patch("sync_trades_from_alpaca.DATA_DIR", data_dir):
        from sync_trades_from_alpaca import update_system_state_trades

        assert update_system_state_trades(2, "2026-03-02") is True

    state = json.loads(state_file.read_text())
    trades = state["trades"]

    assert trades["last_trade_date"] == "2026-03-02"
    assert trades["last_trade_symbol"] == "SYNCED"
    assert trades["today_trades"] == 2
    assert trades["total_trades_today"] == 2
