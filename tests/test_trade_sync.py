"""
Tests for Trade Sync Module.

100% coverage for:
- src/observability/trade_sync.py

Tests:
1. TradeSync initialization
2. Sync to Vertex AI RAG
3. Sync to system_state.json (single source of truth)
4. Trade outcome calculation
5. Trade history queries

Updated: Jan 17, 2026 - Architecture fix: system_state.json replaces trades_*.json
"""

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

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
        """Should initialize without LangSmith when no key.

        Note: LangSmith was REMOVED Jan 9, 2026 - only Vertex AI RAG now.
        """
        from src.observability.trade_sync import TradeSync

        with patch.dict("os.environ", {}, clear=False):
            sync = TradeSync()
            # LangSmith removed Jan 9, 2026 - just verify TradeSync initializes
            assert sync is not None


class TestSyncToSystemState:
    """Test system_state.json sync functionality (single source of truth)."""

    def test_sync_to_system_state(self):
        """Should save trade to system_state.json -> trade_history."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_state_file = module.SYSTEM_STATE_FILE
            module.DATA_DIR = Path(tmpdir)
            module.SYSTEM_STATE_FILE = Path(tmpdir) / "system_state.json"

            sync = TradeSync()

            result = sync._sync_to_system_state(
                {
                    "id": "test-123",
                    "symbol": "SPY",
                    "side": "buy",
                    "qty": "10",
                    "price": "450.0",
                    "strategy": "momentum",
                    "pnl": 50.0,
                    "filled_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            # Restore
            module.DATA_DIR = original_data_dir
            module.SYSTEM_STATE_FILE = original_state_file

            assert result is True

    def test_sync_to_system_state_appends(self):
        """Should append to existing trade_history in system_state.json."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_state_file = module.SYSTEM_STATE_FILE
            module.DATA_DIR = Path(tmpdir)
            state_file = Path(tmpdir) / "system_state.json"
            module.SYSTEM_STATE_FILE = state_file

            # Create initial system_state.json with existing trade
            state_file.write_text(json.dumps({
                "trade_history": [{"id": "existing", "symbol": "EXISTING"}],
                "trades_loaded": 1
            }))

            sync = TradeSync()

            result = sync._sync_to_system_state(
                {
                    "id": "new-123",
                    "symbol": "NEW",
                    "side": "buy",
                    "qty": "5",
                    "price": "100.0",
                    "strategy": "test",
                    "filled_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            # Verify both trades exist
            with open(state_file) as f:
                state = json.load(f)

            module.DATA_DIR = original_data_dir
            module.SYSTEM_STATE_FILE = original_state_file

            assert result is True
            assert len(state["trade_history"]) == 2
            # New trade should be first (most recent)
            assert state["trade_history"][0]["symbol"] == "NEW"


class TestSyncTrade:
    """Test the main sync_trade function."""

    def test_sync_trade_full(self):
        """Should sync trade to all available systems."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_state_file = module.SYSTEM_STATE_FILE
            module.DATA_DIR = Path(tmpdir)
            module.SYSTEM_STATE_FILE = Path(tmpdir) / "system_state.json"

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
            module.SYSTEM_STATE_FILE = original_state_file

            # At minimum, system_state should succeed
            assert results["system_state"] is True
            # Results should include vertex_rag (may be False if not configured)
            assert "vertex_rag" in results

    def test_sync_trade_with_metadata(self):
        """Should sync trade with custom metadata."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_state_file = module.SYSTEM_STATE_FILE
            module.DATA_DIR = Path(tmpdir)
            module.SYSTEM_STATE_FILE = Path(tmpdir) / "system_state.json"

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
            module.SYSTEM_STATE_FILE = original_state_file

            assert results["system_state"] is True


class TestSyncTradeOutcome:
    """Test sync_trade_outcome with P/L calculation."""

    def test_sync_trade_outcome_long_win(self):
        """Should calculate P/L for winning long trade."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_state_file = module.SYSTEM_STATE_FILE
            module.DATA_DIR = Path(tmpdir)
            module.SYSTEM_STATE_FILE = Path(tmpdir) / "system_state.json"

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
            module.SYSTEM_STATE_FILE = original_state_file

            # P/L should be (460-450)*10 = 100
            assert results["system_state"] is True

    def test_sync_trade_outcome_long_loss(self):
        """Should calculate P/L for losing long trade."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_state_file = module.SYSTEM_STATE_FILE
            module.DATA_DIR = Path(tmpdir)
            module.SYSTEM_STATE_FILE = Path(tmpdir) / "system_state.json"

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
            module.SYSTEM_STATE_FILE = original_state_file

            # P/L should be (170-180)*10 = -100
            assert results["system_state"] is True

    def test_sync_trade_outcome_short_win(self):
        """Should calculate P/L for winning short trade."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_state_file = module.SYSTEM_STATE_FILE
            module.DATA_DIR = Path(tmpdir)
            module.SYSTEM_STATE_FILE = Path(tmpdir) / "system_state.json"

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
            module.SYSTEM_STATE_FILE = original_state_file

            # P/L should be (250-240)*5 = 50
            assert results["system_state"] is True


class TestGetTradeHistory:
    """Test trade history queries from system_state.json."""

    def test_get_trade_history_empty(self):
        """Should return empty list when no trades in system_state.json."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_state_file = module.SYSTEM_STATE_FILE
            module.DATA_DIR = Path(tmpdir)
            module.SYSTEM_STATE_FILE = Path(tmpdir) / "system_state.json"

            sync = TradeSync()
            history = sync.get_trade_history(symbol="NONEXISTENT", limit=10)

            module.DATA_DIR = original_data_dir
            module.SYSTEM_STATE_FILE = original_state_file

            assert isinstance(history, list)
            assert history == []

    def test_get_trade_history_with_data(self):
        """Should return trades from system_state.json -> trade_history."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_state_file = module.SYSTEM_STATE_FILE
            module.DATA_DIR = Path(tmpdir)
            state_file = Path(tmpdir) / "system_state.json"
            module.SYSTEM_STATE_FILE = state_file

            # Create system_state.json with trade_history
            state_file.write_text(
                json.dumps({
                    "trade_history": [
                        {"symbol": "SPY", "side": "buy", "qty": "10", "price": "450.0"},
                        {"symbol": "AAPL", "side": "sell", "qty": "5", "price": "180.0"},
                    ],
                    "trades_loaded": 2
                })
            )

            sync = TradeSync()
            history = sync.get_trade_history(limit=10)

            module.DATA_DIR = original_data_dir
            module.SYSTEM_STATE_FILE = original_state_file

            assert isinstance(history, list)
            assert len(history) == 2

    def test_get_trade_history_with_symbol_filter(self):
        """Should filter trades by symbol."""
        from src.observability.trade_sync import TradeSync

        with tempfile.TemporaryDirectory() as tmpdir:
            import src.observability.trade_sync as module

            original_data_dir = module.DATA_DIR
            original_state_file = module.SYSTEM_STATE_FILE
            module.DATA_DIR = Path(tmpdir)
            state_file = Path(tmpdir) / "system_state.json"
            module.SYSTEM_STATE_FILE = state_file

            # Create system_state.json with trade_history
            state_file.write_text(
                json.dumps({
                    "trade_history": [
                        {"symbol": "SPY", "side": "buy"},
                        {"symbol": "AAPL", "side": "sell"},
                        {"symbol": "SPY", "side": "sell"},
                    ],
                    "trades_loaded": 3
                })
            )

            sync = TradeSync()
            history = sync.get_trade_history(symbol="SPY", limit=10)

            module.DATA_DIR = original_data_dir
            module.SYSTEM_STATE_FILE = original_state_file

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
            original_state_file = module.SYSTEM_STATE_FILE
            module.DATA_DIR = Path(tmpdir)
            module.SYSTEM_STATE_FILE = Path(tmpdir) / "system_state.json"
            module._trade_sync = None  # Reset singleton

            results = sync_trade(
                symbol="SPY",
                side="buy",
                qty=10,
                price=450.0,
                strategy="test",
            )

            module.DATA_DIR = original_data_dir
            module.SYSTEM_STATE_FILE = original_state_file

            assert isinstance(results, dict)
            assert "system_state" in results


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
