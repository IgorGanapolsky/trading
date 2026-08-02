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
ANY_REF_PATTERN = re.compile(rf"uses:\s*{re.escape(MONOREPO_ACTION)}/([\w-]+)@(\S+)")
FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def _collect_refs() -> dict[str, list[str]]:
    """Every codeql-action reference (any ref form) -> its usage sites."""
    ref_sites: dict[str, list[str]] = {}
    for workflow in sorted(WORKFLOWS.glob("*.y*ml")):
        for subaction, ref in ANY_REF_PATTERN.findall(workflow.read_text(encoding="utf-8")):
            ref_sites.setdefault(ref.lower(), []).append(f"{workflow.name}:{subaction}")
    return ref_sites


def test_every_codeql_reference_is_full_sha_pinned():
    """A tag ref (@v4) would silently escape a SHA-only scan and can drift
    independently of the pinned sites — reject any non-40-hex reference."""
    ref_sites = _collect_refs()
    assert ref_sites, "expected at least one codeql-action reference in workflows"
    loose = {ref: sites for ref, sites in ref_sites.items() if not FULL_SHA.match(ref)}
    assert not loose, f"{MONOREPO_ACTION} references not pinned to a full SHA: {loose}"


def test_codeql_action_pinned_to_single_sha_everywhere():
    ref_sites = _collect_refs()
    assert ref_sites, "expected at least one codeql-action reference in workflows"
    assert len(ref_sites) == 1, (
        f"{MONOREPO_ACTION} subactions pinned at different refs — CodeQL will "
        f"fail on every PR until aligned: {ref_sites}"
    )
