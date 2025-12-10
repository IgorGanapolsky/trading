"""
Pytest tests for crypto trading without RAG dependencies.

These tests verify that crypto trading can run without requiring
sentence-transformers or other RAG dependencies.
"""

import sys
from unittest.mock import patch

import pytest


class TestCryptoTradingImports:
    """Test that crypto trading imports work without RAG dependencies."""

    def test_embedder_import_without_sentence_transformers(self):
        """Test that embedder can be imported without sentence_transformers."""
        # Should be able to import the module
        from src.rag.vector_db import embedder

        # But trying to get embedder should raise ImportError
        try:
            import sentence_transformers  # noqa: F401

            pytest.skip("sentence-transformers installed - skipping missing dependency test")
        except ImportError:
            with pytest.raises(ImportError, match="sentence-transformers"):
                embedder._get_sentence_transformer()

    def test_autonomous_trader_imports(self):
        """Test that autonomous_trader can be imported."""
        from scripts.autonomous_trader import is_weekend

        # Should be able to call is_weekend
        result = is_weekend()
        assert isinstance(result, bool)

    def test_crypto_strategy_imports(self):
        """Test that crypto strategy can be imported."""
        from src.strategies.crypto_strategy import CryptoStrategy

        # Should be able to create instance
        strategy = CryptoStrategy(daily_amount=0.50)
        assert strategy.daily_amount == 0.50

    def test_sentiment_store_not_imported(self):
        """Test that sentiment_store is NOT imported during crypto trading."""
        # Clear any existing imports
        modules_before = set(sys.modules.keys())

        # Import crypto trading components
        from scripts.autonomous_trader import execute_crypto_trading  # noqa: F401
        from src.strategies.crypto_strategy import CryptoStrategy  # noqa: F401

        # Check if sentiment_store was imported
        modules_after = set(sys.modules.keys())
        new_modules = modules_after - modules_before

        # sentiment_store should NOT be in new modules
        sentiment_modules = [m for m in new_modules if "sentiment_store" in m]
        assert len(sentiment_modules) == 0, f"sentiment_store was imported: {sentiment_modules}"

    def test_deepagents_tools_lazy_import(self):
        """Test that deepagents tools handle missing RAG gracefully."""
        try:
            from src.deepagents_integration import tools

            # _get_sentiment_store should exist
            assert hasattr(tools, "_get_sentiment_store")

            # Should return None when RAG not available
            with patch(
                "src.deepagents_integration.tools._get_sentiment_store",
                return_value=None,
            ):
                result = tools.query_sentiment("test query")
                assert "error" in result.lower() or "not available" in result.lower()
        except ImportError:
            # langchain might not be installed, that's ok
            pytest.skip("langchain not installed - skipping test")


class TestCryptoTradingWorkflow:
    """Test crypto trading workflow integration."""

    def test_import_chain_no_rag(self):
        """Test the full import chain without RAG dependencies."""
        # This simulates what happens in GitHub Actions
        from scripts.autonomous_trader import execute_crypto_trading
        from src.core.risk_manager import RiskManager
        from src.strategies.crypto_strategy import CryptoStrategy

        # All should import successfully
        assert execute_crypto_trading is not None
        assert CryptoStrategy is not None
        assert RiskManager is not None

    def test_crypto_strategy_initialization(self):
        """Test that CryptoStrategy can be initialized without RAG."""
        from src.strategies.crypto_strategy import CryptoStrategy

        # Should work without any RAG dependencies
        strategy = CryptoStrategy(daily_amount=0.50)
        assert strategy.daily_amount == 0.50
        assert strategy.crypto_universe == ["BTCUSD", "ETHUSD", "SOLUSD"]
