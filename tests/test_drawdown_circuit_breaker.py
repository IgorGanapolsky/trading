from src.risk.drawdown_circuit_breaker import DrawdownCircuitBreaker


def test_drawdown_circuit_breaker_normal():
    cb = DrawdownCircuitBreaker(max_drawdown_pct=5.0)
    status = cb.check_equity(current_equity=9700.0, peak_equity=10000.0)
    assert status.tripped is False
    assert status.drawdown_pct == 3.0


def test_drawdown_circuit_breaker_tripped(monkeypatch, tmp_path):
    halt_file = tmp_path / "TRADING_HALTED"
    log_file = tmp_path / "circuit_breaker_log.json"
    monkeypatch.setattr("src.risk.drawdown_circuit_breaker.HALT_FILE_PATH", halt_file)
    monkeypatch.setattr("src.risk.drawdown_circuit_breaker.CIRCUIT_LOG_PATH", log_file)

    cb = DrawdownCircuitBreaker(max_drawdown_pct=5.0)
    status = cb.check_equity(current_equity=9400.0, peak_equity=10000.0)
    assert status.tripped is True
    assert status.drawdown_pct == 6.0
    assert halt_file.exists()
    assert "TRADING_HALTED" in halt_file.read_text()


def test_drawdown_circuit_breaker_persist_false_does_not_write_halt(monkeypatch, tmp_path):
    """Eval/simulation must not poison production TRADING_HALTED."""
    halt_file = tmp_path / "TRADING_HALTED"
    log_file = tmp_path / "circuit_breaker_log.json"
    monkeypatch.setattr("src.risk.drawdown_circuit_breaker.HALT_FILE_PATH", halt_file)
    monkeypatch.setattr("src.risk.drawdown_circuit_breaker.CIRCUIT_LOG_PATH", log_file)

    cb = DrawdownCircuitBreaker(max_drawdown_pct=5.0)
    status = cb.check_equity(
        current_equity=9400.0,
        peak_equity=10000.0,
        persist=False,
    )
    assert status.tripped is True
    assert status.drawdown_pct == 6.0
    assert not halt_file.exists()
    assert not log_file.exists()
