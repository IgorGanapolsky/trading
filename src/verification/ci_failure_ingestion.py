"""
Automated CI Failure Ingestion Pipeline.

Automatically ingests CI/CD failures into the RAG system and ML pattern
detector. Parses GitHub Actions logs to extract failure patterns and
create lessons learned.

Key Features:
1. Parse GitHub Actions workflow run logs
2. Extract error signatures and root causes
3. Create lessons learned automatically
4. Update ML pattern detector
5. Send alerts for critical failures

Integration:
- GitHub API: Fetch workflow run results
- RAG: Store lessons for future lookup
- ML Pattern Detector: Learn from failures
- Slack/Email: Alert on critical failures

Created: 2025-12-14
Author: Trading CTO
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of CI failures."""

    SYNTAX_ERROR = "syntax_error"
    IMPORT_ERROR = "import_error"
    TEST_FAILURE = "test_failure"
    LINT_ERROR = "lint_error"
    BUILD_ERROR = "build_error"
    TIMEOUT = "timeout"
    DEPENDENCY_ERROR = "dependency_error"
    PERMISSION_ERROR = "permission_error"
    UNKNOWN = "unknown"


@dataclass
class CIFailure:
    """Represents a CI failure event."""

    run_id: str
    workflow_name: str
    job_name: str
    failure_type: FailureType
    error_message: str
    error_line: Optional[int]
    file_path: Optional[str]
    full_log: str
    timestamp: datetime
    branch: str
    commit_sha: str
    pr_number: Optional[int]
    actor: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
            "job_name": self.job_name,
            "failure_type": self.failure_type.value,
            "error_message": self.error_message,
            "error_line": self.error_line,
            "file_path": self.file_path,
            "timestamp": self.timestamp.isoformat(),
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "pr_number": self.pr_number,
            "actor": self.actor,
        }


