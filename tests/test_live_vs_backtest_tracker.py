"""Tests for live vs backtest performance tracker."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestLiveVsBacktestTracker:
    """Tests for LiveVsBacktestTracker class."""

    @pytest.fixture
    def tracker(self):
        """Create a tracker with temp data file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.analytics.live_vs_backtest_tracker.DATA_DIR", Path(tmpdir)):
                with patch(
                    "src.analytics.live_vs_backtest_tracker.TRACKER_FILE",
                    Path(tmpdir) / "live_vs_backtest.json",
                ):
                    from src.analytics.live_vs_backtest_tracker import LiveVsBacktestTracker

                    yield LiveVsBacktestTracker()

    def test_init_creates_empty_data(self, tracker):
        """Should initialize with empty data structure."""
        assert tracker.data["trades"] == []
        assert tracker.data["metrics"]["total_trades"] == 0
        assert tracker.data["alerts"] == []

    def test_record_trade_basic(self, tracker):
        """Should record a basic trade."""
        tracker.record_trade(
            symbol="SPY",
            side="buy",
            expected_price=500.0,
            actual_price=500.50,
            expected_qty=10,
            actual_qty=10,
        )

        assert len(tracker.data["trades"]) == 1
        assert tracker.data["trades"][0]["symbol"] == "SPY"
        assert tracker.data["metrics"]["total_trades"] == 1

    def test_slippage_calculation_buy(self, tracker):
        """Should calculate slippage correctly for buys."""
        tracker.record_trade(
            symbol="SPY",
            side="buy",
            expected_price=100.0,
            actual_price=101.0,  # 1% higher = bad for buyer
            expected_qty=10,
            actual_qty=10,
        )

        # For buys, paying more is negative slippage
        trade = tracker.data["trades"][0]
        assert trade["slippage_pct"] == pytest.approx(-1.0, rel=0.01)

    def test_slippage_calculation_sell(self, tracker):
        """Should calculate slippage correctly for sells."""
        tracker.record_trade(
            symbol="SPY",
            side="sell",
            expected_price=100.0,
            actual_price=99.0,  # 1% lower = bad for seller
            expected_qty=10,
            actual_qty=10,
        )

        trade = tracker.data["trades"][0]
        assert trade["slippage_pct"] == pytest.approx(-1.0, rel=0.01)

    def test_fill_rate_calculation(self, tracker):
        """Should calculate fill rate correctly."""
        tracker.record_trade(
            symbol="SPY",
            side="buy",
            expected_price=100.0,
            actual_price=100.0,
            expected_qty=100,
            actual_qty=90,  # 90% filled
        )

        trade = tracker.data["trades"][0]
        assert trade["fill_rate"] == pytest.approx(90.0)

    def test_pl_variance_calculation(self, tracker):
        """Should calculate P/L variance correctly."""
        tracker.record_trade(
            symbol="SPY",
            side="buy",
            expected_price=100.0,
            actual_price=100.0,
            expected_qty=10,
            actual_qty=10,
            backtest_pnl=100.0,
            actual_pnl=80.0,  # 20% less than expected
        )

        trade = tracker.data["trades"][0]
        assert trade["pl_variance_pct"] == pytest.approx(-20.0)

    def test_high_slippage_alert(self, tracker):
        """Should create alert for high slippage."""
        tracker.record_trade(
            symbol="SPY",
            side="buy",
            expected_price=100.0,
            actual_price=102.0,  # 2% slippage
            expected_qty=10,
            actual_qty=10,
        )

        alerts = [a for a in tracker.data["alerts"] if a["type"] == "HIGH_SLIPPAGE"]
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "WARNING"

    def test_low_fill_rate_alert(self, tracker):
        """Should create alert for low fill rate."""
        tracker.record_trade(
            symbol="SPY",
            side="buy",
            expected_price=100.0,
            actual_price=100.0,
            expected_qty=100,
            actual_qty=80,  # 80% fill rate
        )

        alerts = [a for a in tracker.data["alerts"] if a["type"] == "LOW_FILL_RATE"]
        assert len(alerts) == 1

    def test_pl_variance_alert(self, tracker):
        """Should create alert for large P/L variance."""
        tracker.record_trade(
            symbol="SPY",
            side="buy",
            expected_price=100.0,
            actual_price=100.0,
            expected_qty=10,
            actual_qty=10,
            backtest_pnl=100.0,
            actual_pnl=50.0,  # 50% variance
        )

        alerts = [a for a in tracker.data["alerts"] if a["type"] == "PL_VARIANCE"]
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "WARNING"

    def test_get_metrics(self, tracker):
        """Should return metrics correctly."""
        tracker.record_trade(
            symbol="SPY",
            side="buy",
            expected_price=100.0,
            actual_price=100.0,
            expected_qty=10,
            actual_qty=10,
            actual_pnl=50.0,
        )
        tracker.record_trade(
            symbol="QQQ",
            side="buy",
            expected_price=200.0,
            actual_price=200.0,
            expected_qty=5,
            actual_qty=5,
            actual_pnl=-20.0,
        )

        metrics = tracker.get_metrics()
        assert metrics["total_trades"] == 2
        assert metrics["signal_accuracy"] == pytest.approx(50.0)  # 1 of 2 profitable

    def test_get_recent_trades(self, tracker):
        """Should return recent trades with limit."""
        for i in range(5):
            tracker.record_trade(
                symbol=f"SYM{i}",
                side="buy",
                expected_price=100.0,
                actual_price=100.0,
                expected_qty=10,
                actual_qty=10,
            )

        recent = tracker.get_recent_trades(limit=3)
        assert len(recent) == 3
        assert recent[-1]["symbol"] == "SYM4"

    def test_get_alerts_filtered(self, tracker):
        """Should filter alerts by severity."""
        tracker.record_trade(
            symbol="SPY",
            side="buy",
            expected_price=100.0,
            actual_price=102.0,  # Creates WARNING alert
            expected_qty=10,
            actual_qty=10,
        )
        tracker.record_trade(
            symbol="QQQ",
            side="buy",
            expected_price=100.0,
            actual_price=100.0,
            expected_qty=10,
            actual_qty=10,
            backtest_pnl=100.0,
            actual_pnl=20.0,  # 80% variance = HIGH severity
        )

        high_alerts = tracker.get_alerts(severity="HIGH")
        warning_alerts = tracker.get_alerts(severity="WARNING")

        assert len(high_alerts) >= 1
        assert len(warning_alerts) >= 1


