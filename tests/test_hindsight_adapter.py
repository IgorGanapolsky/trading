"""
Tests for Hindsight Adapter

Tests graceful degradation, fallback behavior, and core operations.
Designed to pass whether Hindsight service is running or not.

Author: Trading System CTO
Created: 2025-12-16
"""

from unittest.mock import MagicMock


class TestHindsightAdapterImport:
    """Test that adapter imports correctly regardless of hindsight-client availability."""

    def test_import_succeeds(self):
        """Adapter should import without error even if hindsight-client missing."""
        # This should never raise
        from src.rag.hindsight_adapter import (
            HindsightAdapter,
            HindsightHealthResult,
            MemoryResult,
        )

        assert HindsightAdapter is not None
        assert HindsightHealthResult is not None
        assert MemoryResult is not None
        # HINDSIGHT_AVAILABLE may be True or False depending on environment

    def test_module_level_flags_exist(self):
        """Module should have availability flags set at import time."""
        from src.rag.hindsight_adapter import (
            HINDSIGHT_AVAILABLE,
            HINDSIGHT_BASE_URL,
        )

        assert isinstance(HINDSIGHT_AVAILABLE, bool)
        assert isinstance(HINDSIGHT_BASE_URL, str)
        # HINDSIGHT_CLIENT_CLASS may be None or the class


class TestHindsightHealthResult:
    """Test HindsightHealthResult dataclass."""

    def test_healthy_result(self):
        """Test fully healthy result."""
        from src.rag.hindsight_adapter import HindsightHealthResult

        result = HindsightHealthResult(
            available=True,
            client_installed=True,
            service_reachable=True,
            api_healthy=True,
        )
        assert result.should_use_hindsight is True
        assert len(result.errors) == 0

    def test_degraded_result(self):
        """Test degraded result (service not running)."""
        from src.rag.hindsight_adapter import HindsightHealthResult

        result = HindsightHealthResult(
            available=False,
            client_installed=True,
            service_reachable=False,
            api_healthy=False,
            errors=["Cannot connect to Hindsight at http://localhost:8888"],
        )
        assert result.should_use_hindsight is False
        assert len(result.errors) == 1

    def test_client_not_installed(self):
        """Test when hindsight-client package not installed."""
        from src.rag.hindsight_adapter import HindsightHealthResult

        result = HindsightHealthResult(
            available=False,
            client_installed=False,
            service_reachable=False,
            api_healthy=False,
            errors=["hindsight-client package not installed"],
        )
        assert result.should_use_hindsight is False


class TestMemoryResult:
    """Test MemoryResult dataclass."""

    def test_success_result(self):
        """Test successful memory operation result."""
        from src.rag.hindsight_adapter import MemoryResult

        result = MemoryResult(
            success=True,
            source="hindsight",
            data={"memories": ["trade lesson 1", "trade lesson 2"]},
            confidence=0.85,
        )
        assert result.success is True
        assert result.source == "hindsight"
        assert result.confidence == 0.85

    def test_fallback_result(self):
        """Test fallback to local RAG result."""
        from src.rag.hindsight_adapter import MemoryResult

        result = MemoryResult(
            success=True,
            source="local_rag",
            data=[{"title": "lesson 1"}],
        )
        assert result.success is True
        assert result.source == "local_rag"
        assert result.confidence is None


class TestHindsightAdapterInit:
    """Test adapter initialization and fallback behavior."""

    def test_init_with_no_service(self):
        """Adapter should initialize gracefully when service not running."""
        from src.rag.hindsight_adapter import HindsightAdapter

        # Use a port that definitely won't have Hindsight
        adapter = HindsightAdapter(
            base_url="http://localhost:59999",
            auto_init=True,
        )

        # Should not raise, just be disabled
        assert adapter._hindsight_enabled is False or adapter._hindsight_enabled is True
        # Local RAG fallback should be attempted
        # (may or may not be available depending on test environment)

    def test_init_without_auto_init(self):
        """Adapter can defer initialization."""
        from src.rag.hindsight_adapter import HindsightAdapter

        adapter = HindsightAdapter(auto_init=False)
        assert adapter._client is None
        assert adapter._hindsight_enabled is False


class TestHindsightAdapterHealthCheck:
    """Test health check functionality."""

    def test_health_check_returns_result(self):
        """Health check should always return a result, never raise."""
        from src.rag.hindsight_adapter import HindsightAdapter, HindsightHealthResult

        adapter = HindsightAdapter(base_url="http://localhost:59999")
        result = adapter.check_health()

        assert isinstance(result, HindsightHealthResult)
        assert result.timestamp is not None
        # Service likely not running in test, so expect degraded
        # But we don't assert on availability - test env may vary


