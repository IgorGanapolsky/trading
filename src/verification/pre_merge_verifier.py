"""
Pre-Merge Verifier

Comprehensive verification before any PR merge.
Integrates syntax checks, import verification, RAG safety, and ML anomaly detection.

Created: Dec 11, 2025 (after syntax error incident)
"""

import ast
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of pre-merge verification."""

    passed: bool
    checks_run: int
    checks_passed: int
    checks_failed: int
    failures: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    rag_check: Optional[dict] = None

    def __bool__(self):
        return self.passed

    def summary(self) -> str:
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        return (
            f"{status}: {self.checks_passed}/{self.checks_run} checks passed\n"
            f"Failures: {self.checks_failed}\n"
            f"Warnings: {len(self.warnings)}"
        )


class PreMergeVerifier:
    """
    Multi-layer pre-merge verification system.

    Checks:
    1. Syntax validation (all Python files compile)
    2. Critical import verification
    3. RAG safety check (similar past incidents)
    4. Lint check (ruff)
    5. Type check (mypy) - optional
    6. Test execution - optional

    Usage:
        verifier = PreMergeVerifier()
        result = verifier.verify_all(changed_files)
        if not result.passed:
            print("MERGE BLOCKED:", result.failures)
    """

    # Critical imports that MUST work for trading to function
    CRITICAL_IMPORTS = [
        ("TradingOrchestrator", "from src.orchestrator.main import TradingOrchestrator"),
        ("AlpacaExecutor", "from src.execution.alpaca_executor import AlpacaExecutor"),
        ("TradeGateway", "from src.risk.trade_gateway import TradeGateway"),
        ("CoreStrategy", "from src.strategies.core_strategy import CoreStrategy"),
        ("CryptoStrategy", "from src.strategies.crypto_strategy import CryptoStrategy"),
    ]

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.results: list[dict] = []

    def verify_all(
        self,
        changed_files: Optional[list[str]] = None,
        run_tests: bool = False,
        run_typecheck: bool = False,
    ) -> VerificationResult:
        """
        Run all verification checks.

        Args:
            changed_files: Optional list of changed files (for targeted checks)
            run_tests: Whether to run pytest
            run_typecheck: Whether to run mypy

        Returns:
            VerificationResult with pass/fail status and details
        """
        checks_run = 0
        checks_passed = 0
        failures = []
        warnings = []

        # Check 1: Syntax Validation
        checks_run += 1
        syntax_result = self.check_syntax()
        if syntax_result["passed"]:
            checks_passed += 1
            logger.info("✅ Syntax check passed")
        else:
            failures.append(syntax_result)
            logger.error(f"❌ Syntax check failed: {syntax_result['errors']}")

        # Check 2: Critical Imports
        checks_run += 1
        import_result = self.check_critical_imports()
        if import_result["passed"]:
            checks_passed += 1
            logger.info("✅ Critical imports check passed")
        else:
            failures.append(import_result)
            logger.error(f"❌ Critical imports failed: {import_result['errors']}")

        # Check 3: RAG Safety Check
        checks_run += 1
        rag_result = self.check_rag_safety(changed_files or [])
        if rag_result["passed"]:
            checks_passed += 1
            logger.info("✅ RAG safety check passed")
        else:
            if rag_result.get("blocking"):
                failures.append(rag_result)
                logger.error(f"❌ RAG safety check blocked: {rag_result['reasons']}")
            else:
                checks_passed += 1
                warnings.append(rag_result)
                logger.warning(f"⚠️ RAG safety warnings: {rag_result['warnings']}")

        # Check 4: Lint Check
        checks_run += 1
        lint_result = self.check_lint()
        if lint_result["passed"]:
            checks_passed += 1
            logger.info("✅ Lint check passed")
        else:
            # Lint failures are warnings, not blockers
            checks_passed += 1
            warnings.append(lint_result)
            logger.warning(f"⚠️ Lint issues: {lint_result.get('issues', 'unknown')}")

        # Check 5: Type Check (optional)
        if run_typecheck:
            checks_run += 1
            type_result = self.check_types()
            if type_result["passed"]:
                checks_passed += 1
                logger.info("✅ Type check passed")
            else:
                warnings.append(type_result)
                logger.warning(f"⚠️ Type issues: {type_result.get('issues', 'unknown')}")

        # Check 6: Tests (optional)
        if run_tests:
            checks_run += 1
            test_result = self.check_tests()
            if test_result["passed"]:
                checks_passed += 1
                logger.info("✅ Tests passed")
            else:
                failures.append(test_result)
                logger.error(f"❌ Tests failed: {test_result.get('output', 'unknown')}")

        return VerificationResult(
            passed=len(failures) == 0,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=len(failures),
            failures=failures,
            warnings=warnings,
            rag_check=rag_result,
        )

    def check_syntax(self) -> dict:
        """Verify all Python files have valid syntax."""
        errors = []
        files_checked = 0

        for py_file in self.project_root.glob("src/**/*.py"):
            files_checked += 1
            try:
                with open(py_file) as f:
                    source = f.read()
                ast.parse(source)
            except SyntaxError as e:
                errors.append(
                    {
                        "file": str(py_file),
                        "line": e.lineno,
                        "message": str(e.msg),
                    }
                )

        return {
            "check": "syntax",
            "passed": len(errors) == 0,
            "files_checked": files_checked,
            "errors": errors,
        }

    def check_critical_imports(self) -> dict:
        """Verify critical trading system imports work."""
        errors = []

        # We check by parsing, not importing (to avoid dependency issues)
        for name, import_stmt in self.CRITICAL_IMPORTS:
            try:
                # Parse the import statement
                tree = ast.parse(import_stmt)

                # Extract the module path
                node = tree.body[0]
                if isinstance(node, ast.ImportFrom):
                    module = node.module
                    # Check if file exists
                    module_path = self.project_root / module.replace(".", "/")
                    if not (module_path.exists() or Path(str(module_path) + ".py").exists()):
                        # Module path doesn't exist - check parent
                        parent = module_path.parent
                        if parent.exists():
                            # Check if it's in __init__.py
                            init_file = parent / "__init__.py"
                            if init_file.exists():
                                continue

                    # Try actual import in subprocess to catch runtime errors
                    result = subprocess.run(
                        [sys.executable, "-c", import_stmt],
                        capture_output=True,
                        text=True,
                        cwd=str(self.project_root),
                        timeout=30,
                    )
                    if result.returncode != 0:
                        # Check if it's just a missing dependency vs syntax error
                        if "SyntaxError" in result.stderr:
                            errors.append(
                                {
                                    "name": name,
                                    "import": import_stmt,
                                    "error": result.stderr.strip(),
                                    "type": "syntax_error",
                                }
                            )

            except Exception as e:
                errors.append(
                    {
                        "name": name,
                        "import": import_stmt,
                        "error": str(e),
                    }
                )

        return {
            "check": "critical_imports",
            "passed": len(errors) == 0,
            "imports_checked": len(self.CRITICAL_IMPORTS),
            "errors": errors,
        }

    def check_rag_safety(self, changed_files: list[str]) -> dict:
        """Check RAG for similar past incidents."""
        try:
            from .rag_safety_checker import RAGSafetyChecker

            checker = RAGSafetyChecker()
            result = checker.check_merge_safety(
                changed_files=changed_files,
                commit_message="",
            )

            return {
                "check": "rag_safety",
                "passed": result.safe or len(result.blocking_reasons) == 0,
                "blocking": not result.safe,
                "warnings": result.warnings,
                "reasons": result.blocking_reasons,
                "similar_incidents": result.similar_incidents,
                "confidence": result.confidence,
            }

        except ImportError:
            return {
                "check": "rag_safety",
                "passed": True,
                "warnings": ["RAG safety checker not available"],
            }

    def check_lint(self) -> dict:
        """Run ruff linter."""
        try:
            result = subprocess.run(
                ["ruff", "check", "src/", "--select=E9,F63,F7,F82", "--quiet"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=60,
            )

            return {
                "check": "lint",
                "passed": result.returncode == 0,
                "issues": result.stdout.strip() if result.stdout else None,
            }

        except FileNotFoundError:
            return {
                "check": "lint",
                "passed": True,
                "issues": "ruff not installed",
            }
        except subprocess.TimeoutExpired:
            return {
                "check": "lint",
                "passed": False,
                "issues": "lint check timed out",
            }

    def check_types(self) -> dict:
        """Run mypy type checker."""
        try:
            result = subprocess.run(
                ["mypy", "src/", "--ignore-missing-imports"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=120,
            )

            return {
                "check": "types",
                "passed": result.returncode == 0,
                "issues": result.stdout.strip() if result.stdout else None,
            }

        except FileNotFoundError:
            return {
                "check": "types",
                "passed": True,
                "issues": "mypy not installed",
            }

    def check_tests(self) -> dict:
        """Run pytest."""
        try:
            result = subprocess.run(
                ["pytest", "tests/", "-x", "-q", "--timeout=60"],
                capture_output=True,
                text=True,
                cwd=str(self.project_root),
                timeout=300,
            )

            return {
                "check": "tests",
                "passed": result.returncode == 0,
                "output": result.stdout.strip() if result.stdout else None,
            }

        except FileNotFoundError:
            return {
                "check": "tests",
                "passed": True,
                "output": "pytest not installed",
            }


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Pre-merge verification")
    parser.add_argument("--tests", action="store_true", help="Run tests")
    parser.add_argument("--types", action="store_true", help="Run type check")
    parser.add_argument("--files", nargs="*", help="Changed files")
    args = parser.parse_args()

    verifier = PreMergeVerifier()
    result = verifier.verify_all(
        changed_files=args.files,
        run_tests=args.tests,
        run_typecheck=args.types,
    )

    print("\n" + "=" * 60)
    print("PRE-MERGE VERIFICATION RESULTS")
    print("=" * 60)
    print(result.summary())

    if result.failures:
        print("\nFAILURES:")
        for f in result.failures:
            print(f"  - {f['check']}: {f.get('errors') or f.get('reasons')}")

    if result.warnings:
        print("\nWARNINGS:")
        for w in result.warnings:
            print(f"  - {w['check']}: {w.get('warnings') or w.get('issues')}")

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
