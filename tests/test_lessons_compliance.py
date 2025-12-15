import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.verify_against_lessons import get_keywords_from_path, query_lessons


class TestLessonsCompliance:
    """Test the Lessons Learned verification system."""

    def test_keywords_extraction(self):
        """Test that keywords are correctly extracted from paths."""
        assert "alpaca_executor execution python" in get_keywords_from_path("src/execution/alpaca_executor.py")
        assert "main orchestrator python" in get_keywords_from_path("src/orchestrator/main.py")

    def test_query_lessons_rag(self):
        """Test querying lessons using RAG mock."""
        # Create a mock module for src.rag.unified_rag
        mock_module = MagicMock()
        mock_module.CHROMA_AVAILABLE = True
        mock_instance = MagicMock()
        mock_module.UnifiedRAG.return_value = mock_instance

        # Mock results
        mock_instance.query_lessons.return_value = {
            "documents": [["Don't divide by zero in Sharpe ratio"]],
            "metadatas": [[{"severity": "critical", "source": "ll_001.md"}]],
            "ids": [["123"]]
        }

        # Apply the patch to sys.modules
        with patch.dict(sys.modules, {"src.rag.unified_rag": mock_module}):
            # We also need to ensure the function re-imports or uses the patched module
            # Since the import is inside the function query_lessons, it should pick up the mock from sys.modules

            results = query_lessons("sharpe ratio")

            assert len(results) == 1
            assert "Don't divide by zero" in results[0]["content"]
            assert results[0]["metadata"]["severity"] == "critical"

    def test_verify_script_integration(self):
        """Test the verification script runs via subprocess."""
        import subprocess

        # Run the script on itself (safe test)
        # We need to use sys.executable to ensure we use the same python env
        result = subprocess.run(
            [sys.executable, "scripts/verify_against_lessons.py", "scripts/verify_against_lessons.py"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "Checking" in result.stderr or "Checking" in result.stdout
