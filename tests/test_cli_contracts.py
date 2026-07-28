"""CLI contract evals between orchestrator scripts and their subprocess targets.

Incident source (2026-07-27): run_autonomous_trading.py invoked
mercury_income_loop.py with flags the target's argparse did not define
(--ledger-path/--tax-rate/--live/--json), so every scheduler cycle died with
argparse exit 2 — and nothing caught it before main. These evals generalize
that failure class: any flag an orchestrator passes must be accepted by the
target parser, verified on every CI run.
"""

from __future__ import annotations

import ast
import functools
import re
import subprocess
import sys
from pathlib import Path

import scripts.mercury_income_loop as income_loop

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCHEDULER = SCRIPTS / "run_autonomous_trading.py"


@functools.cache
def _help_flags(script_name: str) -> frozenset[str]:
    """Flags a script's argparse accepts, harvested from its --help output."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script_name), "--help"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=ROOT,
    )
    assert result.returncode == 0, f"{script_name} --help failed: {result.stderr[-300:]}"
    return frozenset(re.findall(r"--[a-z][a-z0-9-]*", result.stdout))


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


def _call_site_flags(source: str) -> dict[str, set[str]]:
    """Map each subprocess target script to the --flags composed for it.

    Walks the caller's AST: a list literal containing "scripts/<x>.py" starts a
    call site; later .append()/.extend() on the same variable contribute the
    conditionally added flags (e.g. --live, --json)."""
    tree = ast.parse(source)
    sites: dict[str, set[str]] = {}
    var_to_target: dict[str, str] = {}

    def _strings(node: ast.AST) -> list[str]:
        return [
            n.value
            for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
            strings = _strings(node.value)
            scripts = [s for s in strings if s.startswith("scripts/") and s.endswith(".py")]
            if scripts and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target_script = Path(scripts[0]).name
                var_to_target[node.targets[0].id] = target_script
                sites.setdefault(target_script, set()).update(
                    s for s in strings if s.startswith("--")
                )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("append", "extend")
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in var_to_target
        ):
            sites[var_to_target[node.func.value.id]].update(
                s for s in _strings(node) if s.startswith("--")
            )
    return sites


class TestCallSiteContracts:
    """Strong-and-broad contract: every flag composed for a specific subprocess
    target must be accepted by THAT target's parser (not merely by any parser
    in the union — a flag valid elsewhere is still the 2026-07-27 incident)."""

    def test_scheduler_composes_at_least_two_call_sites(self):
        sites = _call_site_flags(SCHEDULER.read_text(encoding="utf-8"))
        assert len(sites) >= 2, f"expected multiple subprocess call sites, got {sites}"

    def test_every_call_site_flag_is_accepted_by_its_target(self):
        sites = _call_site_flags(SCHEDULER.read_text(encoding="utf-8"))
        problems: list[str] = []
        for target_script, flags in sorted(sites.items()):
            accepted = _help_flags(target_script)
            for flag in sorted(flags - accepted):
                problems.append(f"{target_script} does not accept {flag}")
        assert not problems, (
            "call-site flag drift (argparse would exit 2 at runtime):\n"
            + "\n".join(problems)
        )
