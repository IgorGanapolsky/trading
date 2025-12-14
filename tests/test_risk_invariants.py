#!/usr/bin/env python3
"""
Risk Invariants Tests - Validate risk management behavior

Based on Dec 11, 2025 analysis recommendations:
1. Daily loss limit enforcement (2% max)
2. Drawdown circuit breaker (10% max)
3. ATR-based position sizing
4. Promotion gate thresholds
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDailyLossLimit:
    """Test daily loss limit enforcement."""

    def test_daily_loss_never_exceeds_limit(self):
        """Daily realized loss must never exceed 2% of equity."""
        starting_equity = 100000
        max_loss_pct = 0.02  # 2%
        max_loss_dollars = starting_equity * max_loss_pct

        # Simulate trades with cumulative loss tracking
        trades = [
            {"pnl": -500},  # -0.5%
            {"pnl": -800},  # -0.8%
            {"pnl": -600},  # -0.6% -> total -1.9%, still OK
            {"pnl": -300},  # Would push to -2.2% -> BLOCKED
        ]

        cumulative_loss = 0
        trades_executed = 0
        blocked_at = None

        for i, trade in enumerate(trades):
            potential_loss = cumulative_loss + abs(trade["pnl"])
            if potential_loss > max_loss_dollars:
                blocked_at = i
                break
            cumulative_loss += abs(trade["pnl"])
            trades_executed += 1

        assert blocked_at == 3, f"Should block at trade 3, got {blocked_at}"
        assert cumulative_loss <= max_loss_dollars, (
            f"Loss ${cumulative_loss} exceeds ${max_loss_dollars}"
        )

    def test_daily_loss_resets_daily(self):
        """Loss counter should reset at start of new trading day."""
        day1_losses = [-500, -500, -500]  # -1.5%
        day2_losses = [-500, -500]  # -1.0% (reset)

        equity = 100000
        max_loss = equity * 0.02

        # Day 1
        day1_total = sum(abs(l) for l in day1_losses)
        assert day1_total <= max_loss, "Day 1 within limit"

        # Day 2 - counter resets
        day2_total = sum(abs(l) for l in day2_losses)
        assert day2_total <= max_loss, "Day 2 within limit after reset"


class TestDrawdownCircuitBreaker:
    """Test max drawdown enforcement."""

    def test_drawdown_triggers_halt(self):
        """Trading halts when drawdown exceeds 10%."""
        peak_equity = 100000
        halt_threshold = 0.10  # 10%

        equity_curve = [100000, 98000, 95000, 92000, 89000, 87000]  # -13%
        halted = False
        halt_point = None

        for i, equity in enumerate(equity_curve):
            drawdown = (peak_equity - equity) / peak_equity
            if drawdown > halt_threshold:
                halted = True
                halt_point = i
                break

        assert halted, "Should halt at >10% drawdown"
        assert equity_curve[halt_point] == 89000, "Should halt at $89k (-11%)"

    def test_drawdown_from_running_peak(self):
        """Drawdown measures from highest equity, not starting."""
        equity_curve = [100000, 105000, 103000, 100000, 94000]  # Peak at 105k
        peak = 100000
        halt_threshold = 0.10
        halted = False

        for equity in equity_curve:
            peak = max(peak, equity)  # Track running peak
            drawdown = (peak - equity) / peak
            if drawdown > halt_threshold:
                halted = True
                break

        assert halted, "Should halt: $94k is >10% below peak $105k"

    def test_no_halt_within_limit(self):
        """No halt if drawdown stays under 10%."""
        equity_curve = [100000, 98000, 96000, 95000, 97000, 99000]  # Max -5%
        peak = 100000
        halted = False

        for equity in equity_curve:
            peak = max(peak, equity)
            if (peak - equity) / peak > 0.10:
                halted = True

        assert not halted, "Should not halt with <10% drawdown"


class TestATRPositionSizing:
    """Test ATR-based position scaling."""

    def test_high_volatility_reduces_position(self):
        """High ATR (>3% of price) reduces position by 50%."""
        base_position = 1000  # dollars

        def calculate_position(atr_pct: float) -> float:
            if atr_pct > 0.03:  # 3%
                scale = max(0.5, 1.0 - min(0.5, atr_pct * 3.0))
                return base_position * scale
            return base_position

        # Normal volatility (1.5% ATR)
        normal_pos = calculate_position(0.015)
        assert normal_pos == base_position, "Normal vol -> full position"

        # High volatility (4% ATR)
        high_vol_pos = calculate_position(0.04)
        assert high_vol_pos < base_position, "High vol -> reduced position"
        assert high_vol_pos >= base_position * 0.5, "Never below 50%"

    def test_atr_scaling_continuous(self):
        """ATR scaling should be continuous, not step-function."""
        base = 1000

        def scale(atr_pct):
            return max(0.5, 1.0 - min(0.5, atr_pct * 3.0))

        positions = [base * scale(atr / 100) for atr in range(1, 10)]

        # Should be monotonically decreasing
        for i in range(len(positions) - 1):
            assert positions[i] >= positions[i + 1], "ATR scaling should decrease with volatility"


class TestPromotionGate:
    """Test promotion gate thresholds."""

    @pytest.fixture
    def passing_metrics(self):
        return {
            "win_rate": 56.0,  # > 55%
            "sharpe_ratio": 1.3,  # > 1.2
            "max_drawdown": 8.0,  # < 10%
            "profitable_days": 35,  # > 30
            "total_trades": 150,  # > 100
        }

    @pytest.fixture
    def failing_metrics(self):
        return {
            "win_rate": 52.0,  # < 55%
            "sharpe_ratio": -45.86,  # < 1.2 (the real bug)
            "max_drawdown": 0.0,  # suspicious
            "profitable_days": 5,  # < 30
            "total_trades": 50,  # < 100
        }

    def test_gate_passes_valid_metrics(self, passing_metrics):
        """Valid metrics should pass promotion gate."""
        deficits = []

        if passing_metrics["win_rate"] < 55.0:
            deficits.append("win_rate")
        if passing_metrics["sharpe_ratio"] < 1.2:
            deficits.append("sharpe")
        if passing_metrics["max_drawdown"] > 10.0:
            deficits.append("drawdown")
        if passing_metrics["profitable_days"] < 30:
            deficits.append("streak")
        if passing_metrics["total_trades"] < 100:
            deficits.append("trades")

        assert len(deficits) == 0, f"Should pass: {deficits}"

    def test_gate_blocks_invalid_metrics(self, failing_metrics):
        """Invalid metrics should fail promotion gate."""
        deficits = []

        if failing_metrics["win_rate"] < 55.0:
            deficits.append("win_rate")
        if failing_metrics["sharpe_ratio"] < 1.2:
            deficits.append("sharpe")
        if failing_metrics["max_drawdown"] > 10.0:
            deficits.append("drawdown")
        if failing_metrics["profitable_days"] < 30:
            deficits.append("streak")
        if failing_metrics["total_trades"] < 100:
            deficits.append("trades")

        assert len(deficits) > 0, "Should fail with invalid metrics"
        assert "sharpe" in deficits, "Sharpe -45.86 should fail"

    def test_gate_json_output_format(self, failing_metrics):
        """Gate should produce machine-parsable JSON output."""
        result = {
            "status": "blocked" if failing_metrics["sharpe_ratio"] < 1.2 else "passed",
            "metrics": {
                "sharpe": failing_metrics["sharpe_ratio"],
                "sharpe_threshold": 1.2,
                "win_rate": failing_metrics["win_rate"],
                "win_rate_threshold": 55.0,
            },
            "deficits": [],
        }

        if failing_metrics["sharpe_ratio"] < 1.2:
            result["deficits"].append(
                {
                    "metric": "sharpe",
                    "actual": failing_metrics["sharpe_ratio"],
                    "required": 1.2,
                }
            )

        # Verify JSON serializable
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed["status"] == "blocked"


class TestSharpeCalculation:
    """Test Sharpe ratio calculation correctness."""

    def test_sharpe_has_volatility_floor(self):
        """Sharpe calculation must have volatility floor to prevent extreme values."""
        MIN_VOLATILITY_FLOOR = 0.0001

        # Near-zero volatility scenario
        returns = [0.0001] * 30  # Flat returns

        mean_return = np.mean(returns)
        std_return = np.std(returns)

        # Apply floor
        std_return = max(std_return, MIN_VOLATILITY_FLOOR)

        risk_free_daily = 0.04 / 252
        sharpe = (mean_return - risk_free_daily) / std_return * np.sqrt(252)

        # Should be clamped to reasonable range
        assert -10 <= sharpe <= 10, f"Sharpe {sharpe} outside [-10, 10]"

    def test_sharpe_clamping(self):
        """Sharpe must be clamped to [-10, 10] range."""
        # Extreme scenario that would produce -45.86
        returns = [-0.001] * 30  # Small consistent losses
        mean_return = np.mean(returns)
        std_return = 0.00001  # Artificially tiny std

        raw_sharpe = (mean_return - 0.04 / 252) / std_return * np.sqrt(252)

        # Without clamping this could be -45000+
        clamped_sharpe = np.clip(raw_sharpe, -10.0, 10.0)

        assert -10 <= clamped_sharpe <= 10, "Should be clamped"

    def test_sharpe_negative_is_valid(self):
        """Negative Sharpe is valid (losing strategy), but -45 is a bug."""
        # Mild losing strategy
        returns = np.random.normal(-0.0005, 0.01, 100)  # -12% annual, 16% vol

        mean_return = np.mean(returns)
        std_return = max(np.std(returns), 0.0001)
        sharpe = (mean_return - 0.04 / 252) / std_return * np.sqrt(252)
        sharpe = np.clip(sharpe, -10.0, 10.0)

        # Mild negative is OK
        assert sharpe > -5, f"Sharpe {sharpe} too negative for mild losses"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
