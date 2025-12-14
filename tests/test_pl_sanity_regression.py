"""
P/L Sanity Checker Regression Tests

This test suite verifies that the P/L sanity checker correctly detects "zombie mode" scenarios
where the trading system appears to run but doesn't execute trades or make meaningful changes.

Test Coverage:
1. Stuck equity detection (3+ days identical equity)
2. No trades detection (3+ days with 0 trades)
3. Zero P/L detection (3+ days P/L exactly $0)
4. Anomalous change detection (>5% daily swing)
5. Drawdown detection (>10% from peak)
6. Healthy system validation (normal varying data)

Created: Dec 11, 2025
Purpose: Prevent silent trading failures like the 30-day zero-trade incident
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Mock alpaca imports BEFORE importing verify_pl_sanity
sys.modules["alpaca"] = MagicMock()
sys.modules["alpaca.trading"] = MagicMock()
sys.modules["alpaca.trading.client"] = MagicMock()

# Import the P/L sanity checker
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.verify_pl_sanity import PLSanityChecker


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory structure."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def mock_alpaca_api():
    """Mock Alpaca API client."""
    mock_api = Mock()
    mock_account = Mock()
    mock_account.equity = 100000.0
    mock_api.get_account.return_value = mock_account

    mock_clock = Mock()
    mock_clock.is_open = False
    mock_api.get_clock.return_value = mock_clock

    return mock_api


def create_performance_log(data_dir: Path, entries: list[dict]) -> Path:
    """
    Create synthetic performance_log.json file.

    Args:
        data_dir: Directory to write file to
        entries: List of daily entries with date, equity, pl

    Returns:
        Path to created file
    """
    log_file = data_dir / "performance_log.json"
    with open(log_file, "w") as f:
        json.dump(entries, f, indent=2)
    return log_file


def create_trades_file(data_dir: Path, date: datetime, trades: list[dict]) -> Path:
    """
    Create synthetic trades_YYYY-MM-DD.json file.

    Args:
        data_dir: Directory to write file to
        date: Date for the trades file
        trades: List of trade entries

    Returns:
        Path to created file
    """
    date_str = date.strftime("%Y-%m-%d")
    trades_file = data_dir / f"trades_{date_str}.json"
    with open(trades_file, "w") as f:
        json.dump(trades, f, indent=2)
    return trades_file


class TestStuckEquityDetection:
    """Test detection of equity stuck at same value for 3+ trading days."""

    def test_stuck_equity_detected(self, temp_data_dir, mock_alpaca_api):
        """Verify that 3+ days of identical equity triggers CRITICAL alert."""
        # Create 5 days of identical equity (stuck at $100,000)
        base_date = datetime(2025, 12, 1)  # Monday
        entries = []

        for i in range(5):
            date = base_date + timedelta(days=i)
            # Skip weekends
            if date.weekday() >= 5:
                continue
            entries.append(
                {
                    "date": date.date().isoformat(),
                    "timestamp": date.isoformat(),
                    "equity": 100000.0,  # STUCK - no change
                    "pl": 0.0,
                }
            )

        # Add today's entry
        today = base_date + timedelta(days=5)
        entries.append(
            {
                "date": today.date().isoformat(),
                "timestamp": today.isoformat(),
                "equity": 100000.0,
                "pl": 0.0,
            }
        )

        create_performance_log(temp_data_dir, entries)

        # Create empty trades files (no trades executed)
        for entry in entries:
            date = datetime.fromisoformat(entry["date"])
            create_trades_file(temp_data_dir, date, [])

        # Run sanity check with patched paths
        with patch("scripts.verify_pl_sanity.DATA_DIR", temp_data_dir):
            with patch(
                "scripts.verify_pl_sanity.PERFORMANCE_LOG_FILE",
                temp_data_dir / "performance_log.json",
            ):
                with patch("scripts.verify_pl_sanity.TRADES_DIR", temp_data_dir):
                    checker = PLSanityChecker(verbose=True)
                    checker.api = mock_alpaca_api

                    # Load the log and check for stuck equity
                    log_data = checker.load_performance_log()
                    assert len(log_data) == 6, "Should have 6 entries"

                    # Check for stuck equity
                    detected = checker.check_stuck_equity(log_data)

                    assert detected is True, "Should detect stuck equity"
                    assert len(checker.alerts) > 0, "Should have alerts"

                    # Verify alert details
                    stuck_alerts = [a for a in checker.alerts if a["type"] == "STUCK_EQUITY"]
                    assert len(stuck_alerts) > 0, "Should have STUCK_EQUITY alert"
                    assert stuck_alerts[0]["level"] == "CRITICAL"
                    assert stuck_alerts[0]["days_stuck"] >= 3

    def test_varying_equity_not_detected(self, temp_data_dir, mock_alpaca_api):
        """Verify that normal equity changes don't trigger stuck alert."""
        base_date = datetime(2025, 12, 1)
        entries = []

        # Create 5 days with varying equity
        equities = [100000.0, 100050.0, 100025.0, 100100.0, 100075.0]
        for i, equity in enumerate(equities):
            date = base_date + timedelta(days=i)
            if date.weekday() >= 5:
                continue
            entries.append(
                {
                    "date": date.date().isoformat(),
                    "timestamp": date.isoformat(),
                    "equity": equity,
                    "pl": equity - 100000.0,
                }
            )

        create_performance_log(temp_data_dir, entries)

        with patch("scripts.verify_pl_sanity.DATA_DIR", temp_data_dir):
            with patch(
                "scripts.verify_pl_sanity.PERFORMANCE_LOG_FILE",
                temp_data_dir / "performance_log.json",
            ):
                checker = PLSanityChecker(verbose=True)
                checker.api = mock_alpaca_api

                log_data = checker.load_performance_log()
                detected = checker.check_stuck_equity(log_data)

                assert detected is False, "Should not detect stuck equity with varying values"


