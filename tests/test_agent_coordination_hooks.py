from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_coordination_shell_surfaces_have_valid_bash() -> None:
    for relative in (
        ".claude/hooks/agent_coordination_guard.sh",
        "scripts/agent_coordination_guard.sh",
        "scripts/worktree_hygiene.sh",
        "plugins/trading-coordination/scripts/audit.sh",
        ".claude/hooks/gsd-pipeline.sh",
        ".claude/hooks/session-start.sh",
        ".claude/hooks/guard_destructive_actions.sh",
    ):
        result = subprocess.run(
            ["bash", "-n", str(ROOT / relative)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"{relative}: {result.stderr}"


def test_gsd_runs_coordination_before_other_pretool_guards() -> None:
    content = (ROOT / ".claude/hooks/gsd-pipeline.sh").read_text(encoding="utf-8")
    coordination = content.index('run_hook "agent_coordination_guard.sh"')
    memory = content.index('run_hook "memory-gateway-pretool.sh"')
    position = content.index('run_hook "block_position_close.sh"')
    assert coordination < memory < position


def test_gsd_coordination_hook_exists_and_delegates_to_repository_guard() -> None:
    hook = ROOT / ".claude/hooks/agent_coordination_guard.sh"
    assert hook.stat().st_mode & 0o111
    assert "scripts/agent_coordination_guard.sh" in hook.read_text(encoding="utf-8")


def test_session_start_runs_read_only_coordination_audit() -> None:
    content = (ROOT / ".claude/hooks/session-start.sh").read_text(encoding="utf-8")
    assert "agent_coordination.py" in content
    assert "audit --warn-only" in content


def test_bash_guard_blocks_raw_worktree_deletion() -> None:
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/agent_coordination_guard.sh"),
            json.dumps({"command": "git worktree remove /tmp/example"}),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "worktree_hygiene.sh" in result.stderr


def test_bash_guard_allows_read_only_git_status() -> None:
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/agent_coordination_guard.sh"),
            json.dumps({"command": "git status --short"}),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_edit_guard_invokes_file_scoped_coordination_preflight() -> None:
    content = (ROOT / ".claude/hooks/guard_destructive_actions.sh").read_text(encoding="utf-8")
    assert "agent_coordination.py" in content
    assert '--file "${FILE_PATH}"' in content


def test_github_workflow_is_bounded_and_sha_pinned() -> None:
    path = ROOT / ".github/workflows/agent-coordination.yml"
    text = path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    assert isinstance(workflow, dict)
    assert "pull_request" in text
    assert workflow["jobs"]["validate"]["timeout-minutes"] == 5
    uses = re.findall(r"^\s*uses:\s*([^\s#]+)", text, re.MULTILINE)
    assert uses
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", item) for item in uses)
    assert "agent_coordination.py validate-pr" in text


def test_pr_template_contains_machine_checked_fields() -> None:
    text = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
    for field in (
        "Linear issue:",
        "Agent:",
        "Base SHA:",
        "Branch/worktree:",
        "Files or systems claimed:",
        "Coordination legacy reason:",
    ):
        assert field in text


def test_herdr_plugin_declares_startup_event_and_manual_audit() -> None:
    manifest = tomllib.loads(
        (ROOT / "plugins/trading-coordination/herdr-plugin.toml").read_text(encoding="utf-8")
    )
    assert manifest["id"] == "trading.coordination"
    assert manifest["min_herdr_version"] == "0.7.5"
    assert manifest["startup"][0]["command"] == ["bash", "scripts/audit.sh"]
    assert manifest["events"][0]["on"] == "worktree.created"
    assert manifest["actions"][0]["id"] == "audit"


def test_makefile_exposes_coordination_and_claim_aware_hygiene() -> None:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "coordination-preflight:" in text
    assert "coordination-audit:" in text
    assert "tests/test_agent_coordination.py" in text
    assert "scripts/worktree_hygiene.sh --prune" in text


def test_coordination_cli_accepts_valid_and_rejects_invalid_pr_events(tmp_path: Path) -> None:
    valid = {
        "pull_request": {
            "head": {"ref": "fix/agent-27-coordination"},
            "user": {"login": "IgorGanapolsky"},
            "labels": [],
            "body": "\n".join(
                (
                    "- Linear issue: AGENT-27",
                    "- Agent: codex",
                    "- Base SHA: 7e693cc7b7b049c74885e14915e94c5523f595fb",
                    "- Branch/worktree: fix/agent-27-coordination / .worktrees/example",
                    "- Files or systems claimed: tests/test_agent_coordination_hooks.py",
                    "- [x] Linear issue and vault claim updated",
                    "- [x] No overlapping active claim or worktree",
                )
            ),
        }
    }
    event = tmp_path / "event.json"
    event.write_text(json.dumps(valid), encoding="utf-8")
    command = [
        sys.executable,
        str(ROOT / "scripts/agent_coordination.py"),
        "validate-pr",
        "--event",
        str(event),
    ]
    accepted = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert json.loads(accepted.stdout)["errors"] == 0

    event.write_text("{}", encoding="utf-8")
    rejected = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert rejected.returncode == 1
    assert json.loads(rejected.stdout)["findings"][0]["code"] == "event-shape"


def test_coordination_guard_fails_closed_when_preflight_is_unavailable(tmp_path: Path) -> None:
    env = {"CLAUDE_PROJECT_DIR": str(tmp_path)}
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/agent_coordination_guard.sh"),
            json.dumps({"command": "git commit -m test"}),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2
    assert "coordination preflight is unavailable" in result.stderr
