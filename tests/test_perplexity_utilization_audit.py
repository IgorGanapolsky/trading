from __future__ import annotations

import json
from pathlib import Path

from src.analytics.perplexity_utilization_audit import (
    build_perplexity_usage_snapshot,
    render_markdown_report,
    scan_perplexity_workflows,
)


def test_scan_perplexity_workflows_detects_models_and_secret(tmp_path: Path) -> None:
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "weekend-research.yml").write_text(
        "\n".join(
            [
                "env:",
                "  PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}",
                "steps:",
                "  - run: |",
                '      payload = {"model": "sonar-pro"}',
                '      url = "https://api.perplexity.ai/chat/completions"',
            ]
        ),
        encoding="utf-8",
    )
    (workflows_dir / "other.yml").write_text("name: noop\n", encoding="utf-8")

    rows = scan_perplexity_workflows(workflows_dir)
    assert len(rows) == 1
    row = rows[0]
    assert row["path"] == ".github/workflows/weekend-research.yml"
    assert row["has_api_key_secret_ref"] is True
    assert row["endpoint_refs"] == 1
    assert "sonar-pro" in row["models"]


def test_build_perplexity_usage_snapshot_and_markdown(tmp_path: Path) -> None:
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "pre-market-scan.yml").write_text(
        "\n".join(
            [
                "name: pre-market",
                "env:",
                "  PERPLEXITY_API_KEY: ${{ secrets.PERPLEXITY_API_KEY }}",
                "steps:",
                "  - run: echo api.perplexity.ai/chat/completions",
                "  - run: echo model sonar",
            ]
        ),
        encoding="utf-8",
    )

    (tmp_path / "src" / "agents").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "agents" / "research_agent.py").write_text("# stub\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "perplexity_local_mcp_snapshot.py").write_text(
        "#!/usr/bin/env python3\n",
        encoding="utf-8",
    )

    report = build_perplexity_usage_snapshot(tmp_path)
    payload = json.loads(json.dumps(report))
    assert payload["workflow_scan"]["count"] == 1
    assert payload["source_presence"]["research_agent"] is True
    assert "sonar" in payload["workflow_scan"]["distinct_models"]

    markdown = render_markdown_report(report)
    assert "# Perplexity Utilization Audit" in markdown
    assert "Workflow Wiring" in markdown
