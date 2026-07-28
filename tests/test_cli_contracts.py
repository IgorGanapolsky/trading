"""CLI contract evals between orchestrator scripts and their subprocess targets.

Incident source (2026-07-27): run_autonomous_trading.py invoked
mercury_income_loop.py with flags the target's argparse did not define
(--ledger-path/--tax-rate/--live/--json), so every scheduler cycle died with
argparse exit 2 — and nothing caught it before main. These evals generalize
that failure class: any flag an orchestrator passes must be accepted by the
target parser, verified on every CI run.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import scripts.mercury_income_loop as income_loop

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCHEDULER = SCRIPTS / "run_autonomous_trading.py"

SUBPROCESS_TARGETS = [
    "run_autonomous_trading.py",  # its own flags appear in its source too
    "mercury_income_loop.py",
    "autonomous_money_cycle.py",
    "remittance_status.py",
]


def _help_flags(script_name: str) -> set[str]:
    """Flags a script's argparse accepts, harvested from its --help output."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script_name), "--help"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=ROOT,
    )
    assert result.returncode == 0, f"{script_name} --help failed: {result.stderr[-300:]}"
    return set(re.findall(r"--[a-z][a-z0-9-]*", result.stdout))


class TestSchedulerToIncomeLoopContract:
    """Strong contract: the exact argv shapes the scheduler composes must parse."""

    def test_dry_run_argv_parses(self, tmp_path):
        ledger = tmp_path / "ledger.jsonl"
        args = income_loop.parse_args(
            [
                "--state-path", str(tmp_path / "state.json"),
                "--ledger-path", str(ledger),
                "--bank-buffer-usd", "500.0",
                "--profit-return-threshold-usd", "50.0",
                "--tax-rate", "20.0",
                "--paper-starting-balance", "1500.0",
                "--json",
            ]
        )
        assert args.mode == "paper"
        assert args.tax_rate_pct == 20.0
        assert args.ledger_path == ledger

    def test_live_argv_parses_and_selects_live_mode(self, tmp_path):
        args = income_loop.parse_args(
            [
                "--state-path", str(tmp_path / "state.json"),
                "--ledger-path", str(tmp_path / "ledger.jsonl"),
                "--bank-buffer-usd", "500.0",
                "--profit-return-threshold-usd", "50.0",
                "--tax-rate", "20.0",
                "--live",
                "--json",
            ]
        )
        assert args.mode == "live"


class TestSchedulerFlagUniverse:
    """Weak-but-broad contract: every --flag literal in the scheduler source is
    accepted by at least one of its subprocess targets (or itself). A flag no
    parser accepts is exactly the 2026-07-27 incident."""

    def test_every_flag_literal_is_accepted_somewhere(self):
        source = SCHEDULER.read_text(encoding="utf-8")
        passed_flags = set(re.findall(r'"(--[a-z][a-z0-9-]*)"', source))
        assert passed_flags, "expected the scheduler to pass at least one --flag"

        accepted: set[str] = set()
        for target in SUBPROCESS_TARGETS:
            accepted |= _help_flags(target)

        orphans = sorted(passed_flags - accepted)
        assert not orphans, (
            f"scheduler passes flags no target parser accepts: {orphans} — "
            "update the target's argparse or the call site together"
        )

    def test_put_credit_cycle_flags_accepted(self):
        cycle_flags = _help_flags("autonomous_money_cycle.py")
        assert {"--dry-run", "--json"} <= cycle_flags

    def test_remittance_status_flags_accepted(self):
        assert "--json" in _help_flags("remittance_status.py")
