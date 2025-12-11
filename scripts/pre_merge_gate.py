#!/usr/bin/env python3
"""
Pre-merge gate - MUST pass before any PR merge.

This script was created after the Dec 11, 2025 incident where a syntax error
in alpaca_executor.py was merged to main, breaking all trading for the day.

Usage:
    python3 scripts/pre_merge_gate.py

Exit codes:
    0 = All checks passed, safe to merge
    1 = One or more checks failed, DO NOT MERGE
"""

import subprocess
import sys
from pathlib import Path


def run_check(name: str, cmd: str) -> bool:
    """Run a check and return True if passed."""
    print(f"Running: {name}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ {name} FAILED")
        if result.stderr:
            print(f"   Error: {result.stderr[:500]}")
        return False
    print(f"✅ {name} passed")
    return True


def main():
    print("=" * 60)
    print("PRE-MERGE GATE - All checks must pass before merge")
    print("=" * 60)
    print()

    # Find project root
    root = Path(__file__).parent.parent
    src_dir = root / "src"

    checks = [
        (
            "Python Syntax Check",
            f"find {src_dir} -name '*.py' -exec python3 -m py_compile {{}} \\;",
        ),
        (
            "Ruff Lint Check",
            f"cd {root} && ruff check src/ --select=E9,F63,F7,F82 --quiet",
        ),
        (
            "Critical Import: TradingOrchestrator",
            f"cd {root} && python3 -c 'from src.orchestrator.main import TradingOrchestrator'",
        ),
        (
            "Critical Import: AlpacaExecutor",
            f"cd {root} && python3 -c 'from src.execution.alpaca_executor import AlpacaExecutor'",
        ),
        (
            "Critical Import: TradeGateway",
            f"cd {root} && python3 -c 'from src.risk.trade_gateway import TradeGateway'",
        ),
        (
            "Critical Import: Psychology Integration",
            f"cd {root} && python3 -c 'from src.coaching.mental_toughness_coach import get_prompt_context, get_position_size_modifier'",
        ),
        (
            "Critical Import: Debate Agents",
            f"cd {root} && python3 -c 'from src.agents.debate_agents import DebateModerator, BullAgent, BearAgent'",
        ),
        (
            "Critical Import: Reflexion Loop",
            f"cd {root} && python3 -c 'from src.coaching.reflexion_loop import ReflexionLoop'",
        ),
        # RL/ML Pipeline Checks (added Dec 11, 2025 per ll_011)
        (
            "Critical Import: RLFilter",
            f"cd {root} && python3 -c 'from src.agents.rl_agent import RLFilter'",
        ),
        (
            "Critical Import: RLWeightUpdater",
            f"cd {root} && python3 -c 'from src.agents.rl_weight_updater import RLWeightUpdater'",
        ),
        (
            "Critical Import: PositionManager",
            f"cd {root} && python3 -c 'from src.risk.position_manager import PositionManager'",
        ),
    ]

    failed = []
    for name, cmd in checks:
        if not run_check(name, cmd):
            failed.append(name)

    print()
    print("=" * 60)
    if failed:
        print(f"🚨 PRE-MERGE GATE FAILED: {len(failed)} check(s) failed")
        print("   Failed checks:")
        for f in failed:
            print(f"   - {f}")
        print()
        print("DO NOT MERGE until all checks pass!")
        sys.exit(1)
    else:
        print("✅ ALL PRE-MERGE CHECKS PASSED")
        print("   Safe to merge this PR.")
        sys.exit(0)


if __name__ == "__main__":
    main()
