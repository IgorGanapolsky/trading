#!/usr/bin/env python3
"""
Unit tests for GitHub Pages link validation.

Run with: pytest tests/test_github_pages_links.py -v
"""

import sys
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from validate_github_pages_links import LinkValidator


class TestGitHubPagesLinkValidator:
    """Test suite for GitHub Pages link validation."""

    @pytest.fixture
    def validator(self):
        """Create a fresh validator instance."""
        return LinkValidator()

    def test_jekyll_templates_use_relative_url(self, validator):
        """
        CRITICAL TEST: Ensures all Jekyll templates use relative_url filter.

        This prevents 404 errors when baseurl is set (e.g., /trading).
        Without relative_url, links go to /lessons/ instead of /trading/lessons/.

        See: index.md, lessons.md - all {{ something.url }} must have | relative_url
        """
        result = validator.validate_jekyll_templates()

        assert result is True, (
            f"Jekyll templates missing relative_url filter!\n"
            f"Errors: {validator.errors}\n"
            f"Fix: Add '| relative_url' to all {{ something.url }} in docs/*.md files"
        )

    def test_no_errors_on_validation(self, validator):
        """Ensure validation produces no errors."""
        validator.validate_jekyll_templates()

        assert len(validator.errors) == 0, (
            f"Validation produced {len(validator.errors)} error(s):\n" + "\n".join(validator.errors)
        )

    def test_index_md_has_relative_url_on_lesson_links(self):
        """
        Specific regression test for index.md Featured Lessons.

        The bug: {{ lesson.url }} was missing | relative_url filter,
        causing all lesson links to 404 because they went to /lessons/
        instead of /trading/lessons/.
        """
        docs_dir = Path(__file__).parent.parent / "docs"
        index_file = docs_dir / "index.md"

        if not index_file.exists():
            pytest.skip("docs/index.md removed per cleanup directive (outdated CSP strategy)")

        content = index_file.read_text()

        # Check that lesson.url has relative_url filter
        import re

        bad_pattern = re.compile(r"\{\{\s*lesson\.url\s*\}\}")
        good_pattern = re.compile(r"\{\{\s*lesson\.url\s*\|\s*relative_url\s*\}\}")

        bad_matches = bad_pattern.findall(content)
        good_matches = good_pattern.findall(content)

        # Filter false positives
        actual_bad = [m for m in bad_matches if m not in str(good_matches)]

        assert len(actual_bad) == 0, (
            f"index.md has {len(actual_bad)} lesson links missing relative_url filter!\n"
            f"Found: {actual_bad}\n"
            f"Fix: Change {{ lesson.url }} to {{ lesson.url | relative_url }}"
        )

    def test_lessons_md_has_relative_url(self):
        """Ensure lessons.md listing uses relative_url filter."""
        docs_dir = Path(__file__).parent.parent / "docs"
        lessons_file = docs_dir / "lessons.md"

        if not lessons_file.exists():
            pytest.skip("docs/lessons.md removed per cleanup directive")
        assert lessons_file.exists(), "docs/lessons.md not found"

        content = lessons_file.read_text()

        # Should contain relative_url filter
        assert "| relative_url" in content, (
            "docs/lessons.md missing relative_url filter on lesson links"
        )


class TestRegressionPrevention:
    """Tests to prevent known regressions."""

    def test_baseurl_configured_in_config(self):
        """Ensure _config.yml has baseurl set to /trading."""
        docs_dir = Path(__file__).parent.parent / "docs"
        config_file = docs_dir / "_config.yml"

        assert config_file.exists(), "docs/_config.yml not found"

        content = config_file.read_text()

        assert 'baseurl: "/trading"' in content, '_config.yml should have baseurl: "/trading" set'

    def test_url_configured_in_config(self):
        """Ensure _config.yml has correct URL."""
        docs_dir = Path(__file__).parent.parent / "docs"
        config_file = docs_dir / "_config.yml"

        content = config_file.read_text()

        assert "igorganapolsky.github.io" in content, (
            "_config.yml should have correct GitHub Pages URL"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
