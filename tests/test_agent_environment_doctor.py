"""Tests for AI Studio agent-environment FORMAT doctor."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from src.ops.agent_environment_doctor import (
    check_network_allowlist,
    check_termination_criteria,
    check_tool_allowlist,
    diagnose_agent_environment,
)

REPO = Path(__file__).resolve().parents[1]


def test_sources_pack_ok_on_repo():
    report = diagnose_agent_environment(REPO)
    assert report.dimensions["sources_pack"].ok is True
    assert report.score >= 3


def test_forbidden_tool_fail_closed():
    d = check_tool_allowlist(["submit_order", "context_gist"])
    assert d.ok is False
    assert any(f.startswith("forbidden_tools:") for f in d.failing)


def test_undeclared_tool_fail_closed():
    d = check_tool_allowlist(["mystery_tool"])
    assert d.ok is False
    assert any("undeclared_tools:mystery_tool" in f for f in d.failing)


def test_paper_safe_tools_pass():
    d = check_tool_allowlist(
        ["context_gist", "spy_put_credit_dry_run", "aistudio_agent_env_doctor"]
    )
    assert d.ok is True


def test_network_deny_unknown_domain():
    d = check_network_allowlist(["evil.example", "api.alpaca.markets"])
    assert d.ok is False
    assert any("evil.example" in f for f in d.failing)


def test_network_allow_alpaca_and_offline():
    assert check_network_allowlist(["paper-api.alpaca.markets"]).ok is True
    assert check_network_allowlist([]).ok is True


def test_termination_requires_stop_and_ac():
    bad = check_termination_criteria(stop_when="", acceptance_criteria=[], out_of_scope="")
    assert bad.ok is False
    good = check_termination_criteria(
        stop_when="stop after summary",
        acceptance_criteria=["tests pass"],
        out_of_scope="live submit",
    )
    assert good.ok is True


def test_doctor_green_path():
    report = diagnose_agent_environment(
        REPO,
        proposed_tools=[
            "context_gist",
            "entry_challenges",
            "system_health_check",
            "aistudio_agent_env_doctor",
        ],
        proposed_domains=["api.github.com"],
        stop_when="exit after doctor",
        acceptance_criteria=["tests pass", "CLI exit 0"],
        out_of_scope="Antigravity",
    )
    assert report.ok is True
    assert report.score == report.max_score == 4
    assert len(report.content_hash) == 16


def test_cli_script_loads(capsys):
    path = REPO / "scripts" / "aistudio_agent_env_doctor.py"
    spec = importlib.util.spec_from_file_location("aistudio_agent_env_doctor", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rc = mod.main(
        [
            "--tools",
            "context_gist,aistudio_agent_env_doctor,system_health_check",
            "--domains",
            "api.github.com",
            "--acs",
            "tests pass|CLI fail-closed",
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True
