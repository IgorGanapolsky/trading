#!/usr/bin/env python3
"""Fail-closed OpenSSF Scorecard hygiene for workflows and Dockerfiles.

Prevents Token-Permissions and Pinned-Dependencies regressions from landing
on main. Prints JSON. Never opens GitHub Issues (LL-569).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO / ".github" / "workflows"
DOCKERFILES = (
    REPO / "go" / "adk_trading" / "Dockerfile",
    REPO / "tests" / "evals" / "harbor_configs" / "environment" / "Dockerfile",
)

READ_ONLY_PERM_VALUES = frozenset({"read", "none", "read-all"})
PIP_INSTALL_RE = re.compile(
    r"(?:^|\s|&&)(?:python\d*(?:\s+-m\s+)?pip|pip3?)\s+install\b",
    re.IGNORECASE,
)
HASHED_PIP_RE = re.compile(r"--require-hashes|--hash(?:=|\s)", re.IGNORECASE)
FROM_RE = re.compile(r"^FROM\s+(\S+)", re.IGNORECASE | re.MULTILINE)
STAGE_FROM_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")


def _top_level_permission_findings(path: Path, doc: dict[str, Any]) -> list[str]:
    perms = doc.get("permissions")
    rel = path.as_posix()
    if perms is None:
        return [f"{rel}: missing top-level permissions (Scorecard Token-Permissions)"]
    if isinstance(perms, str):
        token = perms.strip().lower()
        if token in {"read-all", "contents: read"}:
            return []
        return [f"{rel}: top-level permissions {perms!r} must be read-all"]
    if not isinstance(perms, dict):
        return [f"{rel}: top-level permissions must be a mapping or read-all"]
    bad: list[str] = []
    for key, value in perms.items():
        if str(value).strip().lower() not in READ_ONLY_PERM_VALUES:
            bad.append(f"{rel}: top-level {key}: {value} (move write scopes to the job)")
    return bad


def _pip_findings(path: Path, text: str) -> list[str]:
    findings: list[str] = []
    # Split on step-like run blocks so --require-hashes on a later line counts.
    for idx, line in enumerate(text.splitlines(), start=1):
        stripped = line.split("#", 1)[0]
        if not PIP_INSTALL_RE.search(stripped):
            continue
        window = "\n".join(text.splitlines()[idx - 1 : idx + 8])
        if HASHED_PIP_RE.search(window):
            continue
        findings.append(
            f"{path.as_posix()}:{idx}: unhashed pip install (use uv sync --frozen "
            "or pip --require-hashes)"
        )
    return findings


def _dockerfile_findings(path: Path) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    findings: list[str] = []
    stages: set[str] = set()
    for match in FROM_RE.finditer(text):
        image = match.group(1)
        if image.lower() == "scratch":
            continue
        alias = ""
        raw = match.group(0)
        as_match = re.search(r"\s+AS\s+(\S+)", raw, re.IGNORECASE)
        if as_match:
            alias = as_match.group(1)
            stages.add(alias)
        base = image.split("@", 1)[0]
        if (
            base in stages
            or STAGE_FROM_RE.fullmatch(base)
            and "@" not in image
            and "/" not in base
            and ":" not in base
        ):
            # stage reference like FROM base
            if "@" not in image and ":" not in image:
                continue
        if "@sha256:" not in image:
            findings.append(f"{path.as_posix()}: unpinned FROM {image}")
    findings.extend(_pip_findings(path, text))
    return findings


def scan(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    workflows = root / ".github" / "workflows"
    findings: list[str] = []
    workflow_count = 0
    for path in sorted(workflows.glob("*.yml")):
        workflow_count += 1
        text = path.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
        if not isinstance(doc, dict):
            findings.append(f"{path.as_posix()}: workflow YAML is not a mapping")
            continue
        findings.extend(_top_level_permission_findings(path, doc))
        findings.extend(_pip_findings(path, text))
        if "issues: write" in text and "github.rest.issues.create(" in text:
            findings.append(f"{path.as_posix()}: must not create GitHub Issues")

    dockerfiles = (
        root / "go" / "adk_trading" / "Dockerfile",
        root / "tests" / "evals" / "harbor_configs" / "environment" / "Dockerfile",
    )
    for path in dockerfiles:
        findings.extend(_dockerfile_findings(path))

    return {
        "ok": not findings,
        "workflow_count": workflow_count,
        "finding_count": len(findings),
        "findings": findings,
        "never_opens_github_issues": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPO)
    args = parser.parse_args(argv)
    payload = scan(args.repo_root.resolve())
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if payload["ok"]:
            print(f"ok: {payload['workflow_count']} workflows, 0 Scorecard hygiene findings")
        else:
            print(f"FAIL: {payload['finding_count']} findings")
            for item in payload["findings"]:
                print(f"  - {item}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
