import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        fixed = cls(2026, 3, 17, 12, 34, 56, tzinfo=timezone.utc)
        if tz is None:
            return fixed.replace(tzinfo=None)
        return fixed.astimezone(tz)


def test_update_system_state_from_report_updates_freshness_and_last_trade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    state_file = data_dir / "system_state.json"
    state_file.write_text(
        json.dumps(
            {
                "last_updated": "2026-03-06T20:45:47.929095+00:00",
                "meta": {"last_updated": "2026-03-06T20:45:47.929095+00:00"},
                "trades": {"last_trade_date": "2026-03-06", "last_trade_symbol": "OLD"},
            }
        ),
        encoding="utf-8",
    )

    from daily_verification import DailyReport, LatestTrade, _update_system_state_from_report

    report = DailyReport(
        date="2026-03-17",
        traded_today=False,
        orders_today=0,
        structures_today=0,
        fills_today=0,
        positions_count=6,
        equity=95526.93,
        cash=89392.93,
        daily_pnl=34.0,
        total_pnl=-4473.07,
        last_equity=95492.93,
    )

    with patch("daily_verification.datetime", _FixedDateTime):
        _update_system_state_from_report(
            report,
            latest_trade=LatestTrade(date="2026-03-13", symbol="SPY260501P00630000"),
        )

    state = json.loads(state_file.read_text(encoding="utf-8"))
    expected_now = "2026-03-17T12:34:56+00:00"

    assert state["paper_account"]["equity"] == 95526.93
    assert state["paper_account"]["positions_count"] == 6
    assert state["trades"]["metrics_date"] == "2026-03-17"
    assert state["trades"]["last_trade_date"] == "2026-03-13"
    assert state["trades"]["last_trade_symbol"] == "SPY260501P00630000"
    assert state["meta"]["last_updated"] == expected_now
    assert state["meta"]["last_daily_verification_at"] == expected_now
    assert state["last_updated"] == expected_now


def test_save_report_replaces_duplicate_date_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    reports_file = data_dir / "verification_reports.json"
    reports_file.write_text(
        json.dumps(
            [
                {"date": "2026-03-16", "traded": False, "fills": 0, "daily_pnl": 0.0},
                {"date": "2026-03-17", "traded": False, "fills": 0, "daily_pnl": 1.0},
                {"date": "2026-03-17", "traded": False, "fills": 0, "daily_pnl": 2.0},
            ]
        ),
        encoding="utf-8",
    )

    from daily_verification import DailyReport, save_report

    save_report(
        DailyReport(
            date="2026-03-17",
            traded_today=False,
            orders_today=0,
            structures_today=0,
            fills_today=0,
            positions_count=6,
            equity=95526.93,
            cash=89392.93,
            daily_pnl=34.0,
            total_pnl=-4473.07,
            last_equity=95492.93,
        )
    )

    reports = json.loads(reports_file.read_text(encoding="utf-8"))
    assert [row["date"] for row in reports] == ["2026-03-16", "2026-03-17"]
    assert reports[-1]["daily_pnl"] == 34.0
    assert reports[-1]["equity"] == 95526.93


def test_check_consecutive_no_trades_uses_last_trade_date_when_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "system_state.json").write_text(
        json.dumps({"trades": {"last_trade_date": "2026-03-13"}}),
        encoding="utf-8",
    )
    (data_dir / "verification_reports.json").write_text(
        json.dumps(
            [
                {"date": "2026-03-11", "traded": False},
                {"date": "2026-03-12", "traded": False},
                {"date": "2026-03-13", "traded": False},
                {"date": "2026-03-13", "traded": False},
                {"date": "2026-03-17", "traded": False},
            ]
        ),
        encoding="utf-8",
    )

    from daily_verification import check_consecutive_no_trades

    with patch("daily_verification._calculate_trading_days_since_last_trade", return_value=2):
        check_consecutive_no_trades()

    assert "ALERT" not in capsys.readouterr().out


def test_check_consecutive_no_trades_alerts_after_three_trading_days(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "system_state.json").write_text(
        json.dumps({"trades": {"last_trade_date": "2026-03-12"}}),
        encoding="utf-8",
    )

    from daily_verification import check_consecutive_no_trades

    with patch("daily_verification._calculate_trading_days_since_last_trade", return_value=3):
        check_consecutive_no_trades()

    output = capsys.readouterr().out
    assert "NO TRADES FOR 3 TRADING DAYS" in output
