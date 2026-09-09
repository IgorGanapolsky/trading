import subprocess
from pathlib import Path

from scripts.audit_repository_hygiene import (
    candidate_paths,
    is_leftover_source_fragment,
    scan,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PATHS = {
    "skills/trading-ops/SKILL.md",
    ".github/pull_request_template.md",
    ".gitignore",
    "data/feedback/stats.json",
    "data/put_credit_entries.json",
    "data/runtime/strategy_kill_switch.json",
    "data/system_state.json",
    "data/trades.json",
    "docs/AGENT_COORDINATION.md",
    "docs/EXTENSIONS.md",
    "scripts/query_lessons_learned.py",
}


def test_repository_hygiene_audit_has_no_errors() -> None:
    report = scan(REPO_ROOT)
    assert [item for item in report["findings"] if item["severity"] == "error"] == []


def test_required_operational_paths_remain_in_candidate_tree() -> None:
    assert set(candidate_paths(REPO_ROOT)) >= REQUIRED_PATHS


def test_arxiv_audit_copies_are_not_tracked() -> None:
    tracked = candidate_paths(REPO_ROOT)
    assert not any(path.startswith("data/arxiv/") for path in tracked)


def test_pytorch_weights_are_not_tracked() -> None:
    tracked = candidate_paths(REPO_ROOT)
    assert not any(path.endswith(".pt") for path in tracked)


def test_leftover_source_fragment_detector() -> None:
    assert is_leftover_source_fragment("src/strategies/core_strategy.py_REWRITE_EXECUTE")
    assert is_leftover_source_fragment("src/foo.py.bak")
    assert is_leftover_source_fragment("src/foo.py_ORIG")
    assert not is_leftover_source_fragment("src/strategies/core_strategy.py")
    assert not is_leftover_source_fragment("src/rag/query_rewriter.py")


def test_no_tracked_leftover_source_fragments() -> None:
    tracked = candidate_paths(REPO_ROOT)
    leftovers = [path for path in tracked if is_leftover_source_fragment(path)]
    assert leftovers == []


def test_scan_errors_on_leftover_rewrite_fragment(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    leftover = tmp_path / "core_strategy.py_REWRITE_EXECUTE"
    leftover.write_text("    def execute(self):\n        return {}\n")
    subprocess.run(["git", "add", leftover.name], cwd=tmp_path, check=True, capture_output=True)
    report = scan(tmp_path)
    leftovers = [item for item in report["findings"] if item["kind"] == "leftover-source-fragment"]
    assert leftovers
    assert leftovers[0]["path"] == leftover.name
    assert leftovers[0]["severity"] == "error"


def test_gitignore_covers_generated_surfaces() -> None:
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("artifacts/", "logs/", "data/cache/", "data/screenshots/", "__pycache__/"):
        assert pattern in text
