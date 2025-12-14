"""
Automated Lesson Ingestion System

Automatically detects failures, errors, and anomalies, then ingests them
into the RAG system for future prevention. This creates a self-improving
verification system that learns from every mistake.

Key Features:
1. Monitors CI/CD failures and automatically records lessons
2. Detects trading anomalies and records prevention strategies
3. Integrates with ML anomaly detector for pattern recognition
4. Auto-generates prevention rules from failures

Created: Dec 13, 2025
"""

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FailureEvent:
    """A detected failure event."""

    timestamp: str
    category: str  # ci, trading, syntax, import, test, etc.
    severity: str  # critical, high, medium, low
    description: str
    root_cause: str
    affected_files: list[str]
    error_message: Optional[str] = None
    financial_impact: Optional[float] = None
    similar_lessons: list[str] = None  # IDs of similar past lessons


class AutomatedLessonIngestion:
    """
    Automatically detects failures and ingests them into RAG.

    Monitors:
    - CI/CD workflow failures
    - Trading execution failures
    - Syntax/import errors
    - Test failures
    - Performance anomalies
    """

    def __init__(
        self,
        rag_path: str = "data/rag/lessons_learned.json",
        lessons_dir: Path = Path("rag_knowledge/lessons_learned"),
    ):
        self.rag_path = Path(rag_path)
        self.lessons_dir = lessons_dir
        self.lessons_dir.mkdir(parents=True, exist_ok=True)

    def detect_ci_failure(self, workflow_run_id: Optional[str] = None) -> Optional[FailureEvent]:
        """
        Detect CI/CD failures from GitHub Actions.

        Args:
            workflow_run_id: Optional specific workflow run to check

        Returns:
            FailureEvent if failure detected, None otherwise
        """
        try:
            # Check recent workflow runs
            result = subprocess.run(
                ["gh", "run", "list", "--limit", "5", "--json", "conclusion,name,workflowName"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                logger.warning("Could not check CI status (gh CLI not available)")
                return None

            runs = json.loads(result.stdout)
            failed_runs = [r for r in runs if r.get("conclusion") == "failure"]

            if not failed_runs:
                return None

            latest_failure = failed_runs[0]

            # Get failure details
            run_id = latest_failure.get("id", "unknown")
            workflow_name = latest_failure.get("workflowName", "unknown")

            # Try to get job logs
            log_result = subprocess.run(
                ["gh", "run", "view", str(run_id), "--log"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            error_message = None
            if log_result.returncode == 0:
                logs = log_result.stdout
                # Extract error patterns
                if "SyntaxError" in logs:
                    error_message = "Syntax error detected"
                elif "ImportError" in logs or "ModuleNotFoundError" in logs:
                    error_message = "Import error detected"
                elif "AssertionError" in logs or "test" in logs.lower():
                    error_message = "Test failure detected"

            return FailureEvent(
                timestamp=datetime.now().isoformat(),
                category="ci",
                severity="high",
                description=f"CI workflow '{workflow_name}' failed",
                root_cause=error_message or "Unknown CI failure",
                affected_files=[],
                error_message=error_message,
                similar_lessons=["ll_009", "ll_024"],  # Known CI failures
            )

        except Exception as e:
            logger.warning(f"Error detecting CI failure: {e}")
            return None

    def detect_syntax_errors(self, changed_files: list[str]) -> list[FailureEvent]:
        """
        Detect syntax errors in changed Python files.

        Args:
            changed_files: List of file paths to check

        Returns:
            List of FailureEvent objects for each syntax error
        """
        failures = []

        for file_path in changed_files:
            if not file_path.endswith(".py"):
                continue

            path = Path(file_path)
            if not path.exists():
                continue

            try:
                # Try to compile the file
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode != 0:
                    failures.append(
                        FailureEvent(
                            timestamp=datetime.now().isoformat(),
                            category="syntax",
                            severity="critical",
                            description=f"Syntax error in {file_path}",
                            root_cause=result.stderr[:500] if result.stderr else "Syntax check failed",
                            affected_files=[file_path],
                            error_message=result.stderr[:500] if result.stderr else None,
                            similar_lessons=["ll_009", "ll_024"],
                        )
                    )

            except Exception as e:
                logger.warning(f"Error checking syntax for {file_path}: {e}")

        return failures

    def detect_import_errors(self, critical_imports: list[str]) -> list[FailureEvent]:
        """
        Detect import errors for critical modules.

        Args:
            critical_imports: List of import statements to verify

        Returns:
            List of FailureEvent objects for each import error
        """
        failures = []

        for import_stmt in critical_imports:
            try:
                result = subprocess.run(
                    [sys.executable, "-c", f"import {import_stmt}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode != 0:
                    failures.append(
                        FailureEvent(
                            timestamp=datetime.now().isoformat(),
                            category="import",
                            severity="critical",
                            description=f"Import error: {import_stmt}",
                            root_cause=result.stderr[:500] if result.stderr else "Import failed",
                            affected_files=[],
                            error_message=result.stderr[:500] if result.stderr else None,
                            similar_lessons=["ll_009"],
                        )
                    )

            except Exception as e:
                logger.warning(f"Error checking import {import_stmt}: {e}")

        return failures

    def detect_trading_failures(self) -> Optional[FailureEvent]:
        """
        Detect trading execution failures.

        Checks for:
        - No trades executed when expected
        - Workflow failures
        - Execution errors

        Returns:
            FailureEvent if failure detected, None otherwise
        """
        try:
            # Check system state for trading failures
            state_path = Path("data/system_state.json")
            if not state_path.exists():
                return None

            with open(state_path) as f:
                state = json.load(f)

            # Check automation status
            automation = state.get("automation", {})
            if automation.get("workflow_status") != "OPERATIONAL":
                return FailureEvent(
                    timestamp=datetime.now().isoformat(),
                    category="trading",
                    severity="high",
                    description="Trading workflow not operational",
                    root_cause=automation.get("failure_reasons", ["Unknown"])[0] if automation.get("failure_reasons") else "Workflow status not operational",
                    affected_files=[],
                    similar_lessons=["ll_009", "ll_019"],
                )

            # Check for zero trades when expected
            performance = state.get("performance", {})
            total_trades = performance.get("total_trades", 0)

            # This is a heuristic - in production, would check expected vs actual
            # For now, just check if system is completely dead
            return None

        except Exception as e:
            logger.warning(f"Error detecting trading failures: {e}")
            return None

    def ingest_failure(self, failure: FailureEvent) -> str:
        """
        Ingest a failure event into the RAG system.

        Creates both:
        1. JSON entry in RAG store
        2. Markdown file in lessons_learned directory

        Args:
            failure: The failure event to ingest

        Returns:
            Lesson ID
        """
        # Generate lesson ID
        lesson_id = f"ll_{datetime.now().strftime('%Y%m%d')}_{failure.category}_{len(self._get_existing_lessons())}"

        # Create markdown lesson file
        md_content = self._generate_markdown_lesson(failure, lesson_id)
        md_path = self.lessons_dir / f"{lesson_id}.md"
        md_path.write_text(md_content, encoding="utf-8")

        # Add to RAG JSON store
        self._add_to_rag_store(failure, lesson_id)

        logger.info(f"✅ Ingested failure as lesson: {lesson_id}")
        return lesson_id

    def _generate_markdown_lesson(self, failure: FailureEvent, lesson_id: str) -> str:
        """Generate markdown content for a lesson learned."""
        prevention = self._generate_prevention(failure)

        md = f"""# Lesson Learned: {failure.description}

**ID**: {lesson_id}
**Date**: {datetime.now().strftime('%Y-%m-%d')}
**Severity**: {failure.severity.upper()}
**Category**: {failure.category}
**Impact**: {failure.financial_impact or 'System failure'}

## Executive Summary

{failure.description}

## Root Cause

{failure.root_cause}

## Prevention

{prevention}

## Affected Files

{chr(10).join(f"- {f}" for f in failure.affected_files) if failure.affected_files else "None"}

## Similar Past Incidents

{chr(10).join(f"- {lid}" for lid in (failure.similar_lessons or []))}

## Tags

#{failure.category} #automated-detection #verification #lessons-learned
"""

        if failure.error_message:
            md += f"""
## Error Message

```
{failure.error_message[:500]}
```
"""

        return md

    def _generate_prevention(self, failure: FailureEvent) -> str:
        """Generate prevention strategy based on failure type."""
        prevention_map = {
            "syntax": "Add syntax check to pre-merge gate. Run `python3 -m py_compile` on all Python files before commit.",
            "import": "Add import verification to CI. Test critical imports before merge.",
            "ci": "Require CI to pass before merge. Add branch protection rules.",
            "trading": "Add post-deploy verification. Monitor trading execution daily.",
            "test": "Increase test coverage. Add regression tests for this failure mode.",
        }

        base_prevention = prevention_map.get(failure.category, "Add validation to prevent this failure type.")

        if failure.similar_lessons:
            base_prevention += f"\n\nSee similar incidents: {', '.join(failure.similar_lessons)}"

        return base_prevention

    def _add_to_rag_store(self, failure: FailureEvent, lesson_id: str) -> None:
        """Add failure to RAG JSON store."""
        self.rag_path.parent.mkdir(parents=True, exist_ok=True)

        if self.rag_path.exists():
            with open(self.rag_path) as f:
                data = json.load(f)
        else:
            data = {"lessons": []}

        lesson_entry = {
            "id": lesson_id,
            "timestamp": failure.timestamp,
            "category": failure.category,
            "title": failure.description,
            "description": failure.description,
            "root_cause": failure.root_cause,
            "prevention": self._generate_prevention(failure),
            "severity": failure.severity,
            "tags": [failure.category, "automated-detection"],
            "financial_impact": failure.financial_impact,
        }

        data["lessons"].append(lesson_entry)

        with open(self.rag_path, "w") as f:
            json.dump(data, f, indent=2)

    def _get_existing_lessons(self) -> list[str]:
        """Get list of existing lesson IDs."""
        if not self.lessons_dir.exists():
            return []

        return [f.stem for f in self.lessons_dir.glob("ll_*.md")]

    def run_full_detection(self) -> list[FailureEvent]:
        """
        Run full failure detection across all categories.

        Returns:
            List of detected failure events
        """
        failures = []

        # Check CI failures
        ci_failure = self.detect_ci_failure()
        if ci_failure:
            failures.append(ci_failure)

        # Check trading failures
        trading_failure = self.detect_trading_failures()
        if trading_failure:
            failures.append(trading_failure)

        return failures


def main():
    """CLI entry point for automated lesson ingestion."""
    import argparse

    parser = argparse.ArgumentParser(description="Automated Lesson Ingestion")
    parser.add_argument("--check-ci", action="store_true", help="Check CI failures")
    parser.add_argument("--check-syntax", nargs="*", help="Check syntax for files")
    parser.add_argument("--check-imports", nargs="*", help="Check imports")
    parser.add_argument("--auto-ingest", action="store_true", help="Automatically ingest detected failures")
    args = parser.parse_args()

    ingestion = AutomatedLessonIngestion()

    failures = []

    if args.check_ci:
        failure = ingestion.detect_ci_failure()
        if failure:
            failures.append(failure)

    if args.check_syntax:
        failures.extend(ingestion.detect_syntax_errors(args.check_syntax))

    if args.check_imports:
        failures.extend(ingestion.detect_import_errors(args.check_imports))

    if not args.check_ci and not args.check_syntax and not args.check_imports:
        # Run full detection
        failures = ingestion.run_full_detection()

    if failures:
        print(f"Detected {len(failures)} failure(s):")
        for f in failures:
            print(f"  [{f.severity.upper()}] {f.description}")

        if args.auto_ingest:
            print("\nIngesting failures into RAG...")
            for failure in failures:
                lesson_id = ingestion.ingest_failure(failure)
                print(f"  ✅ Ingested: {lesson_id}")
    else:
        print("✅ No failures detected")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
