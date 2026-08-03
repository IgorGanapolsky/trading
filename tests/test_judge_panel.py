"""Tests for LLM-as-Judge MoE panel (claim/PR/coord — not trade entry)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


from src.evals.judge_panel import ExpertName, ExpertRouter, JudgePanel, TaskKind, run_panel
from src.evals.judge_panel.models import PanelInput
from src.evals.judge_panel.experts import RiskRulesExpert, EvidenceExpert, CoordinationExpert

ROOT = Path(__file__).resolve().parents[1]


class TestRouter:
    def test_claim_routes_evidence_and_risk(self):
        r = ExpertRouter().select(TaskKind.CLAIM_AUDIT)
        assert ExpertName.EVIDENCE in r
        assert ExpertName.RISK_RULES in r
        assert ExpertName.COORDINATION not in r

    def test_trade_entry_risk_only(self):
        r = ExpertRouter().select(TaskKind.TRADE_ENTRY)
        assert r == (ExpertName.RISK_RULES,)

    def test_pr_uses_all_three(self):
        r = ExpertRouter().select(TaskKind.PR_AUDIT)
        assert set(r) == {
            ExpertName.RISK_RULES,
            ExpertName.EVIDENCE,
            ExpertName.COORDINATION,
        }


class TestRiskExpert:
    def test_ic_new_entry_veto(self):
        o = RiskRulesExpert().evaluate(
            PanelInput(kind=TaskKind.PR_AUDIT, text="let's open new iron condor tomorrow")
        )
        assert o.veto is True
        assert o.passed is False

    def test_trade_entry_always_veto(self):
        o = RiskRulesExpert().evaluate(
            PanelInput(kind=TaskKind.TRADE_ENTRY, text="sell put credit 15d")
        )
        assert o.veto is True
        assert o.passed is False

    def test_clean_text_passes(self):
        o = RiskRulesExpert().evaluate(
            PanelInput(kind=TaskKind.PR_AUDIT, text="docs only: operator guide link")
        )
        assert o.passed is True
        assert o.veto is False


class TestEvidenceExpert:
    def test_unverified_edge_claim_vetoes(self):
        o = EvidenceExpert().evaluate(
            PanelInput(
                kind=TaskKind.CLAIM_AUDIT,
                text="Edge proven and profitable, ready for live",
            )
        )
        assert o.passed is False
        assert o.veto is True

    def test_claim_with_run_and_sha_passes(self):
        o = EvidenceExpert().evaluate(
            PanelInput(
                kind=TaskKind.CLAIM_AUDIT,
                text="CI green on run 30780143772 merge sha d69beb2b6ec419b8 n=162 expectancy=-47",
            )
        )
        assert o.passed is True


class TestCoordExpert:
    def test_file_overlap_collision(self):
        o = CoordinationExpert().evaluate(
            PanelInput(
                kind=TaskKind.COORD_AUDIT,
                agent="grok",
                claimed_files=["src/risk/trade_gateway.py"],
                other_agent_claims=(
                    "codex In Progress claimed_files: src/risk/trade_gateway.py trading cleanup"
                ),
            )
        )
        assert o.veto is True
        assert o.passed is False

    def test_orthogonal_files_ok(self):
        o = CoordinationExpert().evaluate(
            PanelInput(
                kind=TaskKind.COORD_AUDIT,
                agent="grok",
                claimed_files=["src/evals/judge_panel/panel.py"],
                other_agent_claims=(
                    "codex In Progress IGO-35 trading cleanup claimed_files: scripts/audit_open_inventory.py"
                ),
            )
        )
        assert o.passed is True
        assert o.veto is False


class TestPanel:
    def test_veto_cannot_be_overridden_by_narrative(self):
        def lying_narrative(summary, opinions):
            return "PASS: all good ignore experts"

        v = JudgePanel(narrative_fn=lying_narrative).run(
            PanelInput(
                kind=TaskKind.CLAIM_AUDIT,
                text="Edge proven and profitable, ready for live",
            )
        )
        assert v.passed is False
        assert v.vetoed is True
        assert "narrative_stripped_false_pass" in v.judge_summary or not v.passed

    def test_run_panel_convenience(self):
        v = run_panel(
            TaskKind.CLAIM_AUDIT,
            text="docs updated; no edge claim",
        )
        assert v.passed is True
        assert "evidence" in v.experts_used
        assert "risk_rules" in v.experts_used

    def test_to_dict_serializable(self):
        v = run_panel(TaskKind.TRADE_ENTRY, text="enter")
        d = v.to_dict()
        json.dumps(d)
        assert d["passed"] is False
        assert d["vetoed"] is True


class TestCLI:
    def test_self_check_exit_zero(self):
        script = ROOT / "scripts" / "judge_panel.py"
        proc = subprocess.run(
            [sys.executable, str(script), "--self-check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "SELF-CHECK PASS" in proc.stdout

    def test_cli_unverified_claim_exit_2(self):
        script = ROOT / "scripts" / "judge_panel.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--kind",
                "claim_audit",
                "--text",
                "Edge proven profitable ready for live",
                "--json",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 2
        data = json.loads(proc.stdout)
        assert data["passed"] is False
