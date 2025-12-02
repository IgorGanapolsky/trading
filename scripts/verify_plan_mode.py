#!/usr/bin/env python3
"""
Plan Mode guardrail.

This script enforces Claude Code Plan Mode requirements before any commit lands.
It is intentionally strict so that research (Plan Mode) and execution (editor mode)
remain separated per https://www.claudelog.com/mechanics/plan-mode/.
"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

REQUIRED_SECTIONS = [
    "## Metadata",
    "## Clarifying Questions",
    "## Execution Plan",
    "## Approval",
    "## Exit Checklist",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that plan.md satisfies Claude Code Plan Mode requirements."
    )
    parser.add_argument(
        "--plan-file",
        default="plan.md",
        help="Path to the Plan Mode artifact (default: plan.md in repo root).",
    )
    parser.add_argument(
        "--max-age-minutes",
        type=int,
        default=180,
        help="Maximum allowed age (minutes) since plan file modification.",
    )
    parser.add_argument(
        "--require-status",
        default="APPROVED",
        help="Expected Status value in Metadata (default: APPROVED).",
    )
    return parser.parse_args()


def fail(message: str) -> NoReturn:
    hint = textwrap.dedent(
        """
        See docs/PLAN_MODE_ENFORCEMENT.md for the required workflow:
          1. Enter Plan Mode (Shift+Tab twice) before making changes.
          2. Capture clarifying questions + execution plan in plan.md.
          3. Mark Status: APPROVED only after reviewing the plan.
          4. Exit Plan Mode and execute tasks.
        """
    ).strip()
    print("❌ Plan Mode enforcement failed.")
    print(message.strip())
    print("")
    print(hint)
    sys.exit(1)


def extract_section(content: str, heading: str) -> str:
    pattern = rf"{re.escape(heading)}\s*(.*?)(?=\n## |\Z)"
    match = re.search(pattern, content, flags=re.DOTALL)
    if not match:
        fail(f"Missing required section '{heading}'.")
    return match.group(1).strip()


def assert_metadata(metadata: str, required_status: str) -> None:
    status_match = re.search(r"Status:\s*([A-Za-z_]+)", metadata)
    if not status_match:
        fail("Metadata block must include 'Status: <value>'.")
    status = status_match.group(1).upper()
    if status != required_status.upper():
        fail(f"Plan status is '{status}', but '{required_status}' is required before committing.")

    if "Approved at:" not in metadata:
        fail("Metadata must include 'Approved at:' timestamp to document the approval.")


def assert_clarifying_questions(section: str) -> None:
    if not section:
        fail("Clarifying Questions section is empty.")
    # Expect at least one markdown table row or bullet list entry.
    has_table_row = bool(re.search(r"^\|\s*\d+", section, flags=re.MULTILINE))
    has_bullet = bool(re.search(r"^- ", section, flags=re.MULTILINE))
    if not (has_table_row or has_bullet):
        fail("Clarifying Questions must list at least one question/resolution row.")


def assert_execution_plan(section: str) -> None:
    if not re.search(r"^\d+\.\s", section, flags=re.MULTILINE):
        fail("Execution Plan must enumerate ordered steps (e.g., '1. ...').")


def assert_approval(section: str) -> None:
    if not re.search(r"\[x\].*Approved", section, flags=re.IGNORECASE):
        fail("Approval section must include a checked item noting CTO approval.")


def assert_exit_checklist(section: str) -> None:
    if "- [" not in section:
        fail("Exit Checklist must include at least one checkbox item.")


def assert_freshness(plan_path: Path, max_age_minutes: int) -> None:
    mtime = datetime.fromtimestamp(plan_path.stat().st_mtime, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    age_minutes = (now - mtime).total_seconds() / 60.0
    if age_minutes > max_age_minutes:
        fail(
            f"Plan file is {age_minutes:.1f} minutes old (> {max_age_minutes} minute limit). "
            "Regenerate or refresh the plan in Plan Mode."
        )


def main() -> None:
    args = parse_args()
    plan_path = Path(args.plan_file)

    if not plan_path.exists():
        fail(f"Plan file not found at '{plan_path}'. Run Plan Mode to generate plan.md.")

    content = plan_path.read_text(encoding="utf-8").strip()

    for heading in REQUIRED_SECTIONS:
        if heading not in content:
            fail(f"Missing heading '{heading}'.")

    metadata = extract_section(content, "## Metadata")
    clarifying = extract_section(content, "## Clarifying Questions")
    execution = extract_section(content, "## Execution Plan")
    approval = extract_section(content, "## Approval")
    exit_checklist = extract_section(content, "## Exit Checklist")

    assert_metadata(metadata, args.require_status)
    assert_clarifying_questions(clarifying)
    assert_execution_plan(execution)
    assert_approval(approval)
    assert_exit_checklist(exit_checklist)
    assert_freshness(plan_path, args.max_age_minutes)

    print(
        f"✅ Plan Mode ready: {plan_path} exists, is approved, "
        f"and updated within {args.max_age_minutes} minutes."
    )


if __name__ == "__main__":
    main()
