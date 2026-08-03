from pathlib import Path

from scripts.audit_repository_hygiene import candidate_paths, scan

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PATHS = {
    ".agents/skills/trading-ops/SKILL.md",
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


def test_gitignore_covers_generated_surfaces() -> None:
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("artifacts/", "logs/", "data/cache/", "data/screenshots/", "__pycache__/"):
        assert pattern in text
