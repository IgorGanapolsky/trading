"""Prevention: keep Herdr-inspired docs/skill layout present."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "docs/README.md",
    "docs/operator-guide.md",
    "skills/bogleheads-forum-operator/SKILL.md",
    "skills/trading-ops/SKILL.md",
)


def test_required_docs_and_skill_exist() -> None:
    missing = [p for p in REQUIRED_PATHS if not (ROOT / p).is_file()]
    assert missing == [], f"missing layout files: {missing}"


def test_readme_points_at_skill_and_honest_strategy() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "skills/trading-ops/SKILL.md" in text
    assert "spy_put_credit" in text
    assert "not" in text.lower() and "proven" in text.lower()


def test_skill_has_safety_gates() -> None:
    text = (ROOT / "skills/trading-ops/SKILL.md").read_text(encoding="utf-8")
    assert "strategy_kill_switch" in text
    assert "dry-run" in text
    assert "TRADING_HALTED" in text or "halt" in text.lower()
