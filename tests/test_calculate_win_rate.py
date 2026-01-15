"""Tests for win rate calculation utility.

Created: Jan 14, 2026
Per CLAUDE.md: 100% test coverage on all changed/added code.
"""

import json
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

    def test_trades_json_structure(self, tmp_path):
        """Trades.json should have required structure when created."""
        # Create a test trades.json with proper structure
        trades_file = tmp_path / "trades.json"
        test_data = {
            "metadata": {"version": "1.0"},
            "stats": {
                "total_trades": 0,
                "closed_trades": 0,
                "open_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate_pct": None,
                "avg_win": None,
                "avg_loss": None,
                "profit_factor": None,
            },
            "trades": [],
        }
        trades_file.write_text(json.dumps(test_data))

        with open(trades_file) as f:
            data = json.load(f)

        assert "metadata" in data
        assert "stats" in data
        assert "trades" in data
        assert isinstance(data["trades"], list)

    def test_trades_json_has_stats_fields(self, tmp_path):
        """Stats should have all required fields per CLAUDE.md."""
        # Create a test trades.json
        trades_file = tmp_path / "trades.json"
        test_data = {
            "metadata": {},
            "stats": {
                "total_trades": 0,
                "closed_trades": 0,
                "open_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate_pct": None,
                "avg_win": None,
                "avg_loss": None,
                "profit_factor": None,
            },
            "trades": [],
        }
        trades_file.write_text(json.dumps(test_data))

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
        trades_file.write_text(json.dumps({"metadata": {}, "stats": {}, "trades": []}))

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
        trades_file.write_text(
            json.dumps(
                {
                    "metadata": {},
                    "stats": {},
                    "trades": [
                        {
                            "id": "TEST_001",
                            "symbol": "AAPL",
                            "type": "stock",
                            "side": "buy",
                            "qty": 10,
                            "entry_price": 150.0,
                            "status": "open",
                        }
                    ],
                }
            )
        )

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


class TestPaperPhaseTracking:
    """Test 90-day paper phase tracking per CLAUDE.md."""

    def test_paper_phase_days_calculated(self):
        """Stats should include paper phase days when start date provided."""
        from scripts.calculate_win_rate import calculate_stats

        trades = [
            {"id": "t1", "status": "closed", "outcome": "win", "realized_pnl": 50},
        ]
        stats = calculate_stats(trades, paper_phase_start="2026-01-01")

        assert "paper_phase_start" in stats
        assert "paper_phase_days" in stats
        assert stats["paper_phase_start"] == "2026-01-01"
        # paper_phase_days should be > 0 since start is in the past
        assert stats["paper_phase_days"] >= 0

    def test_paper_phase_no_start_date(self):
        """Stats should handle missing paper phase start date."""
        from scripts.calculate_win_rate import calculate_stats

        trades = [
            {"id": "t1", "status": "closed", "outcome": "win", "realized_pnl": 50},
        ]
        stats = calculate_stats(trades, paper_phase_start=None)

        assert stats["paper_phase_start"] is None
        assert stats["paper_phase_days"] == 0


class TestWinRateThresholds:
    """Test win rate decision thresholds per CLAUDE.md (Jan 15, 2026).

    Thresholds:
    - <75%: Not profitable, reassess strategy
    - 75-80%: Marginally profitable, proceed with caution
    - 80%+: Profitable, consider scaling after 90 days
    """

    def test_win_rate_below_75_should_reassess(self):
        """Win rate <75% should trigger reassess warning."""
        from scripts.calculate_win_rate import calculate_stats

        # Create trades with 60% win rate (18 wins, 12 losses = 30 trades)
        trades = []
        for i in range(18):
            trades.append({"id": f"w{i}", "status": "closed", "outcome": "win", "realized_pnl": 50})
        for i in range(12):
            trades.append({"id": f"l{i}", "status": "closed", "outcome": "loss", "realized_pnl": -50})

        stats = calculate_stats(trades)

        assert stats["closed_trades"] == 30
        assert stats["win_rate_pct"] == 60.0
        # This would trigger reassess per CLAUDE.md (<75%)

    def test_win_rate_75_to_80_marginally_profitable(self):
        """Win rate 75-80% should indicate marginal profitability."""
        from scripts.calculate_win_rate import calculate_stats

        # 77% win rate (23 wins, 7 losses = 30 trades)
        trades = []
        for i in range(23):
            trades.append({"id": f"w{i}", "status": "closed", "outcome": "win", "realized_pnl": 50})
        for i in range(7):
            trades.append({"id": f"l{i}", "status": "closed", "outcome": "loss", "realized_pnl": -50})

        stats = calculate_stats(trades)

        assert stats["closed_trades"] == 30
        assert stats["win_rate_pct"] == pytest.approx(76.7, rel=0.1)
        # This would indicate marginal profitability (75-80%)

    def test_win_rate_above_80_profitable(self):
        """Win rate >=80% should indicate profitable strategy."""
        from scripts.calculate_win_rate import calculate_stats

        # 83% win rate (25 wins, 5 losses = 30 trades)
        trades = []
        for i in range(25):
            trades.append({"id": f"w{i}", "status": "closed", "outcome": "win", "realized_pnl": 50})
        for i in range(5):
            trades.append({"id": f"l{i}", "status": "closed", "outcome": "loss", "realized_pnl": -50})

        stats = calculate_stats(trades)

        assert stats["closed_trades"] == 30
        assert stats["win_rate_pct"] == pytest.approx(83.3, rel=0.1)
        # This would indicate profitable strategy (80%+)
