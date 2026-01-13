#!/usr/bin/env python3
"""
Smoke tests for Vertex AI RAG module.

These tests verify:
1. Module imports successfully
2. Key classes/functions exist
3. Basic instantiation with mocked dependencies

Created: Jan 13, 2026
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestVertexRAGImports:
    """Test that vertex_rag module imports correctly."""

    def test_module_imports(self):
        """Should import vertex_rag module without errors."""
        from src.rag import vertex_rag

        assert vertex_rag is not None

    def test_vertexrag_class_exists(self):
        """Should have VertexRAG class."""
        from src.rag.vertex_rag import VertexRAG

        assert VertexRAG is not None
        assert callable(VertexRAG)

    def test_get_vertex_rag_function_exists(self):
        """Should have get_vertex_rag function."""
        from src.rag.vertex_rag import get_vertex_rag

        assert get_vertex_rag is not None
        assert callable(get_vertex_rag)

    def test_constants_defined(self):
        """Should have configuration constants defined."""
        from src.rag.vertex_rag import (
            CHUNK_OVERLAP,
            CHUNK_SIZE,
            EMBEDDING_MODEL,
            RAG_CORPUS_DESCRIPTION,
            RAG_CORPUS_DISPLAY_NAME,
            SIMILARITY_TOP_K,
        )

        assert RAG_CORPUS_DISPLAY_NAME == "trading-system-rag"
        assert RAG_CORPUS_DESCRIPTION is not None
        assert EMBEDDING_MODEL is not None
        assert CHUNK_SIZE == 512
        assert CHUNK_OVERLAP == 100
        assert SIMILARITY_TOP_K == 5


class TestVertexRAGInstantiation:
    """Test VertexRAG class instantiation."""

    def test_init_without_project_id(self):
        """Should handle missing project ID gracefully."""
        # Clear any project ID env vars
        env_overrides = {
            "GOOGLE_CLOUD_PROJECT": "",
            "GCP_PROJECT_ID": "",
            "GCLOUD_PROJECT": "",
            "GCP_SA_KEY": "",
            "GOOGLE_APPLICATION_CREDENTIALS": "",
        }

        with patch.dict(os.environ, env_overrides, clear=False):
            # Also clear these if they exist
            for key in ["GOOGLE_CLOUD_PROJECT", "GCP_PROJECT_ID", "GCLOUD_PROJECT"]:
                os.environ.pop(key, None)

            from src.rag.vertex_rag import VertexRAG

            # Should not raise, just not initialize
            rag = VertexRAG()
            assert rag.is_initialized is False

    def test_class_has_expected_methods(self):
        """Should have expected public methods."""
        from src.rag.vertex_rag import VertexRAG

        # Check class has methods (not calling them)
        assert hasattr(VertexRAG, "add_trade")
        assert hasattr(VertexRAG, "add_lesson")
        assert hasattr(VertexRAG, "query")
        assert hasattr(VertexRAG, "is_initialized")

    def test_class_has_private_methods(self):
        """Should have expected private methods."""
        from src.rag.vertex_rag import VertexRAG

        assert hasattr(VertexRAG, "_get_project_id")
        assert hasattr(VertexRAG, "_init_vertex_rag")
        assert hasattr(VertexRAG, "_get_or_create_corpus")


class TestVertexRAGMethodSignatures:
    """Test method signatures without actually calling external APIs."""

    def test_add_trade_signature(self):
        """Should accept expected parameters for add_trade."""
        from src.rag.vertex_rag import VertexRAG

        # Clear env to get uninitialized instance
        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": ""}, clear=False):
            os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
            os.environ.pop("GCP_PROJECT_ID", None)

            rag = VertexRAG()

            # Should return False when not initialized (no API call made)
            result = rag.add_trade(
                symbol="SPY",
                side="buy",
                qty=10.0,
                price=450.0,
                strategy="test",
                pnl=100.0,
                pnl_pct=2.5,
            )
            assert result is False  # Not initialized

    def test_add_lesson_signature(self):
        """Should accept expected parameters for add_lesson."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": ""}, clear=False):
            os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
            os.environ.pop("GCP_PROJECT_ID", None)

            rag = VertexRAG()

            result = rag.add_lesson(
                lesson_id="LL-001",
                title="Test Lesson",
                content="Test content",
                severity="MEDIUM",
                category="trading",
            )
            assert result is False  # Not initialized

    def test_query_signature(self):
        """Should accept expected parameters for query."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": ""}, clear=False):
            os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
            os.environ.pop("GCP_PROJECT_ID", None)

            rag = VertexRAG()

            result = rag.query(
                query_text="What trades did I make today?",
                similarity_top_k=5,
                vector_distance_threshold=0.7,
            )
            assert result == []  # Not initialized, returns empty list


class TestGetVertexRAGSingleton:
    """Test get_vertex_rag singleton function."""

    def test_returns_vertexrag_instance(self):
        """Should return a VertexRAG instance."""
        # Reset the singleton for this test
        import src.rag.vertex_rag as vr_module

        vr_module._vertex_rag = None

        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": ""}, clear=False):
            os.environ.pop("GOOGLE_CLOUD_PROJECT", None)

            from src.rag.vertex_rag import VertexRAG, get_vertex_rag

            result = get_vertex_rag()
            assert isinstance(result, VertexRAG)

    def test_returns_same_instance(self):
        """Should return the same instance on multiple calls (singleton)."""
        import src.rag.vertex_rag as vr_module

        vr_module._vertex_rag = None

        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": ""}, clear=False):
            os.environ.pop("GOOGLE_CLOUD_PROJECT", None)

            from src.rag.vertex_rag import get_vertex_rag

            instance1 = get_vertex_rag()
            instance2 = get_vertex_rag()
            assert instance1 is instance2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