class CIFailureIngestionPipeline:
    """
    Pipeline for ingesting CI failures into RAG and ML systems.

    Workflow:
    1. Fetch failed workflow runs from GitHub
    2. Parse logs to extract failure details
    3. Classify failure type
    4. Create lesson learned entry
    5. Update ML pattern detector
    6. Alert if critical
    """

    FAILURES_LOG_PATH = Path("data/ci/failures_log.json")

    # Error patterns for classification
    ERROR_PATTERNS = {
        FailureType.SYNTAX_ERROR: [
            r"SyntaxError:",
            r"invalid syntax",
            r"unexpected EOF while parsing",
            r"f-string: invalid",
        ],
        FailureType.IMPORT_ERROR: [
            r"ImportError:",
            r"ModuleNotFoundError:",
            r"cannot import name",
            r"No module named",
        ],
        FailureType.TEST_FAILURE: [
            r"FAILED.*test_",
            r"AssertionError:",
            r"pytest.*\d+ failed",
            r"test.*failed",
        ],
        FailureType.LINT_ERROR: [
            r"ruff.*error",
            r"mypy.*error:",
            r"flake8.*:.*:",
            r"black.*would reformat",
        ],
        FailureType.BUILD_ERROR: [
            r"pip install.*failed",
            r"compilation.*error",
            r"build failed",
        ],
        FailureType.TIMEOUT: [
            r"timeout",
            r"exceeded.*time.*limit",
            r"Job.*cancelled",
        ],
        FailureType.DEPENDENCY_ERROR: [
            r"Could not find.*version",
            r"dependency.*conflict",
            r"package.*not found",
        ],
        FailureType.PERMISSION_ERROR: [
            r"PermissionError",
            r"Permission denied",
            r"EACCES",
        ],
    }

    def __init__(
        self,
        repo: str = "IgorGanapolsky/agent-web-crawler",
        rag_enabled: bool = True,
        ml_detector_enabled: bool = True,
    ):
        """
        Initialize the ingestion pipeline.

        Args:
            repo: GitHub repository (owner/name)
            rag_enabled: Whether to ingest to RAG
            ml_detector_enabled: Whether to update ML pattern detector
        """
        self.repo = repo
        self.rag = None
        self.ml_detector = None
        self.failures_history: list[dict] = []

        # Load history
        self._load_history()

        # Initialize integrations
        if rag_enabled:
            self._init_rag()
        if ml_detector_enabled:
            self._init_ml_detector()

    def _init_rag(self) -> None:
        """Initialize RAG connection."""
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            self.rag = LessonsLearnedRAG()
            logger.info("RAG integration enabled for CI failure ingestion")
        except Exception as e:
            logger.warning(f"Could not initialize RAG: {e}")

    def _init_ml_detector(self) -> None:
        """Initialize ML pattern detector."""
        try:
            from src.verification.ml_lesson_pattern_detector import (
                MLLessonPatternDetector,
                FailureCategory,
                RiskLevel,
            )

            self.ml_detector = MLLessonPatternDetector(rag_enabled=False)
            self.FailureCategory = FailureCategory
            self.RiskLevel = RiskLevel
            logger.info("ML detector enabled for CI failure ingestion")
        except Exception as e:
            logger.warning(f"Could not initialize ML detector: {e}")

    def _load_history(self) -> None:
        """Load failure history from disk."""
        if self.FAILURES_LOG_PATH.exists():
            try:
                with open(self.FAILURES_LOG_PATH) as f:
                    self.failures_history = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load failure history: {e}")

    def _save_failure(self, failure: CIFailure) -> None:
        """Save failure to history."""
        self.failures_history.append(failure.to_dict())

        # Keep last 500 failures
        self.failures_history = self.failures_history[-500:]

        self.FAILURES_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(self.FAILURES_LOG_PATH, "w") as f:
            json.dump(self.failures_history, f, indent=2)

    def fetch_failed_runs(
        self,
        limit: int = 10,
        branch: Optional[str] = None,
    ) -> list[dict]:
        """
        Fetch failed workflow runs from GitHub.

        Args:
            limit: Maximum number of runs to fetch
            branch: Filter by branch (optional)

        Returns:
            List of failed run metadata
        """
        try:
            cmd = ["gh", "run", "list", "--repo", self.repo, "--status", "failure", "--limit", str(limit), "--json", "databaseId,name,headBranch,headSha,conclusion,createdAt,actor,number"]

            if branch:
                cmd.extend(["--branch", branch])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                logger.error(f"gh run list failed: {result.stderr}")
                return []

            runs = json.loads(result.stdout)
            return runs

        except Exception as e:
            logger.error(f"Failed to fetch runs: {e}")
            return []

    def fetch_run_logs(self, run_id: str) -> str:
        """
        Fetch logs for a specific workflow run.

        Args:
            run_id: The workflow run ID

        Returns:
            Log content as string
        """
        try:
            cmd = ["gh", "run", "view", str(run_id), "--repo", self.repo, "--log-failed"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode != 0:
                # Try full log if failed-only doesn't work
                cmd[-1] = "--log"
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            return result.stdout

        except Exception as e:
            logger.error(f"Failed to fetch logs for run {run_id}: {e}")
            return ""

    def classify_failure(self, log_content: str) -> FailureType:
        """
        Classify the type of failure from log content.

        Args:
            log_content: The log content to analyze

        Returns:
            FailureType enum value
        """
        for failure_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, log_content, re.IGNORECASE):
                    return failure_type

        return FailureType.UNKNOWN

    def extract_error_details(
        self,
        log_content: str,
    ) -> tuple[str, Optional[str], Optional[int]]:
        """
        Extract error message, file path, and line number from logs.

        Args:
            log_content: The log content to analyze

        Returns:
            Tuple of (error_message, file_path, line_number)
        """
        error_message = "Unknown error"
        file_path = None
        line_number = None

        # Look for common error patterns
        patterns = [
            # Python errors with traceback
            r'File "([^"]+)", line (\d+).*\n.*\n\s*(\w+Error: .+)',
            # Syntax errors
            r'File "([^"]+)", line (\d+)\n\s*(.+)\n\s*\^+\n(\w+Error: .+)',
            # Import errors
            r"(ImportError|ModuleNotFoundError): (.+)",
            # Test failures
            r"FAILED ([\w/]+\.py)::([\w_]+) - (.+)",
            # Generic errors
            r"(\w+Error): (.+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, log_content, re.MULTILINE)
            if match:
                groups = match.groups()
                if len(groups) >= 3 and "/" in groups[0]:
                    file_path = groups[0]
                    try:
                        line_number = int(groups[1])
                    except (ValueError, IndexError):
                        pass
                    error_message = groups[-1][:200]  # Truncate
                elif len(groups) >= 2:
                    error_message = f"{groups[0]}: {groups[1]}"[:200]
                break

        # Also extract file path from error context
        if not file_path:
            file_match = re.search(r"(src/[\w/]+\.py|tests/[\w/]+\.py)", log_content)
            if file_match:
                file_path = file_match.group(1)

        return error_message, file_path, line_number

    def parse_failure(
        self,
        run_metadata: dict,
        log_content: str,
    ) -> CIFailure:
        """
        Parse a CI failure from run metadata and logs.

        Args:
            run_metadata: Metadata from gh run list
            log_content: Log content from gh run view

        Returns:
            CIFailure object
        """
        failure_type = self.classify_failure(log_content)
        error_message, file_path, line_number = self.extract_error_details(log_content)

        # Extract PR number if available
        pr_number = None
        pr_match = re.search(r"#(\d+)", run_metadata.get("name", ""))
        if pr_match:
            pr_number = int(pr_match.group(1))

        return CIFailure(
            run_id=str(run_metadata.get("databaseId", "")),
            workflow_name=run_metadata.get("name", "unknown"),
            job_name="unknown",  # Would need additional API call
            failure_type=failure_type,
            error_message=error_message,
            error_line=line_number,
            file_path=file_path,
            full_log=log_content[:10000],  # Truncate for storage
            timestamp=datetime.now(timezone.utc),
            branch=run_metadata.get("headBranch", "unknown"),
            commit_sha=run_metadata.get("headSha", "")[:8],
            pr_number=pr_number,
            actor=run_metadata.get("actor", {}).get("login", "unknown"),
        )

    def ingest_failure(self, failure: CIFailure) -> dict[str, Any]:
        """
        Ingest a CI failure into RAG and ML systems.

        Args:
            failure: The CIFailure to ingest

        Returns:
            Dict with ingestion results
        """
        results = {
            "run_id": failure.run_id,
            "ingested_to_rag": False,
            "ingested_to_ml": False,
            "lesson_id": None,
            "pattern_id": None,
        }

        # Save to local history
        self._save_failure(failure)

        # Ingest to RAG
        if self.rag:
            try:
                severity = "critical" if failure.failure_type in [
                    FailureType.SYNTAX_ERROR,
                    FailureType.IMPORT_ERROR,
                ] else "high"

                lesson_id = self.rag.add_lesson(
                    category=f"ci_{failure.failure_type.value}",
                    title=f"CI Failure: {failure.failure_type.value} in {failure.workflow_name}",
                    description=f"Run {failure.run_id} failed on branch {failure.branch}. "
                                f"Error: {failure.error_message}",
                    root_cause=f"File: {failure.file_path or 'unknown'}, "
                               f"Line: {failure.error_line or 'unknown'}",
                    prevention=self._get_prevention_for_type(failure.failure_type),
                    severity=severity,
                    tags=[
                        "ci-failure",
                        failure.failure_type.value,
                        failure.branch,
                    ],
                )
                results["ingested_to_rag"] = True
                results["lesson_id"] = lesson_id
                logger.info(f"Ingested failure to RAG: {lesson_id}")

            except Exception as e:
                logger.error(f"Failed to ingest to RAG: {e}")

        # Ingest to ML pattern detector
        if self.ml_detector:
            try:
                files_involved = [failure.file_path] if failure.file_path else []

                # Map FailureType to FailureCategory
                category_map = {
                    FailureType.SYNTAX_ERROR: self.FailureCategory.SYNTAX_ERROR,
                    FailureType.IMPORT_ERROR: self.FailureCategory.IMPORT_ERROR,
                    FailureType.TEST_FAILURE: self.FailureCategory.RUNTIME_ERROR,
                    FailureType.LINT_ERROR: self.FailureCategory.SYNTAX_ERROR,
                    FailureType.BUILD_ERROR: self.FailureCategory.DEPLOYMENT,
                    FailureType.TIMEOUT: self.FailureCategory.CI_CD,
                    FailureType.DEPENDENCY_ERROR: self.FailureCategory.CONFIGURATION,
                    FailureType.PERMISSION_ERROR: self.FailureCategory.SECURITY,
                    FailureType.UNKNOWN: self.FailureCategory.RUNTIME_ERROR,
                }

                pattern_id = self.ml_detector.learn_from_failure(
                    error_message=failure.error_message,
                    files_involved=files_involved,
                    category=category_map.get(
                        failure.failure_type,
                        self.FailureCategory.RUNTIME_ERROR,
                    ),
                    prevention=self._get_prevention_for_type(failure.failure_type),
                    risk_level=self.RiskLevel.CRITICAL
                    if failure.failure_type
                    in [FailureType.SYNTAX_ERROR, FailureType.IMPORT_ERROR]
                    else self.RiskLevel.HIGH,
                )
                results["ingested_to_ml"] = True
                results["pattern_id"] = pattern_id
                logger.info(f"Ingested failure to ML detector: {pattern_id}")

            except Exception as e:
                logger.error(f"Failed to ingest to ML detector: {e}")

        return results

    def _get_prevention_for_type(self, failure_type: FailureType) -> str:
        """Get prevention recommendation for a failure type."""
        preventions = {
            FailureType.SYNTAX_ERROR: "Run `python3 -m py_compile` on all changed files before commit",
            FailureType.IMPORT_ERROR: "Verify all critical imports work after changes: `python3 -c 'from module import ...'`",
            FailureType.TEST_FAILURE: "Run `pytest tests/` locally before pushing",
            FailureType.LINT_ERROR: "Run `ruff check src/` and fix all errors before commit",
            FailureType.BUILD_ERROR: "Verify dependencies with `pip install -r requirements.txt` locally",
            FailureType.TIMEOUT: "Check for infinite loops or long-running operations",
            FailureType.DEPENDENCY_ERROR: "Pin dependency versions in requirements.txt",
            FailureType.PERMISSION_ERROR: "Verify file permissions and access rights",
            FailureType.UNKNOWN: "Review logs carefully and add specific prevention",
        }
        return preventions.get(failure_type, "Review and fix the underlying issue")

    def process_recent_failures(
        self,
        limit: int = 10,
        skip_processed: bool = True,
    ) -> list[dict]:
        """
        Process recent CI failures.

        Args:
            limit: Maximum failures to process
            skip_processed: Skip already processed failures

        Returns:
            List of ingestion results
        """
        results = []

        # Get processed run IDs
        processed_ids = set()
        if skip_processed:
            processed_ids = {f["run_id"] for f in self.failures_history}

        # Fetch failed runs
        failed_runs = self.fetch_failed_runs(limit=limit)
        logger.info(f"Found {len(failed_runs)} failed runs")

        for run in failed_runs:
            run_id = str(run.get("databaseId", ""))

            if run_id in processed_ids:
                logger.debug(f"Skipping already processed run: {run_id}")
                continue

            # Fetch logs
            log_content = self.fetch_run_logs(run_id)
            if not log_content:
                logger.warning(f"No logs available for run: {run_id}")
                continue

            # Parse and ingest
            failure = self.parse_failure(run, log_content)
            result = self.ingest_failure(failure)
            results.append(result)

            logger.info(
                f"Processed failure {run_id}: "
                f"RAG={result['ingested_to_rag']}, ML={result['ingested_to_ml']}"
            )

        return results

    def get_failure_stats(self) -> dict[str, Any]:
        """Get statistics about ingested failures."""
        if not self.failures_history:
            return {"total": 0, "by_type": {}, "by_branch": {}}

        type_counts: dict[str, int] = {}
        branch_counts: dict[str, int] = {}

        for failure in self.failures_history:
            failure_type = failure.get("failure_type", "unknown")
            branch = failure.get("branch", "unknown")

            type_counts[failure_type] = type_counts.get(failure_type, 0) + 1
            branch_counts[branch] = branch_counts.get(branch, 0) + 1

        return {
            "total": len(self.failures_history),
            "by_type": type_counts,
            "by_branch": branch_counts,
            "most_common_type": max(type_counts, key=type_counts.get) if type_counts else None,
            "most_failing_branch": max(branch_counts, key=branch_counts.get) if branch_counts else None,
        }


def ingest_current_failure(
    error_message: str,
    file_path: Optional[str] = None,
    failure_type: str = "unknown",
) -> dict[str, Any]:
    """
    Quick function to ingest a failure happening right now.

    Args:
        error_message: The error message
        file_path: File that caused the error
        failure_type: Type of failure

    Returns:
        Ingestion result
    """
    pipeline = CIFailureIngestionPipeline()

    failure = CIFailure(
        run_id=f"local-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        workflow_name="local",
        job_name="local",
        failure_type=FailureType(failure_type) if failure_type in [e.value for e in FailureType] else FailureType.UNKNOWN,
        error_message=error_message,
        error_line=None,
        file_path=file_path,
        full_log=error_message,
        timestamp=datetime.now(timezone.utc),
        branch="local",
        commit_sha="local",
        pr_number=None,
        actor="local",
    )

    return pipeline.ingest_failure(failure)


if __name__ == "__main__":
    """Process recent CI failures."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("CI FAILURE INGESTION PIPELINE")
    print("=" * 80)

    pipeline = CIFailureIngestionPipeline()

    # Process recent failures
    print("\nProcessing recent CI failures...")
    results = pipeline.process_recent_failures(limit=5)

    print(f"\nProcessed {len(results)} failures:")
    for r in results:
        print(f"  Run {r['run_id']}: RAG={r['ingested_to_rag']}, ML={r['ingested_to_ml']}")

    # Show stats
    stats = pipeline.get_failure_stats()
    print(f"\nFailure Statistics:")
    print(f"  Total: {stats['total']}")
    print(f"  By Type: {stats['by_type']}")
    print(f"  Most Common: {stats['most_common_type']}")
