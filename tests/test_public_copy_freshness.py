from __future__ import annotations

import json
from pathlib import Path

from scripts.check_public_copy_freshness import find_violations


def _seed_public_surfaces(tmp_path: Path) -> Path:
    required = {
        "README.md": "# Repo\n",
        "docs/index.md": "fetch('/data/public_status.json')\n",
        "docs/LIVE_STRATEGY.md": "# Live Strategy\n",
        "wiki/Home.md": "# Home\n",
        "wiki/Progress-Dashboard.md": "# Progress\n",
        "wiki/Development-Engine-and-Evidence.md": "# Evidence\n",
        ".github/public/about.txt": "Broker-backed validation platform.\n",
    }
    for rel, content in required.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (tmp_path / "docs/data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/data/public_status.json").write_text(
        json.dumps(
            {
                "generated_at_et": "2026-04-03T10:00:00-04:00",
                "paper": {},
                "ledger": {},
                "gate": {},
                "links": {},
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_find_violations_passes_on_clean_public_surfaces(tmp_path: Path):
    repo = _seed_public_surfaces(tmp_path)
    assert find_violations(repo) == []


def test_find_violations_catches_stale_copy(tmp_path: Path):
    repo = _seed_public_surfaces(tmp_path)
    (repo / "wiki/Progress-Dashboard.md").write_text(
        "Current Position (Trade 1 of 30)\n", encoding="utf-8"
    )
    violations = find_violations(repo)
    assert any("stale public copy" in violation for violation in violations)