class TestTrackerSingleton:
    """Tests for singleton pattern."""

    def test_get_tracker_returns_same_instance(self):
        """Should return same tracker instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.analytics.live_vs_backtest_tracker.DATA_DIR", Path(tmpdir)):
                with patch(
                    "src.analytics.live_vs_backtest_tracker.TRACKER_FILE",
                    Path(tmpdir) / "live_vs_backtest.json",
                ):
                    # Reset singleton
                    import src.analytics.live_vs_backtest_tracker as module

                    module._tracker = None

                    tracker1 = module.get_tracker()
                    tracker2 = module.get_tracker()

                    assert tracker1 is tracker2


class TestConvenienceFunction:
    """Tests for record_trade convenience function."""

    def test_record_trade_function(self):
        """Should record trade via convenience function."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.analytics.live_vs_backtest_tracker.DATA_DIR", Path(tmpdir)):
                with patch(
                    "src.analytics.live_vs_backtest_tracker.TRACKER_FILE",
                    Path(tmpdir) / "live_vs_backtest.json",
                ):
                    import src.analytics.live_vs_backtest_tracker as module

                    module._tracker = None

                    module.record_trade(
                        symbol="SPY",
                        side="buy",
                        expected_price=100.0,
                        actual_price=100.0,
                        expected_qty=10,
                        actual_qty=10,
                    )

                    tracker = module.get_tracker()
                    assert len(tracker.data["trades"]) == 1


class TestDataPersistence:
    """Tests for data persistence."""

    def test_data_persists_across_instances(self):
        """Should persist data to file and reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir)
            tracker_file = data_path / "live_vs_backtest.json"

            with patch("src.analytics.live_vs_backtest_tracker.DATA_DIR", data_path):
                with patch("src.analytics.live_vs_backtest_tracker.TRACKER_FILE", tracker_file):
                    from src.analytics.live_vs_backtest_tracker import LiveVsBacktestTracker

                    # Create first tracker and record trade
                    tracker1 = LiveVsBacktestTracker()
                    tracker1.record_trade(
                        symbol="SPY",
                        side="buy",
                        expected_price=100.0,
                        actual_price=100.0,
                        expected_qty=10,
                        actual_qty=10,
                    )

                    # Verify file exists
                    assert tracker_file.exists()

                    # Create second tracker - should load existing data
                    tracker2 = LiveVsBacktestTracker()
                    assert len(tracker2.data["trades"]) == 1
                    assert tracker2.data["trades"][0]["symbol"] == "SPY"