class TestNoTradesDetection:
    """Test detection of zero trades for 3+ trading days."""

    def test_no_trades_detected(self, temp_data_dir, mock_alpaca_api):
        """Verify that 3+ days with 0 trades triggers CRITICAL alert."""
        # Create trades files with no trades for past 5 days
        base_date = datetime.now() - timedelta(days=5)

        for i in range(6):
            date = base_date + timedelta(days=i)
            if date.weekday() >= 5:  # Skip weekends
                continue
            create_trades_file(temp_data_dir, date, [])  # Empty trades

        with patch("scripts.verify_pl_sanity.TRADES_DIR", temp_data_dir):
            checker = PLSanityChecker(verbose=True)
            checker.api = mock_alpaca_api

            detected = checker.check_no_trades()

            assert detected is True, "Should detect no trades"
            assert len(checker.alerts) > 0, "Should have alerts"

            no_trade_alerts = [a for a in checker.alerts if a["type"] == "NO_TRADES"]
            assert len(no_trade_alerts) > 0, "Should have NO_TRADES alert"
            assert no_trade_alerts[0]["level"] == "CRITICAL"
            assert no_trade_alerts[0]["days_without_trades"] >= 3

    def test_recent_trades_not_detected(self, temp_data_dir, mock_alpaca_api):
        """Verify that recent trades prevent no-trade alert."""
        # Create trades files with some trades in last 3 days
        base_date = datetime.now() - timedelta(days=2)

        for i in range(3):
            date = base_date + timedelta(days=i)
            if date.weekday() >= 5:
                continue

            # Create 2 trades per day
            trades = [
                {
                    "symbol": "SPY",
                    "quantity": 1,
                    "price": 450.0,
                    "timestamp": date.isoformat(),
                    "action": "BUY",
                },
                {
                    "symbol": "QQQ",
                    "quantity": 1,
                    "price": 380.0,
                    "timestamp": date.isoformat(),
                    "action": "BUY",
                },
            ]
            create_trades_file(temp_data_dir, date, trades)

        with patch("scripts.verify_pl_sanity.TRADES_DIR", temp_data_dir):
            checker = PLSanityChecker(verbose=True)
            checker.api = mock_alpaca_api

            detected = checker.check_no_trades()

            assert detected is False, "Should not detect no-trade alert with recent trades"


