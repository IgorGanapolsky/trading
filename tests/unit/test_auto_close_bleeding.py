"""Tests for auto_close_bleeding.py - CRITICAL SAFETY MODULE.

This module tests the emergency loss control system that prevents
catastrophic losses by auto-closing bleeding positions.

Per LL-281: This is a crisis-prevention component.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

try:
    from src.safety.auto_close_bleeding import (
        LOSS_THRESHOLD,
        SINGLE_POSITION_LOSS_THRESHOLD,
        PositionCloseRecommendation,
        analyze_positions_for_closure,
        execute_auto_close,
        get_pdt_safe_close_qty,
    )
except ImportError:
    pytest.skip(
        "auto_close_bleeding imports unavailable in this environment", allow_module_level=True
    )


class TestPositionCloseRecommendation:
    """Tests for PositionCloseRecommendation dataclass."""

    def test_creates_recommendation(self):
        """Should create a recommendation with all fields."""
        rec = PositionCloseRecommendation(
            symbol="SPY260227P00660000",
            qty=1.0,
            reason="Test reason",
            priority="CRITICAL",
            unrealized_pl=-500.0,
            cost_basis=1000.0,
        )
        assert rec.symbol == "SPY260227P00660000"
        assert rec.qty == 1.0
        assert rec.priority == "CRITICAL"
        assert rec.unrealized_pl == -500.0
        assert rec.cost_basis == 1000.0

    def test_to_dict(self):
        """Should convert to dictionary correctly."""
        rec = PositionCloseRecommendation(
            symbol="SPY260227P00660000",
            qty=1.0,
            reason="Test",
            priority="HIGH",
            unrealized_pl=-100.0,
            cost_basis=500.0,
        )
        d = rec.to_dict()
        assert d["symbol"] == "SPY260227P00660000"
        assert d["qty"] == 1.0
        assert d["priority"] == "HIGH"
        assert "created_at" in d


class TestAnalyzePositionsForClosure:
    """Tests for the main analysis function."""

    def test_no_recommendations_for_profitable_positions(self):
        """Should not recommend closing profitable positions."""
        positions = [
            {
                "symbol": "SPY260227P00660000",
                "qty": 1,
                "unrealized_pl": 100,
                "cost_basis": 500,
            }
        ]
        recs = analyze_positions_for_closure(positions, account_equity=30000)
        assert len(recs) == 0

    def test_recommends_closing_50pct_loss(self):
        """Should recommend closing when single position loses > 50%."""
        positions = [
            {
                "symbol": "SPY260227P00660000",
                "qty": 1,
                "unrealized_pl": -600,
                "cost_basis": 1000,
            }
        ]
        recs = analyze_positions_for_closure(positions, account_equity=30000)
        assert len(recs) == 1
        assert recs[0].priority == "CRITICAL"
        assert "50" in recs[0].reason  # Check for 50 (handles "50%" or "50.0%")

    def test_recommends_closing_at_portfolio_threshold(self):
        """Should recommend closing when portfolio loss > 25%."""
        positions = [
            {
                "symbol": "SPY260227P00660000",
                "qty": 1,
                "unrealized_pl": -8000,
                "cost_basis": 10000,
            }
        ]
        recs = analyze_positions_for_closure(positions, account_equity=30000)
        # 8000/30000 = 26.7% > 25%
        assert len(recs) >= 1
        assert any(r.priority in ["CRITICAL", "HIGH"] for r in recs)

    def test_no_recommendation_below_thresholds(self):
        """Should not recommend if below all thresholds."""
        positions = [
            {
                "symbol": "SPY260227P00660000",
                "qty": 1,
                "unrealized_pl": -100,
                "cost_basis": 500,
            }
        ]
        # Loss is 20% (below 50%) and 100/30000 = 0.3% (below 25%)
        recs = analyze_positions_for_closure(positions, account_equity=30000)
        assert len(recs) == 0

    def test_sorts_by_priority(self):
        """Should sort recommendations by priority (CRITICAL first)."""
        positions = [
            {
                "symbol": "SPY1",
                "qty": 1,
                "unrealized_pl": -600,
                "cost_basis": 1000,
            },  # 60% loss
            {
                "symbol": "SPY2",
                "qty": 1,
                "unrealized_pl": -5000,
                "cost_basis": 10000,
            },  # 50% loss
        ]
        recs = analyze_positions_for_closure(positions, account_equity=30000)
        assert len(recs) >= 1
        # CRITICAL should come before HIGH
        priorities = [r.priority for r in recs]
        if "CRITICAL" in priorities and "HIGH" in priorities:
            assert priorities.index("CRITICAL") < priorities.index("HIGH")

    def test_handles_zero_cost_basis(self):
        """Should handle positions with zero cost basis gracefully."""
        positions = [
            {
                "symbol": "SPY260227P00660000",
                "qty": 1,
                "unrealized_pl": -100,
                "cost_basis": 0,
            }
        ]
        # Should not crash
        recs = analyze_positions_for_closure(positions, account_equity=30000)
        # No division by zero error
        assert isinstance(recs, list)

    def test_handles_empty_positions(self):
        """Should return empty list for no positions."""
        recs = analyze_positions_for_closure([], account_equity=30000)
        assert recs == []


class TestGetPDTSafeCloseQty:
    """Tests for PDT-safe quantity calculation."""

    def test_safe_qty_no_buys_today(self):
        """Should return full qty if no buys today."""
        trade_history = [
            {
                "symbol": "SPY260227P00660000",
                "side": "BUY",
                "filled_qty": 2,
                "filled_at": (datetime.now() - timedelta(days=2)).isoformat(),
            }
        ]
        safe_qty = get_pdt_safe_close_qty("SPY260227P00660000", 2.0, trade_history)
        assert safe_qty == 2.0

    def test_safe_qty_with_buys_today(self):
        """Should subtract today's buys from safe quantity."""
        today = datetime.now().isoformat()
        trade_history = [
            {
                "symbol": "SPY260227P00660000",
                "side": "BUY",
                "filled_qty": 1,
                "filled_at": today,
            }
        ]
        safe_qty = get_pdt_safe_close_qty("SPY260227P00660000", 2.0, trade_history)
        assert safe_qty == 1.0

    def test_safe_qty_all_bought_today(self):
        """Should return 0 if all contracts bought today."""
        today = datetime.now().isoformat()
        trade_history = [
            {
                "symbol": "SPY260227P00660000",
                "side": "BUY",
                "filled_qty": 2,
                "filled_at": today,
            }
        ]
        safe_qty = get_pdt_safe_close_qty("SPY260227P00660000", 2.0, trade_history)
        assert safe_qty == 0.0

    def test_ignores_sells_in_history(self):
        """Should only count BUY trades, not SELL."""
        today = datetime.now().isoformat()
        trade_history = [
            {
                "symbol": "SPY260227P00660000",
                "side": "SELL",
                "filled_qty": 1,
                "filled_at": today,
            }
        ]
        safe_qty = get_pdt_safe_close_qty("SPY260227P00660000", 2.0, trade_history)
        assert safe_qty == 2.0

    def test_handles_empty_history(self):
        """Should return full qty for empty trade history."""
        safe_qty = get_pdt_safe_close_qty("SPY260227P00660000", 2.0, [])
        assert safe_qty == 2.0


