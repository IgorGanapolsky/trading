from __future__ import annotations

from pathlib import Path

from src.analytics import build_perplexity_usage_snapshot
from src.analytics.perplexity_utilization_audit import (
    render_perplexity_usage_markdown,
    write_perplexity_usage_artifacts,
)


def test_perplexity_usage_snapshot_detects_high_roi_wiring(tmp_path: Path) -> None:
    files = {
        "src/analytics/perplexity_trading_intel.py": 'model = "sonar-pro"\n',
        "src/analytics/perplexity_utilization_audit.py": "PERPLEXITY_API_KEY\n",
        "scripts/run_perplexity_trading_intel.py": "perplexity_trading_intel\n",
        ".github/workflows/pre-market-scan.yml": "PERPLEXITY_API_KEY\nsonar-pro\n",
        ".github/workflows/perplexity-trading-intel.yml": "api.perplexity.ai\nsonar\n",
    }
    for rel_path, content in files.items():
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    snapshot = build_perplexity_usage_snapshot(tmp_path, credential_present=True)

    assert snapshot["credential_available_in_runtime"] is True
    assert snapshot["missing_expected_files"] == []
    assert snapshot["max_utilization_score"] >= 90
    assert ".github/workflows/perplexity-trading-intel.yml" in {
        item["path"] for item in snapshot["workflows_with_perplexity"]
    }


def test_perplexity_usage_artifacts_render_markdown(tmp_path: Path) -> None:
    path = tmp_path / "src" / "analytics" / "perplexity_trading_intel.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("PERPLEXITY_API_KEY\nsonar-pro\n", encoding="utf-8")

    paths = write_perplexity_usage_artifacts(tmp_path, credential_present=False)
    markdown = paths["markdown"].read_text(encoding="utf-8")

    assert paths["json"].exists()
    assert "# Perplexity Utilization Audit" in markdown
    assert "local_runtime_missing_perplexity_credential" in markdown


def test_render_perplexity_usage_markdown_has_gap_section() -> None:
    markdown = render_perplexity_usage_markdown(
        {
            "generated_at_utc": "2026-04-13T00:00:00+00:00",
            "credential_available_in_runtime": False,
            "active_perplexity_files": 1,
            "max_utilization_score": 20,
            "models_referenced": ["sonar-pro"],
            "workflows_with_perplexity": [],
            "gaps": ["agent_playground_not_versioned_in_repo"],
        }
    )

    assert "## Gaps" in markdown
    assert "agent_playground_not_versioned_in_repo" in markdown