class TestZeroPLDetection:
    """Test detection of P/L exactly $0.00 for 3+ days."""

    def test_zero_pl_detected(self, temp_data_dir, mock_alpaca_api):
        """Verify that 3+ days of exactly $0 P/L triggers WARNING."""
        base_date = datetime(2025, 12, 1)
        entries = []

        # Create 5 days with exactly $0 P/L
        for i in range(5):
            date = base_date + timedelta(days=i)
            if date.weekday() >= 5:
                continue
            entries.append(
                {
                    "date": date.date().isoformat(),
                    "timestamp": date.isoformat(),
                    "equity": 100000.0,
                    "pl": 0.0,  # Exactly zero
                }
            )

        create_performance_log(temp_data_dir, entries)

        with patch("scripts.verify_pl_sanity.DATA_DIR", temp_data_dir):
            with patch(
                "scripts.verify_pl_sanity.PERFORMANCE_LOG_FILE",
                temp_data_dir / "performance_log.json",
            ):
                checker = PLSanityChecker(verbose=True)
                checker.api = mock_alpaca_api

                log_data = checker.load_performance_log()
                detected = checker.check_zero_pl(log_data)

                assert detected is True, "Should detect zero P/L"
                assert len(checker.alerts) > 0, "Should have alerts"

                zero_pl_alerts = [a for a in checker.alerts if a["type"] == "ZERO_PL"]
                assert len(zero_pl_alerts) > 0, "Should have ZERO_PL alert"
                assert zero_pl_alerts[0]["level"] == "WARNING"
                assert zero_pl_alerts[0]["days_zero"] >= 3

    def test_nonzero_pl_not_detected(self, temp_data_dir, mock_alpaca_api):
        """Verify that non-zero P/L doesn't trigger alert."""
        base_date = datetime(2025, 12, 1)
        entries = []

        # Create 5 days with varying P/L
        pls = [10.0, -5.0, 20.0, -3.0, 15.0]
        for i, pl in enumerate(pls):
            date = base_date + timedelta(days=i)
            if date.weekday() >= 5:
                continue
            entries.append(
                {
                    "date": date.date().isoformat(),
                    "timestamp": date.isoformat(),
                    "equity": 100000.0 + pl,
                    "pl": pl,
                }
            )

        create_performance_log(temp_data_dir, entries)

        with patch("scripts.verify_pl_sanity.DATA_DIR", temp_data_dir):
            with patch(
                "scripts.verify_pl_sanity.PERFORMANCE_LOG_FILE",
                temp_data_dir / "performance_log.json",
            ):
                checker = PLSanityChecker(verbose=True)
                checker.api = mock_alpaca_api

                log_data = checker.load_performance_log()
                detected = checker.check_zero_pl(log_data)

                assert detected is False, "Should not detect zero P/L with varying values"


class TestAnomalousChangeDetection:
    """Test detection of >5% daily equity swings."""

    def test_anomalous_change_detected(self, temp_data_dir, mock_alpaca_api):
        """Verify that >5% daily change triggers WARNING."""
        base_date = datetime(2025, 12, 1)
        entries = []

        # Create normal days, then a 10% jump
        # Need at least 4 entries for the check to work properly
        entries.append(
            {
                "date": base_date.date().isoformat(),
                "timestamp": base_date.isoformat(),
                "equity": 100000.0,
                "pl": 0.0,
            }
        )

        day2 = base_date + timedelta(days=1)
        entries.append(
            {
                "date": day2.date().isoformat(),
                "timestamp": day2.isoformat(),
                "equity": 100100.0,  # +0.1%
                "pl": 100.0,
            }
        )

        day3 = base_date + timedelta(days=2)
        entries.append(
            {
                "date": day3.date().isoformat(),
                "timestamp": day3.isoformat(),
                "equity": 110110.0,  # +10% from day2 - ANOMALOUS
                "pl": 10110.0,
            }
        )

        day4 = base_date + timedelta(days=3)
        entries.append(
            {
                "date": day4.date().isoformat(),
                "timestamp": day4.isoformat(),
                "equity": 110200.0,  # Small change after anomaly
                "pl": 10200.0,
            }
        )

        create_performance_log(temp_data_dir, entries)

        with patch("scripts.verify_pl_sanity.DATA_DIR", temp_data_dir):
            with patch(
                "scripts.verify_pl_sanity.PERFORMANCE_LOG_FILE",
                temp_data_dir / "performance_log.json",
            ):
                checker = PLSanityChecker(verbose=True)
                checker.api = mock_alpaca_api

                log_data = checker.load_performance_log()
                detected = checker.check_anomalous_pl_change(log_data)

                assert detected is True, "Should detect anomalous change"
                assert len(checker.alerts) > 0, "Should have alerts"

                anomalous_alerts = [a for a in checker.alerts if a["type"] == "ANOMALOUS_CHANGE"]
                assert len(anomalous_alerts) > 0, "Should have ANOMALOUS_CHANGE alert"
                assert anomalous_alerts[0]["level"] == "WARNING"
                assert anomalous_alerts[0]["pct_change"] > 5.0

    def test_normal_change_not_detected(self, temp_data_dir, mock_alpaca_api):
        """Verify that <5% daily changes don't trigger alert."""
        base_date = datetime(2025, 12, 1)
        entries = []

        # Create 4 days with small (<5%) daily changes
        equities = [100000.0, 100300.0, 100150.0, 100400.0]  # All <1% daily change
        for i, equity in enumerate(equities):
            date = base_date + timedelta(days=i)
            entries.append(
                {
                    "date": date.date().isoformat(),
                    "timestamp": date.isoformat(),
                    "equity": equity,
                    "pl": equity - 100000.0,
                }
            )

        create_performance_log(temp_data_dir, entries)

        with patch("scripts.verify_pl_sanity.DATA_DIR", temp_data_dir):
            with patch(
                "scripts.verify_pl_sanity.PERFORMANCE_LOG_FILE",
                temp_data_dir / "performance_log.json",
            ):
                checker = PLSanityChecker(verbose=True)
                checker.api = mock_alpaca_api

                log_data = checker.load_performance_log()
                detected = checker.check_anomalous_pl_change(log_data)

                assert detected is False, "Should not detect anomalous change with small moves"


