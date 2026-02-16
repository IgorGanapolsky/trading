"""Tests for scripts/check_ai_discoverability.py."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.check_ai_discoverability import collect_discoverability_metrics


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_collect_metrics_happy_path(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "llms.txt", "# llms")
    _write(tmp_path / "docs" / "llms-full.txt", "# llms-full")
    _write(
        tmp_path / "docs" / "robots.txt",
        "User-agent: *\nSitemap: https://example.com/sitemap.xml\n",
    )

    _write(
        tmp_path / "docs" / "_posts" / "2026-02-16-post-a.md",
        """---
title: "A"
description: "d"
image: "/assets/og-image.png"
faq: true
questions:
  - question: "q"
    answer: "a"
---

## Evidence
- https://github.com/IgorGanapolsky/trading/blob/main/docs/_posts/2026-02-16-post-a.md
""",
    )
    _write(
        tmp_path / "docs" / "_posts" / "2026-02-15-post-b.md",
        """---
title: "B"
description: "d"
image: "/assets/og-image.png"
---

## Answer Block
test
## Evidence
- https://github.com/IgorGanapolsky/trading
""",
    )
    _write(
        tmp_path / "docs" / "_reports" / "2026-02-16-dashboard-snapshot.md",
        "snapshot",
    )

    metrics = collect_discoverability_metrics(
        repo_root=tmp_path,
        recent_posts=10,
        max_snapshot_age_days=2,
        today=date(2026, 2, 16),
    )

    assert metrics["summary"]["critical_failed"] == 0
    assert metrics["answer_block_ratio"] == 1.0
    assert metrics["evidence_link_ratio"] == 1.0
    assert metrics["latest_dashboard_snapshot_age_days"] == 0


def test_collect_metrics_fails_when_critical_assets_missing(tmp_path: Path) -> None:
    _write(tmp_path / "docs" / "robots.txt", "User-agent: *\n")
    _write(tmp_path / "docs" / "_posts" / "2026-02-16-post-a.md", "# no metadata")

    metrics = collect_discoverability_metrics(
        repo_root=tmp_path,
        recent_posts=5,
        max_snapshot_age_days=2,
        today=date(2026, 2, 16),
    )

    assert metrics["summary"]["critical_failed"] >= 1
    check_names = {check["name"]: check["status"] for check in metrics["checks"]}
    assert check_names["llms_manifest"] == "fail"
    assert check_names["dashboard_snapshot_freshness"] == "fail"