class TestExecuteAutoClose:
    """Tests for auto-close execution."""

    def test_dry_run_does_not_close(self):
        """Should not actually close positions in dry run mode."""
        mock_client = MagicMock()
        rec = PositionCloseRecommendation(
            symbol="SPY260227P00660000",
            qty=1.0,
            reason="Test",
            priority="CRITICAL",
            unrealized_pl=-500.0,
            cost_basis=1000.0,
        )
        results = execute_auto_close([rec], mock_client, dry_run=True)
        assert len(results) == 1
        assert results[0]["status"] == "dry_run"
        mock_client.close_position.assert_not_called()

    def test_live_run_calls_close_position(self):
        """Should call close_position when not dry run."""
        mock_client = MagicMock()
        mock_order = MagicMock()
        mock_order.id = "test-order-id"
        mock_client.close_position.return_value = mock_order

        rec = PositionCloseRecommendation(
            symbol="SPY260227P00660000",
            qty=1.0,
            reason="Test",
            priority="CRITICAL",
            unrealized_pl=-500.0,
            cost_basis=1000.0,
        )
        results = execute_auto_close([rec], mock_client, dry_run=False)
        assert len(results) == 1
        assert results[0]["status"] == "submitted"
        assert results[0]["order_id"] == "test-order-id"
        mock_client.close_position.assert_called_once_with("SPY260227P00660000")

    def test_handles_close_failure(self):
        """Should handle close_position failure gracefully."""
        mock_client = MagicMock()
        mock_client.close_position.side_effect = Exception("API Error")

        rec = PositionCloseRecommendation(
            symbol="SPY260227P00660000",
            qty=1.0,
            reason="Test",
            priority="CRITICAL",
            unrealized_pl=-500.0,
            cost_basis=1000.0,
        )
        results = execute_auto_close([rec], mock_client, dry_run=False)
        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "API Error" in results[0]["error"]


class TestThresholdConstants:
    """Tests for threshold constants."""

    def test_single_position_threshold_is_50_percent(self):
        """Single position loss threshold should be 50%."""
        assert SINGLE_POSITION_LOSS_THRESHOLD == 0.50

    def test_portfolio_threshold_is_25_percent(self):
        """Portfolio loss threshold should be 25%."""
        assert LOSS_THRESHOLD == 0.25
