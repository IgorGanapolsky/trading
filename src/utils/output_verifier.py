"""
Output Verification Utility - Catches silent pipeline failures.

Created: Dec 28, 2025
Purpose: Prevent the "Dec 22 incident" where workflows ran successfully
         but produced zero output with no alerts.

Usage:
    from src.utils.output_verifier import verify_output, OutputVerificationError

    # In your pipeline/script:
    result = do_some_work()

    # Verify output was actually produced
    verify_output(
        condition=len(result) > 0,
        output_description="processed records",
        expected_min=1,
        actual_count=len(result),
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class OutputVerificationError(Exception):
    """Raised when output verification fails (silent failure detected)."""

    pass


@dataclass
class VerificationResult:
    """Result of output verification."""

    verified: bool
    description: str
    expected_min: int
    actual_count: int
    message: str
    timestamp: str


def verify_output(
    condition: bool,
    output_description: str,
    expected_min: int = 1,
    actual_count: int = 0,
    raise_on_failure: bool = True,
) -> VerificationResult:
    """
    Verify that a pipeline/script produced expected output.

    Args:
        condition: The verification condition (e.g., len(results) > 0)
        output_description: Human-readable description of what was expected
        expected_min: Minimum expected count
        actual_count: Actual count produced
        raise_on_failure: If True, raise OutputVerificationError on failure

    Returns:
        VerificationResult with details

    Raises:
        OutputVerificationError if condition is False and raise_on_failure is True
    """
    timestamp = datetime.now().isoformat()

    if condition:
        result = VerificationResult(
            verified=True,
            description=output_description,
            expected_min=expected_min,
            actual_count=actual_count,
            message=f"✅ Output verified: {actual_count} {output_description}",
            timestamp=timestamp,
        )
        logger.info(result.message)
        return result

    # Verification failed
    result = VerificationResult(
        verified=False,
        description=output_description,
        expected_min=expected_min,
        actual_count=actual_count,
        message=f"⛔ OUTPUT VERIFICATION FAILED: Expected at least {expected_min} {output_description}, got {actual_count}",
        timestamp=timestamp,
    )
    logger.error(result.message)
    logger.error("This is a SILENT FAILURE - the process completed but produced no output.")

    if raise_on_failure:
        raise OutputVerificationError(result.message)

    return result


def verify_files_exist(
    directory: Path,
    pattern: str = "*",
    expected_min: int = 1,
    description: str | None = None,
) -> VerificationResult:
    """
    Verify that files matching a pattern exist in a directory.

    Args:
        directory: Directory to check
        pattern: Glob pattern for files
        expected_min: Minimum expected file count
        description: Optional description for error messages

    Returns:
        VerificationResult with details
    """
    if not directory.exists():
        return VerificationResult(
            verified=False,
            description=description or f"files in {directory}",
            expected_min=expected_min,
            actual_count=0,
            message=f"⛔ OUTPUT VERIFICATION FAILED: Directory {directory} does not exist",
            timestamp=datetime.now().isoformat(),
        )

    files = list(directory.glob(pattern))
    file_count = len(files)

    return verify_output(
        condition=file_count >= expected_min,
        output_description=description or f"files matching {pattern} in {directory}",
        expected_min=expected_min,
        actual_count=file_count,
        raise_on_failure=False,  # Return result, let caller decide
    )
