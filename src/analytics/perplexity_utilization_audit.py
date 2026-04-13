"""Audit how much of Perplexity is wired into the trading system."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PERPLEXITY_PATTERNS = (
    "PERPLEXITY_API_KEY",
    "api.perplexity.ai",
    "sonar",
    "perplexity",
)

EXPECTED_HIGH_ROI_FILES = (
    "src/analytics/perplexity_trading_intel.py",
    "src/analytics/perplexity_utilization_audit.py",
    "scripts/run_perplexity_trading_intel.py",
    ".github/workflows/pre-market-scan.yml",
    ".github/workflows/perplexity-trading-intel.yml",
)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return ""


def _scan_file(path: Path, repo_root: Path) -> dict[str, Any] | None:
    text = _read_text(path)
    lowered = text.lower()
    if not any(pattern.lower() in lowered for pattern in PERPLEXITY_PATTERNS):
        return None

    models = sorted(set(re.findall(r"\bsonar(?:-[a-z]+)*\b", text)))
    path_label = str(path.relative_to(repo_root))
    playground_reference = (
        ("console.perplexity.ai/group" in lowered or "agent-playground" in lowered)
        and not path_label.endswith("perplexity_utilization_audit.py")
    )

    return {
        "path": path_label,
        "models": models,
        "uses_perplexity_credential": "PERPLEXITY_API_KEY" in text,
        "uses_api_endpoint": "api.perplexity.ai" in text,
        "mentions_agent_playground": playground_reference,
    }


def _iter_scannable_files(repo_root: Path) -> list[Path]:
    roots = [
        repo_root / ".github" / "workflows",
        repo_root / "scripts",
        repo_root / "src",
        repo_root / "tests",
    ]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix in {".py", ".yml", ".yaml", ".md", ".txt"}
        )
    return sorted(files)


def build_perplexity_usage_snapshot(
    repo_root: Path | str | None = None,
    *,
    credential_present: bool = False,
) -> dict[str, Any]:
    """Build a machine-readable Perplexity utilization snapshot."""

    root = Path.cwd().resolve() if repo_root is None else Path(repo_root).resolve()
    matches = [
        match
        for path in _iter_scannable_files(root)
        if (match := _scan_file(path, root))
    ]

    workflow_matches = [item for item in matches if item["path"].startswith(".github/workflows/")]
    source_matches = [item for item in matches if item["path"].startswith("src/")]
    script_matches = [item for item in matches if item["path"].startswith("scripts/")]
    missing_expected = [path for path in EXPECTED_HIGH_ROI_FILES if not (root / path).exists()]

    gaps: list[str] = []
    if not credential_present:
        gaps.append("local_runtime_missing_perplexity_credential")
    if missing_expected:
        gaps.append("missing_high_roi_files")
    if not any(item["path"] == ".github/workflows/perplexity-trading-intel.yml" for item in matches):
        gaps.append("missing_24_7_trading_intel_workflow")
    if not any(item["path"] == "src/analytics/perplexity_trading_intel.py" for item in matches):
        gaps.append("missing_structured_trading_intel_engine")
    if not any(item["mentions_agent_playground"] for item in matches):
        gaps.append("agent_playground_not_versioned_in_repo")

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "credential_available_in_runtime": credential_present,
        "active_perplexity_files": len(matches),
        "workflows_with_perplexity": workflow_matches,
        "source_modules_with_perplexity": source_matches,
        "scripts_with_perplexity": script_matches,
        "models_referenced": sorted({model for item in matches for model in item["models"]}),
        "expected_high_roi_files": list(EXPECTED_HIGH_ROI_FILES),
        "missing_expected_files": missing_expected,
        "gaps": gaps,
        "max_utilization_score": _score_utilization(
            credential_present=credential_present,
            missing_expected=missing_expected,
            matches=matches,
        ),
    }


def _score_utilization(
    *,
    credential_present: bool,
    missing_expected: list[str],
    matches: list[dict[str, Any]],
) -> int:
    score = 0
    if credential_present:
        score += 20
    if not missing_expected:
        score += 30
    if any(item["path"] == ".github/workflows/perplexity-trading-intel.yml" for item in matches):
        score += 20
    if any(item["path"] == "src/analytics/perplexity_trading_intel.py" for item in matches):
        score += 20
    if any(item["mentions_agent_playground"] for item in matches):
        score += 10
    return score


def render_perplexity_usage_markdown(snapshot: dict[str, Any]) -> str:
    """Render audit snapshot as operator-readable markdown."""

    lines = [
        "# Perplexity Utilization Audit",
        "",
        f"- Generated UTC: `{snapshot.get('generated_at_utc')}`",
        f"- Runtime credential available: `{snapshot.get('credential_available_in_runtime')}`",
        f"- Active Perplexity files: `{snapshot.get('active_perplexity_files')}`",
        f"- Max utilization score: `{snapshot.get('max_utilization_score')}/100`",
        f"- Models referenced: `{', '.join(snapshot.get('models_referenced') or []) or 'none'}`",
        "",
        "## Workflows",
    ]

    for item in snapshot.get("workflows_with_perplexity", []):
        lines.append(f"- `{item['path']}` models=`{', '.join(item['models']) or 'n/a'}`")

    lines.append("")
    lines.append("## Gaps")
    gaps = snapshot.get("gaps") or []
    if gaps:
        lines.extend(f"- `{gap}`" for gap in gaps)
    else:
        lines.append("- `none`")

    missing = snapshot.get("missing_expected_files") or []
    if missing:
        lines.append("")
        lines.append("## Missing Expected Files")
        lines.extend(f"- `{path}`" for path in missing)

    lines.append("")
    return "\n".join(lines)


def write_perplexity_usage_artifacts(
    repo_root: Path | str | None = None,
    *,
    credential_present: bool = False,
) -> dict[str, Path]:
    root = Path.cwd().resolve() if repo_root is None else Path(repo_root).resolve()
    snapshot = build_perplexity_usage_snapshot(root, credential_present=credential_present)
    output_dir = root / "data" / "analytics"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "perplexity_utilization_latest.json"
    md_path = output_dir / "perplexity_utilization_latest.md.txt"
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_perplexity_usage_markdown(snapshot), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Perplexity utilization")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--credential-present", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.write:
        paths = write_perplexity_usage_artifacts(
            args.repo_root,
            credential_present=args.credential_present,
        )
        print(json.dumps({key: str(value) for key, value in paths.items()}, indent=2))
        return

    snapshot = build_perplexity_usage_snapshot(
        args.repo_root,
        credential_present=args.credential_present,
    )
    print(json.dumps(snapshot, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
