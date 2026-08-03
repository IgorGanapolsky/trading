from __future__ import annotations

import json
import subprocess
from pathlib import Path

import src.coordination.agent_contract as contract
from src.coordination.agent_contract import (
    Finding,
    LEGACY_LABEL,
    audit_repository,
    default_vault_root,
    has_errors,
    load_latest_claims,
    normalize_issue_key,
    protect_worktree,
    read_claim,
    read_herdr_agents,
    scopes_overlap,
    list_worktrees,
    validate_local_preflight,
    validate_pr_event,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    empty_hooks = tmp_path / "empty-hooks"
    empty_hooks.mkdir()
    _git(repo, "config", "core.hooksPath", str(empty_hooks))
    _git(repo, "config", "user.email", "coordination@example.invalid")
    _git(repo, "config", "user.name", "Coordination Test")
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    worktree = repo / ".worktrees" / "agent-27-coordination"
    worktree.parent.mkdir()
    _git(repo, "worktree", "add", "-b", "fix/agent-27-coordination", str(worktree), "main")
    return repo, worktree


def _write_claim(
    vault: Path,
    *,
    issue: str = "AGENT-27",
    agent: str = "codex",
    status: str = "In Progress",
    files: tuple[str, ...] = ("src/coordination", "tests/test_agent_coordination.py"),
    timestamp: str = "2026-08-03T12:00:00Z",
) -> Path:
    claims = vault / "Handoffs" / "linear-claims"
    claims.mkdir(parents=True, exist_ok=True)
    path = claims / f"2026-08-03_{issue}_{agent}.md"
    file_lines = "\n".join(f"  - {item}" for item in files)
    path.write_text(
        "\n".join(
            (
                "---",
                f"linear_id: {issue}",
                f"status: {status}",
                f"agent: {agent}",
                "action: claim",
                f"updated_at: {timestamp}",
                "claimed_files:",
                file_lines,
                "---",
                "",
                f"# Claim {issue}",
            )
        ),
        encoding="utf-8",
    )
    return path


def _valid_pr_event() -> dict:
    body = """# Pull request

## Work item

- Linear issue: AGENT-27
- Agent: codex
- Base SHA: 7e693cc7b7b049c74885e14915e94c5523f595fb
- Branch/worktree: fix/agent-27-coordination / .worktrees/agent-27-coordination
- Files or systems claimed: src/coordination, tests/test_agent_coordination.py
- Coordination legacy reason:

## Coordination

- [x] Linear issue and vault claim updated
- [x] No overlapping active claim or worktree
- [ ] Claim will be marked done or released after merge
"""
    return {
        "pull_request": {
            "head": {"ref": "fix/agent-27-coordination"},
            "user": {"login": "IgorGanapolsky"},
            "labels": [],
            "body": body,
        }
    }


def _codes(findings) -> set[str]:
    return {item.code for item in findings}


def test_latest_claim_wins_and_parses_file_scope(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    _write_claim(vault, timestamp="2026-08-03T11:00:00Z", files=("old.py",))
    latest = _write_claim(vault, timestamp="2026-08-03T12:00:00Z", files=("new.py",))

    claims = load_latest_claims(vault)

    assert claims["AGENT-27"].path == latest
    assert claims["AGENT-27"].claimed_files == ("new.py",)


def test_preflight_accepts_matching_claim_linked_worktree_and_files(tmp_path: Path) -> None:
    _, worktree = _repo_with_worktree(tmp_path)
    vault = tmp_path / "vault"
    _write_claim(vault)

    findings = validate_local_preflight(
        worktree,
        vault_root=vault,
        issue_key="AGENT-27",
        agent="codex",
        candidate_files=("src/coordination/agent_contract.py",),
    )

    assert findings == []


def test_preflight_rejects_primary_checkout(tmp_path: Path) -> None:
    repo, _ = _repo_with_worktree(tmp_path)
    vault = tmp_path / "vault"
    _write_claim(vault)

    assert "primary-checkout" in _codes(validate_local_preflight(repo, vault_root=vault))


def test_preflight_rejects_inactive_wrong_agent_and_unclaimed_file(tmp_path: Path) -> None:
    _, worktree = _repo_with_worktree(tmp_path)
    vault = tmp_path / "vault"
    _write_claim(vault, agent="grok", status="Backlog")

    findings = validate_local_preflight(
        worktree,
        vault_root=vault,
        agent="codex",
        candidate_files=("unclaimed.py",),
    )

    assert {"claim-inactive", "claim-agent-mismatch", "file-outside-claim"} <= _codes(findings)


def test_preflight_rejects_foreign_active_overlap(tmp_path: Path) -> None:
    _, worktree = _repo_with_worktree(tmp_path)
    vault = tmp_path / "vault"
    _write_claim(vault)
    _write_claim(
        vault,
        issue="AGENT-99",
        agent="grok",
        files=("src/coordination/agent_contract.py",),
    )

    findings = validate_local_preflight(
        worktree,
        vault_root=vault,
        candidate_files=("src/coordination/agent_contract.py",),
    )

    assert "foreign-claim-overlap" in _codes(findings)


def test_inactive_foreign_claim_does_not_block(tmp_path: Path) -> None:
    _, worktree = _repo_with_worktree(tmp_path)
    vault = tmp_path / "vault"
    _write_claim(vault)
    _write_claim(
        vault,
        issue="AGENT-99",
        agent="grok",
        status="Done",
        files=("src/coordination",),
    )
    _write_claim(
        vault,
        issue="AGENT-100",
        agent="claude",
        files=("docs",),
    )

    findings = validate_local_preflight(
        worktree,
        vault_root=vault,
        candidate_files=("src/coordination/agent_contract.py",),
    )

    assert findings == []


def test_valid_pr_metadata_passes() -> None:
    assert validate_pr_event(_valid_pr_event()) == []


def test_pr_branch_and_body_issue_must_match() -> None:
    event = _valid_pr_event()
    event["pull_request"]["head"]["ref"] = "fix/agent-88-other"

    assert "pr-issue-mismatch" in _codes(validate_pr_event(event))


def test_pr_requires_exact_base_sha_fields_and_checked_coordination() -> None:
    event = _valid_pr_event()
    event["pull_request"]["body"] = (
        event["pull_request"]["body"]
        .replace("7e693cc7b7b049c74885e14915e94c5523f595fb", "7e693cc")
        .replace("- Agent: codex", "- Agent:")
        .replace(
            "- [x] No overlapping active claim or worktree",
            "- [ ] No overlapping active claim or worktree",
        )
    )

    assert {"pr-base-sha", "pr-field-missing", "pr-checkbox"} <= _codes(validate_pr_event(event))


def test_dependabot_exemption_requires_actor_and_branch() -> None:
    event = {
        "pull_request": {
            "head": {"ref": "dependabot/pip/example-2"},
            "user": {"login": "dependabot[bot]"},
            "labels": [],
            "body": "",
        }
    }
    assert validate_pr_event(event) == []
    event["pull_request"]["user"]["login"] = "human"
    assert "pr-branch-missing-issue" in _codes(validate_pr_event(event))


def test_legacy_exception_requires_visible_reason() -> None:
    event = _valid_pr_event()
    event["pull_request"]["labels"] = [{"name": LEGACY_LABEL}]
    assert "legacy-reason-missing" in _codes(validate_pr_event(event))
    event["pull_request"]["body"] = event["pull_request"]["body"].replace(
        "- Coordination legacy reason:",
        "- Coordination legacy reason: branch predates AGENT-27 enforcement",
    )
    findings = validate_pr_event(event)
    assert [item.code for item in findings] == ["legacy-exception"]


def test_malformed_github_event_fails_closed() -> None:
    assert "event-shape" in _codes(validate_pr_event({}))


def test_worktree_removal_rejects_active_claim(tmp_path: Path) -> None:
    repo, worktree = _repo_with_worktree(tmp_path)
    vault = tmp_path / "vault"
    _write_claim(vault)

    assert "active-worktree-claim" in _codes(protect_worktree(repo, worktree, vault_root=vault))


def test_worktree_removal_rejects_dirty_and_unmerged_targets(tmp_path: Path) -> None:
    repo, worktree = _repo_with_worktree(tmp_path)
    vault = tmp_path / "vault"
    _write_claim(vault, status="Done")
    (worktree / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    dirty = protect_worktree(repo, worktree, vault_root=vault)
    assert "dirty-worktree" in _codes(dirty)

    (worktree / "dirty.txt").unlink()
    (worktree / "unique.txt").write_text("unique\n", encoding="utf-8")
    _git(worktree, "add", "unique.txt")
    _git(worktree, "commit", "-m", "unique")
    unmerged = protect_worktree(repo, worktree, vault_root=vault)
    assert "unmerged-worktree" in _codes(unmerged)


def test_worktree_removal_accepts_inactive_clean_merged_target(tmp_path: Path) -> None:
    repo, worktree = _repo_with_worktree(tmp_path)
    vault = tmp_path / "vault"
    _write_claim(vault, status="Done")

    assert protect_worktree(repo, worktree, vault_root=vault) == []


def test_worktree_removal_accepts_clean_squash_equivalent_target(tmp_path: Path) -> None:
    repo, worktree = _repo_with_worktree(tmp_path)
    vault = tmp_path / "vault"
    _write_claim(vault, status="Done")

    (worktree / "squashed.txt").write_text("same patch\n", encoding="utf-8")
    _git(worktree, "add", "squashed.txt")
    _git(worktree, "commit", "-m", "feature commit")

    (repo / "squashed.txt").write_text("same patch\n", encoding="utf-8")
    _git(repo, "add", "squashed.txt")
    _git(repo, "commit", "-m", "squash merge equivalent")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")

    assert protect_worktree(repo, worktree, vault_root=vault) == []


def test_audit_detects_live_agent_in_primary_checkout(tmp_path: Path) -> None:
    repo, _ = _repo_with_worktree(tmp_path)
    vault = tmp_path / "vault"
    _write_claim(vault)
    payload = {
        "result": {
            "agents": [
                {
                    "agent": "grok",
                    "agent_status": "working",
                    "cwd": str(repo),
                    "foreground_cwd": str(repo),
                }
            ]
        }
    }

    audit = audit_repository(repo, vault_root=vault, herdr_payload=payload)

    assert any(item["code"] == "live-agent-without-claim" for item in audit["findings"])


def test_issue_normalization_and_default_vault(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_AGENT_SYNC_VAULT", str(tmp_path / "vault"))
    assert default_vault_root() == tmp_path / "vault"
    assert normalize_issue_key("fix/agent-27-example") == "AGENT-27"
    assert normalize_issue_key("nothing-here") is None
    assert normalize_issue_key(None) is None


def test_claim_parser_fails_closed_on_malformed_notes(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.md"
    malformed.write_text("not frontmatter\n", encoding="utf-8")
    assert read_claim(malformed) is None

    unclosed = tmp_path / "unclosed.md"
    unclosed.write_text("---\nlinear_id: AGENT-27\n", encoding="utf-8")
    assert read_claim(unclosed) is None

    invalid = tmp_path / "invalid.md"
    invalid.write_text(
        "---\nignored line\nlinear_id: invalid\nclaimed_files: scalar\n---\n",
        encoding="utf-8",
    )
    assert read_claim(invalid) is None

    scalar = tmp_path / "scalar.md"
    scalar.write_text(
        "---\nlinear_id: AGENT-27\nagent: Codex\nstatus: Started\n"
        "action: claim\nupdated_at: '2026-08-03T12:00:00Z'\n"
        "claimed_files: scalar\n---\n",
        encoding="utf-8",
    )
    claim = read_claim(scalar)
    assert claim is not None
    assert claim.active
    assert claim.claimed_files == ()
    assert load_latest_claims(tmp_path / "missing") == {}


def test_claim_loader_skips_invalid_files_and_uses_mtime_tiebreaker(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    claims_dir = vault / "Handoffs" / "linear-claims"
    claims_dir.mkdir(parents=True)
    invalid = claims_dir / "00-invalid.md"
    invalid.write_text("---\nlinear_id: invalid\n---\n", encoding="utf-8")
    first = _write_claim(vault, timestamp="")
    second = claims_dir / "zz-latest.md"
    second.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
    second.touch()
    assert load_latest_claims(vault)["AGENT-27"].path == second

    old = claims_dir / "zzz-old.md"
    old.write_text(
        second.read_text(encoding="utf-8").replace(
            "updated_at: ", "updated_at: 2000-01-01T00:00:00Z"
        ),
        encoding="utf-8",
    )
    assert load_latest_claims(vault)["AGENT-27"].path == second


def test_worktree_parser_handles_detached_and_empty_records(monkeypatch, tmp_path: Path) -> None:
    first = tmp_path / "detached"
    second = tmp_path / "linked"
    output = "\n".join(
        (
            f"worktree {first}",
            "HEAD 1111111111111111111111111111111111111111",
            "detached",
            "",
            "",
            f"worktree {second}",
            "HEAD 2222222222222222222222222222222222222222",
            "branch refs/heads/fix/agent-27-linked",
        )
    )
    monkeypatch.setattr(contract, "_git_text", lambda *args: output)
    parsed = list_worktrees(tmp_path)
    assert [item.branch for item in parsed] == [None, "fix/agent-27-linked"]


def test_scope_matching_handles_broad_absolute_and_external_paths(tmp_path: Path) -> None:
    repo = tmp_path / "trading"
    repo.mkdir()
    assert scopes_overlap(".", "anything.py", repo)
    assert scopes_overlap(str(repo / "src"), "src/module.py", repo)
    assert scopes_overlap("src/module.py", "src", repo)
    assert not scopes_overlap(str(tmp_path / "other"), "src", repo)


def test_preflight_fails_closed_for_non_repo_missing_issue_and_empty_claim(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    assert "not-git-repository" in _codes(validate_local_preflight(outside))

    case_root = tmp_path / "repo-case"
    case_root.mkdir()
    _, worktree = _repo_with_worktree(case_root)
    vault = case_root / "vault"
    findings = validate_local_preflight(
        worktree,
        vault_root=vault,
        issue_key="AGENT-88",
        agent="codex",
    )
    assert {"branch-issue-mismatch", "claim-missing"} <= _codes(findings)

    _write_claim(vault, agent="", files=())
    _write_claim(vault, issue="AGENT-99", agent="grok", files=("other.py",))
    findings = validate_local_preflight(worktree, vault_root=vault, agent="codex")
    assert {"claim-agent-mismatch", "claim-files-empty"} <= _codes(findings)


def test_preflight_rejects_branch_without_issue_key(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "coordination@example.invalid")
    _git(repo, "config", "user.name", "Coordination Test")
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    worktree = tmp_path / "plain-worktree"
    _git(repo, "worktree", "add", "-b", "fix/plain-name", str(worktree), "main")
    findings = validate_local_preflight(worktree, vault_root=tmp_path / "vault")
    assert {"branch-missing-issue", "claim-missing"} <= _codes(findings)


def test_pr_validator_reports_all_static_metadata_failures() -> None:
    event = _valid_pr_event()
    event["pull_request"]["head"] = "invalid"
    event["pull_request"]["user"] = "invalid"
    event["pull_request"]["labels"] = ["invalid", {"name": ""}]
    event["pull_request"]["body"] = "- Linear issue:\n"
    codes = _codes(validate_pr_event(event))
    assert {
        "pr-branch-missing-issue",
        "pr-body-missing-issue",
        "pr-field-missing",
        "pr-base-sha",
        "pr-checkbox",
    } <= codes

    event = _valid_pr_event()
    event["pull_request"]["body"] = event["pull_request"]["body"].replace(
        "fix/agent-27-coordination / .worktrees/agent-27-coordination",
        ".worktrees/wrong",
    )
    assert "pr-worktree-branch" in _codes(validate_pr_event(event))


def test_herdr_reader_handles_disabled_failures_and_valid_payload(monkeypatch) -> None:
    monkeypatch.delenv("HERDR_ENV", raising=False)
    assert read_herdr_agents() is None

    monkeypatch.setenv("HERDR_ENV", "1")
    monkeypatch.setattr(contract.shutil, "which", lambda _: "/usr/local/bin/herdr")

    def completed(returncode: int, stdout: str):
        return subprocess.CompletedProcess(["herdr"], returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(contract.subprocess, "run", lambda *args, **kwargs: completed(1, ""))
    assert read_herdr_agents() is None
    monkeypatch.setattr(contract.subprocess, "run", lambda *args, **kwargs: completed(0, "no"))
    assert read_herdr_agents() is None
    monkeypatch.setattr(contract.subprocess, "run", lambda *args, **kwargs: completed(0, "[]"))
    assert read_herdr_agents() is None
    payload = {"result": {"agents": [{"agent": "codex"}, "bad"]}}
    monkeypatch.setattr(
        contract.subprocess,
        "run",
        lambda *args, **kwargs: completed(0, json.dumps(payload)),
    )
    assert read_herdr_agents() == payload


def test_herdr_payload_parser_rejects_empty_and_malformed_shapes() -> None:
    assert contract._parse_herdr_agents(None) == []
    assert contract._parse_herdr_agents({}) == []
    assert contract._parse_herdr_agents({"result": []}) == []
    assert contract._parse_herdr_agents({"result": {"agents": ["bad"]}}) == []


def test_audit_detects_claim_worktree_and_live_agent_mismatches(tmp_path: Path) -> None:
    repo, worktree = _repo_with_worktree(tmp_path)
    vault = tmp_path / "vault"
    _write_claim(vault, files=("src",))
    _write_claim(vault, issue="AGENT-99", agent="grok", files=("src/module.py",))
    _write_claim(vault, issue="AGENT-100", agent="claude", files=("docs",))

    no_issue = repo / ".worktrees" / "plain"
    _git(repo, "worktree", "add", "-b", "fix/plain", str(no_issue), "main")
    inactive = repo / ".worktrees" / "agent-88"
    _git(repo, "worktree", "add", "-b", "fix/agent-88-old", str(inactive), "main")
    payload = {
        "result": {
            "agents": [
                {"agent": "grok", "foreground_cwd": str(worktree)},
                {"agent": "codex", "foreground_cwd": str(worktree)},
                {"agent": "ignored", "cwd": ""},
                {"agent": "outside", "cwd": str(tmp_path.parent)},
            ]
        }
    }
    audit = audit_repository(repo, vault_root=vault, herdr_payload=payload)
    codes = {item["code"] for item in audit["findings"]}
    assert {
        "active-claim-overlap",
        "worktree-missing-issue",
        "worktree-without-active-claim",
        "live-agent-claim-mismatch",
    } <= codes
    assert audit["errors"] >= 2
    assert audit["warnings"] >= 2


def test_worktree_protection_rejects_unknown_and_primary(tmp_path: Path) -> None:
    repo, _ = _repo_with_worktree(tmp_path)
    assert "unknown-worktree" in _codes(
        protect_worktree(repo, tmp_path / "unknown", vault_root=tmp_path / "vault")
    )
    assert "primary-worktree" in _codes(protect_worktree(repo, repo, vault_root=tmp_path / "vault"))


def test_has_errors_only_counts_error_severity() -> None:
    assert not has_errors([])
    assert not has_errors([Finding("warning", "warn", "warning")])
    assert has_errors([Finding("error", "error", "failure")])
