"""Tests for trade lock mechanism - prevents race conditions.

Created: Jan 22, 2026 (LL-281)
"""

import os
import threading
import time
from unittest.mock import patch


class TestTradeLock:
    """Test suite for trade lock mechanism."""

    def test_lock_file_creation(self, tmp_path):
        """Test that lock file is created when acquiring lock."""
        lock_file = tmp_path / ".trade_lock"

        with patch("src.safety.trade_lock.LOCK_FILE", lock_file):
            from src.safety.trade_lock import acquire_trade_lock

            with acquire_trade_lock(timeout=5):
                assert lock_file.exists()

    def test_lock_released_after_context(self, tmp_path):
        """Test that lock is released after context exits."""
        lock_file = tmp_path / ".trade_lock"

        with patch("src.safety.trade_lock.LOCK_FILE", lock_file):
            from src.safety.trade_lock import acquire_trade_lock, is_trade_locked

            with acquire_trade_lock(timeout=5):
                pass  # Lock held here

            # Lock should be released
            assert not is_trade_locked()

    def test_lock_prevents_concurrent_access(self, tmp_path):
        """Test that lock prevents concurrent access."""
        lock_file = tmp_path / ".trade_lock"
        results = []

        with patch("src.safety.trade_lock.LOCK_FILE", lock_file):
            from src.safety.trade_lock import TradeLockTimeout, acquire_trade_lock

            def worker(worker_id, hold_time=0.5, timeout=1):
                try:
                    with acquire_trade_lock(timeout=timeout):
                        results.append(f"worker_{worker_id}_acquired")
                        time.sleep(hold_time)
                        results.append(f"worker_{worker_id}_released")
                except TradeLockTimeout:
                    results.append(f"worker_{worker_id}_timeout")

            # Start first worker - holds lock for 2 seconds
            t1 = threading.Thread(target=worker, args=(1, 2.0, 5))
            t1.start()
            time.sleep(0.2)  # Let t1 acquire lock

            # Start second worker - should timeout after 0.5s (before t1 releases)
            t2 = threading.Thread(target=worker, args=(2, 0.5, 0.5))
            t2.start()

            t1.join()
            t2.join()

            # Worker 1 should complete, worker 2 should timeout
            assert "worker_1_acquired" in results
            assert "worker_1_released" in results
            assert "worker_2_timeout" in results

    def test_stale_lock_cleared(self, tmp_path):
        """Test that stale locks are automatically cleared."""
        lock_file = tmp_path / ".trade_lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text("stale lock")

        # Make lock file appear old
        old_time = time.time() - 400  # 400 seconds old (> 300 threshold)
        os.utime(lock_file, (old_time, old_time))

        with patch("src.safety.trade_lock.LOCK_FILE", lock_file):
            from src.safety.trade_lock import _is_lock_stale

            assert _is_lock_stale(lock_file)

    def test_force_release_lock(self, tmp_path):
        """Test force release functionality."""
        lock_file = tmp_path / ".trade_lock"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text("stuck lock")

        with patch("src.safety.trade_lock.LOCK_FILE", lock_file):
            from src.safety.trade_lock import force_release_lock

            assert lock_file.exists()
            result = force_release_lock()
            assert result
            assert not lock_file.exists()


