"""Pi (pi.dev) harness contracts — complement PR #4624, do not require its files."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PI = ROOT / ".pi"


def test_append_system_is_paper_only() -> None:
    text = (PI / "APPEND_SYSTEM.md").read_text(encoding="utf-8")
    assert "spy_put_credit" in text
    assert "live_blocked" in text
    assert "no mcp" in text.lower()
    assert "EDGE_CANDIDATE" in text


def test_settings_disable_telemetry_and_untrusted_packages() -> None:
    settings = json.loads((PI / "settings.json").read_text(encoding="utf-8"))
    assert settings.get("enableInstallTelemetry") is False
    assert settings.get("packages") == []


def test_live_gate_extension_denies_boundary_actions() -> None:
    src = (PI / "extensions" / "trading-live-gate.ts").read_text(encoding="utf-8")
    assert "tool_call" in src
    assert "close_position" in src
    assert "close_positions" in src
    assert "manage_positions" in src
    assert "--live" in src
    assert "PAPER_TRADING" in src
    assert "pi\\s+install" in src or r"\bpi\s+install\b" in src
    assert "strategy_kill_switch" in src
    assert "TRADING_HALTED" in src
    assert "trading_constants" in src
    assert "PROTECTED_PATHS" in src
    assert "block: true" in src
    assert "pi-mcp" not in src.lower()


def test_paper_factory_skill_and_prompts_exist() -> None:
    skill = (PI / "skills" / "pi-paper-factory" / "SKILL.md").read_text(encoding="utf-8")
    assert "spy_put_credit.py" in skill
    assert "pi-mcp-adapter" in skill
    connectors = (PI / "prompts" / "connectors.md").read_text(encoding="utf-8")
    assert "no MCP" in connectors or "No MCP" in connectors
    factory = (PI / "prompts" / "factory.md").read_text(encoding="utf-8")
    assert "put_credit_cohort_scorecard.py" in factory
