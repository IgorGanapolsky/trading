"""Deterministic coordination checks for Linear, Vault, Herdr, and Git.

Linear and the shared Obsidian Vault remain external sources of truth. This
module reads their claim notes and validates local/GitHub state; it does not
create a second task database or infer completion from terminal presence.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # nosec B404
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

ISSUE_KEY_PATTERN = re.compile(r"\b((?:AGENT|IGO)-\d+)\b", re.IGNORECASE)
FULL_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
ACTIVE_STATES = frozenset({"in progress", "started"})
DEPENDABOT_LOGIN = "dependabot[bot]"
LEGACY_LABEL = "coordination-legacy"


@dataclass(frozen=True)
class Claim:
    """Latest durable Vault mirror for one Linear issue."""

    issue_key: str
    agent: str
    status: str
    action: str
    updated_at: str
    claimed_files: tuple[str, ...]
    path: Path

    @property
    def active(self) -> bool:
        return self.status.strip().lower() in ACTIVE_STATES


@dataclass(frozen=True)
class Finding:
    """One coordination validation result."""

    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class Worktree:
    path: Path
    head: str
    branch: str | None


def normalize_issue_key(value: str | None) -> str | None:
    """Return a canonical issue key found in arbitrary text."""

    if not value:
        return None
    match = ISSUE_KEY_PATTERN.search(value)
    return match.group(1).upper() if match else None


def default_vault_root() -> Path:
    return Path(os.environ.get("AI_AGENT_SYNC_VAULT", "~/Documents/AI-Agent-Sync")).expanduser()


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse the small YAML subset emitted by linear-agent-bridge.js."""

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}

    result: dict[str, Any] = {}
    active_list: str | None = None
    for raw_line in lines[1:end]:
        if raw_line.startswith("  - ") and active_list:
            result.setdefault(active_list, []).append(raw_line[4:].strip())
            continue
        match = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", raw_line)
        if not match:
            continue
        key, value = match.groups()
        if value:
            result[key] = value.strip().strip("\"'")
            active_list = None
        else:
            result[key] = []
            active_list = key
    return result


def read_claim(path: Path) -> Claim | None:
    payload = _parse_frontmatter(path.read_text(encoding="utf-8"))
    issue_key = normalize_issue_key(str(payload.get("linear_id", "")))
    if not issue_key:
        return None
    claimed_files = payload.get("claimed_files", [])
    if not isinstance(claimed_files, list):
        claimed_files = []
    return Claim(
        issue_key=issue_key,
        agent=str(payload.get("agent", "")).strip().lower(),
        status=str(payload.get("status", "")).strip(),
        action=str(payload.get("action", "")).strip(),
        updated_at=str(payload.get("updated_at", "")).strip(),
        claimed_files=tuple(str(item).strip() for item in claimed_files if str(item).strip()),
        path=path,
    )


def load_latest_claims(vault_root: Path | None = None) -> dict[str, Claim]:
    """Load the newest Vault claim note for every Linear issue."""

    root = (vault_root or default_vault_root()).expanduser().resolve()
    claims_dir = root / "Handoffs" / "linear-claims"
    if not claims_dir.is_dir():
        return {}
    claims: dict[str, Claim] = {}
    for path in sorted(claims_dir.glob("*.md")):
        claim = read_claim(path)
        if claim is None:
            continue
        previous = claims.get(claim.issue_key)
        claim_order = (claim.updated_at, path.stat().st_mtime_ns)
        previous_order = (
            (previous.updated_at, previous.path.stat().st_mtime_ns) if previous else ("", -1)
        )
        if previous is None or claim_order > previous_order:
            claims[claim.issue_key] = claim
    return claims


def _run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # nosec B603 B607
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


def _git_text(repo: Path, *args: str) -> str:
    return _run_git(repo, *args).stdout.strip()


def list_worktrees(repo_root: Path) -> list[Worktree]:
    """Return worktrees from Git's porcelain format without guessing paths."""

    output = _git_text(repo_root, "worktree", "list", "--porcelain")
    records: list[Worktree] = []
    current: dict[str, str] = {}
    for line in [*output.splitlines(), ""]:
        if not line:
            if current.get("worktree"):
                branch = current.get("branch")
                if branch and branch.startswith("refs/heads/"):
                    branch = branch.removeprefix("refs/heads/")
                records.append(
                    Worktree(
                        path=Path(current["worktree"]).resolve(),
                        head=current.get("HEAD", ""),
                        branch=branch,
                    )
                )
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return records


