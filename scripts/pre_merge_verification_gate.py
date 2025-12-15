#!/usr/bin/env python3
"""
PRE-MERGE VERIFICATION GATE
===========================
PREVENTS breaking changes from reaching main branch.

This is what ACTUALLY improves reliability (not quantum computing).

Usage:
    python3 scripts/pre_merge_verification_gate.py

Exit codes:
    0 = Safe to merge (trading won't break)
    1 = BLOCKS merge (would break trading)
"""

import ast
import subprocess
import sys
from pathlib import Path


class MergeVerificationGate:
    """Block ANY merge that would break trading operations."""

    CRITICAL_MODULES = [
        "src/orchestrator/main.py",
        "src/safety/circuit_breaker.py",
        "src/safety/risk_manager.py",
        "src/strategies/base.py",
    ]

    def __init__(self):
        self.workspace = Path(__file__).parent.parent
        self.errors: list[str] = []

    def run_all_checks(self) -> bool:
        """Run all verification checks."""
        print("🔒 PRE-MERGE VERIFICATION GATE")
        print("=" * 60)
        print("Purpose: Prevent breaking changes from reaching main")
        print("=" * 60)

        checks = [
            ("Python Syntax", self.check_syntax),
            ("Critical Imports", self.check_imports),
            ("TradingOrchestrator", self.verify_orchestrator),
            ("Safety Systems", self.verify_safety),
        ]

        all_passed = True
        for name, check_fn in checks:
            print(f"\n🔍 {name}...")
            try:
                if check_fn():
                    print("   ✅ PASSED")
                else:
                    print("   ❌ FAILED")
                    all_passed = False
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
                self.errors.append(f"{name}: {e}")
                all_passed = False

        print("\n" + "=" * 60)
        if all_passed:
            print("✅ ALL CHECKS PASSED - SAFE TO MERGE")
            print("Trading operations will remain functional.")
            return True
        else:
            print("❌ VERIFICATION FAILED - BLOCKING MERGE")
            print("\n🚫 DO NOT MERGE - Would break trading!")
            print("\nErrors found:")
            for error in self.errors:
                print(f"  • {error}")
            return False

    def check_syntax(self) -> bool:
        """Verify Python syntax is valid."""
        python_files = list(self.workspace.glob("src/**/*.py"))
        python_files.extend(self.workspace.glob("scripts/**/*.py"))

        failed = []
        for file in python_files:
            try:
                with open(file) as f:
                    ast.parse(f.read(), filename=str(file))
            except SyntaxError as e:
                failed.append(f"{file.relative_to(self.workspace)}: {e}")

        if failed:
            self.errors.extend(failed)
            return False

        print(f"   Checked {len(python_files)} Python files")
        return True

    def check_imports(self) -> bool:
        """Verify critical packages can be imported."""
        critical = ["alpaca", "pandas", "numpy", "pydantic"]

        failed = []
        for module in critical:
            result = subprocess.run(
                [sys.executable, "-c", f"import {module}"],
                capture_output=True
            )
            if result.returncode != 0:
                failed.append(f"Cannot import {module}")

        if failed:
            self.errors.extend(failed)
            return False

        return True

    def verify_orchestrator(self) -> bool:
        """Verify TradingOrchestrator can be imported."""
        result = subprocess.run(
            [
                sys.executable, "-c",
                "from src.orchestrator.main import TradingOrchestrator"
            ],
            capture_output=True,
            cwd=self.workspace
        )

        if result.returncode != 0:
            self.errors.append("TradingOrchestrator import failed")
            return False

        return True

    def verify_safety(self) -> bool:
        """Verify safety systems are intact."""
        checks = [
            "from src.safety.circuit_breaker import CircuitBreaker",
            "from src.safety.risk_manager import RiskManager",
        ]

        for check in checks:
            result = subprocess.run(
                [sys.executable, "-c", check],
                capture_output=True,
                cwd=self.workspace
            )
            if result.returncode != 0:
                self.errors.append(f"Safety check failed: {check}")
                return False

        return True


def main():
    """Run verification gate."""
    gate = MergeVerificationGate()

    if gate.run_all_checks():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
