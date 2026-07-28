"""GitHub Actions version-alignment eval.

Incident source (2026-07-27): dependabot merged the codeql-action
upload-sarif bump while init stayed one version behind; the resulting
'Loaded a configuration file for version 4.37.1, but running 4.37.3'
error turned CodeQL red on every PR in the repo. The codeql-action
subactions ship from one monorepo and must be pinned to one commit SHA
across all workflows.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"

MONOREPO_ACTION = "github/codeql-action"
REF_PATTERN = re.compile(
    rf"uses:\s*{re.escape(MONOREPO_ACTION)}/([\w-]+)@([0-9a-fA-F]{{7,40}})"
)


def test_codeql_action_pinned_to_single_sha_everywhere():
    sha_sites: dict[str, list[str]] = {}
    for workflow in sorted(WORKFLOWS.glob("*.y*ml")):
        for subaction, sha in REF_PATTERN.findall(workflow.read_text(encoding="utf-8")):
            sha_sites.setdefault(sha.lower(), []).append(f"{workflow.name}:{subaction}")

    assert sha_sites, "expected at least one codeql-action reference in workflows"
    assert len(sha_sites) == 1, (
        f"{MONOREPO_ACTION} subactions pinned at different SHAs — CodeQL will "
        f"fail on every PR until aligned: {sha_sites}"
    )