def _normalized_scope(scope: str, repo_root: Path) -> str:
    raw = scope.strip().replace("\\", "/")
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        try:
            raw = candidate.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return candidate.resolve().as_posix()
    normalized = PurePosixPath(raw.removeprefix("./")).as_posix().rstrip("/")
    return normalized or "."


def scopes_overlap(left: str, right: str, repo_root: Path) -> bool:
    """Return whether two claimed file/directory scopes intersect."""

    first = _normalized_scope(left, repo_root)
    second = _normalized_scope(right, repo_root)
    broad = {".", repo_root.name}
    if first in broad or second in broad:
        return True
    return first == second or first.startswith(f"{second}/") or second.startswith(f"{first}/")


def _scope_covers(claimed_scope: str, candidate: str, repo_root: Path) -> bool:
    claimed = _normalized_scope(claimed_scope, repo_root)
    requested = _normalized_scope(candidate, repo_root)
    return (
        claimed in {".", repo_root.name}
        or requested == claimed
        or requested.startswith(f"{claimed}/")
    )


def _is_linked_worktree(repo_root: Path) -> bool:
    git_dir = Path(_git_text(repo_root, "rev-parse", "--git-dir"))
    common_dir = Path(_git_text(repo_root, "rev-parse", "--git-common-dir"))
    if not git_dir.is_absolute():
        git_dir = (repo_root / git_dir).resolve()
    if not common_dir.is_absolute():
        common_dir = (repo_root / common_dir).resolve()
    return git_dir != common_dir


def validate_local_preflight(
    repo_root: Path,
    *,
    vault_root: Path | None = None,
    issue_key: str | None = None,
    agent: str | None = None,
    candidate_files: Sequence[str] = (),
) -> list[Finding]:
    """Validate the durable claim and isolated worktree before local writes."""

    root = repo_root.resolve()
    findings: list[Finding] = []
    try:
        branch = _git_text(root, "branch", "--show-current")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return [Finding("error", "not-git-repository", str(exc))]

    branch_key = normalize_issue_key(branch)
    requested_key = normalize_issue_key(issue_key) if issue_key else branch_key
    if not branch_key:
        findings.append(
            Finding(
                "error",
                "branch-missing-issue",
                f"branch '{branch or '(detached)'}' has no issue key",
            )
        )
    if requested_key and branch_key and requested_key != branch_key:
        findings.append(
            Finding(
                "error",
                "branch-issue-mismatch",
                f"branch key {branch_key} does not match requested {requested_key}",
            )
        )
    if not _is_linked_worktree(root):
        findings.append(
            Finding("error", "primary-checkout", "writes require a dedicated linked worktree")
        )

    claims = load_latest_claims(vault_root)
    claim = claims.get(requested_key or "")
    if claim is None:
        findings.append(
            Finding("error", "claim-missing", f"no Vault claim for {requested_key or 'branch'}")
        )
        return findings
    if not claim.active:
        findings.append(
            Finding(
                "error",
                "claim-inactive",
                f"{claim.issue_key} is {claim.status or 'missing a state'}, not In Progress",
            )
        )
    requested_agent = (agent or claim.agent).strip().lower()
    if not requested_agent or claim.agent != requested_agent:
        findings.append(
            Finding(
                "error",
                "claim-agent-mismatch",
                f"{claim.issue_key} belongs to {claim.agent or '(unknown)'}, not {requested_agent or '(unknown)'}",
            )
        )
    if not claim.claimed_files:
        findings.append(Finding("error", "claim-files-empty", "claim has no file scope"))

    files_to_check = tuple(candidate_files) or claim.claimed_files
    for candidate in files_to_check:
        if not any(_scope_covers(scope, candidate, root) for scope in claim.claimed_files):
            findings.append(
                Finding(
                    "error",
                    "file-outside-claim",
                    f"{candidate} is not covered by {claim.issue_key}",
                )
            )

    for foreign in claims.values():
        if foreign.issue_key == claim.issue_key or not foreign.active:
            continue
        for candidate in files_to_check:
            if any(scopes_overlap(candidate, scope, root) for scope in foreign.claimed_files):
                findings.append(
                    Finding(
                        "error",
                        "foreign-claim-overlap",
                        f"{candidate} overlaps {foreign.issue_key}/{foreign.agent}: "
                        f"{', '.join(foreign.claimed_files)}",
                    )
                )
                break
    return findings


def _body_field(body: str, label: str) -> str:
    # Keep matching on one Markdown line. ``\s`` includes newlines and caused
    # an empty field to consume the following heading or checklist item.
    match = re.search(rf"(?im)^-[ \t]*{re.escape(label)}:[ \t]*(.*?)[ \t]*$", body)
    return match.group(1).strip() if match else ""


