from src.safety.trading_halt import get_trading_halt_state


def test_prefers_system_halt_file(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "TRADING_HALTED").write_text("System halted for rebuild.", encoding="utf-8")
    (data_dir / "trading_halt.txt").write_text("Legacy halt.", encoding="utf-8")

    halt = get_trading_halt_state(tmp_path)

    assert halt.active is True
    assert halt.kind == "system_halt"
    assert halt.reason == "System halted for rebuild."
    assert halt.path.endswith("data/TRADING_HALTED")


def test_returns_inactive_when_no_halt_files_present(tmp_path):
    halt = get_trading_halt_state(tmp_path)

    assert halt.active is False
    assert halt.kind == "none"
    assert halt.path == ""
