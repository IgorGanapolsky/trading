from __future__ import annotations

import pytest

from src.content.blog_seo import (
    canonical_url_for_collection_item,
    canonical_url_for_post,
    canonical_url_for_post_file,
    render_frontmatter,
    truncate_meta_description,
)


def test_canonical_url_for_post() -> None:
    assert (
        canonical_url_for_post("2026-02-14", "lessons-learned")
        == "https://igorganapolsky.github.io/trading/2026/02/14/lessons-learned/"
    )


def test_canonical_url_for_post_allows_datetime_string() -> None:
    assert (
        canonical_url_for_post("2026-02-14 12:34:56", "rlhf-win")
        == "https://igorganapolsky.github.io/trading/2026/02/14/rlhf-win/"
    )


def test_canonical_url_for_post_file() -> None:
    assert (
        canonical_url_for_post_file("docs/_posts/2026-02-14-rlhf-win-1530.md")
        == "https://igorganapolsky.github.io/trading/2026/02/14/rlhf-win-1530/"
    )


def test_canonical_url_for_collection_item() -> None:
    assert (
        canonical_url_for_collection_item("reports", "2026-02-14-daily-report")
        == "https://igorganapolsky.github.io/trading/reports/2026-02-14-daily-report/"
    )


def test_truncate_meta_description_collapses_and_truncates() -> None:
    text = "This is   a  description with  extra\nwhitespace that should collapse."
    out = truncate_meta_description(text, max_chars=40)
    assert "\n" not in out
    assert "  " not in out
    assert len(out) <= 43  # 40 + "..."


def test_render_frontmatter_with_questions() -> None:
    fm = render_frontmatter(
        {
            "layout": "post",
            "title": "Example",
            "date": "2026-02-14",
            "tags": ["ai", "trading"],
        },
        questions=[
            {"question": "What is this?", "answer": "A test."},
            {"question": "Why?", "answer": "To verify YAML safety: quotes, colons, etc."},
        ],
    )

    assert fm.startswith("---\n")
    assert fm.endswith("\n---\n")
    assert "questions:" in fm
    assert 'question: "What is this?"' in fm
    assert 'answer: "A test."' in fm


def test_render_frontmatter_rejects_invalid_question() -> None:
    with pytest.raises(ValueError):
        render_frontmatter({"title": "x"}, questions=[{"question": "Q", "answer": ""}])
