"""Tests for Pi (pi.dev) agent integration, prompt templates, and CLI bridge."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.pi_trading_bridge as bridge  # noqa: E402


def test_pi_prompt_templates_exist():
    prompts_dir = ROOT / ".pi" / "prompts"
    assert prompts_dir.is_dir()

    expected_templates = ["status.md", "dryrun.md", "exits.md", "scorecard.md", "hygiene.md"]
    for template in expected_templates:
        path = prompts_dir / template
        assert path.is_file(), f"Missing template: {template}"
        content = path.read_text(encoding="utf-8")
        assert "---" in content
        assert "description:" in content


def test_pi_bridge_script_executable():
    bridge_script = ROOT / "scripts" / "pi_trading_bridge.py"
    assert bridge_script.is_file()


def test_pi_bridge_main_status_json(capsys):
    with patch.object(sys, "argv", ["pi_trading_bridge.py", "status", "--json"]):
        code = bridge.main()
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data.get("status") == "ok"
        assert "equity" in data


def test_pi_bridge_main_status_text(capsys):
    with patch.object(sys, "argv", ["pi_trading_bridge.py", "status"]):
        code = bridge.main()
        assert code == 0
        captured = capsys.readouterr()
        assert "PI TRADING BRIDGE: SYSTEM STATUS" in captured.out


def test_pi_bridge_main_dryrun_json(capsys):
    with patch.object(sys, "argv", ["pi_trading_bridge.py", "dry-run", "--json"]):
        code = bridge.main()
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "regime_passed" in data


def test_pi_bridge_main_dryrun_text(capsys):
    with patch.object(sys, "argv", ["pi_trading_bridge.py", "dry-run"]):
        code = bridge.main()
        assert code == 0
        captured = capsys.readouterr()
        assert "PI TRADING BRIDGE: DRY RUN PLAN" in captured.out


def test_pi_bridge_main_manage_exits_json(capsys):
    with patch.object(sys, "argv", ["pi_trading_bridge.py", "manage-exits", "--json"]):
        code = bridge.main()
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "exit_code" in data


def test_pi_bridge_main_manage_exits_text(capsys):
    with patch.object(sys, "argv", ["pi_trading_bridge.py", "manage-exits"]):
        code = bridge.main()
        assert code == 0
        captured = capsys.readouterr()
        assert "PI TRADING BRIDGE: EXIT MANAGEMENT" in captured.out


def test_pi_bridge_main_scorecard_json(capsys):
    with patch.object(sys, "argv", ["pi_trading_bridge.py", "scorecard", "--json"]):
        code = bridge.main()
        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, dict)


def test_pi_bridge_main_scorecard_text(capsys):
    with patch.object(sys, "argv", ["pi_trading_bridge.py", "scorecard"]):
        code = bridge.main()
        assert code == 0
        captured = capsys.readouterr()
        assert "PI TRADING BRIDGE: COHORT SCORECARD" in captured.out


def test_pi_bridge_error_handling():
    with patch.object(bridge, "run_subcommand", return_value=(1, "raw non-json", "err")):
        sc = bridge.get_scorecard()
        assert sc == {"raw_output": "raw non-json"}

    with patch.object(Path, "is_file", return_value=False):
        status = bridge.get_status()
        assert status["status"] == "ok"
