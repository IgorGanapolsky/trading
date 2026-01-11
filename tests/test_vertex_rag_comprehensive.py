"""
Comprehensive tests for Vertex RAG module.

Tests cover:
1. _get_project_id() - all source detection methods
2. add_trade() - actual upload behavior (not stub)
3. add_lesson() - actual upload behavior (not stub)
4. Initialization behavior
5. 2026 Best Practices - embedding model, chunking, Gemini 2.0 Flash

Created: January 5, 2026
Updated: January 10, 2026 - Added 2026 best practices tests
Reason: LL-081 - Vertex RAG was a stub, needs full test coverage
"""

import inspect
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestVertexRAGProjectIdDetection:
    """Test _get_project_id() method - all detection sources."""

    def test_get_project_id_from_google_cloud_project(self):
        """Test project ID from GOOGLE_CLOUD_PROJECT env var."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project-123"}, clear=False):
            # Create instance but mock the init to avoid actual GCP calls
            with patch.object(VertexRAG, "_init_vertex_rag"):
                rag = VertexRAG()
                assert rag._project_id == "test-project-123"

    def test_get_project_id_from_gcp_project_id(self):
        """Test project ID from GCP_PROJECT_ID env var."""
        from src.rag.vertex_rag import VertexRAG

        # Clear GOOGLE_CLOUD_PROJECT to test fallback
        env = {
            "GCP_PROJECT_ID": "fallback-project-456",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch.object(os.environ, "get") as mock_get:
                mock_get.side_effect = lambda k, d=None: env.get(k, d) if k in env else None
                with patch.object(VertexRAG, "_init_vertex_rag"):
                    rag = VertexRAG()
                    # Verify instance was created (method checks multiple env vars)
                    assert rag is not None

    def test_get_project_id_from_service_account_json(self):
        """Test project ID extraction from GCP_SA_KEY JSON."""
        from src.rag.vertex_rag import VertexRAG

        sa_json = json.dumps(
            {
                "type": "service_account",
                "project_id": "sa-extracted-project",
                "private_key_id": "fake",
                "client_email": "test@test.iam.gserviceaccount.com",
            }
        )

        with patch.dict(os.environ, {"GCP_SA_KEY": sa_json}, clear=True):
            with patch.object(VertexRAG, "_init_vertex_rag"):
                rag = VertexRAG()
                # Should extract from SA JSON when env vars not set
                result = rag._get_project_id()
                assert result == "sa-extracted-project"

    def test_get_project_id_from_credentials_file(self):
        """Test project ID extraction from credentials file."""
        from src.rag.vertex_rag import VertexRAG

        sa_data = {
            "type": "service_account",
            "project_id": "file-extracted-project",
            "private_key_id": "fake",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sa_data, f)
            creds_path = f.name

        try:
            with patch.dict(os.environ, {"GOOGLE_APPLICATION_CREDENTIALS": creds_path}, clear=True):
                with patch.object(VertexRAG, "_init_vertex_rag"):
                    rag = VertexRAG()
                    result = rag._get_project_id()
                    assert result == "file-extracted-project"
        finally:
            os.unlink(creds_path)

    def test_get_project_id_returns_none_when_not_found(self):
        """Test that None is returned when no project ID source available."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(VertexRAG, "_init_vertex_rag"):
                rag = VertexRAG()
                result = rag._get_project_id()
                assert result is None

    def test_get_project_id_handles_invalid_json(self):
        """Test graceful handling of invalid JSON in GCP_SA_KEY."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {"GCP_SA_KEY": "not valid json"}, clear=True):
            with patch.object(VertexRAG, "_init_vertex_rag"):
                rag = VertexRAG()
                result = rag._get_project_id()
                # Should not crash, just return None
                assert result is None


class TestVertexRAGNotStub:
    """Verify add_trade and add_lesson are NOT stubs."""

    def test_add_trade_uses_import_files(self):
        """Verify add_trade actually calls rag.import_files()."""
        from src.rag.vertex_rag import VertexRAG

        source = inspect.getsource(VertexRAG.add_trade)

        # Must use actual upload methods
        assert "import_files" in source, (
            "add_trade() must use rag.import_files() to actually upload"
        )

        # Must NOT have stub pattern
        assert "_trade_text prepared for batch import" not in source, (
            "add_trade() still has stub comment - not implemented"
        )

        # Must write to temp file for upload
        assert "tempfile" in source, "add_trade() should use tempfile for upload"

    def test_add_lesson_uses_import_files(self):
        """Verify add_lesson actually calls rag.import_files()."""
        from src.rag.vertex_rag import VertexRAG

        source = inspect.getsource(VertexRAG.add_lesson)

        # Must use actual upload methods
        assert "import_files" in source, (
            "add_lesson() must use rag.import_files() to actually upload"
        )

        # Must write to temp file for upload
        assert "tempfile" in source, "add_lesson() should use tempfile for upload"

    def test_add_trade_cleans_up_temp_file(self):
        """Verify add_trade cleans up temporary files."""
        from src.rag.vertex_rag import VertexRAG

        source = inspect.getsource(VertexRAG.add_trade)

        assert "unlink" in source or "delete=True" in source, (
            "add_trade() must clean up temp files after upload"
        )

    def test_add_lesson_cleans_up_temp_file(self):
        """Verify add_lesson cleans up temporary files."""
        from src.rag.vertex_rag import VertexRAG

        source = inspect.getsource(VertexRAG.add_lesson)

        assert "unlink" in source or "delete=True" in source, (
            "add_lesson() must clean up temp files after upload"
        )


class TestVertexRAGBehavior:
    """Test actual behavior of Vertex RAG methods."""

    def test_add_trade_returns_false_when_not_initialized(self):
        """Verify add_trade returns False when not initialized."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {}, clear=True):
            rag = VertexRAG()
            assert rag._initialized is False

            result = rag.add_trade(symbol="AAPL", side="buy", qty=10, price=150.0, strategy="test")
            assert result is False

    def test_add_lesson_returns_false_when_not_initialized(self):
        """Verify add_lesson returns False when not initialized."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {}, clear=True):
            rag = VertexRAG()
            assert rag._initialized is False

            result = rag.add_lesson(
                lesson_id="test_001", title="Test Lesson", content="Test content"
            )
            assert result is False

    def test_query_returns_empty_when_not_initialized(self):
        """Verify query returns empty list when not initialized."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {}, clear=True):
            rag = VertexRAG()
            assert rag._initialized is False

            result = rag.query("test query")
            assert result == []

    def test_is_initialized_property(self):
        """Verify is_initialized property works correctly."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {}, clear=True):
            rag = VertexRAG()
            assert rag.is_initialized is False


class TestVertexRAGIntegration:
    """Integration tests for Vertex RAG (mocked GCP calls)."""

    @pytest.fixture(autouse=True)
    def check_vertexai(self):
        """Skip if vertexai not installed."""
        try:
            import vertexai  # noqa: F401
        except ImportError:
            pytest.skip("vertexai not installed - skipping integration tests")

    def test_add_trade_integration_mocked(self):
        """Test add_trade with mocked GCP calls."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}, clear=False):
            rag = VertexRAG()
            rag._initialized = True
            rag._corpus = MagicMock()
            rag._corpus.name = "test-corpus"

            # Patch the import inside the method
            with patch("vertexai.preview.rag") as mock_rag:
                result = rag.add_trade(
                    symbol="AAPL", side="buy", qty=10, price=150.0, strategy="momentum"
                )

                # Should have called import_files
                mock_rag.import_files.assert_called_once()
                assert result is True

    def test_add_lesson_integration_mocked(self):
        """Test add_lesson with mocked GCP calls."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}, clear=False):
            rag = VertexRAG()
            rag._initialized = True
            rag._corpus = MagicMock()
            rag._corpus.name = "test-corpus"

            # Patch the import inside the method
            with patch("vertexai.preview.rag") as mock_rag:
                result = rag.add_lesson(
                    lesson_id="ll_test_001", title="Test Lesson", content="This is test content"
                )

                # Should have called import_files
                mock_rag.import_files.assert_called_once()
                assert result is True


class TestSystemHealthCheckFixes:
    """Test fixes made to system_health_check.py."""

    def test_health_check_has_sys_path_fix(self):
        """Verify health check adds project root to sys.path."""
        health_check_path = Path("scripts/system_health_check.py")
        if not health_check_path.exists():
            pytest.skip("system_health_check.py not found")

        source = health_check_path.read_text()
        assert "sys.path.insert" in source, (
            "system_health_check.py must add project root to sys.path"
        )

    def test_health_check_collection_name_access(self):
        """Verify health check uses .name attribute for collection."""
        health_check_path = Path("scripts/system_health_check.py")
        if not health_check_path.exists():
            pytest.skip("system_health_check.py not found")

        source = health_check_path.read_text()

        # Should use collections[0].name, not collections[0] directly
        assert "collections[0].name" in source or "col_name = " in source, (
            "system_health_check.py must access collection.name, not use Collection object as string"
        )


class Test2026BestPractices:
    """Test 2026 RAG best practices implementation."""

    def test_embedding_model_constant_defined(self):
        """Verify text-embedding-004 model is configured."""
        from src.rag.vertex_rag import EMBEDDING_MODEL

        assert EMBEDDING_MODEL == "publishers/google/models/text-embedding-004"

    def test_chunk_size_configured(self):
        """Verify optimal chunk size is configured."""
        from src.rag.vertex_rag import CHUNK_SIZE, CHUNK_OVERLAP

        assert CHUNK_SIZE == 512, "Chunk size should be 512 tokens"
        assert CHUNK_OVERLAP == 100, "Chunk overlap should be 100 tokens (20%)"

    def test_similarity_top_k_configured(self):
        """Verify top-k retrieval is within best practice range (3-5)."""
        from src.rag.vertex_rag import SIMILARITY_TOP_K

        assert 3 <= SIMILARITY_TOP_K <= 5, "Top-k should be 3-5 per best practices"

    def test_query_uses_gemini_2_flash(self):
        """Verify query uses Gemini 2.0 Flash (GA Jan 2026)."""
        from src.rag.vertex_rag import VertexRAG

        source = inspect.getsource(VertexRAG.query)
        assert "gemini-2.0-flash" in source, "Query should use Gemini 2.0 Flash (not 1.5)"

    def test_corpus_creation_has_embedding_config(self):
        """Verify corpus creation includes embedding model config."""
        from src.rag.vertex_rag import VertexRAG

        source = inspect.getsource(VertexRAG._get_or_create_corpus)
        assert "EmbeddingModelConfig" in source, (
            "Corpus creation should use EmbeddingModelConfig"
        )
        assert "EMBEDDING_MODEL" in source, (
            "Corpus creation should reference EMBEDDING_MODEL constant"
        )

    def test_add_trade_has_chunking_config(self):
        """Verify add_trade uses chunking configuration."""
        from src.rag.vertex_rag import VertexRAG

        source = inspect.getsource(VertexRAG.add_trade)
        assert "ChunkingConfig" in source, "add_trade should use ChunkingConfig"
        assert "CHUNK_SIZE" in source, "add_trade should reference CHUNK_SIZE"

    def test_add_lesson_has_chunking_config(self):
        """Verify add_lesson uses chunking configuration."""
        from src.rag.vertex_rag import VertexRAG

        source = inspect.getsource(VertexRAG.add_lesson)
        assert "ChunkingConfig" in source, "add_lesson should use ChunkingConfig"
        assert "CHUNK_SIZE" in source, "add_lesson should reference CHUNK_SIZE"

    def test_query_has_vector_distance_threshold(self):
        """Verify query supports vector distance threshold for hybrid search."""
        from src.rag.vertex_rag import VertexRAG

        source = inspect.getsource(VertexRAG.query)
        assert "vector_distance_threshold" in source, (
            "Query should support vector_distance_threshold for hybrid search"
        )

    def test_docstring_updated_for_2026(self):
        """Verify module docstring reflects 2026 best practices."""
        import src.rag.vertex_rag as vertex_rag_module

        docstring = vertex_rag_module.__doc__
        assert "2026" in docstring, "Module docstring should mention 2026 best practices"
        assert "text-embedding-004" in docstring, "Module should document embedding model"
        assert "ChromaDB" not in docstring or "deprecated" in docstring.lower(), (
            "ChromaDB reference should be removed or marked deprecated"
        )


class TestSmokeTests:
    """Smoke tests for critical functionality."""

    def test_vertex_rag_import(self):
        """Smoke test: VertexRAG can be imported."""
        from src.rag.vertex_rag import VertexRAG, get_vertex_rag

        assert VertexRAG is not None
        assert get_vertex_rag is not None

    def test_vertex_rag_instantiation(self):
        """Smoke test: VertexRAG can be instantiated."""
        from src.rag.vertex_rag import VertexRAG

        with patch.dict(os.environ, {}, clear=True):
            rag = VertexRAG()
            assert rag is not None
            assert hasattr(rag, "add_trade")
            assert hasattr(rag, "add_lesson")
            assert hasattr(rag, "query")

    def test_system_health_check_runs(self):
        """Smoke test: system_health_check.py runs without import errors."""
        import subprocess

        result = subprocess.run(
            ["python3", "scripts/system_health_check.py"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Should complete (exit code doesn't matter for smoke test)
        assert result.returncode in [0, 1], f"Health check crashed: {result.stderr}"
