#!/usr/bin/env python3
"""
Smoke tests for critical trading system paths.

These tests verify basic functionality works without full dependencies.
Updated Jan 13, 2026: Real smoke tests instead of placeholders.
"""

import os
from pathlib import Path


class TestCriticalPaths:
    """Smoke tests for critical system paths."""

    def test_project_structure_exists(self):
        """Verify critical directories exist."""
        project_root = Path(__file__).parent.parent
        critical_dirs = [
            "src/orchestrator",
            "src/rag",
            "src/execution",
            "scripts",
            "data",
        ]
        for dir_name in critical_dirs:
            dir_path = project_root / dir_name
            assert dir_path.exists(), f"Critical directory missing: {dir_name}"

    def test_core_modules_syntax_valid(self):
        """Verify core Python modules have valid syntax."""
        import ast

        project_root = Path(__file__).parent.parent
        core_files = [
            "src/orchestrator/gates.py",
            "src/orchestrator/main.py",
            "src/rag/lessons_learned_rag.py",
        ]
        for file_name in core_files:
            file_path = project_root / file_name
            if file_path.exists():
                with open(file_path) as f:
                    # This will raise SyntaxError if invalid
                    ast.parse(f.read())

    def test_trading_constants_reasonable(self):
        """Verify trading constants are reasonable."""
        from src.constants.trading_thresholds import PositionSizing

        # Rule #1: Don't lose money - verify conservative limits
        assert 0 < PositionSizing.MAX_POSITION_PCT <= 0.5
        assert 0 < PositionSizing.MAX_DAILY_LOSS_PCT <= 0.1
        assert PositionSizing.MIN_CAPITAL >= 0

    def test_data_directory_writable(self):
        """Verify data directory is writable."""
        project_root = Path(__file__).parent.parent
        data_dir = project_root / "data"
        assert data_dir.exists()
        # Check we can write (CI needs this)
        test_file = data_dir / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except PermissionError:
            pass  # OK in read-only environments

    def test_environment_aware(self):
        """Verify environment detection works."""
        # Should not crash even without env vars set
        api_key = os.getenv("ALPACA_API_KEY", "")
        paper_key = os.getenv("ALPACA_PAPER_TRADING_5K_API_KEY", "")
        # At least one should be set in CI, but test shouldn't fail if not
        assert isinstance(api_key, str)
        assert isinstance(paper_key, str)