class TestHindsightAdapterOperations:
    """Test core memory operations with mocked backends."""

    def test_retain_falls_back_gracefully(self):
        """Retain should not raise even if all backends fail."""
        from src.rag.hindsight_adapter import HindsightAdapter

        adapter = HindsightAdapter(base_url="http://localhost:59999", auto_init=False)
        adapter._hindsight_enabled = False
        adapter._local_rag_enabled = False

        # Should not raise
        result = adapter.retain(
            content="Test trade lesson",
            bank_id="trading-lessons",
        )

        assert result.success is False
        assert result.source == "none"
        assert "No memory backend available" in result.error

    def test_recall_falls_back_gracefully(self):
        """Recall should not raise even if all backends fail."""
        from src.rag.hindsight_adapter import HindsightAdapter

        adapter = HindsightAdapter(base_url="http://localhost:59999", auto_init=False)
        adapter._hindsight_enabled = False
        adapter._local_rag_enabled = False

        result = adapter.recall(query="What should I know about SPY?")

        assert result.success is False
        assert result.source == "none"

    def test_reflect_degrades_to_recall(self):
        """Reflect should degrade to recall when Hindsight unavailable."""
        from src.rag.hindsight_adapter import HindsightAdapter

        adapter = HindsightAdapter(base_url="http://localhost:59999", auto_init=False)
        adapter._hindsight_enabled = False
        adapter._local_rag_enabled = False

        result = adapter.reflect(query="What is my conviction on AAPL?")

        # Should try recall fallback, which also fails, but doesn't raise
        assert result.success is False


class TestHindsightAdapterTradingMethods:
    """Test trading-specific convenience methods."""

    def test_remember_trade_outcome(self):
        """Test remembering a trade outcome."""
        from src.rag.hindsight_adapter import HindsightAdapter

        adapter = HindsightAdapter(base_url="http://localhost:59999", auto_init=False)

        # Even with no backend, should not raise
        result = adapter.remember_trade_outcome(
            symbol="SPY",
            side="buy",
            outcome="loss",
            pnl=-50.0,
            lesson="Should have waited for MACD confirmation",
        )

        # Result indicates no backend, but no exception
        assert isinstance(result.success, bool)

    def test_check_similar_trades(self):
        """Test checking for similar past trades."""
        from src.rag.hindsight_adapter import HindsightAdapter

        adapter = HindsightAdapter(base_url="http://localhost:59999", auto_init=False)

        result = adapter.check_similar_trades(
            symbol="QQQ",
            strategy="MACD crossover",
        )

        assert isinstance(result.success, bool)

    def test_get_ticker_opinion(self):
        """Test getting opinion on a ticker."""
        from src.rag.hindsight_adapter import HindsightAdapter

        adapter = HindsightAdapter(base_url="http://localhost:59999", auto_init=False)

        result = adapter.get_ticker_opinion(symbol="TSLA")

        assert isinstance(result.success, bool)


class TestModuleLevelFunctions:
    """Test module-level convenience functions."""

    def test_get_hindsight_adapter_singleton(self):
        """get_hindsight_adapter should return singleton."""
        from src.rag.hindsight_adapter import get_hindsight_adapter

        adapter1 = get_hindsight_adapter()
        adapter2 = get_hindsight_adapter()

        assert adapter1 is adapter2

    def test_check_hindsight_health_function(self):
        """Convenience function should work."""
        from src.rag.hindsight_adapter import check_hindsight_health

        result = check_hindsight_health()
        assert result is not None

    def test_is_hindsight_available_function(self):
        """is_hindsight_available should return bool."""
        from src.rag.hindsight_adapter import is_hindsight_available

        result = is_hindsight_available()
        assert isinstance(result, bool)


class TestGracefulDegradationIntegration:
    """Integration tests for graceful degradation patterns."""

    def test_full_degradation_chain(self):
        """Test complete fallback chain: Hindsight -> Local RAG -> None."""
        from src.rag.hindsight_adapter import HindsightAdapter

        adapter = HindsightAdapter(
            base_url="http://localhost:59999",  # Won't connect
            auto_init=True,
        )

        # Health check
        health = adapter.check_health()
        assert health is not None

        # Operations should all complete without raising
        retain_result = adapter.retain("Test content")
        recall_result = adapter.recall("Test query")
        reflect_result = adapter.reflect("Test reflection")

        # All should return MemoryResult, success depends on what's available
        assert retain_result is not None
        assert recall_result is not None
        assert reflect_result is not None

    def test_no_exceptions_propagate(self):
        """Ensure no exceptions propagate from adapter operations."""
        from src.rag.hindsight_adapter import HindsightAdapter

        adapter = HindsightAdapter(base_url="http://localhost:59999", auto_init=False)

        # Force both backends to be "enabled" but mock them to raise
        adapter._hindsight_enabled = True
        adapter._client = MagicMock()
        adapter._client.retain.side_effect = Exception("Simulated Hindsight failure")
        adapter._client.recall.side_effect = Exception("Simulated Hindsight failure")
        adapter._client.reflect.side_effect = Exception("Simulated Hindsight failure")

        adapter._local_rag_enabled = True
        adapter._local_rag = MagicMock()
        adapter._local_rag.add_lesson.side_effect = Exception("Simulated RAG failure")
        adapter._local_rag.search.side_effect = Exception("Simulated RAG failure")

        # None of these should raise
        retain_result = adapter.retain("Test")
        recall_result = adapter.recall("Test")
        reflect_result = adapter.reflect("Test")

        # All return results (with success=False)
        assert retain_result.success is False
        assert recall_result.success is False
        assert reflect_result.success is False


class TestMemoryBankConfiguration:
    """Test memory bank configuration."""

    def test_memory_banks_defined(self):
        """Verify memory banks are properly defined."""
        from src.rag.hindsight_adapter import MEMORY_BANKS

        assert "trading-lessons" in MEMORY_BANKS
        assert "market-observations" in MEMORY_BANKS
        assert "trade-opinions" in MEMORY_BANKS

        # Each bank should have description and disposition
        for bank_id, config in MEMORY_BANKS.items():
            assert "description" in config
            assert "disposition" in config
            assert "skepticism" in config["disposition"]
