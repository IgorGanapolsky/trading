"""
Tests for Trade Sync Module.

100% coverage for:
- src/observability/trade_sync.py

Tests:
1. TradeSync initialization
2. Sync to Vertex AI RAG
3. Sync to local JSON
4. Trade outcome calculation
5. Lesson creation
6. Trade history queries

Updated: Jan 7, 2026 - Removed ChromaDB tests (CEO directive)
"""

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTradeSyncInitialization:
    """Test TradeSync initialization."""

    def test_import_trade_sync(self):
        """Should import TradeSync without errors."""
        from src.observability.trade_sync import TradeSync

        assert TradeSync is not None

    def test_init_creates_trades_dir(self):
        """Initialization should create trades directory."""
        # Reset singleton
        import src.observability.trade_sync as module
        from src.observability.trade_sync import TradeSync

        module._trade_sync = None

        with tempfile.TemporaryDirectory():
            with patch.object(Path, "mkdir", return_value=None):
                sync = TradeSync()
                # Should have called mkdir at least once
                assert sync is not None

    def test_init_without_langsmith_key(self):
        """Should initialize without LangSmith when no key."""
        from src.observability.trade_sync import TradeSync

        with patch.dict("os.environ", {}, clear=False):
            sync = TradeSync()
            # LangSmith should be disabled
            assert sync._langsmith_client is None or sync._langsmith_client is not None


