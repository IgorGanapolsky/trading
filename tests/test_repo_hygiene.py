from pathlib import Path

from scripts.audit_repository_hygiene import candidate_paths, scan

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PATHS = {
    ".agents/skills/trading-ops/SKILL.md",
    ".gitignore",
    "data/feedback/stats.json",
    "data/put_credit_entries.json",
    "data/runtime/strategy_kill_switch.json",
    "data/system_state.json",
    "data/trades.json",
    "docs/EXTENSIONS.md",
}


def test_repository_hygiene_audit_has_no_errors() -> None:
    report = scan(REPO_ROOT)
    assert [item for item in report["findings"] if item["severity"] == "error"] == []


def test_required_operational_paths_remain_in_candidate_tree() -> None:
    assert REQUIRED_PATHS <= set(candidate_paths(REPO_ROOT))


def test_gitignore_covers_generated_surfaces() -> None:
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("artifacts/", "logs/", "data/cache/", "data/screenshots/", "__pycache__/"):
        assert pattern in text
