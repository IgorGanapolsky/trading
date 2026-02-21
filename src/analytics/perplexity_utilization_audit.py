"""Audit how Perplexity capabilities are wired and exercised in this repo."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PERPLEXITY_ENDPOINT = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL_PATTERN = re.compile(r"\bsonar(?:-[a-z0-9-]+)?\b", re.IGNORECASE)


def build_perplexity_usage_snapshot(repo_root: Path) -> dict[str, Any]:
    """Collect static, file-based Perplexity usage evidence from the codebase."""
    workflows_dir = repo_root / ".github" / "workflows"
    workflow_rows = scan_perplexity_workflows(workflows_dir)

    references = {
        "research_agent": str(repo_root / "src" / "agents" / "research_agent.py"),
        "weekend_research_workflow": str(
            repo_root / ".github" / "workflows" / "weekend-research.yml"
        ),
        "pre_market_scan_workflow": str(
            repo_root / ".github" / "workflows" / "pre-market-scan.yml"
        ),
        "local_mcp_snapshot_script": str(
            repo_root / "scripts" / "perplexity_local_mcp_snapshot.py"
        ),
    }

    source_presence = {key: Path(path).exists() for key, path in references.items()}

    models: set[str] = set()
    endpoint_refs = 0
    for row in workflow_rows:
        models.update(row.get("models", []))
        endpoint_refs += int(row.get("endpoint_refs", 0))

    return {
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "workflow_scan": {
            "workflows_with_perplexity": workflow_rows,
            "count": len(workflow_rows),
            "distinct_models": sorted(models),
            "endpoint_ref_count": endpoint_refs,
        },
        "source_presence": source_presence,
        "references": references,
    }


def scan_perplexity_workflows(workflows_dir: Path) -> list[dict[str, Any]]:
    """Scan workflow files for Perplexity key usage, endpoint calls, and model ids."""
    if not workflows_dir.exists():
        return []

    rows: list[dict[str, Any]] = []
    for path in sorted(workflows_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        if "perplexity" not in lowered and "api.perplexity.ai" not in lowered:
            continue

        has_secret = "PERPLEXITY_API_KEY" in text
        endpoint_refs = lowered.count("api.perplexity.ai/chat/completions")
        models = sorted(
            {match.group(0).lower() for match in PERPLEXITY_MODEL_PATTERN.finditer(text)}
        )

        rows.append(
            {
                "path": str(path).replace(str(workflows_dir.parent.parent) + "/", ""),
                "has_api_key_secret_ref": has_secret,
                "endpoint_refs": endpoint_refs,
                "models": models,
            }
        )
    return rows


def render_markdown_report(report: dict[str, Any]) -> str:
    """Render concise markdown for humans and command-connectors."""
    workflow_scan = report.get("workflow_scan", {})
    rows = workflow_scan.get("workflows_with_perplexity", [])
    source_presence = report.get("source_presence", {})
    live_probe = report.get("live_probe", {})
    recent_runs = report.get("recent_workflow_runs", [])
    gaps = report.get("gaps", [])

    lines = [
        "# Perplexity Utilization Audit",
        "",
        f"- Generated (UTC): `{report.get('generated_at_utc')}`",
        f"- Workflows wired: `{workflow_scan.get('count', 0)}`",
        f"- Models referenced: `{', '.join(workflow_scan.get('distinct_models', [])) or 'none'}`",
        "",
        "## Workflow Wiring",
    ]

    for row in rows:
        lines.extend(
            [
                f"- `{row.get('path')}`",
                f"  - secret ref: `{row.get('has_api_key_secret_ref')}`",
                f"  - endpoint refs: `{row.get('endpoint_refs')}`",
                f"  - models: `{', '.join(row.get('models', [])) or 'none'}`",
            ]
        )

    lines.extend(["", "## Source Presence"])
    for key, exists in sorted(source_presence.items()):
        lines.append(f"- `{key}`: `{exists}`")

    lines.extend(["", "## Recent Workflow Runs"])
    if not recent_runs:
        lines.append("- none")
    else:
        for run in recent_runs:
            lines.append(
                f"- `{run.get('workflow')}`: status=`{run.get('status')}` "
                f"conclusion=`{run.get('conclusion')}` updated=`{run.get('updated_at')}`"
            )

    lines.extend(["", "## Live Probe"])
    if live_probe:
        lines.extend(
            [
                f"- enabled: `{live_probe.get('enabled')}`",
                f"- status: `{live_probe.get('status')}`",
                f"- latency_ms: `{live_probe.get('latency_ms')}`",
                f"- model: `{live_probe.get('model')}`",
            ]
        )
    else:
        lines.append("- not run")

    lines.extend(["", "## Gaps"])
    if not gaps:
        lines.append("- none")
    else:
        lines.extend([f"- {gap}" for gap in gaps])

    return "\n".join(lines) + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic JSON payload."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    """Append one JSON line to history stream."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