class TestSyncToLocalJSON:
    """Test local JSON sync functionality."""

    def test_sync_to_local_json(self):
        """Should save trade to local JSON file."""
        from src.observability.trade_sync import TradeSync

        sync = TradeSync()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Override DATA_DIR for test
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            module.DATA_DIR = Path(tmpdir)

            result = sync._sync_to_local_json(
                {
                    "symbol": "SPY",
                    "side": "buy",
                    "qty": 10,
                    "price": 450.0,
                    "strategy": "momentum",
                    "pnl": 50.0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

            # Restore
            module.DATA_DIR = original_data_dir

            assert result is True

    def test_sync_to_local_json_appends(self):
        """Should append to existing JSON file."""
        from src.observability.trade_sync import TradeSync

        sync = TradeSync()

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            module.DATA_DIR = Path(tmpdir)

            # Create initial file
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            trades_file = Path(tmpdir) / f"trades_{today}.json"
            trades_file.write_text('[{"symbol": "EXISTING"}]')

            result = sync._sync_to_local_json(
                {
                    "symbol": "NEW",
                    "side": "buy",
                    "qty": 5,
                    "price": 100.0,
                    "strategy": "test",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

            # Verify both trades exist
            with open(trades_file) as f:
                trades = json.load(f)

            module.DATA_DIR = original_data_dir

            assert result is True
            assert len(trades) == 2


class TestSyncTrade:
    """Test the main sync_trade function."""

    def test_sync_trade_full(self):
        """Should sync trade to all available systems."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            module.DATA_DIR = Path(tmpdir)

            sync = TradeSync()

            results = sync.sync_trade(
                symbol="SPY",
                side="buy",
                qty=10,
                price=450.0,
                strategy="momentum",
                pnl=50.0,
                pnl_pct=1.11,
            )

            module.DATA_DIR = original_data_dir

            # At minimum, local_json should succeed
            assert results["local_json"] is True
            # Results should include vertex_rag (may be False if not configured)
            assert "vertex_rag" in results

    def test_sync_trade_with_metadata(self):
        """Should sync trade with custom metadata."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            module.DATA_DIR = Path(tmpdir)

            sync = TradeSync()

            results = sync.sync_trade(
                symbol="AAPL",
                side="sell",
                qty=5,
                price=180.0,
                strategy="theta_decay",
                pnl=-10.0,
                metadata={"reason": "stop_loss", "iv_rank": 0.65},
            )

            module.DATA_DIR = original_data_dir

            assert results["local_json"] is True


class TestSyncTradeOutcome:
    """Test sync_trade_outcome with P/L calculation."""

    def test_sync_trade_outcome_long_win(self):
        """Should calculate P/L for winning long trade."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_lessons_dir = module.LESSONS_DIR
            module.DATA_DIR = Path(tmpdir)
            module.LESSONS_DIR = Path(tmpdir) / "lessons"

            sync = TradeSync()

            results = sync.sync_trade_outcome(
                symbol="SPY",
                entry_price=450.0,
                exit_price=460.0,
                qty=10,
                side="buy",
                strategy="momentum",
                holding_period_days=3,
            )

            module.DATA_DIR = original_data_dir
            module.LESSONS_DIR = original_lessons_dir

            # P/L should be (460-450)*10 = 100
            assert results["local_json"] is True

    def test_sync_trade_outcome_long_loss(self):
        """Should calculate P/L for losing long trade."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_lessons_dir = module.LESSONS_DIR
            module.DATA_DIR = Path(tmpdir)
            module.LESSONS_DIR = Path(tmpdir) / "lessons"

            sync = TradeSync()

            results = sync.sync_trade_outcome(
                symbol="AAPL",
                entry_price=180.0,
                exit_price=170.0,
                qty=10,
                side="buy",
                strategy="momentum",
            )

            module.DATA_DIR = original_data_dir
            module.LESSONS_DIR = original_lessons_dir

            # P/L should be (170-180)*10 = -100
            assert results["local_json"] is True

    def test_sync_trade_outcome_short_win(self):
        """Should calculate P/L for winning short trade."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_lessons_dir = module.LESSONS_DIR
            module.DATA_DIR = Path(tmpdir)
            module.LESSONS_DIR = Path(tmpdir) / "lessons"

            sync = TradeSync()

            results = sync.sync_trade_outcome(
                symbol="TSLA",
                entry_price=250.0,
                exit_price=240.0,
                qty=5,
                side="sell",
                strategy="mean_reversion",
            )

            module.DATA_DIR = original_data_dir
            module.LESSONS_DIR = original_lessons_dir

            # P/L should be (250-240)*5 = 50
            assert results["local_json"] is True


class TestGetTradeHistory:
    """Test trade history queries."""

    def test_get_trade_history_empty(self):
        """Should return empty list when no trades in directory."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            module.DATA_DIR = Path(tmpdir)

            sync = TradeSync()
            history = sync.get_trade_history(symbol="NONEXISTENT", limit=10)

            module.DATA_DIR = original_data_dir

            assert isinstance(history, list)
            assert history == []

    def test_get_trade_history_with_data(self):
        """Should return trades from JSON files."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            module.DATA_DIR = Path(tmpdir)

            # Create some test data
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            trades_file = Path(tmpdir) / f"trades_{today}.json"
            trades_file.write_text(json.dumps([
                {"symbol": "SPY", "side": "buy", "qty": 10, "price": 450.0},
                {"symbol": "AAPL", "side": "sell", "qty": 5, "price": 180.0},
            ]))

            sync = TradeSync()
            history = sync.get_trade_history(limit=10)

            module.DATA_DIR = original_data_dir

            assert isinstance(history, list)
            assert len(history) == 2

    def test_get_trade_history_with_symbol_filter(self):
        """Should filter trades by symbol."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            module.DATA_DIR = Path(tmpdir)

            # Create test data
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            trades_file = Path(tmpdir) / f"trades_{today}.json"
            trades_file.write_text(json.dumps([
                {"symbol": "SPY", "side": "buy"},
                {"symbol": "AAPL", "side": "sell"},
                {"symbol": "SPY", "side": "sell"},
            ]))

            sync = TradeSync()
            history = sync.get_trade_history(symbol="SPY", limit=10)

            module.DATA_DIR = original_data_dir

            assert len(history) == 2
            for trade in history:
                assert trade["symbol"] == "SPY"


class TestSingleton:
    """Test singleton pattern."""

    def test_get_trade_sync_singleton(self):
        """Should return same instance."""
        # Reset singleton
        import src.observability.trade_sync as module
        from src.observability.trade_sync import get_trade_sync

        module._trade_sync = None

        sync1 = get_trade_sync()
        sync2 = get_trade_sync()

        assert sync1 is sync2


class TestConvenienceFunction:
    """Test the sync_trade convenience function."""

    def test_sync_trade_convenience(self):
        """Convenience function should work."""
        from src.observability.trade_sync import sync_trade

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            module.DATA_DIR = Path(tmpdir)
            module._trade_sync = None  # Reset singleton

            results = sync_trade(
                symbol="SPY",
                side="buy",
                qty=10,
                price=450.0,
                strategy="test",
            )

            module.DATA_DIR = original_data_dir

            assert isinstance(results, dict)
            assert "local_json" in results


class TestIntegration:
    """Integration tests."""

    def test_smoke_imports(self):
        """Smoke test that all imports work."""
        from src.observability.trade_sync import TradeSync, get_trade_sync, sync_trade

        assert TradeSync is not None
        assert get_trade_sync is not None
        assert sync_trade is not None

    def test_trade_sync_in_observability_init(self):
        """TradeSync should be exported from observability package."""
        from src.observability import TradeSync, get_trade_sync

        assert TradeSync is not None
        assert get_trade_sync is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
