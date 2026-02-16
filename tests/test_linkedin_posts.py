from __future__ import annotations

from src.content.linkedin_posts import build_answer_first_linkedin_post


def test_build_answer_first_linkedin_post_contains_required_sections() -> None:
    post = build_answer_first_linkedin_post(
        title="How We Improved AI Discoverability",
        body_markdown="""
## Answer Block
We improved visibility by standardizing metadata and answer-first content.

## Implementation
We implemented CI checks for canonical URL, author credentials, and FAQ schema.

## Results
Coverage rose from 62% to 94% across recent posts.
""",
        canonical_url="https://igorganapolsky.github.io/trading/2026/02/16/discoverability-upgrade/",
        tags=["ai-discovery", "linkedin", "seo"],
        question_cluster="AI visibility for blogs and technical docs",
    )

    assert "Direct answer:" in post
    assert "Problem:" in post
    assert "Method:" in post
    assert "Result:" in post
    assert "Evidence: https://igorganapolsky.github.io/trading/2026/02/16/discoverability-upgrade/" in post
    assert "#aidiscovery" in post.lower()


def test_build_answer_first_linkedin_post_respects_max_length() -> None:
    long_body = ("We implemented robust metadata and schema checks. " * 200).strip()
    post = build_answer_first_linkedin_post(
        title="Long Post",
        body_markdown=long_body,
        canonical_url="https://igorganapolsky.github.io/trading/long-post/",
        max_chars=700,
    )

    assert len(post) <= 700
    assert "Evidence: https://igorganapolsky.github.io/trading/long-post/" in post
