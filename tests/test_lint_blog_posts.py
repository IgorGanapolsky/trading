"""Tests for blog discoverability lint checks."""

from __future__ import annotations

from pathlib import Path

from scripts.lint_blog_posts import lint_file


def _write_post(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_lint_flags_missing_answer_block_and_evidence(tmp_path: Path) -> None:
    post = tmp_path / "docs" / "_posts" / "2026-02-16-test-post.md"
    content = """---
title: "Test Post"
description: "Desc"
image: "/assets/og-image.png"
---

# Test Post

This is a long body.
"""
    _write_post(post, content + (" lorem ipsum" * 220))

    issues = lint_file(post)
    messages = [msg for _, msg in issues]

    assert "missing Answer Block or structured Q&A (faq/questions)" in messages
    assert "missing evidence link to repository or commit" in messages


def test_lint_accepts_structured_qa_and_evidence_link(tmp_path: Path) -> None:
    post = tmp_path / "docs" / "_posts" / "2026-02-16-test-post.md"
    content = """---
title: "Test Post"
description: "Desc"
image: "/assets/og-image.png"
faq: true
questions:
  - question: "What happened?"
    answer: "Something useful."
---

# Test Post

## Evidence

- https://github.com/IgorGanapolsky/trading/blob/main/docs/_posts/2026-02-16-test-post.md
"""
    _write_post(post, content + (" lorem ipsum" * 220))

    issues = lint_file(post)
    messages = [msg for _, msg in issues]

    assert "missing Answer Block or structured Q&A (faq/questions)" not in messages
    assert "missing evidence link to repository or commit" not in messages
