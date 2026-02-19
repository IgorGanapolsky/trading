from __future__ import annotations

import json
from pathlib import Path

from scripts.auto_clear_stale_trading_halt import auto_clear_stale_halt


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_auto_clear_no_halt_file(tmp_path: Path) -> None:
    state_file = tmp_path / "system_state.json"
    _write_json(state_file, {"positions": []})

    result = auto_clear_stale_halt(
        halt_file=tmp_path / "TRADING_HALTED",
        state_file=state_file,
        backup_dir=tmp_path,
    )

    assert result.status == "no_halt_file"
    assert not result.cleared


def test_auto_clear_clears_stale_halt_when_flat(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.delenv("ALPACA_BROKERAGE_TRADING_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_BROKERAGE_TRADING_API_SECRET", raising=False)

    halt_file = tmp_path / "TRADING_HALTED"
    halt_file.write_text("CRISIS MODE", encoding="utf-8")
    state_file = tmp_path / "system_state.json"
    _write_json(
        state_file,
        {
            "positions": [],
            "paper_account": {"positions_count": 0},
            "live_account": {"positions_count": 0},
        },
    )

    result = auto_clear_stale_halt(
        halt_file=halt_file,
        state_file=state_file,
        backup_dir=tmp_path,
    )

    assert result.status == "halt_cleared"
    assert result.cleared
    assert not halt_file.exists()
    backup_files = list(tmp_path.glob("crisis_cleared_*.txt"))
    assert len(backup_files) == 1


def test_auto_clear_retains_halt_when_positions_open(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.delenv("ALPACA_BROKERAGE_TRADING_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_BROKERAGE_TRADING_API_SECRET", raising=False)

    halt_file = tmp_path / "TRADING_HALTED"
    halt_file.write_text("CRISIS MODE", encoding="utf-8")
    state_file = tmp_path / "system_state.json"
    _write_json(
        state_file,
        {
            "positions": [{"symbol": "SPY260320C00720000"}],
            "paper_account": {"positions_count": 1},
        },
    )

    result = auto_clear_stale_halt(
        halt_file=halt_file,
        state_file=state_file,
        backup_dir=tmp_path,
    )

    assert result.status == "halt_retained_open_positions"
    assert not result.cleared
    assert halt_file.exists()
