#!/usr/bin/env python3
"""
Check and report AI discoverability hygiene for blog/docs/dashboard content.

This script is designed for:
- CI enforcement (critical checks)
- Autonomous ops reporting (markdown artifact + optional state sync)
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ANSWER_BLOCK_PATTERN = re.compile(r"^##\s+Answer Block\b", re.IGNORECASE | re.MULTILINE)
QUESTIONS_PATTERN = re.compile(r"^questions:\s*$", re.IGNORECASE | re.MULTILINE)
FAQ_PATTERN = re.compile(r"^faq:\s*true\s*$", re.IGNORECASE | re.MULTILINE)
EVIDENCE_LINK_PATTERN = re.compile(
    r"https://github\.com/IgorGanapolsky/trading(?:/|$)", re.IGNORECASE
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # pass | warn | fail
    detail: str
    critical: bool = False


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _safe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def _has_answer_block_or_structured_qa(text: str) -> bool:
    return bool(
        ANSWER_BLOCK_PATTERN.search(text)
        or QUESTIONS_PATTERN.search(text)
        or FAQ_PATTERN.search(text)
    )


def _has_evidence_link(text: str) -> bool:
    return bool(EVIDENCE_LINK_PATTERN.search(text))


def _recent_post_paths(posts_dir: Path, limit: int) -> list[Path]:
    posts = sorted(posts_dir.glob("*.md"), reverse=True)
    return posts[:limit]


def _latest_snapshot_age_days(reports_dir: Path, today: date) -> int | None:
    snapshots = sorted(reports_dir.glob("*-dashboard-snapshot.md"), reverse=True)
    if not snapshots:
        return None
    latest = snapshots[0]
    stem = latest.stem
    try:
        snapshot_day = datetime.strptime(stem[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return (today - snapshot_day).days


def collect_discoverability_metrics(
    *,
    repo_root: Path,
    recent_posts: int,
    max_snapshot_age_days: int,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    docs_dir = repo_root / "docs"
    posts_dir = docs_dir / "_posts"
    reports_dir = docs_dir / "_reports"
    robots_path = docs_dir / "robots.txt"
    llms_path = docs_dir / "llms.txt"
    llms_full_path = docs_dir / "llms-full.txt"

    post_paths = _recent_post_paths(posts_dir, recent_posts)
    answer_count = 0
    evidence_count = 0
    for path in post_paths:
        text = _read_text(path)
        if _has_answer_block_or_structured_qa(text):
            answer_count += 1
        if _has_evidence_link(text):
            evidence_count += 1

    answer_ratio = (answer_count / len(post_paths)) if post_paths else 0.0
    evidence_ratio = (evidence_count / len(post_paths)) if post_paths else 0.0

    snapshot_age_days = _latest_snapshot_age_days(reports_dir, today)
    robots_text = _read_text(robots_path) if robots_path.exists() else ""

    checks: list[CheckResult] = []

    if llms_path.exists() and llms_path.stat().st_size > 0:
        checks.append(
            CheckResult(
                "llms_manifest", "pass", "docs/llms.txt present and non-empty", critical=True
            )
        )
    else:
        checks.append(
            CheckResult("llms_manifest", "fail", "docs/llms.txt missing or empty", critical=True)
        )

    if llms_full_path.exists() and llms_full_path.stat().st_size > 0:
        checks.append(
            CheckResult(
                "llms_full_manifest",
                "pass",
                "docs/llms-full.txt present and non-empty",
                critical=True,
            )
        )
    else:
        checks.append(
            CheckResult(
                "llms_full_manifest", "fail", "docs/llms-full.txt missing or empty", critical=True
            )
        )

    if "Sitemap:" in robots_text:
        checks.append(
            CheckResult("robots_sitemap", "pass", "robots.txt declares Sitemap", critical=True)
        )
    else:
        checks.append(
            CheckResult(
                "robots_sitemap", "fail", "robots.txt missing Sitemap declaration", critical=True
            )
        )

    if snapshot_age_days is None:
        checks.append(
            CheckResult(
                "dashboard_snapshot_freshness",
                "fail",
                "No dashboard snapshot report found",
                critical=True,
            )
        )
    elif snapshot_age_days <= max_snapshot_age_days:
        checks.append(
            CheckResult(
                "dashboard_snapshot_freshness",
                "pass",
                f"Latest dashboard snapshot is {snapshot_age_days} day(s) old",
                critical=True,
            )
        )
    else:
        checks.append(
            CheckResult(
                "dashboard_snapshot_freshness",
                "fail",
                f"Latest dashboard snapshot is stale ({snapshot_age_days} day(s) old)",
                critical=True,
            )
        )

    if answer_ratio >= 0.8:
        answer_status = "pass"
    elif answer_ratio >= 0.6:
        answer_status = "warn"
    else:
        answer_status = "fail"
    checks.append(
        CheckResult(
            "recent_posts_answer_block_ratio",
            answer_status,
            f"{answer_count}/{len(post_paths)} recent posts include Answer Block or structured Q&A",
            critical=False,
        )
    )

    if evidence_ratio >= 0.9:
        evidence_status = "pass"
    elif evidence_ratio >= 0.7:
        evidence_status = "warn"
    else:
        evidence_status = "fail"
    checks.append(
        CheckResult(
            "recent_posts_evidence_link_ratio",
            evidence_status,
            f"{evidence_count}/{len(post_paths)} recent posts include repository evidence links",
            critical=False,
        )
    )

    critical_failed = sum(1 for c in checks if c.critical and c.status == "fail")
    warnings = sum(1 for c in checks if c.status == "warn")
    noncritical_failed = sum(1 for c in checks if (not c.critical) and c.status == "fail")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "today": today.isoformat(),
        "recent_posts_window": len(post_paths),
        "answer_block_ratio": round(answer_ratio, 4),
        "evidence_link_ratio": round(evidence_ratio, 4),
        "latest_dashboard_snapshot_age_days": snapshot_age_days,
        "checks": [c.__dict__ for c in checks],
        "summary": {
            "critical_failed": critical_failed,
            "warnings": warnings,
            "noncritical_failed": noncritical_failed,
            "overall_status": (
                "fail"
                if critical_failed
                else "warn"
                if (warnings or noncritical_failed)
                else "pass"
            ),
        },
    }


def _render_markdown_report(metrics: dict[str, Any]) -> str:
    checks = metrics.get("checks", [])
    summary = metrics.get("summary", {})
    lines = [
        "# AI Discoverability Report",
        "",
        f"- Generated: {metrics.get('generated_at', 'unknown')}",
        f"- Recent posts window: {metrics.get('recent_posts_window', 0)}",
        f"- Answer Block ratio: {metrics.get('answer_block_ratio', 0):.2f}",
        f"- Evidence link ratio: {metrics.get('evidence_link_ratio', 0):.2f}",
        f"- Latest dashboard snapshot age (days): {metrics.get('latest_dashboard_snapshot_age_days')}",
        f"- Overall status: **{summary.get('overall_status', 'unknown').upper()}**",
        "",
        "## Checks",
    ]
    for check in checks:
        status = str(check.get("status", "unknown")).upper()
        critical_tag = " (critical)" if check.get("critical") else ""
        lines.append(f"- `{check.get('name')}`: **{status}**{critical_tag} - {check.get('detail')}")

    lines.append("")
    lines.append("## Recommendation")
    lines.append(
        "- Keep one canonical page per topic; use llms manifests as index pointers, not alternate content pages."
    )
    return "\n".join(lines) + "\n"


def _should_fail(metrics: dict[str, Any], fail_on: str) -> bool:
    summary = metrics.get("summary", {})
    critical_failed = int(summary.get("critical_failed", 0))
    warnings = int(summary.get("warnings", 0))
    noncritical_failed = int(summary.get("noncritical_failed", 0))

    if fail_on == "none":
        return False
    if fail_on == "critical":
        return critical_failed > 0
    return (critical_failed + warnings + noncritical_failed) > 0


def _sync_state(state_path: Path, metrics: dict[str, Any]) -> None:
    state = _safe_load_json(state_path)
    content = state.setdefault("content", {})
    content["discoverability"] = {
        "generated_at": metrics.get("generated_at"),
        "overall_status": metrics.get("summary", {}).get("overall_status"),
        "answer_block_ratio": metrics.get("answer_block_ratio"),
        "evidence_link_ratio": metrics.get("evidence_link_ratio"),
        "latest_dashboard_snapshot_age_days": metrics.get("latest_dashboard_snapshot_age_days"),
        "critical_failed": metrics.get("summary", {}).get("critical_failed"),
        "warnings": metrics.get("summary", {}).get("warnings"),
        "noncritical_failed": metrics.get("summary", {}).get("noncritical_failed"),
    }
    _write_json(state_path, state)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check AI discoverability hygiene for content")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--report", default="artifacts/devloop/ai_discoverability_report.md")
    parser.add_argument("--json-out", default="artifacts/devloop/ai_discoverability_report.json")
    parser.add_argument("--state", default="data/system_state.json")
    parser.add_argument("--sync-state", action="store_true")
    parser.add_argument("--recent-posts", type=int, default=20)
    parser.add_argument("--max-snapshot-age-days", type=int, default=2)
    parser.add_argument(
        "--fail-on",
        choices=["none", "critical", "all"],
        default="critical",
        help="Failure mode: none, critical-only, or all warnings+fails",
    )
    args = parser.parse_args()

    metrics = collect_discoverability_metrics(
        repo_root=Path(args.repo_root),
        recent_posts=max(1, args.recent_posts),
        max_snapshot_age_days=max(0, args.max_snapshot_age_days),
    )

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_render_markdown_report(metrics), encoding="utf-8")

    json_path = Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    if args.sync_state:
        _sync_state(Path(args.state), metrics)

    print(f"Wrote discoverability report: {report_path}")
    print(f"Wrote discoverability JSON: {json_path}")

    if _should_fail(metrics, args.fail_on):
        print("Discoverability gate failed.")
        return 2

    print("Discoverability gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
