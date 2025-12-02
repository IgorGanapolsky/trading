"""
Test that embedder can be imported without sentence_transformers installed.

This test verifies that the lazy import fix works correctly.
"""

from unittest.mock import patch

import pytest


def test_embedder_import_without_sentence_transformers():
    """Test that embedder module can be imported without sentence_transformers."""
    # Mock the import to simulate missing sentence_transformers
    with patch.dict("sys.modules", {"sentence_transformers": None}):
        # Should be able to import the module
        from src.rag.vector_db import embedder

        # But trying to get embedder should raise ImportError
        with pytest.raises(ImportError):
            embedder._get_sentence_transformer()


def test_embedder_import_with_sentence_transformers():
    """Test that embedder works when sentence_transformers is available."""
    try:
        import sentence_transformers  # noqa: F401

        # If available, test that it works
        from src.rag.vector_db.embedder import NewsEmbedder

        # Should be able to create embedder
        embedder = NewsEmbedder()
        assert embedder is not None
        assert embedder.get_dimensions() > 0
    except ImportError:
        pytest.skip("sentence-transformers not installed - skipping test")


def test_deepagents_tools_import_without_rag():
    """Test that deepagents tools can be imported without RAG dependencies."""
    try:
        # Should be able to import the module (may fail if langchain not installed, that's ok)
        from src.deepagents_integration import tools

        # _get_sentiment_store should return None when RAG not available
        with patch("src.deepagents_integration.tools._get_sentiment_store", return_value=None):
            # Should handle gracefully
            result = tools.query_sentiment("test query")
            assert "error" in result.lower() or "not available" in result.lower()
    except ImportError:
        pytest.skip("langchain_core not installed - skipping test")


def test_crypto_strategy_imports_without_rag():
    """Test that crypto strategy can be imported without RAG dependencies."""
    # This should work even if RAG dependencies aren't installed
    from src.strategies.crypto_strategy import CryptoStrategy

    # Should be able to create instance
    strategy = CryptoStrategy(daily_amount=0.50)
    assert strategy is not None
    assert strategy.daily_amount == 0.50