class TestDrawdownDetection:
    """Test detection of >10% drawdown from peak."""

    def test_drawdown_detected(self, temp_data_dir, mock_alpaca_api):
        """Verify that >10% drawdown triggers WARNING."""
        base_date = datetime(2025, 12, 1)
        entries = []

        # Create peak, then drawdown >10%
        equities = [100000.0, 105000.0, 110000.0, 98000.0]  # Peak: 110k, Current: 98k = 10.9% DD
        for i, equity in enumerate(equities):
            date = base_date + timedelta(days=i)
            entries.append(
                {
                    "date": date.date().isoformat(),
                    "timestamp": date.isoformat(),
                    "equity": equity,
                    "pl": equity - 100000.0,
                }
            )

        create_performance_log(temp_data_dir, entries)

        with patch("scripts.verify_pl_sanity.DATA_DIR", temp_data_dir):
            with patch(
                "scripts.verify_pl_sanity.PERFORMANCE_LOG_FILE",
                temp_data_dir / "performance_log.json",
            ):
                checker = PLSanityChecker(verbose=True)
                checker.api = mock_alpaca_api

                log_data = checker.load_performance_log()
                detected = checker.check_drawdown(log_data)

                assert detected is True, "Should detect drawdown"
                assert len(checker.alerts) > 0, "Should have alerts"

                dd_alerts = [a for a in checker.alerts if a["type"] == "DRAWDOWN"]
                assert len(dd_alerts) > 0, "Should have DRAWDOWN alert"
                assert dd_alerts[0]["level"] == "WARNING"
                assert dd_alerts[0]["drawdown_pct"] > 10.0
                assert dd_alerts[0]["peak_equity"] == 110000.0

    def test_small_drawdown_not_detected(self, temp_data_dir, mock_alpaca_api):
        """Verify that <10% drawdown doesn't trigger alert."""
        base_date = datetime(2025, 12, 1)
        entries = []

        # Create peak, then small drawdown <10%
        equities = [100000.0, 105000.0, 110000.0, 102000.0]  # Peak: 110k, Current: 102k = 7.3% DD
        for i, equity in enumerate(equities):
            date = base_date + timedelta(days=i)
            entries.append(
                {
                    "date": date.date().isoformat(),
                    "timestamp": date.isoformat(),
                    "equity": equity,
                    "pl": equity - 100000.0,
                }
            )

        create_performance_log(temp_data_dir, entries)

        with patch("scripts.verify_pl_sanity.DATA_DIR", temp_data_dir):
            with patch(
                "scripts.verify_pl_sanity.PERFORMANCE_LOG_FILE",
                temp_data_dir / "performance_log.json",
            ):
                checker = PLSanityChecker(verbose=True)
                checker.api = mock_alpaca_api

                log_data = checker.load_performance_log()
                detected = checker.check_drawdown(log_data)

                assert detected is False, "Should not detect small drawdown"


