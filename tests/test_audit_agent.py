import json
from pathlib import Path

import pytest

# Skip all tests if anthropic is not available
pytest.importorskip("anthropic")

from src.agents.audit_agent import AuditAgent
from src.resilience.audit_graph import AuditGraph


@pytest.fixture
def mock_trade_logs(tmp_path):
    """Create mock trade logs and audit graph for testing."""
    # Temporarily point the agent to a mock log directory
    date_str = "2026-02-23"
    log_file = tmp_path / f"trades_{date_str}.json"
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()

    trades = [
        {
            "symbol": "SPY",
            "action": "BUY",
            "max_risk": 150.0,
            "timestamp": "2026-02-23T10:00:00",
            "order_id": "T1",
        },
        {
            "symbol": "PROHIBITED",  # Violation
            "action": "BUY",
            "max_risk": 150.0,
            "timestamp": "2026-02-23T10:05:00",
            "order_id": "T2",
        },
        {
            "symbol": "SPY260327P00640000",
            "action": "SELL",
            "max_risk": 800.0,  # Note: AuditAgent now pulls sizing from AuditGraph or legacy logic
            "timestamp": "2026-02-23T10:10:00",
            "order_id": "T3",
        },
    ]

    with open(log_file, "w") as f:
        json.dump(trades, f)

    return str(tmp_path), str(audit_dir), date_str


def test_audit_agent_perform_audit(mock_trade_logs):
    """Test deterministic audit logic."""
    log_dir, audit_dir, date_str = mock_trade_logs

    agent = AuditAgent()
    agent.log_dir = Path(log_dir)  # Point to mock dir
    agent.audit_graph = AuditGraph(data_dir=audit_dir)  # Point to mock graph dir

    report = agent.perform_audit(date_str)

    assert report.trades_scanned == 3
    # Mismatch check: Since AuditGraph is empty, it shouldn't find mismatches yet
    # Violations: 1 (PROHIBITED ticker). Sizing violation removed from simple log scan in new logic
    # Wait, I kept Ticker Whitelist in log scanning.
    # Let me re-verify AuditAgent logic.
    assert len(report.violations) == 1
    assert report.status == "FAIL"  # HIGH severity violation exists

    v_symbols = [v.rule for v in report.violations]
    assert "Ticker Whitelist" in v_symbols

    # Check that report file was saved
    report_file = agent.report_dir / f"audit_{date_str}.json"
    assert report_file.exists()
    with open(report_file) as f:
        saved_report = json.load(f)
        assert saved_report["status"] == "FAIL"


def test_audit_agent_no_logs():
    """Test audit with no logs."""
    agent = AuditAgent()
    agent.log_dir = Path("non_existent_dir")

    report = agent.perform_audit("2020-01-01")
    assert report.trades_scanned == 0
    assert report.status == "PASS"
    assert "No trade logs found" in report.summary
