"""Tests for win rate calculation utility.

Created: Jan 14, 2026
Per CLAUDE.md: 100% test coverage on all changed/added code.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestCalculateWinRate:
    """Test win rate calculation functions."""

    def test_calculate_stats_no_closed_trades(self):
        """Stats should handle no closed trades."""
        from scripts.calculate_win_rate import calculate_stats

        trades = [
            {"id": "t1", "status": "open", "outcome": None},
            {"id": "t2", "status": "open", "outcome": None},
        ]
        stats = calculate_stats(trades)

        assert stats["total_trades"] == 2
        assert stats["closed_trades"] == 0
        assert stats["open_trades"] == 2
        assert stats["win_rate_pct"] is None

    def test_calculate_stats_with_closed_trades(self):
        """Stats should calculate win rate from closed trades."""
        from scripts.calculate_win_rate import calculate_stats

        trades = [
            {"id": "t1", "status": "closed", "outcome": "win", "realized_pnl": 100},
            {"id": "t2", "status": "closed", "outcome": "win", "realized_pnl": 50},
            {"id": "t3", "status": "closed", "outcome": "loss", "realized_pnl": -30},
            {"id": "t4", "status": "open", "outcome": None},
        ]
        stats = calculate_stats(trades)

        assert stats["total_trades"] == 4
        assert stats["closed_trades"] == 3
        assert stats["open_trades"] == 1
        assert stats["wins"] == 2
        assert stats["losses"] == 1
        assert stats["win_rate_pct"] == pytest.approx(66.7, rel=0.1)
        assert stats["avg_win"] == 75.0  # (100 + 50) / 2
        assert stats["avg_loss"] == 30.0
        assert stats["profit_factor"] == 5.0  # 150 / 30

    def test_calculate_stats_all_wins(self):
        """Stats should handle 100% win rate."""
        from scripts.calculate_win_rate import calculate_stats

        trades = [
            {"id": "t1", "status": "closed", "outcome": "win", "realized_pnl": 100},
            {"id": "t2", "status": "closed", "outcome": "win", "realized_pnl": 50},
        ]
        stats = calculate_stats(trades)

        assert stats["win_rate_pct"] == 100.0
        assert stats["losses"] == 0
        assert stats["profit_factor"] is None  # Can't divide by 0

    def test_calculate_stats_breakeven(self):
        """Stats should count breakeven trades."""
        from scripts.calculate_win_rate import calculate_stats

        trades = [
            {"id": "t1", "status": "closed", "outcome": "win", "realized_pnl": 50},
            {"id": "t2", "status": "closed", "outcome": "breakeven", "realized_pnl": 0},
            {"id": "t3", "status": "closed", "outcome": "loss", "realized_pnl": -25},
        ]
        stats = calculate_stats(trades)

        assert stats["wins"] == 1
        assert stats["losses"] == 1
        assert stats["breakeven"] == 1


class TestTradesFile:
    """Test trades.json file operations."""

    def test_trades_json_exists(self):
        """Trades.json should exist with required structure."""
        trades_file = Path("data/trades.json")
        assert trades_file.exists(), "data/trades.json must exist"

        with open(trades_file) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "stats" in data
        assert "trades" in data
        assert isinstance(data["trades"], list)

    def test_trades_json_has_stats_fields(self):
        """Stats should have all required fields per CLAUDE.md."""
        trades_file = Path("data/trades.json")
        with open(trades_file) as f:
            data = json.load(f)

        required_fields = [
            "total_trades",
            "closed_trades",
            "open_trades",
            "wins",
            "losses",
            "win_rate_pct",
            "avg_win",
            "avg_loss",
            "profit_factor",
        ]

        for field in required_fields:
            assert field in data["stats"], f"Missing required field: {field}"


class TestAddTrade:
    """Test adding trades to ledger."""

    def test_add_trade_creates_entry(self, tmp_path):
        """Adding a trade should create entry in ledger."""
        # Create temp trades file
        trades_file = tmp_path / "trades.json"
        trades_file.write_text(json.dumps({
            "metadata": {},
            "stats": {},
            "trades": []
        }))

        with patch("scripts.calculate_win_rate.TRADES_FILE", trades_file):
            from scripts.calculate_win_rate import add_trade, load_trades

            result = add_trade(
                trade_id="TEST_001",
                symbol="AAPL",
                trade_type="stock",
                side="buy",
                qty=10,
                entry_price=150.0,
                strategy="test",
            )

            assert result is True
            data = load_trades()
            assert len(data["trades"]) == 1
            assert data["trades"][0]["id"] == "TEST_001"


class TestCloseTrade:
    """Test closing trades."""

    def test_close_trade_calculates_pnl(self, tmp_path):
        """Closing a trade should calculate P/L correctly."""
        trades_file = tmp_path / "trades.json"
        trades_file.write_text(json.dumps({
            "metadata": {},
            "stats": {},
            "trades": [{
                "id": "TEST_001",
                "symbol": "AAPL",
                "type": "stock",
                "side": "buy",
                "qty": 10,
                "entry_price": 150.0,
                "status": "open",
            }]
        }))

        with patch("scripts.calculate_win_rate.TRADES_FILE", trades_file):
            from scripts.calculate_win_rate import close_trade, load_trades

            result = close_trade("TEST_001", exit_price=160.0)

            assert result is True
            data = load_trades()
            trade = data["trades"][0]
            assert trade["status"] == "closed"
            assert trade["exit_price"] == 160.0
            assert trade["realized_pnl"] == 100.0  # (160-150) * 10
            assert trade["outcome"] == "win"