class TestHealthySystemValidation:
    """Test that healthy trading system passes all checks."""

    def test_healthy_system_passes(self, temp_data_dir, mock_alpaca_api):
        """Verify that a healthy system with normal metrics passes all checks."""
        base_date = datetime.now() - timedelta(days=5)
        entries = []

        # Create realistic healthy trading scenario:
        # - Varying equity (not stuck)
        # - Non-zero P/L
        # - Small daily changes (<5%)
        # - Small drawdown (<10%)
        equities = [100000.0, 100150.0, 100080.0, 100250.0, 100180.0, 100320.0]

        for i, equity in enumerate(equities):
            date = base_date + timedelta(days=i)
            if date.weekday() >= 5:  # Skip weekends
                continue
            entries.append(
                {
                    "date": date.date().isoformat(),
                    "timestamp": date.isoformat(),
                    "equity": equity,
                    "pl": equity - 100000.0,
                }
            )

        create_performance_log(temp_data_dir, entries)

        # Create trades for each trading day
        for entry in entries:
            date = datetime.fromisoformat(entry["date"])
            trades = [
                {
                    "symbol": "SPY",
                    "quantity": 1,
                    "price": 450.0,
                    "timestamp": date.isoformat(),
                    "action": "BUY",
                }
            ]
            create_trades_file(temp_data_dir, date, trades)

        with patch("scripts.verify_pl_sanity.DATA_DIR", temp_data_dir):
            with patch(
                "scripts.verify_pl_sanity.PERFORMANCE_LOG_FILE",
                temp_data_dir / "performance_log.json",
            ):
                with patch("scripts.verify_pl_sanity.TRADES_DIR", temp_data_dir):
                    checker = PLSanityChecker(verbose=True)
                    checker.api = mock_alpaca_api

                    # Mock get_current_equity
                    with patch.object(checker, "get_current_equity", return_value=100320.0):
                        is_healthy = checker.run_all_checks()

                    # Healthy system should pass all checks
                    assert is_healthy is True, (
                        f"Healthy system should pass, but got alerts: {checker.alerts}"
                    )
                    assert len(checker.alerts) == 0, "Healthy system should have no alerts"

    def test_multiple_failures_detected(self, temp_data_dir, mock_alpaca_api):
        """Verify that multiple failures are all detected in one run."""
        base_date = datetime(2025, 12, 1)
        entries = []

        # Create scenario with MULTIPLE problems:
        # 1. Stuck equity (same for 5 days)
        # 2. Zero P/L
        # 3. No trades
        for i in range(5):
            date = base_date + timedelta(days=i)
            if date.weekday() >= 5:
                continue
            entries.append(
                {
                    "date": date.date().isoformat(),
                    "timestamp": date.isoformat(),
                    "equity": 100000.0,  # STUCK
                    "pl": 0.0,  # ZERO
                }
            )

        create_performance_log(temp_data_dir, entries)

        # Create empty trades files (no trades)
        for entry in entries:
            date = datetime.fromisoformat(entry["date"])
            create_trades_file(temp_data_dir, date, [])

        with patch("scripts.verify_pl_sanity.DATA_DIR", temp_data_dir):
            with patch(
                "scripts.verify_pl_sanity.PERFORMANCE_LOG_FILE",
                temp_data_dir / "performance_log.json",
            ):
                with patch("scripts.verify_pl_sanity.TRADES_DIR", temp_data_dir):
                    checker = PLSanityChecker(verbose=True)
                    checker.api = mock_alpaca_api

                    with patch.object(checker, "get_current_equity", return_value=100000.0):
                        is_healthy = checker.run_all_checks()

                    # Should fail with multiple alerts
                    assert is_healthy is False, "Unhealthy system should fail"
                    assert len(checker.alerts) >= 3, (
                        f"Should detect multiple failures, got {len(checker.alerts)}"
                    )

                    # Verify all expected alert types are present
                    alert_types = {a["type"] for a in checker.alerts}
                    assert "STUCK_EQUITY" in alert_types, "Should detect stuck equity"
                    assert "NO_TRADES" in alert_types, "Should detect no trades"
                    assert "ZERO_PL" in alert_types, "Should detect zero P/L"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
