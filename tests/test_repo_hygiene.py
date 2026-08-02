"""Prevention: block re-introduction of runtime garbage into git.

These paths are local/runtime artifacts. They must never be re-committed.
See .gitignore "REPO HYGIENE (2026-08-02)" and LL cleanup session.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Prefixes that must not appear in `git ls-files` output.
FORBIDDEN_TRACKED_PREFIXES = (
    "data/screenshots/",
    "data/audit/",
    "data/audit_trail/",
    "data/agent_context/",
    "data/debug/",
    "data/analysis/",
    "data/reports/",
    "data/backtests/",
    "data/ml_training_data/",
    "data/rag_knowledge/",
    "data/memory/",
    "data/sentiment/",
    "data/options_signals/",
    "rag_knowledge/",
    ".planning/",
    ".thumbgate/",
    ".agents/",
    "logs/autonomous_trading_",
    "artifacts/devloop/",
    "artifacts/tars/",
    ".playwright-mcp/",
    ".obsidian/",
    ".aider.chat.history.md",
    ".aider*",
    ".claude/logs/",
    "docs/contest/",
    "docs/data/",
    "docs/assets/snapshots/",
    "graphify-out/",
)

# Exact deprecated dump filenames (root of data/)
FORBIDDEN_TRACKED_EXACT = (
    "data/trades_for_clustering.json",
    "data/backtest_trades.json",
)

# Canonical ledgers that MUST remain tracked
REQUIRED_TRACKED = (
    "data/system_state.json",
    "data/trades.json",
    "data/put_credit_entries.json",
    "data/strategy_params.json",
    "data/runtime/strategy_kill_switch.json",
    ".gitignore",
)


def _git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


@pytest.fixture(scope="module")
def tracked_files() -> list[str]:
    return _git_ls_files()


def test_forbidden_runtime_garbage_not_tracked(tracked_files: list[str]) -> None:
    offenders: list[str] = []
    for path in tracked_files:
        if path in FORBIDDEN_TRACKED_EXACT:
            offenders.append(path)
            continue
        for prefix in FORBIDDEN_TRACKED_PREFIXES:
            if path == prefix.rstrip("/") or path.startswith(prefix):
                offenders.append(path)
                break
        if path.startswith("data/trades_") and path.endswith(".json"):
            offenders.append(path)
    assert offenders == [], (
        "Runtime garbage re-entered the git index. Remove with "
        "`git rm --cached <path>` and keep .gitignore hygiene rules.\n"
        f"Offenders ({len(offenders)}):\n" + "\n".join(offenders[:40])
    )


def test_canonical_ledgers_still_tracked(tracked_files: list[str]) -> None:
    tracked = set(tracked_files)
    missing = [p for p in REQUIRED_TRACKED if p not in tracked]
    assert missing == [], f"Canonical paths missing from git: {missing}"


def test_gitignore_has_hygiene_section() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "REPO HYGIENE (2026-08-02)" in gitignore
    assert "data/screenshots/" in gitignore
    assert "logs/" in gitignore
    assert "rag_knowledge/" in gitignore
    assert ".planning/" in gitignore
    assert "docs/data/" in gitignore
    assert "docs/assets/snapshots/" in gitignore
    assert "graphify-out/" in gitignore
