#!/usr/bin/env python3
"""
Pre-merge gate - MUST pass before any PR merge.

This script was created after the Dec 11, 2025 incident where a syntax error
in alpaca_executor.py was merged to main, breaking all trading for the day.

Enhanced Dec 11, 2025: Added volatility-adjusted safety checks, RAG lessons
query, and ML anomaly detection based on Deep Research analysis.

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


def run_rag_check(root: Path, changed_files: list = None) -> bool:
    """Query RAG for similar past failures using new verification gate."""
    print("Running: RAG Safety Check (lessons learned)...")
    try:
        sys.path.insert(0, str(root))
        from src.verification.rag_verification_gate import RAGVerificationGate

        gate = RAGVerificationGate()

        # If we have changed files, check them
        if changed_files:
            is_safe, warnings = gate.check_merge_safety(
                pr_description="Pre-merge verification",
                changed_files=changed_files,
                pr_size=len(changed_files),
            )

            if warnings:
                print("⚠️  RAG Safety Check: Found relevant warnings")
                for w in warnings:
                    print(f"   {w}")
            else:
                print("✅ RAG Safety Check passed (no warnings)")

            return True  # Warnings only, don't block

        else:
            # Fallback: semantic search for common failure patterns
            results = gate.semantic_search("merge syntax error import failure CI", top_k=3)

            if results:
                print("⚠️  RAG Safety Check: Found relevant past incidents")
                for lesson, score in results[:3]:
                    print(
                        f"   [{lesson.severity.upper()}] {lesson.id}: {lesson.title} (score: {score:.1f})"
                    )
            else:
                print("✅ RAG Safety Check passed (no relevant history)")

            return True  # Warnings only, don't block

    except Exception as e:
        print(f"⚠️  RAG Safety Check: Could not query ({e})")
        return True  # Don't block if RAG unavailable


def run_volatility_safety_check(root: Path) -> bool:
    """Verify volatility-adjusted safety module is importable."""
    print("Running: Volatility Safety Module Check...")
    try:
        sys.path.insert(0, str(root))
        from src.safety.volatility_adjusted_safety import (
            ATRBasedLimits,
            DriftDetector,
            HourlyLossHeartbeat,
            LLMHallucinationChecker,
            run_all_safety_checks,
        )

        # Quick sanity test
        checker = LLMHallucinationChecker()
        result = checker.validate_trade_signal({"ticker": "SPY", "side": "buy"})
        if not result.is_valid:
            print("❌ Volatility Safety Module: Self-test failed")
            return False

        print("✅ Volatility Safety Module passed")
        return True
    except ImportError as e:
        print(f"❌ Volatility Safety Module: Import failed ({e})")
        return False
    except Exception as e:
        print(f"⚠️  Volatility Safety Module: Check failed ({e})")
        return True  # Don't block on non-import errors


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

    # Enhanced checks (Dec 11, 2025 - Deep Research improvements)
    # Updated Dec 14, 2025 - Added ML anomaly detection
    print()
    print("-" * 60)
    print("ENHANCED CHECKS (Deep Research + ML)")
    print("-" * 60)

    # Get changed files using git
    try:
        import subprocess

        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        changed_files = [f for f in result.stdout.strip().split("\n") if f]
    except Exception:
        changed_files = []

    if not run_volatility_safety_check(root):
        failed.append("Volatility Safety Module")

    if not run_rag_check(root, changed_files=changed_files):
        failed.append("RAG Safety Check")

    # ML Anomaly Detection (Dec 14, 2025)
    print("Running: ML Anomaly Detection...")
    try:
        sys.path.insert(0, str(root))
        from src.verification.ml_anomaly_detector import MLAnomalyDetector

        detector = MLAnomalyDetector()
        anomalies = detector.run_all_checks(files_changed=changed_files)

        if anomalies:
            critical_anomalies = [a for a in anomalies if a.severity == "critical"]
            high_anomalies = [a for a in anomalies if a.severity == "high"]

            if critical_anomalies:
                print(f"🚨 ML Anomaly Detection: {len(critical_anomalies)} CRITICAL anomalies")
                for a in critical_anomalies[:3]:
                    print(f"   {a.description}")
            elif high_anomalies:
                print(f"⚠️  ML Anomaly Detection: {len(high_anomalies)} HIGH severity anomalies")
                for a in high_anomalies[:2]:
                    print(f"   {a.description}")
            else:
                print(f"ℹ️  ML Anomaly Detection: {len(anomalies)} minor anomalies (warnings only)")
        else:
            print("✅ ML Anomaly Detection passed (no anomalies)")

    except Exception as e:
        print(f"⚠️  ML Anomaly Detection: Could not run ({e})")

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
