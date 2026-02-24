import json
import pytest
from pathlib import Path
from src.agents.audit_agent import AuditAgent


@pytest.fixture
def mock_trade_logs(tmp_path):
    """Create mock trade logs for testing."""
    # Temporarily point the agent to a mock log directory
    date_str = "2026-02-23"
    log_file = tmp_path / f"trades_{date_str}.json"

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
            "max_risk": 800.0,  # Violation (> 500)
            "timestamp": "2026-02-23T10:10:00",
            "order_id": "T3",
        },
    ]

    with open(log_file, "w") as f:
        json.dump(trades, f)

    return str(tmp_path), date_str


def test_audit_agent_perform_audit(mock_trade_logs):
    """Test deterministic audit logic."""
    log_dir, date_str = mock_trade_logs

    agent = AuditAgent()
    agent.log_dir = Path(log_dir)  # Point to mock dir

    report = agent.perform_audit(date_str)

    assert report.trades_scanned == 3
    assert len(report.violations) == 2
    assert report.status == "FAIL"  # HIGH severity violation exists

    v_symbols = [v.rule for v in report.violations]
    assert "Ticker Whitelist" in v_symbols
    assert "Position Sizing" in v_symbols

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
