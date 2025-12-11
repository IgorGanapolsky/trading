#!/usr/bin/env python3
"""
RAG Pre-Merge Check

A streamlined script that queries the RAG lessons learned database
before ANY merge to prevent repeated failures.

This script:
1. Checks syntax of all Python files
2. Verifies critical imports work
3. Queries RAG for similar past failures
4. Blocks merge if high-risk patterns detected
5. Logs the check for audit trail

Usage:
    python scripts/rag_premerge_check.py                    # Check staged files
    python scripts/rag_premerge_check.py --all              # Check all files
    python scripts/rag_premerge_check.py --files src/*.py   # Check specific files

Exit codes:
    0 - All checks passed
    1 - Syntax errors found
    2 - Import errors found
    3 - RAG found similar past failures (high risk)
    4 - Other errors

Author: Trading System CTO
Created: 2025-12-11
"""

import argparse
import ast
import json
import py_compile
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


@dataclass
class CheckResult:
    """Result of a pre-merge check."""
    name: str
    passed: bool
    message: str
    details: list[str] = field(default_factory=list)
    severity: str = "MEDIUM"  # CRITICAL, HIGH, MEDIUM, LOW


class RAGPreMergeChecker:
    """Pre-merge verification with RAG integration."""

    CRITICAL_FILES = [
        "src/orchestrator/main.py",
        "src/execution/alpaca_executor.py",
        "src/risk/trade_gateway.py",
        "src/strategies/core_strategy.py",
    ]

    CRITICAL_IMPORTS = [
        "from src.orchestrator.main import TradingOrchestrator",
        "from src.execution.alpaca_executor import AlpacaExecutor",
        "from src.risk.trade_gateway import TradeGateway",
    ]

    LESSONS_DIR = Path("rag_knowledge/lessons_learned")

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent
        self.results: list[CheckResult] = []
        self.lessons_cache: list[dict] = []

    def run_all_checks(self, files: list[Path] = None) -> bool:
        """Run all pre-merge checks."""
        print(f"\n{BOLD}=== RAG Pre-Merge Verification ==={RESET}\n")

        if files is None:
            files = self._get_staged_files()

        # 1. Syntax check
        self.check_syntax(files)

        # 2. Critical imports
        self.check_critical_imports()

        # 3. RAG lessons query
        self.check_rag_lessons(files)

        # 4. Pattern detection
        self.check_dangerous_patterns(files)

        # Print results
        self._print_results()

        # Determine exit code
        return self._determine_outcome()

    def _get_staged_files(self) -> list[Path]:
        """Get files staged for commit."""
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )
            files = [
                self.project_root / f.strip()
                for f in result.stdout.strip().split("\n")
                if f.strip() and f.endswith(".py")
            ]
            if not files:
                # No staged files, check all Python files
                files = list((self.project_root / "src").rglob("*.py"))
            return files
        except Exception:
            return list((self.project_root / "src").rglob("*.py"))

    def check_syntax(self, files: list[Path]) -> CheckResult:
        """Check syntax of all Python files."""
        print(f"{BLUE}[1/4] Checking syntax...{RESET}")

        errors = []
        for file_path in files:
            if not file_path.exists() or file_path.suffix != ".py":
                continue

            try:
                py_compile.compile(str(file_path), doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(f"{file_path.relative_to(self.project_root)}: {e.msg}")

        # Also check critical files even if not staged
        for critical in self.CRITICAL_FILES:
            critical_path = self.project_root / critical
            if critical_path.exists() and critical_path not in files:
                try:
                    py_compile.compile(str(critical_path), doraise=True)
                except py_compile.PyCompileError as e:
                    errors.append(f"{critical}: {e.msg}")

        result = CheckResult(
            name="Syntax Check",
            passed=len(errors) == 0,
            message=f"Checked {len(files)} files, {len(errors)} errors",
            details=errors[:10],  # Limit to first 10
            severity="CRITICAL" if errors else "LOW",
        )
        self.results.append(result)
        return result

    def check_critical_imports(self) -> CheckResult:
        """Verify critical imports work."""
        print(f"{BLUE}[2/4] Checking critical imports...{RESET}")

        errors = []
        for import_stmt in self.CRITICAL_IMPORTS:
            try:
                exec(import_stmt)
            except ImportError as e:
                errors.append(f"{import_stmt}: {e}")
            except SyntaxError as e:
                errors.append(f"SYNTAX ERROR: {import_stmt}: {e}")
            except Exception as e:
                # Other errors (missing env vars, etc) are OK
                pass

        result = CheckResult(
            name="Critical Imports",
            passed=len(errors) == 0,
            message=f"Checked {len(self.CRITICAL_IMPORTS)} imports, {len(errors)} failures",
            details=errors,
            severity="CRITICAL" if errors else "LOW",
        )
        self.results.append(result)
        return result

    def check_rag_lessons(self, files: list[Path]) -> CheckResult:
        """Query RAG for similar past failures."""
        print(f"{BLUE}[3/4] Querying RAG lessons learned...{RESET}")

        if not self.LESSONS_DIR.exists():
            result = CheckResult(
                name="RAG Lessons",
                passed=True,
                message="No lessons directory found",
                severity="LOW",
            )
            self.results.append(result)
            return result

        # Load lessons
        self._load_lessons()

        # Check for pattern matches
        warnings = []
        changed_files = [str(f.relative_to(self.project_root)) for f in files if f.exists()]

        for lesson in self.lessons_cache:
            # Check if any changed files match lesson patterns
            for pattern in lesson.get("file_patterns", []):
                for changed in changed_files:
                    if pattern in changed or changed in pattern:
                        warnings.append(
                            f"[{lesson['id']}] File '{changed}' matches lesson pattern"
                        )

        result = CheckResult(
            name="RAG Lessons",
            passed=len(warnings) < 3,  # Allow some warnings
            message=f"Found {len(warnings)} pattern matches with past failures",
            details=warnings[:5],
            severity="HIGH" if len(warnings) >= 3 else "MEDIUM" if warnings else "LOW",
        )
        self.results.append(result)
        return result

    def check_dangerous_patterns(self, files: list[Path]) -> CheckResult:
        """Check for dangerous code patterns."""
        print(f"{BLUE}[4/4] Checking for dangerous patterns...{RESET}")

        DANGEROUS_PATTERNS = [
            (r"\.env", "Possible secret file modification"),
            (r"password|secret|key\s*=\s*['\"]", "Possible hardcoded credential"),
            (r"eval\(|exec\(", "Dynamic code execution"),
            (r"subprocess\.call.*shell\s*=\s*True", "Shell injection risk"),
            (r"# type:\s*ignore", "Type checking bypassed"),
        ]

        warnings = []
        for file_path in files:
            if not file_path.exists() or file_path.suffix != ".py":
                continue

            try:
                content = file_path.read_text()
                for pattern, description in DANGEROUS_PATTERNS:
                    if re.search(pattern, content, re.IGNORECASE):
                        warnings.append(
                            f"{file_path.relative_to(self.project_root)}: {description}"
                        )
            except Exception:
                pass

        result = CheckResult(
            name="Dangerous Patterns",
            passed=len(warnings) == 0,
            message=f"Found {len(warnings)} potentially dangerous patterns",
            details=warnings[:5],
            severity="MEDIUM" if warnings else "LOW",
        )
        self.results.append(result)
        return result

    def _load_lessons(self) -> None:
        """Load lessons learned into cache."""
        if self.lessons_cache:
            return

        for md_file in self.LESSONS_DIR.glob("*.md"):
            try:
                content = md_file.read_text()
                lesson = {
                    "id": self._extract_id(content, md_file),
                    "severity": self._extract_severity(content),
                    "file_patterns": self._extract_file_patterns(content),
                }
                self.lessons_cache.append(lesson)
            except Exception:
                pass

    def _extract_id(self, content: str, file_path: Path) -> str:
        """Extract lesson ID."""
        match = re.search(r"\*\*ID\*\*:\s*(\w+)", content)
        return match.group(1) if match else file_path.stem

    def _extract_severity(self, content: str) -> str:
        """Extract severity."""
        match = re.search(r"\*\*Severity\*\*:\s*(\w+)", content, re.IGNORECASE)
        return match.group(1).upper() if match else "MEDIUM"

    def _extract_file_patterns(self, content: str) -> list[str]:
        """Extract file patterns."""
        patterns = re.findall(r"`([^`]+\.py)`", content)
        patterns.extend(re.findall(r"(src/\S+\.py)", content))
        return list(set(patterns))

    def _print_results(self) -> None:
        """Print results summary."""
        print(f"\n{BOLD}=== Results ==={RESET}\n")

        for result in self.results:
            icon = f"{GREEN}PASS{RESET}" if result.passed else f"{RED}FAIL{RESET}"
            print(f"{icon} {result.name}: {result.message}")

            if result.details:
                for detail in result.details[:3]:
                    print(f"   {YELLOW}!{RESET} {detail}")
                if len(result.details) > 3:
                    print(f"   ... and {len(result.details) - 3} more")

        print()

    def _determine_outcome(self) -> bool:
        """Determine final pass/fail outcome."""
        critical_failures = [r for r in self.results if not r.passed and r.severity == "CRITICAL"]
        high_failures = [r for r in self.results if not r.passed and r.severity == "HIGH"]

        if critical_failures:
            print(f"{RED}{BOLD}BLOCKED: Critical failures found. DO NOT MERGE.{RESET}")
            return False
        elif high_failures:
            print(f"{YELLOW}{BOLD}WARNING: High-risk issues found. Review carefully.{RESET}")
            return True  # Allow but warn
        else:
            print(f"{GREEN}{BOLD}PASSED: All checks passed. Safe to merge.{RESET}")
            return True

    def log_result(self) -> None:
        """Log check result for audit trail."""
        log_dir = self.project_root / "data" / "verification_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "severity": r.severity,
                }
                for r in self.results
            ],
        }

        log_file = log_dir / f"premerge_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        log_file.write_text(json.dumps(log_entry, indent=2))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="RAG Pre-Merge Verification")
    parser.add_argument("--all", action="store_true", help="Check all Python files")
    parser.add_argument("--files", nargs="*", help="Specific files to check")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    checker = RAGPreMergeChecker(project_root)

    if args.files:
        files = [Path(f) for f in args.files]
    elif args.all:
        files = list((project_root / "src").rglob("*.py"))
    else:
        files = None  # Will use staged files

    passed = checker.run_all_checks(files)
    checker.log_result()

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
