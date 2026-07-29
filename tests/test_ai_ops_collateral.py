import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pitch_deck_exists_and_valid():
    pitch_file = ROOT / "docs" / "AI_OPS_COLD_OUTREACH_PITCH_DECK.md"
    assert pitch_file.exists()
    content = pitch_file.read_text(encoding="utf-8")
    assert len(content) > 500
    assert "autonomous AI SDR agents" in content
    assert "Template 1" in content


def test_loom_script_exists_and_valid():
    loom_file = ROOT / "docs" / "AI_OPS_LOOM_DEMO_SCRIPT.md"
    assert loom_file.exists()
    content = loom_file.read_text(encoding="utf-8")
    assert len(content) > 500
    assert "Hook & Problem Statement" in content
    assert "Appointment Setter Agent" in content
