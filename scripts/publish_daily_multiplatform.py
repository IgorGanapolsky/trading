#!/usr/bin/env python3
"""Publish a daily report to Dev.to, LinkedIn, X, and record verification artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.cross_publish import parse_frontmatter, publish_to_devto, publish_to_linkedin
from scripts.publish_twitter import (
    generate_twitter_post,
    missing_credential_names,
    post_to_twitter,
    resolve_credentials,
)

ET = ZoneInfo("America/New_York")
DEFAULT_SITE_URL = "https://igorganapolsky.github.io/trading"


@dataclass
class PlatformResult:
    status: str
    detail: str = ""
    url: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"status": self.status, "detail": self.detail}
        if self.url:
            payload["url"] = self.url
        return payload


def _derive_report_date(report_path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    match = re.match(r"^(\d{4}-\d{2}-\d{2})-", report_path.name)
    if match:
        return match.group(1)
    return datetime.now(ET).date().isoformat()


def _canonical_url(report_path: Path, frontmatter: dict[str, Any], site_url: str) -> str:
    canonical = str(frontmatter.get("canonical_url") or "").strip()
    if canonical:
        return canonical
    stem = report_path.stem
    return f"{site_url}/reports/{stem}/"


def _title(report_path: Path, frontmatter: dict[str, Any], body: str) -> str:
    fm_title = str(frontmatter.get("title") or "").strip()
    if fm_title:
        return fm_title
    for line in body.splitlines():
        text = line.strip()
        if text.startswith("# "):
            return text[2:].strip()
    return report_path.stem.replace("-", " ").title()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _write_markdown_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_et = result.get("generated_at_et", "")
    report_date = result.get("date", "")
    report_file = result.get("report_path", "")
    canonical_url = result.get("canonical_url", "")
    title = result.get("title", "")
    platforms = result.get("platforms", {})

    lines = [
        "---",
        "layout: post",
        f'title: "Publication Status - {report_date}"',
        f"date: {report_date}",
        "---",
        "",
        f"# Daily Publication Status - {report_date}",
        "",
        f"- Generated (ET): `{generated_et}`",
        f"- Report file: `{report_file}`",
        f"- Canonical URL: {canonical_url}",
        f"- Title: {title}",
        "",
        "| Platform | Status | Details |",
        "|---|---|---|",
    ]

    for name in ("gh_pages", "devto", "linkedin", "x"):
        info = platforms.get(name, {})
        status = str(info.get("status", "unknown"))
        detail = str(info.get("detail", ""))
        url = str(info.get("url", "")) if info.get("url") else ""
        extra = f"{detail} {url}".strip()
        lines.append(f"| {name} | {status} | {extra} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def publish_daily_report(
    report_path: Path,
    *,
    report_date: str | None = None,
    site_url: str = DEFAULT_SITE_URL,
    strict: bool = False,
    dry_run: bool = False,
) -> tuple[int, dict[str, Any]]:
    if not report_path.exists():
        result = {
            "date": report_date or datetime.now(ET).date().isoformat(),
            "report_path": str(report_path),
            "generated_at_et": datetime.now(ET).isoformat(),
            "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "error": "report_missing",
            "platforms": {
                "gh_pages": PlatformResult("failed", "Report file does not exist").as_dict(),
                "devto": PlatformResult("skipped", "No report to publish").as_dict(),
                "linkedin": PlatformResult("skipped", "No report to publish").as_dict(),
                "x": PlatformResult("skipped", "No report to publish").as_dict(),
            },
        }
        return 1, result

    raw = report_path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(raw)
    computed_date = _derive_report_date(report_path, report_date)
    title = _title(report_path, frontmatter, body)
    canonical = _canonical_url(report_path, frontmatter, site_url)
    tags = frontmatter.get("tags", frontmatter.get("categories", ["ai", "trading", "automation"]))
    if not isinstance(tags, list):
        tags = ["ai", "trading", "automation"]

    platforms: dict[str, dict[str, Any]] = {}

    platforms["gh_pages"] = PlatformResult(
        "success",
        "Report file exists and is ready for Pages deploy.",
        url=canonical,
    ).as_dict()

    devto_key = os.environ.get("DEVTO_API_KEY") or os.environ.get("DEV_TO_API_KEY")
    if not devto_key:
        platforms["devto"] = PlatformResult("skipped", "DEVTO_API_KEY missing").as_dict()
    else:
        try:
            devto_url = publish_to_devto(title, body, tags, canonical)
            if devto_url:
                platforms["devto"] = PlatformResult("success", "Published", url=devto_url).as_dict()
            else:
                platforms["devto"] = PlatformResult("failed", "API publish failed").as_dict()
        except Exception as exc:  # pragma: no cover - defensive
            platforms["devto"] = PlatformResult("failed", f"Exception: {exc}").as_dict()

    linkedin_token = re.sub(r"\s+", "", os.environ.get("LINKEDIN_ACCESS_TOKEN", ""))
    if not linkedin_token:
        platforms["linkedin"] = PlatformResult(
            "skipped", "LINKEDIN_ACCESS_TOKEN missing"
        ).as_dict()
    else:
        try:
            linkedin_ok = publish_to_linkedin(title, body, canonical)
            if linkedin_ok:
                platforms["linkedin"] = PlatformResult("success", "Published").as_dict()
            else:
                platforms["linkedin"] = PlatformResult("failed", "API publish failed").as_dict()
        except Exception as exc:  # pragma: no cover - defensive
            platforms["linkedin"] = PlatformResult("failed", f"Exception: {exc}").as_dict()

    x_credentials = resolve_credentials()
    x_missing = missing_credential_names(x_credentials)
    if x_missing:
        platforms["x"] = PlatformResult("skipped", f"Missing credentials: {', '.join(x_missing)}").as_dict()
    else:
        tweet = generate_twitter_post("positive", title, canonical)
        x_ok = post_to_twitter(tweet, dry_run=dry_run)
        platforms["x"] = (
            PlatformResult("success", "Published")
            if x_ok
            else PlatformResult("failed", "API publish failed")
        ).as_dict()

    result = {
        "date": computed_date,
        "report_path": str(report_path),
        "title": title,
        "canonical_url": canonical,
        "generated_at_et": datetime.now(ET).isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "platforms": platforms,
    }

    if not strict:
        return 0, result

    failures: list[str] = []
    if platforms["gh_pages"]["status"] != "success":
        failures.append("gh_pages")
    if devto_key and platforms["devto"]["status"] != "success":
        failures.append("devto")
    if linkedin_token and platforms["linkedin"]["status"] != "success":
        failures.append("linkedin")
    if not x_missing and platforms["x"]["status"] != "success":
        failures.append("x")
    if failures:
        result["strict_failures"] = failures
        return 1, result
    return 0, result


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish daily report to all blog channels")
    parser.add_argument(
        "--report",
        required=True,
        help="Path to daily report markdown file (e.g., docs/_reports/YYYY-MM-DD-daily-report.md)",
    )
    parser.add_argument("--date", help="Report date override (YYYY-MM-DD)")
    parser.add_argument("--strict", action="store_true", help="Fail when enabled platform publish fails")
    parser.add_argument("--dry-run-x", action="store_true", help="Dry-run X publish only")
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL, help="Canonical site base URL")
    args = parser.parse_args()

    report_path = Path(args.report)
    exit_code, result = publish_daily_report(
        report_path,
        report_date=args.date,
        site_url=args.site_url.rstrip("/"),
        strict=args.strict,
        dry_run=args.dry_run_x,
    )

    report_date = str(result.get("date", datetime.now(ET).date().isoformat()))
    status_json = PROJECT_ROOT / "data" / "analytics" / f"{report_date}-publication-status.json"
    status_jsonl = PROJECT_ROOT / "data" / "analytics" / "publication-status-history.jsonl"
    md_report = PROJECT_ROOT / "docs" / "_reports" / f"{report_date}-publication-status.md"

    _write_json(status_json, result)
    _append_jsonl(status_jsonl, result)
    _write_markdown_report(md_report, result)

    print(json.dumps(result, indent=2))
    print(f"Wrote status JSON: {status_json}")
    print(f"Appended status history: {status_jsonl}")
    print(f"Wrote status report: {md_report}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