class TestCrisisMonitor:
    """Test suite for crisis monitor."""

    def test_excess_positions_detected(self):
        """Test that excess positions trigger crisis."""
        from src.safety.crisis_monitor import check_crisis_conditions

        positions = [
            {"symbol": "SPY260220P00565000", "qty": -4, "unrealized_pl": -100, "cost_basis": 500},
            {"symbol": "SPY260220P00570000", "qty": 4, "unrealized_pl": -50, "cost_basis": 500},
            {"symbol": "SPY260220P00653000", "qty": -2, "unrealized_pl": -100, "cost_basis": 500},
            {"symbol": "SPY260220P00658000", "qty": 8, "unrealized_pl": -200, "cost_basis": 500},
            {"symbol": "SPY260220P00660000", "qty": 2, "unrealized_pl": -50, "cost_basis": 500},
        ]

        conditions = check_crisis_conditions(positions, account_equity=5000)

        # Should detect excess positions (5 > 4)
        excess_conditions = [c for c in conditions if c.condition_type == "EXCESS_POSITIONS"]
        assert len(excess_conditions) > 0

    def test_excess_loss_detected(self):
        """Test that excess unrealized loss triggers crisis."""
        from src.safety.crisis_monitor import check_crisis_conditions

        # 30% loss on $5000 account = $1500 loss
        positions = [
            {"symbol": "SPY260220P00658000", "qty": 4, "unrealized_pl": -1500, "cost_basis": 2000},
        ]

        conditions = check_crisis_conditions(positions, account_equity=5000)

        # Should detect excess loss (30% > 25% threshold)
        loss_conditions = [c for c in conditions if c.condition_type == "EXCESS_UNREALIZED_LOSS"]
        assert len(loss_conditions) > 0

    def test_single_position_crisis(self):
        """Test that single position losing 50%+ triggers crisis."""
        from src.safety.crisis_monitor import check_crisis_conditions

        positions = [
            {"symbol": "SPY260220P00658000", "qty": 4, "unrealized_pl": -600, "cost_basis": 1000},
        ]

        conditions = check_crisis_conditions(positions, account_equity=10000)

        # Should detect single position crisis (60% loss > 50% threshold)
        single_conditions = [c for c in conditions if c.condition_type == "SINGLE_POSITION_CRISIS"]
        assert len(single_conditions) > 0

    def test_no_crisis_when_normal(self):
        """Test that normal conditions don't trigger crisis."""
        from src.safety.crisis_monitor import check_crisis_conditions

        positions = [
            {"symbol": "SPY260220P00658000", "qty": 2, "unrealized_pl": -100, "cost_basis": 1000},
        ]

        conditions = check_crisis_conditions(positions, account_equity=10000)

        # Should not detect any crisis
        assert len(conditions) == 0

    def test_trading_halt_creation(self, tmp_path):
        """Test that TRADING_HALTED file is created correctly."""
        halt_file = tmp_path / "TRADING_HALTED"

        with patch("src.safety.crisis_monitor.TRADING_HALTED_FILE", halt_file):
            from src.safety.crisis_monitor import CrisisCondition, trigger_trading_halt

            conditions = [
                CrisisCondition(
                    condition_type="TEST_CRISIS",
                    current_value=10,
                    threshold=5,
                    details="Test crisis condition",
                )
            ]

            result = trigger_trading_halt(conditions)

            assert result
            assert halt_file.exists()
            content = halt_file.read_text()
            assert "TEST_CRISIS" in content
            assert "10" in content

    def test_is_in_crisis_mode(self, tmp_path):
        """Test crisis mode detection."""
        halt_file = tmp_path / "TRADING_HALTED"

        with patch("src.safety.crisis_monitor.TRADING_HALTED_FILE", halt_file):
            from src.safety.crisis_monitor import is_in_crisis_mode

            # No halt file
            assert not is_in_crisis_mode()

            # Create halt file
            halt_file.write_text("CRISIS")
            assert is_in_crisis_mode()


class TestAutoCloseBleedingPositions:
    """Test suite for auto-close bleeding positions."""

    def test_single_position_close_recommendation(self):
        """Test that heavily losing positions are recommended for closure."""
        from src.safety.auto_close_bleeding import analyze_positions_for_closure

        positions = [
            {"symbol": "SPY260220P00658000", "qty": 4, "unrealized_pl": -600, "cost_basis": 1000},
        ]

        recommendations = analyze_positions_for_closure(positions, account_equity=10000)

        # Should recommend closing this position (60% loss > 50% threshold)
        assert len(recommendations) > 0
        assert recommendations[0].symbol == "SPY260220P00658000"
        assert recommendations[0].priority == "CRITICAL"

    def test_portfolio_level_close_recommendation(self):
        """Test that portfolio-level losses trigger recommendations."""
        from src.safety.auto_close_bleeding import analyze_positions_for_closure

        positions = [
            {"symbol": "SPY260220P00658000", "qty": 4, "unrealized_pl": -800, "cost_basis": 2000},
            {"symbol": "SPY260220P00565000", "qty": 2, "unrealized_pl": -700, "cost_basis": 2000},
        ]

        # Total loss = $1500 on $5000 account = 30% > 25% threshold
        recommendations = analyze_positions_for_closure(positions, account_equity=5000)

        # Should recommend closing
        assert len(recommendations) > 0

    def test_pdt_safe_qty_calculation(self):
        """Test PDT-safe quantity calculation."""
        from src.safety.auto_close_bleeding import get_pdt_safe_close_qty

        trade_history = [
            {
                "symbol": "SPY260220P00658000",
                "side": "BUY",
                "filled_qty": 2,
                "filled_at": "2026-01-21T10:00:00Z",
            },
            {
                "symbol": "SPY260220P00658000",
                "side": "BUY",
                "filled_qty": 3,
                "filled_at": "2026-01-20T10:00:00Z",
            },
        ]

        # All buys were before today, so all 8 contracts are safe to close
        safe_qty = get_pdt_safe_close_qty("SPY260220P00658000", 8, trade_history)
        assert safe_qty == 8

    def test_no_recommendations_for_profitable(self):
        """Test that profitable positions aren't recommended for closure."""
        from src.safety.auto_close_bleeding import analyze_positions_for_closure

        positions = [
            {"symbol": "SPY260220P00658000", "qty": 4, "unrealized_pl": 200, "cost_basis": 1000},
        ]

        recommendations = analyze_positions_for_closure(positions, account_equity=10000)

        # No recommendations for profitable positions
        assert len(recommendations) == 0
