"""Tests for sync_rag_to_blog.py script."""

import tempfile
from pathlib import Path

import pytest


def test_parse_lesson_file():
    """Test parsing a lesson file."""
    from scripts.sync_rag_to_blog import parse_lesson_file

    # Create temp lesson file
    with tempfile.NamedTemporaryFile(mode="w", suffix="_jan13.md", delete=False) as f:
        f.write("""# Test Lesson Title

**Severity**: CRITICAL
**Category**: testing

This is the content.
""")
        temp_path = Path(f.name)

    try:
        result = parse_lesson_file(temp_path)
        assert result is not None
        assert result["severity"] == "CRITICAL"
        assert "2026-01-13" in result["date"]
        assert "Test Lesson Title" in result["title"]
    finally:
        temp_path.unlink()


def test_parse_lesson_file_low_severity():
    """Test parsing lesson with no explicit severity defaults to LOW."""
    from scripts.sync_rag_to_blog import parse_lesson_file

    with tempfile.NamedTemporaryFile(mode="w", suffix="_jan12.md", delete=False) as f:
        f.write("# Simple Lesson\n\nJust content here.")
        temp_path = Path(f.name)

    try:
        result = parse_lesson_file(temp_path)
        assert result["severity"] == "LOW"
    finally:
        temp_path.unlink()


def test_generate_daily_summary_post():
    """Test blog post generation."""
    from scripts.sync_rag_to_blog import generate_daily_summary_post

    lessons = [
        {
            "id": "ll_001",
            "title": "Test Lesson",
            "severity": "HIGH",
            "content": "This is test content for the lesson.",
        },
        {
            "id": "ll_002",
            "title": "Another Lesson",
            "severity": "LOW",
            "content": "More test content.",
        },
    ]

    post = generate_daily_summary_post("2026-01-13", lessons)

    assert "Day" in post
    assert "2026-01-13" in post
    assert "Total Lessons" in post
    assert "2" in post  # 2 lessons
    assert "Test Lesson" in post
    assert "[HIGH]" in post
