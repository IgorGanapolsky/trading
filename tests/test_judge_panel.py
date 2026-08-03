"""Tests for LLM-as-Judge MoE panel (claim/PR/coord — not trade entry)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from src.evals.judge_panel import ExpertName, ExpertRouter, JudgePanel, TaskKind, run_panel
from src.evals.judge_panel.experts import (
    CoordinationExpert,
    EvidenceExpert,
    RiskRulesExpert,
)
from src.evals.judge_panel.models import PanelInput
from src.evals.judge_panel.panel import re_claims_pass

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

    def test_coord_routes_coord_and_risk(self):
        r = ExpertRouter().select(TaskKind.COORD_AUDIT)
        assert ExpertName.COORDINATION in r
        assert ExpertName.RISK_RULES in r


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

    def test_foreign_claim_does_not_veto_current_change(self):
        o = RiskRulesExpert().evaluate(
            PanelInput(
                kind=TaskKind.PR_AUDIT,
                text="docs only: operator guide link",
                other_agent_claims="claude-code owns a task to open new iron condor",
            )
        )
        assert o.passed is True
        assert o.veto is False

    def test_hardcoded_credential_veto_redacts_value(self):
        fake_value = "not-a-real-secret-value"
        o = RiskRulesExpert().evaluate(
            PanelInput(
                kind=TaskKind.PR_AUDIT,
                diff=f"+ ALPACA_API_KEY='{fake_value}'",
            )
        )
        assert o.veto is True
        assert fake_value not in " ".join(o.findings)
        assert "[REDACTED]" in " ".join(o.findings)

    def test_live_capital_veto(self):
        o = RiskRulesExpert().evaluate(
            PanelInput(kind=TaskKind.PR_AUDIT, text="deploy live capital now")
        )
        assert o.veto is True

    def test_halt_tamper_veto(self):
        o = RiskRulesExpert().evaluate(
            PanelInput(kind=TaskKind.PR_AUDIT, text="rm data/TRADING_HALTED")
        )
        assert o.veto is True

    def test_llm_trade_council_veto(self):
        o = RiskRulesExpert().evaluate(
            PanelInput(
                kind=TaskKind.PR_AUDIT,
                text="llm council approves the trade for entry",
            )
        )
        assert o.veto is True


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
                text=(
                    "CI green on run 30780143772 merge sha d69beb2b6ec419b8 n=162 expectancy=-47"
                ),
            )
        )
        assert o.passed is True

    def test_foreign_evidence_cannot_validate_current_claim(self):
        o = EvidenceExpert().evaluate(
            PanelInput(
                kind=TaskKind.CLAIM_AUDIT,
                text="Edge proven and ready for live",
                other_agent_claims="codex cited run 30780143772 and sha d69beb2b6",
            )
        )
        assert o.passed is False
        assert o.veto is True

    def test_no_claims_passes(self):
        o = EvidenceExpert().evaluate(
            PanelInput(kind=TaskKind.CLAIM_AUDIT, text="docs only, no status claim")
        )
        assert o.passed is True
        assert o.score == 1.0

    def test_soft_claim_without_edge_fails_not_veto(self):
        # "shipped" is a claim marker but not edge-like → fail without veto
        o = EvidenceExpert().evaluate(
            PanelInput(kind=TaskKind.CLAIM_AUDIT, text="Feature shipped to users")
        )
        assert o.passed is False
        assert o.veto is False


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
                    "codex In Progress IGO-35 trading cleanup "
                    "claimed_files: scripts/audit_open_inventory.py"
                ),
            )
        )
        # Soft foreign trading warning but still passed
        assert o.passed is True
        assert o.veto is False

    def test_grok_is_detected_as_foreign_agent(self):
        o = CoordinationExpert().evaluate(
            PanelInput(
                kind=TaskKind.COORD_AUDIT,
                agent="codex",
                claimed_files=["src/risk/trade_gateway.py"],
                other_agent_claims=(
                    "grok In Progress claimed_files: src/risk/trade_gateway.py trading cleanup"
                ),
            )
        )
        assert o.passed is False
        assert o.veto is True

    def test_empty_claims_limited_check(self):
        o = CoordinationExpert().evaluate(PanelInput(kind=TaskKind.COORD_AUDIT, agent="grok"))
        assert o.passed is True
        assert "coord:no_foreign_claims" in o.evidence_cites

    def test_clean_when_no_in_progress(self):
        o = CoordinationExpert().evaluate(
            PanelInput(
                kind=TaskKind.COORD_AUDIT,
                agent="grok",
                claimed_files=["src/foo.py"],
                other_agent_claims="codex finished yesterday on other work",
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

    def test_honest_narrative_kept_on_pass(self):
        def ok_narrative(summary, opinions):
            return "PASS: experts agree on docs-only change"

        v = JudgePanel(narrative_fn=ok_narrative).run(
            PanelInput(kind=TaskKind.CLAIM_AUDIT, text="docs only")
        )
        assert v.passed is True
        assert "experts agree" in v.judge_summary

    def test_missing_expert_vetoes(self):
        v = JudgePanel(experts={}).run(PanelInput(kind=TaskKind.CLAIM_AUDIT, text="docs only"))
        assert v.passed is False
        assert v.vetoed is True
        assert any("missing expert" in r for r in v.veto_reasons)

    def test_run_panel_convenience(self):
        v = run_panel(
            TaskKind.CLAIM_AUDIT,
            text="docs updated; no edge claim",
        )
        assert v.passed is True
        assert "evidence" in v.experts_used
        assert "risk_rules" in v.experts_used

    def test_run_panel_string_kind(self):
        v = run_panel("trade_entry", text="buy")
        assert v.kind is TaskKind.TRADE_ENTRY
        assert v.passed is False

    def test_to_dict_serializable(self):
        v = run_panel(TaskKind.TRADE_ENTRY, text="enter")
        d = v.to_dict()
        json.dumps(d)
        assert d["passed"] is False
        assert d["vetoed"] is True

    def test_re_claims_pass_helpers(self):
        assert re_claims_pass("") is False
        assert re_claims_pass("PASS: ok") is True
        assert re_claims_pass("panel pass confirmed") is True
        assert re_claims_pass("FAIL: no") is False


class TestSafeRead:
    def test_safe_read_allows_repo_file(self, tmp_path):
        # Import from script module path
        sys.path.insert(0, str(ROOT / "scripts"))
        import judge_panel as cli  # type: ignore

        target = ROOT / "scripts" / "judge_panel.py"
        text = cli.safe_read_text(str(target), roots=(ROOT,))
        assert "safe_read_text" in text or "Judge panel" in text

    def test_safe_read_rejects_outside_root(self, tmp_path):
        sys.path.insert(0, str(ROOT / "scripts"))
        import judge_panel as cli  # type: ignore

        outsider = tmp_path / "secret.txt"
        outsider.write_text("leak", encoding="utf-8")
        try:
            cli.safe_read_text(str(outsider), roots=(ROOT,))
            raise AssertionError("expected SystemExit")
        except SystemExit as exc:
            assert "outside allowed roots" in str(exc)

    def test_safe_read_empty_path(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import judge_panel as cli  # type: ignore

        assert cli.safe_read_text(None) == ""
        assert cli.safe_read_text("") == ""


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

    def test_cli_reads_diff_file_under_repo(self, tmp_path):
        # write under repo root via relative path in cwd
        diff = ROOT / "artifacts"
        diff.mkdir(exist_ok=True)
        f = diff / "judge_panel_test.diff"
        f.write_text("+ open new iron condor\n", encoding="utf-8")
        try:
            script = ROOT / "scripts" / "judge_panel.py"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--kind",
                    "pr_audit",
                    "--diff-file",
                    str(f),
                    "--json",
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                check=False,
            )
            assert proc.returncode == 2
            data = json.loads(proc.stdout)
            assert data["vetoed"] is True
        finally:
            f.unlink(missing_ok=True)