def validate_pr_event(event: Mapping[str, Any]) -> list[Finding]:
    """Validate issue/claim metadata from a GitHub pull_request event."""

    pull_request = event.get("pull_request")
    if not isinstance(pull_request, Mapping):
        return [Finding("error", "event-shape", "pull_request payload is missing")]
    head = pull_request.get("head") or {}
    user = pull_request.get("user") or {}
    branch = str(head.get("ref", "")) if isinstance(head, Mapping) else ""
    login = str(user.get("login", "")) if isinstance(user, Mapping) else ""
    body = str(pull_request.get("body") or "")
    labels_raw = pull_request.get("labels") or []
    labels = {
        str(item.get("name", "")).lower()
        for item in labels_raw
        if isinstance(item, Mapping) and item.get("name")
    }

    if login == DEPENDABOT_LOGIN and branch.startswith("dependabot/"):
        return []
    if LEGACY_LABEL in labels:
        reason = _body_field(body, "Coordination legacy reason")
        if reason:
            return [
                Finding(
                    "warning",
                    "legacy-exception",
                    f"legacy coordination exception: {reason}",
                )
            ]
        return [
            Finding(
                "error",
                "legacy-reason-missing",
                f"{LEGACY_LABEL} requires '- Coordination legacy reason:' in the PR body",
            )
        ]

    findings: list[Finding] = []
    branch_key = normalize_issue_key(branch)
    linear_value = _body_field(body, "Linear issue")
    body_key = normalize_issue_key(linear_value)
    if not branch_key:
        findings.append(
            Finding("error", "pr-branch-missing-issue", f"branch '{branch}' has no issue key")
        )
    if not body_key:
        findings.append(Finding("error", "pr-body-missing-issue", "Linear issue is missing"))
    if branch_key and body_key and branch_key != body_key:
        findings.append(
            Finding(
                "error",
                "pr-issue-mismatch",
                f"branch {branch_key} does not match PR body {body_key}",
            )
        )

    required_fields = {
        "Agent": _body_field(body, "Agent"),
        "Branch/worktree": _body_field(body, "Branch/worktree"),
        "Files or systems claimed": _body_field(body, "Files or systems claimed"),
    }
    for label, value in required_fields.items():
        if not value:
            findings.append(Finding("error", "pr-field-missing", f"PR field '{label}' is empty"))
    base_sha = _body_field(body, "Base SHA")
    if not FULL_SHA_PATTERN.fullmatch(base_sha):
        findings.append(
            Finding("error", "pr-base-sha", "Base SHA must be an exact 40-character commit")
        )
    branch_worktree = required_fields["Branch/worktree"]
    if branch and branch_worktree and branch not in branch_worktree:
        findings.append(
            Finding("error", "pr-worktree-branch", "Branch/worktree must name the PR branch")
        )
    for checkbox in (
        "Linear issue and vault claim updated",
        "No overlapping active claim or worktree",
    ):
        if not re.search(rf"(?im)^-\s*\[[xX]\]\s*{re.escape(checkbox)}\s*$", body):
            findings.append(
                Finding("error", "pr-checkbox", f"unchecked coordination item: {checkbox}")
            )
    return findings


