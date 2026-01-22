"""Tests for Ralph discovery blog post system."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDiscoveryLoader:
    """Test discovery data loading."""

    def test_load_discoveries_file_exists(self, tmp_path):
        """Test loading discoveries from existing file."""
        from scripts.generate_ralph_discovery_post import load_discoveries

        # Create test file
        test_data = {"discoveries": [{"id": "RD-001", "title": "Test"}]}
        discoveries_file = tmp_path / "ralph_discoveries.json"
        discoveries_file.write_text(json.dumps(test_data))

        with patch(
            "scripts.generate_ralph_discovery_post.DISCOVERIES_FILE",
            discoveries_file
        ):
            result = load_discoveries()
            assert result["discoveries"][0]["id"] == "RD-001"

    def test_load_discoveries_file_missing(self, tmp_path):
        """Test loading when file doesn't exist."""
        from scripts.generate_ralph_discovery_post import load_discoveries

        missing_file = tmp_path / "nonexistent.json"

        with patch(
            "scripts.generate_ralph_discovery_post.DISCOVERIES_FILE",
            missing_file
        ):
            result = load_discoveries()
            assert result == {"discoveries": []}


class TestBlogContentGeneration:
    """Test blog content generation."""

    def test_generate_blog_content_structure(self):
        """Test that blog content has required sections."""
        from scripts.generate_ralph_discovery_post import generate_blog_content

        discovery = {
            "id": "RD-001",
            "title": "Test Discovery",
            "category": "security",
            "severity": "critical",
            "iteration": 100,
            "timestamp": "2026-01-21T12:00:00Z",
            "summary": "Test summary",
            "details": {
                "problem": "Test problem",
                "root_cause": "Test cause",
                "impact": "Test impact",
                "solution": "Test solution",
                "files_changed": ["file1.py", "file2.py"],
                "tests_affected": 100
            },
            "lessons_learned": ["Lesson 1", "Lesson 2"],
            "metrics_before": {"bugs": 5},
            "metrics_after": {"bugs": 0}
        }

        content = generate_blog_content(discovery)

        # Check required sections exist
        assert "---" in content  # YAML frontmatter
        assert "layout: post" in content
        assert "Test Discovery" in content
        assert "CRITICAL" in content
        assert "Test summary" in content
        assert "Test problem" in content
        assert "Test solution" in content
        assert "Lesson 1" in content
        assert "file1.py" in content
        assert "Before vs After" in content

    def test_generate_blog_content_emoji_categories(self):
        """Test that categories get correct emojis."""
        from scripts.generate_ralph_discovery_post import generate_blog_content

        categories = {
            "security": "🔒",
            "performance": "⚡",
            "bug_fix": "🐛",
            "testing": "🧪"
        }

        for category, emoji in categories.items():
            discovery = {
                "title": "Test",
                "category": category,
                "severity": "medium",
                "summary": "Test",
                "details": {}
            }
            content = generate_blog_content(discovery)
            assert emoji in content


class TestDevToPayload:
    """Test Dev.to API payload generation."""

    def test_generate_devto_content_structure(self):
        """Test Dev.to payload has required fields."""
        from scripts.generate_ralph_discovery_post import generate_devto_content

        discovery = {
            "title": "Test Discovery",
            "category": "security",
            "severity": "high",
            "iteration": 50,
            "summary": "Test summary",
            "details": {
                "problem": "Problem",
                "root_cause": "Cause",
                "impact": "Impact",
                "solution": "Solution"
            },
            "lessons_learned": ["Lesson 1"]
        }

        payload = generate_devto_content(discovery)

        assert "article" in payload
        article = payload["article"]
        assert "title" in article
        assert "body_markdown" in article
        assert "tags" in article
        assert article["published"] is True
        assert len(article["tags"]) <= 5  # Dev.to limit

    def test_devto_tags_include_base_tags(self):
        """Test that base tags are always included."""
        from scripts.generate_ralph_discovery_post import generate_devto_content

        discovery = {
            "title": "Test",
            "category": "testing",
            "summary": "Test",
            "details": {},
            "lessons_learned": []
        }

        payload = generate_devto_content(discovery)
        tags = payload["article"]["tags"]

        assert "ai" in tags
        assert "python" in tags


class TestDiscoveryLogger:
    """Test the discovery logging script."""

    def test_get_next_id_empty_list(self):
        """Test ID generation with no existing discoveries."""
        from scripts.log_ralph_discovery import get_next_id

        result = get_next_id([])
        assert result == "RD-001"

    def test_get_next_id_with_existing(self):
        """Test ID generation with existing discoveries."""
        from scripts.log_ralph_discovery import get_next_id

        existing = [
            {"id": "RD-001"},
            {"id": "RD-005"},
            {"id": "RD-003"}
        ]
        result = get_next_id(existing)
        assert result == "RD-006"

    def test_get_next_id_handles_invalid(self):
        """Test ID generation handles invalid IDs gracefully."""
        from scripts.log_ralph_discovery import get_next_id

        existing = [
            {"id": "RD-001"},
            {"id": "invalid"},
            {"id": "RD-002"}
        ]
        result = get_next_id(existing)
        assert result == "RD-003"


class TestPublishWorkflow:
    """Test the publishing workflow logic."""

    def test_publish_discovery_dry_run(self, capsys):
        """Test dry run doesn't actually publish."""
        from scripts.generate_ralph_discovery_post import publish_discovery

        discovery = {
            "title": "Test",
            "category": "testing",
            "severity": "low",
            "summary": "Test",
            "details": {}
        }

        results = publish_discovery(discovery, dry_run=True)

        assert results["github_pages"] is None
        assert results["devto"] is None

        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out

    @patch("scripts.generate_ralph_discovery_post.publish_to_github_pages")
    @patch("scripts.generate_ralph_discovery_post.publish_to_devto")
    def test_publish_discovery_calls_both_platforms(
        self, mock_devto, mock_gh, tmp_path
    ):
        """Test that publishing calls both platforms."""
        from scripts.generate_ralph_discovery_post import publish_discovery

        mock_gh.return_value = "/path/to/post.md"
        mock_devto.return_value = "https://dev.to/test"

        discovery = {
            "title": "Test",
            "category": "testing",
            "severity": "low",
            "summary": "Test",
            "details": {}
        }

        results = publish_discovery(discovery, dry_run=False)

        mock_gh.assert_called_once()
        mock_devto.assert_called_once()
        assert results["github_pages"] == "/path/to/post.md"
        assert results["devto"] == "https://dev.to/test"
