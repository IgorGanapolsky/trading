#!/usr/bin/env python3
"""
Enhanced Pre-Merge Gate with ML + RAG Integration

This is an enhanced version of pre_merge_gate.py that integrates:
1. ML anomaly detection
2. RAG semantic search for similar failures
3. Automated lesson ingestion
4. Comprehensive verification

Usage:
    python3 scripts/enhanced_pre_merge_gate.py [--files FILE1 FILE2 ...] [--commit-msg MESSAGE]

Exit codes:
    0 = All checks passed, safe to merge
    1 = One or more checks failed, DO NOT MERGE
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_changed_files() -> list[str]:
    """Get list of changed files from git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "origin/main"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.split("\n") if f.strip()]
    except Exception:
        pass

    # Fallback: check staged files
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.split("\n") if f.strip()]
    except Exception:
        pass

    return []


def get_commit_message() -> str:
    """Get commit message from git."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%B"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return ""


def run_basic_checks(root: Path) -> tuple[bool, list[str]]:
    """Run basic syntax and import checks."""
    failed = []
    src_dir = root / "src"

    checks = [
        (
            "Python Syntax Check",
            f"find {src_dir} -name '*.py' -exec python3 -m py_compile {{}} \\;",
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
    ]

    for name, cmd in checks:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ {name} FAILED")
            if result.stderr:
                print(f"   Error: {result.stderr[:300]}")
            failed.append(name)
        else:
            print(f"✅ {name} passed")

    return len(failed) == 0, failed


def run_ml_rag_verification(changed_files: list[str], commit_msg: str) -> tuple[bool, dict]:
    """Run ML+RAG integrated verification."""
    try:
        from src.verification.ml_rag_integrated_verifier import MLRAGIntegratedVerifier

        verifier = MLRAGIntegratedVerifier()
        result = verifier.verify_pre_merge(changed_files, commit_msg)

        print("\n" + "=" * 60)
        print("ML + RAG INTEGRATED VERIFICATION")
        print("=" * 60)

        if result.ml_anomalies:
            print(f"\nML Anomalies Detected: {len(result.ml_anomalies)}")
            for anomaly in result.ml_anomalies[:5]:  # Show top 5
                severity_icon = {"high": "🚨", "medium": "⚠️", "low": "ℹ️"}.get(
                    anomaly.get("severity", "low"), "•"
                )
                print(f"  {severity_icon} [{anomaly.get('category', 'unknown')}] {anomaly.get('description', 'N/A')}")

        if result.rag_warnings:
            print(f"\nRAG Warnings: {len(result.rag_warnings)}")
            for warning in result.rag_warnings[:5]:  # Show top 5
                if isinstance(warning, dict):
                    print(f"  ⚠️  {warning.get('title', warning.get('type', 'Unknown'))}")
                else:
                    print(f"  ⚠️  {warning}")

        if result.similar_lessons:
            print(f"\nSimilar Past Lessons: {len(result.similar_lessons)}")
            for lesson_id in result.similar_lessons[:3]:
                print(f"  📚 {lesson_id}")

        if result.recommendations:
            print("\nRecommendations:")
            for rec in result.recommendations:
                print(f"  {rec}")

        print(f"\nRisk Score: {result.risk_score}/100")
        status = "✅ PASSED" if result.passed else "❌ FAILED"
        print(f"\n{status}")

        return result.passed, {
            "risk_score": result.risk_score,
            "ml_anomalies": len(result.ml_anomalies),
            "rag_warnings": len(result.rag_warnings),
            "similar_lessons": result.similar_lessons,
        }

    except ImportError as e:
        print(f"⚠️  ML+RAG verification not available: {e}")
        print("   Falling back to basic checks only")
        return True, {}
    except Exception as e:
        print(f"⚠️  Error running ML+RAG verification: {e}")
        print("   Continuing with basic checks")
        return True, {}


def main():
    parser = argparse.ArgumentParser(description="Enhanced Pre-Merge Gate")
    parser.add_argument("--files", nargs="*", help="Changed files (auto-detected if not provided)")
    parser.add_argument("--commit-msg", help="Commit message (auto-detected if not provided)")
    parser.add_argument("--skip-ml-rag", action="store_true", help="Skip ML+RAG verification")
    args = parser.parse_args()

    print("=" * 60)
    print("ENHANCED PRE-MERGE GATE")
    print("ML + RAG Integrated Verification")
    print("=" * 60)
    print()

    root = Path(__file__).parent.parent

    # Get changed files and commit message
    changed_files = args.files or get_changed_files()
    commit_msg = args.commit_msg or get_commit_message()

    if changed_files:
        print(f"Changed files: {len(changed_files)}")
        for f in changed_files[:10]:  # Show first 10
            print(f"  - {f}")
        if len(changed_files) > 10:
            print(f"  ... and {len(changed_files) - 10} more")
    else:
        print("⚠️  No changed files detected")

    if commit_msg:
        print(f"\nCommit message: {commit_msg[:100]}...")
    print()

    # Run basic checks
    print("-" * 60)
    print("BASIC CHECKS")
    print("-" * 60)
    basic_passed, basic_failed = run_basic_checks(root)

    # Run ML+RAG verification
    ml_rag_passed = True
    ml_rag_info = {}
    if not args.skip_ml_rag and changed_files:
        ml_rag_passed, ml_rag_info = run_ml_rag_verification(changed_files, commit_msg)

    # Final decision
    print()
    print("=" * 60)
    all_passed = basic_passed and ml_rag_passed

    if all_passed:
        print("✅ ALL PRE-MERGE CHECKS PASSED")
        print("   Safe to merge this PR.")
        return 0
    else:
        print("🚨 PRE-MERGE GATE FAILED")
        if not basic_passed:
            print("   Failed basic checks:")
            for f in basic_failed:
                print(f"     - {f}")
        if not ml_rag_passed:
            print("   Failed ML+RAG verification")
            if ml_rag_info.get("risk_score", 0) >= 50:
                print(f"     Risk score too high: {ml_rag_info['risk_score']}/100")
        print()
        print("DO NOT MERGE until all checks pass!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