def _parse_herdr_agents(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not payload:
        return []
    result = payload.get("result")
    if isinstance(result, Mapping) and isinstance(result.get("agents"), list):
        return [item for item in result["agents"] if isinstance(item, Mapping)]
    return []


def read_herdr_agents() -> Mapping[str, Any] | None:
    if os.environ.get("HERDR_ENV") != "1" or shutil.which("herdr") is None:
        return None
    completed = subprocess.run(  # nosec B603 B607
        ["herdr", "agent", "list"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if completed.returncode != 0:
        return None
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, Mapping) else None


def audit_repository(
    repo_root: Path,
    *,
    vault_root: Path | None = None,
    herdr_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconcile active claims, local worktrees, and live Herdr agents."""

    root = repo_root.resolve()
    claims = load_latest_claims(vault_root)
    active_claims = {key: claim for key, claim in claims.items() if claim.active}
    worktrees = list_worktrees(root)
    findings: list[Finding] = []

    active_values = list(active_claims.values())
    for index, left in enumerate(active_values):
        for right in active_values[index + 1 :]:
            if any(
                scopes_overlap(first, second, root)
                for first in left.claimed_files
                for second in right.claimed_files
            ):
                findings.append(
                    Finding(
                        "error",
                        "active-claim-overlap",
                        f"{left.issue_key}/{left.agent} overlaps {right.issue_key}/{right.agent}",
                    )
                )

    worktree_by_path = {item.path: item for item in worktrees}
    for worktree in worktrees[1:]:
        key = normalize_issue_key(worktree.branch or worktree.path.name)
        if not key:
            findings.append(
                Finding(
                    "warning",
                    "worktree-missing-issue",
                    f"{worktree.path} has no issue key",
                )
            )
        elif key not in active_claims:
            findings.append(
                Finding(
                    "warning",
                    "worktree-without-active-claim",
                    f"{worktree.path} references {key} without an active claim",
                )
            )

    observed_herdr = herdr_payload if herdr_payload is not None else read_herdr_agents()
    for live_agent in _parse_herdr_agents(observed_herdr):
        cwd_raw = str(live_agent.get("foreground_cwd") or live_agent.get("cwd") or "")
        if not cwd_raw:
            continue
        cwd = Path(cwd_raw).expanduser().resolve()
        # Linked worktrees commonly live below the primary checkout (for
        # example ``repo/.worktrees/issue``). Choose the deepest registered
        # ancestor so the primary checkout cannot shadow the issue worktree.
        matched = max(
            (item for path, item in worktree_by_path.items() if cwd == path or path in cwd.parents),
            key=lambda item: len(item.path.parts),
            default=None,
        )
        if matched is None:
            continue
        key = normalize_issue_key(matched.branch or matched.path.name)
        agent = str(live_agent.get("agent", "")).lower()
        if not key:
            findings.append(
                Finding(
                    "error",
                    "live-agent-without-claim",
                    f"Herdr agent {agent or '(unknown)'} is working in {cwd} without an issue worktree",
                )
            )
            continue
        claim = active_claims.get(key)
        if claim and claim.agent != agent:
            findings.append(
                Finding(
                    "error",
                    "live-agent-claim-mismatch",
                    f"Herdr agent {agent} is in {key}, claimed by {claim.agent}",
                )
            )

    return {
        "repo_root": str(root),
        "active_claims": [asdict(item) | {"path": str(item.path)} for item in active_values],
        "worktrees": [asdict(item) | {"path": str(item.path)} for item in worktrees],
        "herdr_agents": list(_parse_herdr_agents(observed_herdr)),
        "findings": [asdict(item) for item in findings],
        "errors": sum(item.severity == "error" for item in findings),
        "warnings": sum(item.severity == "warning" for item in findings),
    }


def protect_worktree(
    repo_root: Path,
    target: Path,
    *,
    vault_root: Path | None = None,
) -> list[Finding]:
    """Fail closed unless a worktree is unclaimed, clean, and in origin/main."""

    root = repo_root.resolve()
    resolved_target = target.expanduser().resolve()
    findings: list[Finding] = []
    worktrees = {item.path: item for item in list_worktrees(root)}
    worktree = worktrees.get(resolved_target)
    if worktree is None:
        return [Finding("error", "unknown-worktree", f"{resolved_target} is not registered")]
    if resolved_target == root:
        findings.append(Finding("error", "primary-worktree", "never remove the primary checkout"))
        return findings

    key = normalize_issue_key(worktree.branch or resolved_target.name)
    claims = load_latest_claims(vault_root)
    if key and (claim := claims.get(key)) and claim.active:
        findings.append(
            Finding(
                "error",
                "active-worktree-claim",
                f"{resolved_target} is protected by {claim.issue_key}/{claim.agent}",
            )
        )
    status = _git_text(resolved_target, "status", "--porcelain")
    if status:
        findings.append(
            Finding("error", "dirty-worktree", f"{resolved_target} has uncommitted files")
        )
    ancestor = _run_git(
        resolved_target,
        "merge-base",
        "--is-ancestor",
        "HEAD",
        "origin/main",
        check=False,
    )
    if ancestor.returncode != 0:
        # Squash merges deliberately produce a different commit SHA. Git's
        # patch-id comparison marks those commits with ``-`` when their patch
        # is already represented on origin/main. Only accept the worktree when
        # every unique commit is patch-equivalent; any ``+`` remains protected.
        cherry = _run_git(
            resolved_target,
            "cherry",
            "origin/main",
            "HEAD",
            check=False,
        )
        patch_lines = [line for line in cherry.stdout.splitlines() if line.strip()]
        patch_equivalent = (
            cherry.returncode == 0
            and bool(patch_lines)
            and all(line.startswith("- ") for line in patch_lines)
        )
        if not patch_equivalent:
            findings.append(
                Finding(
                    "error",
                    "unmerged-worktree",
                    f"{resolved_target} has commits not represented on origin/main",
                )
            )
    return findings


def has_errors(findings: Iterable[Finding]) -> bool:
    return any(item.severity == "error" for item in findings)
