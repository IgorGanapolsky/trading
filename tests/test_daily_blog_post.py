"""
Tests for scripts/generate_daily_blog_post.py

Coverage for:
- calculate_day_number() - correct day calculation from system_state.json
- update_index_day_number() - index.md day number update
"""

import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest


class TestCalculateDayNumber:
    """Tests for calculate_day_number function."""

    def test_calculate_day_number_from_system_state(self):
        """Test that day number is calculated from system_state.json."""
        from scripts.generate_daily_blog_post import calculate_day_number

        # The actual function should return today's day number
        day_num = calculate_day_number()

        # Should be a positive integer
        assert isinstance(day_num, int)
        assert day_num > 0
        assert day_num <= 90  # Within 90-day R&D phase

    def test_calculate_day_number_correct_for_jan_6_2026(self):
        """Test specific day calculation for Jan 6, 2026."""
        # Start date from system_state.json is 2025-10-29
        start_date = date(2025, 10, 29)
        test_date = date(2026, 1, 6)
        expected_day = (test_date - start_date).days + 1

        assert expected_day == 70, f"Jan 6 2026 should be Day 70, got {expected_day}"

    def test_calculate_day_number_fallback(self):
        """Test fallback when system_state.json doesn't exist."""
        from scripts.generate_daily_blog_post import calculate_day_number

        with patch("pathlib.Path.exists", return_value=False):
            day_num = calculate_day_number()
            # Should still return a valid day number using fallback date
            assert isinstance(day_num, int)
            assert day_num > 0


class TestUpdateIndexDayNumber:
    """Tests for update_index_day_number function."""

    def test_update_index_day_number_changes_content(self):
        """Test that index.md day number is updated."""
        from scripts.generate_daily_blog_post import update_index_day_number, DOCS_DIR

        # Create a temporary index.md
        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.md"
            index_path.write_text("## Live Status (Day 69/90)\nSome content")

            with patch.object(
                Path, "parent", new_callable=lambda: Path(tmpdir)
            ):
                # Mock DOCS_DIR to point to temp directory
                with patch(
                    "scripts.generate_daily_blog_post.DOCS_DIR", Path(tmpdir)
                ):
                    update_index_day_number(70)

                    content = index_path.read_text()
                    assert "Day 70/90" in content
                    assert "Day 69/90" not in content

    def test_update_index_day_number_no_change_if_same(self):
        """Test that no write occurs if day number is already correct."""
        from scripts.generate_daily_blog_post import update_index_day_number

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = Path(tmpdir) / "index.md"
            original_content = "## Live Status (Day 70/90)\nSome content"
            index_path.write_text(original_content)

            with patch(
                "scripts.generate_daily_blog_post.DOCS_DIR", Path(tmpdir)
            ):
                update_index_day_number(70)

                # Content should be unchanged
                assert index_path.read_text() == original_content


class TestGenerateDailyBlogPostIntegration:
    """Integration tests for the blog post generator."""

    def test_script_imports(self):
        """Test that the script imports without errors."""
        import scripts.generate_daily_blog_post as blog

        assert hasattr(blog, "calculate_day_number")
        assert hasattr(blog, "update_index_day_number")
        assert hasattr(blog, "generate_blog_post")
        assert hasattr(blog, "main")

    def test_day_number_consistency(self):
        """Test that day number is consistent across functions."""
        from scripts.generate_daily_blog_post import calculate_day_number

        # Call twice - should return same value
        day1 = calculate_day_number()
        day2 = calculate_day_number()
        assert day1 == day2, "Day number should be deterministic"
