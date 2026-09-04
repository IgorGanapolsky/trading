"""uv.lock is the installer contract. pnpm 12 numbers are not ours."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.ops.package_manager_honesty import (
    FORBIDDEN_CLAIMS,
    classify_command,
    lookalike_hits,
    scan_tree,
)

REPO = Path(__file__).resolve().parents[1]
OPS = REPO / "scripts" / "package_manager_honesty.py"
ADAPTER = REPO / "src" / "ops" / "package_manager_honesty.py"


def test_repo_scan_is_uv_only() -> None:
    report = scan_tree(REPO)
    assert report["ok"] is True
    assert report["canonical"] == "uv"
    assert report["uv_lock"] is True
    assert report["pyproject"] is True
    assert report["foreign_lockfiles"] == []
    assert report["pnpm_speedup_is_not_ours"] is True
    assert report["do_not_migrate_to_pnpm"] is True


def test_missing_lockfile_is_unavailable(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    report = scan_tree(tmp_path)
    assert report["ok"] is False
    assert report["status"] == "UNAVAILABLE"


def test_dual_lockfile_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("# fake\n", encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
    report = scan_tree(tmp_path)
    assert report["ok"] is False
    assert report["status"] == "DUAL_LOCKFILE"
    assert "pnpm-lock.yaml" in report["foreign_lockfiles"]


def test_frozen_uv_is_allowed() -> None:
    row = classify_command("uv sync --frozen")
    assert row["allowed"] is True
    assert row["role"] == "frozen_lock"
    check = classify_command("uv lock --check")
    assert check["allowed"] is True


def test_pnpm_and_npm_are_denied() -> None:
    for command in ("pnpm install", "npm ci", "yarn install", "bun install"):
        row = classify_command(command)
        assert row["allowed"] is False, command
        assert row["role"] == "denied"


def test_unpinned_pip_denied_when_uv_lock_present() -> None:
    row = classify_command("pip install -r requirements.txt", has_uv_lock=True)
    assert row["allowed"] is False
    assert row["lifecycle_scripts_default_deny"] is True


def test_propose_switch_pnpm_is_denied() -> None:
    row = classify_command("", propose_switch="pnpm")
    assert row["allowed"] is False
    assert "pnpm" in row["reason"]


def test_cli_json_ok() -> None:
    completed = subprocess.run(
        [sys.executable, str(OPS)],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["canonical"] == "uv"
    assert payload["pnpm_speedup_is_not_ours"] is True


def test_cli_propose_switch_json() -> None:
    completed = subprocess.run(
        [sys.executable, str(OPS), "--propose-switch", "pnpm"],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["allowed"] is False


def test_cli_invalid_flag_json() -> None:
    completed = subprocess.run(
        [sys.executable, str(OPS), "--not-a-flag"],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["status"] == "UNAVAILABLE"


def test_sources_do_not_claim_pnpm_speedup() -> None:
    cli = OPS.read_text(encoding="utf-8")
    assert lookalike_hits(cli) == []
    runtime_without_policy = "\n".join(
        line
        for line in ADAPTER.read_text(encoding="utf-8").splitlines()
        if "FORBIDDEN_CLAIMS" not in line and not line.strip().startswith('"')
    )
    assert lookalike_hits(runtime_without_policy) == []
    assert "15ms repeated install" in FORBIDDEN_CLAIMS


def test_dual_lockfile_cli(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text("# fake\n", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("{}\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(OPS), "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["status"] == "DUAL_LOCKFILE"
