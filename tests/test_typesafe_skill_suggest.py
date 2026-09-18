"""Tests for TypeSafe skill-suggestion FORMAT steal."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "typesafe_skill_suggest.py"
    spec = importlib.util.spec_from_file_location("typesafe_skill_suggest", path)
    assert spec and spec.loader
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    mod = importlib.util.module_from_spec(spec)
    # dataclasses requires the module to be present in sys.modules during decoration
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_load_roster_from_temp(tmp_path: Path):
    mod = _load()
    skill_dir = tmp_path / "alpaca-paper-trading"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: alpaca-paper-trading\ndescription: >\n  Paper trading Alpaca put credit\n---\n\n# Alpaca\nUse spy_put_credit.\n",
        encoding="utf-8",
    )
    roster = mod.load_roster([tmp_path])
    assert len(roster) == 1
    assert roster[0].name == "alpaca-paper-trading"
    assert "Paper trading" in roster[0].description_full


def test_offline_suggests_matching_skill(tmp_path: Path):
    mod = _load()
    (tmp_path / "typesafe-claim-gate").mkdir()
    (tmp_path / "typesafe-claim-gate" / "SKILL.md").write_text(
        "---\ndescription: Gate profitability claims with TypeSafe System One\n---\n\nRefuse false edge claims.\n",
        encoding="utf-8",
    )
    (tmp_path / "bogleheads-forum").mkdir()
    (tmp_path / "bogleheads-forum" / "SKILL.md").write_text(
        "---\ndescription: Bogleheads forum research ingest\n---\n\nPassive investing forum.\n",
        encoding="utf-8",
    )
    result = mod.suggest(
        "Use TypeSafe to gate a profitability claim before I assert edge",
        offline=True,
        roots=[tmp_path],
    )
    assert result["mode"] == "offline"
    assert result["gate"] >= mod.GATE_THRESHOLD
    assert "typesafe-claim-gate" in result["suggested"]


def test_offline_suggests_nothing_for_pure_prose(tmp_path: Path):
    mod = _load()
    (tmp_path / "random-timer-coach").mkdir()
    (tmp_path / "random-timer-coach" / "SKILL.md").write_text(
        "---\ndescription: HIIT combat sports timer coach\n---\n\nRounds and drills.\n",
        encoding="utf-8",
    )
    result = mod.suggest(
        "What does the word monad mean in category theory?",
        offline=True,
        roots=[tmp_path],
    )
    # prose-heavy requests should usually stay quiet
    assert result["suggested"] == [] or result["gate"] < mod.GATE_THRESHOLD


def test_suggestion_block_shapes():
    mod = _load()
    assert "typesafe-ai-api" in mod.suggestion_block(("typesafe-ai-api",))
    assert "No skill" in mod.suggestion_block(())


def test_online_shortlist_then_rerank(monkeypatch, tmp_path: Path):
    mod = _load()
    (tmp_path / "alpaca-paper-trading").mkdir()
    (tmp_path / "alpaca-paper-trading" / "SKILL.md").write_text(
        "---\ndescription: Alpaca paper put credit validation path\n---\n\nspy_put_credit dry-run.\n",
        encoding="utf-8",
    )
    (tmp_path / "fleet-pr-hygiene").mkdir()
    (tmp_path / "fleet-pr-hygiene" / "SKILL.md").write_text(
        "---\ndescription: Merge ready PRs and clean orphan branches\n---\n\nPR hygiene.\n",
        encoding="utf-8",
    )

    calls = {"n": 0}

    def fake_system_one(**kwargs):
        calls["n"] += 1
        qs = kwargs["questions"]
        if any(k.startswith("fits::") for k in qs):
            return {
                "model": "jev-test",
                "answers": {
                    "which": {
                        "type": "choice",
                        "choice": "alpaca-paper-trading",
                        "confidence": 0.9,
                    },
                    "fits::alpaca-paper-trading": {"type": "noul", "noul": 0.8},
                    "fits::fleet-pr-hygiene": {"type": "noul", "noul": 0.1},
                },
                "usage": {},
            }
        return {
            "model": "jev-test",
            "answers": {
                "which": {
                    "type": "choice",
                    "choice": "alpaca-paper-trading",
                    "probabilities": {
                        "alpaca-paper-trading": 0.7,
                        "fleet-pr-hygiene": 0.3,
                    },
                    "confidence": 0.8,
                },
                "gate::acts_on_user_system": {"type": "noul", "noul": 0.9},
                "gate::would_follow_documented_procedure": {"type": "noul", "noul": 0.8},
                "gate::prose_suffices": {"type": "noul", "noul": 0.1},
            },
            "usage": {},
        }

    monkeypatch.setattr(mod, "system_one", fake_system_one)
    result = mod.suggest(
        "Run the Alpaca paper put credit dry-run status check",
        offline=False,
        roots=[tmp_path],
        api_key="test-key",
    )
    assert result["mode"] == "online"
    assert result["suggested"] == ["alpaca-paper-trading"]
    assert calls["n"] == 2


def test_cli_offline_json(tmp_path: Path):
    skill = tmp_path / "trading-ralph-gsd-24-7"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\ndescription: Continuous Ralph Loop and GSD for trading cash rails\n---\n\nNever stop.\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "typesafe_skill_suggest.py"),
            "--offline",
            "--roots",
            str(tmp_path),
            "--request",
            "Keep the trading Ralph GSD loop running and fix the next residual",
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert "trading-ralph-gsd-24-7" in payload["suggested"]
