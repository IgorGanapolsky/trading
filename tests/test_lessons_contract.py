"""
Lessons Learned Contract Tests.

These tests make "lessons learned" actionable:
- required metadata fields are present (so RAG/ML can index reliably)
- CRITICAL lessons must include prevention + verification sections (so incidents become regression tests)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.verification.lessons_contract import iter_lessons, normalize_severity


PROJECT_ROOT = Path(__file__).parent.parent
LESSONS_DIR = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"


def test_lessons_directory_exists() -> None:
    assert LESSONS_DIR.exists(), "rag_knowledge/lessons_learned must exist"


def test_all_lessons_have_required_metadata_fields() -> None:
    """
    Required fields are needed for consistent RAG/vector store ingestion and ML training exports.
    """
    missing: list[str] = []
    for lesson in iter_lessons(LESSONS_DIR):
        # Enforce strictly only for CRITICAL lessons, since those must always be regression-ready.
        # Non-critical lessons may be legacy/essay-style; we don't want CI blocked by missing metadata.
        sev = normalize_severity(lesson.severity)
        if sev != "CRITICAL":
            continue

        if not lesson.inferred_id():
            missing.append(f"{lesson.path.name}: CRITICAL lesson missing **ID** (or ll_### filename)")
        if not lesson.date:
            missing.append(f"{lesson.path.name}: CRITICAL lesson missing **Date**")
        if not lesson.severity:
            missing.append(f"{lesson.path.name}: CRITICAL lesson missing **Severity**")
        if not lesson.category:
            missing.append(f"{lesson.path.name}: CRITICAL lesson missing **Category**")
        if not lesson.has_impact_any_form():
            missing.append(
                f"{lesson.path.name}: CRITICAL lesson missing **Impact** (or a '## Impact' section)"
            )

    assert not missing, "Lessons contract violations:\n" + "\n".join(missing)


def test_critical_lessons_have_prevention_and_verification_sections() -> None:
    violations: list[str] = []
    for lesson in iter_lessons(LESSONS_DIR):
        sev = normalize_severity(lesson.severity)
        if sev != "CRITICAL":
            continue

        if not (lesson.has_any_section_prefix("Prevention") or lesson.has_section("Prevention Rules")):
            violations.append(f"{lesson.path.name}: CRITICAL lesson missing a '## Prevention...' section")

        if not (
            lesson.has_any_section_prefix("Verification Test")
            or lesson.has_any_section_prefix("Verification Tests")
        ):
            violations.append(
                f"{lesson.path.name}: CRITICAL lesson missing a '## Verification Test(s)' section"
            )

    assert not violations, "CRITICAL lessons must be regression-ready:\n" + "\n".join(violations)


def test_lesson_references_point_to_real_repo_paths_when_present() -> None:
    """
    If a lesson cites files (backticked repo paths), those paths must exist.
    This prevents lessons from rotting and becoming non-actionable.
    """
    missing: list[str] = []
    for lesson in iter_lessons(LESSONS_DIR):
        # Only enforce on CRITICAL lessons to keep signal high.
        sev = normalize_severity(lesson.severity)
        if sev != "CRITICAL":
            continue

        for rel in lesson.referenced_repo_paths():
            # Only validate file-like references (not directories).
            if not any(rel.endswith(ext) for ext in (".py", ".yml", ".yaml", ".json", ".md", ".txt")):
                continue
            if not (PROJECT_ROOT / rel).exists():
                missing.append(f"{lesson.path.name}: references missing path `{rel}`")

    assert not missing, "Broken lesson references:\n" + "\n".join(missing)

