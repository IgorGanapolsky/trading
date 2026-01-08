"""
Test that ChromaDB has been properly removed from workflows.

Created: Jan 8, 2026
Purpose: Verify ChromaDB removal fix (PR for 2-day trading gap)

This test ensures:
1. No active ChromaDB imports in daily-trading.yml
2. No ChromaDB pip install in critical workflows
3. Vectorization scripts don't depend on ChromaDB
"""

import re
from pathlib import Path

import pytest


def read_file(path: str) -> str:
    """Read file contents."""
    return Path(path).read_text()


class TestChromaDBRemoved:
    """Verify ChromaDB has been removed from all critical paths."""

    def test_daily_trading_no_chromadb_import(self):
        """daily-trading.yml should not try to import chromadb."""
        content = read_file(".github/workflows/daily-trading.yml")

        # Should NOT have active chromadb import (only comments allowed)
        # Look for: python3 -c "import chromadb" (active import)
        active_import_pattern = r'python3.*-c.*["\']import chromadb'
        matches = re.findall(active_import_pattern, content)

        assert len(matches) == 0, (
            f"Found active chromadb import in daily-trading.yml: {matches}\n"
            "ChromaDB was removed Jan 7, 2026 - this will cause workflow failures!"
        )

    def test_daily_trading_no_chromadb_pip_install(self):
        """daily-trading.yml should not pip install chromadb."""
        content = read_file(".github/workflows/daily-trading.yml")

        # Check for pip install chromadb (should be removed or commented)
        if "pip install" in content and "chromadb" in content:
            # Make sure it's commented out
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "chromadb" in line.lower() and "pip install" in line.lower():
                    if not line.strip().startswith("#"):
                        pytest.fail(
                            f"Line {i+1}: Active chromadb pip install found:\n{line}\n"
                            "ChromaDB was removed Jan 7, 2026!"
                        )

    def test_phil_town_ingestion_no_chromadb(self):
        """phil-town-ingestion.yml should not install chromadb."""
        content = read_file(".github/workflows/phil-town-ingestion.yml")

        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "pip install" in line and "chromadb" in line.lower():
                if not line.strip().startswith("#"):
                    pytest.fail(
                        f"Line {i+1}: Active chromadb install in phil-town-ingestion.yml:\n{line}"
                    )

    def test_weekend_learning_no_chromadb(self):
        """weekend-learning.yml should not install chromadb."""
        content = read_file(".github/workflows/weekend-learning.yml")

        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "pip install" in line and "chromadb" in line.lower():
                if not line.strip().startswith("#"):
                    pytest.fail(
                        f"Line {i+1}: Active chromadb install in weekend-learning.yml:\n{line}"
                    )

    def test_vectorize_script_no_chromadb_dependency(self):
        """vectorize_rag_knowledge.py should not import chromadb."""
        content = read_file("scripts/vectorize_rag_knowledge.py")

        # Check for active chromadb import
        if "import chromadb" in content or "from chromadb" in content:
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if ("import chromadb" in line or "from chromadb" in line):
                    if not line.strip().startswith("#"):
                        pytest.fail(
                            f"Line {i+1}: Active chromadb import in vectorize_rag_knowledge.py:\n{line}"
                        )

    def test_requirements_chromadb_commented(self):
        """requirements-minimal.txt should have chromadb commented out."""
        content = read_file("requirements-minimal.txt")

        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "chromadb" in line.lower():
                if not line.strip().startswith("#"):
                    pytest.fail(
                        f"Line {i+1}: ChromaDB should be commented out:\n{line}"
                    )


class TestWorkflowStructure:
    """Verify workflow structure is valid after ChromaDB removal."""

    def test_daily_trading_has_rag_sync(self):
        """daily-trading.yml should still have RAG sync step."""
        content = read_file(".github/workflows/daily-trading.yml")

        assert "Sync Trades to RAG" in content, (
            "RAG sync step missing from daily-trading.yml!\n"
            "Trades must be recorded to Vertex AI RAG."
        )

    def test_daily_trading_has_trailing_stops(self):
        """daily-trading.yml should have trailing stop step."""
        content = read_file(".github/workflows/daily-trading.yml")

        assert "Set Trailing Stop-Loss Orders" in content, (
            "Trailing stop step missing from daily-trading.yml!\n"
            "Phil Town Rule #1: Don't lose money."
        )

    def test_daily_trading_stop_loss_not_skippable(self):
        """Phil Town Rule 1 trailing stop step should have continue-on-error: false."""
        content = read_file(".github/workflows/daily-trading.yml")

        # Find the Phil Town Rule 1 trailing stop section (the critical one)
        stop_section_start = content.find("Set Trailing Stop-Loss Orders (Phil Town Rule 1)")
        if stop_section_start == -1:
            pytest.fail("Phil Town Rule 1 trailing stop step not found!")

        # Look back to find the step definition with continue-on-error
        section_start = max(0, stop_section_start - 300)
        stop_section = content[section_start:stop_section_start + 500]

        # Should have continue-on-error: false (not true!)
        assert "continue-on-error: false" in stop_section, (
            "Phil Town Rule 1 trailing stop step must have 'continue-on-error: false'!\n"
            "If stops fail, positions are UNPROTECTED."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
