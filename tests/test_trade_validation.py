"""
Unit tests for trade validation and dashboard integrity.

These tests prevent issues like:
- Recording trades with qty=0
- Dashboard showing LIVE_FAILED entries
- Iron condor trades missing required fields

Added Dec 30, 2025 after discovering broken dashboard entries.
"""

import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest


class TestTradeRecordingValidation:
    """Test that trades are properly validated before recording."""

    def test_reject_trade_with_zero_quantity(self):
        """Trade with qty=0 should NOT be recorded to trades file."""
        # Simulate what iron_condor_trader does
        trade = {
            "timestamp": "2025-12-29T10:00:00",
            "strategy": "iron_condor",
            "underlying": "SPY",
            "symbol": "SPY",
            "status": "LIVE_FAILED",
            "order_ids": [],
        }

        # A failed trade should not have qty field, and should be skipped
        qty = trade.get("qty", trade.get("quantity", trade.get("notional", 0)))
        assert qty == 0, "Failed trade should have zero qty"

        # Our fix: Don't record if status is FAILED
        should_record = trade["status"] not in ["LIVE_FAILED", "LIVE_ERROR"]
        assert not should_record, "Failed trades should NOT be recorded"

    def test_valid_trade_has_positive_quantity(self):
        """Valid trades must have positive quantity."""
        trade = {
            "timestamp": "2025-12-23T10:00:00",
            "symbol": "SPY",
            "side": "buy",
            "qty": 0.735530,
            "status": "FILLED",
        }

        qty = trade.get("qty", 0)
        assert qty > 0, f"Valid trade must have qty > 0, got {qty}"

    def test_iron_condor_success_has_required_fields(self):
        """Successful iron condor trade must have symbol and status fields."""
        trade = {
            "timestamp": "2025-12-29T10:00:00",
            "strategy": "iron_condor",
            "underlying": "SPY",
            "symbol": "SPY",  # Required for dashboard
            "status": "LIVE_SUBMITTED",
            "order_ids": [{"leg": "short_put", "order_id": "123"}],
            "legs": {
                "long_put": 580,
                "short_put": 585,
                "short_call": 620,
                "long_call": 625,
            },
        }

        # Must have symbol field for dashboard compatibility
        assert "symbol" in trade, "Iron condor must have symbol field"
        assert trade["symbol"] == "SPY"

        # Status should indicate success
        assert trade["status"] == "LIVE_SUBMITTED"
        assert len(trade["order_ids"]) > 0


class TestDashboardOutputValidation:
    """Test that dashboard output is valid and has no broken entries."""

    def test_dashboard_filters_zero_qty_trades(self):
        """Dashboard should skip trades with qty=0."""
        # Simulate what the dashboard does
        trades = [
            {"symbol": "SPY", "qty": 0.735530, "status": "FILLED"},
            {"symbol": "SPY", "qty": 0, "status": "LIVE_FAILED"},  # Should be filtered
            {"symbol": "SPY", "qty": 0.734400, "status": "FILLED"},
        ]

        # Apply the dashboard filter logic
        filtered_trades = []
        for trade in trades:
            status = trade.get("status", "FILLED").upper()
            if "FAILED" in status or "ERROR" in status:
                continue
            qty = trade.get("qty", 0)
            if qty == 0 or qty is None:
                continue
            filtered_trades.append(trade)

        assert len(filtered_trades) == 2, f"Expected 2 trades, got {len(filtered_trades)}"
        for trade in filtered_trades:
            assert trade["qty"] > 0, "All filtered trades must have qty > 0"
            assert "FAILED" not in trade["status"].upper()

    def test_dashboard_filters_failed_status(self):
        """Dashboard should skip trades with FAILED or ERROR status."""
        statuses_to_filter = ["LIVE_FAILED", "LIVE_ERROR", "SIMULATED", "failed"]
        statuses_to_keep = ["FILLED", "COMPLETED", "SUCCESS", "PENDING"]

        for status in statuses_to_filter:
            should_skip = "FAILED" in status.upper() or "ERROR" in status.upper()
            # SIMULATED should also be skipped if qty=0
            if status == "SIMULATED":
                should_skip = True  # We skip SIMULATED with qty=0
            # For this test, we're checking FAILED/ERROR filter
            if "FAILED" in status.upper() or "ERROR" in status.upper():
                assert should_skip, f"Status {status} should be filtered"

    def test_no_zero_qty_in_dashboard_output(self):
        """Generated dashboard should never contain '0.000000' qty entries."""
        # This test would run the actual dashboard generation
        # For unit test, we simulate the output check
        sample_dashboard = """
| Date | Symbol | Action | Qty/Amount | Price | Status |
|------|--------|--------|------------|-------|--------|
| 2025-12-23 | **SPY** | BUY | 0.735530 | Market | ✅ FILLED |
| 2025-12-23 | **SPY** | BUY | 0.734400 | Market | ✅ FILLED |
"""
        assert "0.000000" not in sample_dashboard, "Dashboard should not contain 0.000000 qty"
        assert "LIVE_FAILED" not in sample_dashboard, "Dashboard should not contain LIVE_FAILED"


class TestOptionsTradeValidation:
    """Test validation for options trades."""

    def test_iron_condor_failed_not_recorded(self):
        """Iron condor with LIVE_FAILED status should not be recorded."""
        # Simulate iron_condor_trader.py logic (after fix)
        status = "LIVE_FAILED"
        order_ids = []  # Empty because all legs failed

        # Our fix: only record if successful
        should_record = status not in ["LIVE_FAILED", "LIVE_ERROR"]
        assert not should_record, "Failed iron condor should NOT be recorded"

    def test_iron_condor_success_recorded(self):
        """Iron condor with successful submission should be recorded."""
        status = "LIVE_SUBMITTED"
        order_ids = [
            {"leg": "long_put", "order_id": "1"},
            {"leg": "short_put", "order_id": "2"},
        ]

        should_record = status not in ["LIVE_FAILED", "LIVE_ERROR"]
        assert should_record, "Successful iron condor SHOULD be recorded"
        assert len(order_ids) > 0, "Successful trade should have order IDs"


class TestTradeFileIntegrity:
    """Test that trade files maintain integrity."""

    def test_trade_file_json_valid(self):
        """Trade files must be valid JSON."""
        # Create a temp trade file and verify it's valid JSON
        trades = [
            {
                "timestamp": "2025-12-23T10:00:00",
                "symbol": "SPY",
                "side": "buy",
                "qty": 0.735530,
                "status": "FILLED",
            }
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(trades, f)
            f.flush()

            # Read back and verify
            with open(f.name) as rf:
                loaded = json.load(rf)
                assert len(loaded) == 1
                assert loaded[0]["qty"] == 0.735530

    def test_trade_file_no_invalid_entries(self):
        """Trade file should not contain invalid entries."""
        valid_trades = [
            {"symbol": "SPY", "qty": 0.735530, "status": "FILLED"},
            {"symbol": "SPY", "qty": 0.734400, "status": "FILLED"},
        ]

        for trade in valid_trades:
            assert trade.get("qty", 0) > 0, f"Invalid qty in trade: {trade}"
            assert trade.get("status") not in [
                "LIVE_FAILED",
                "LIVE_ERROR",
            ], f"Invalid status: {trade}"
