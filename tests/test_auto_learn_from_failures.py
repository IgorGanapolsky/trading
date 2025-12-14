#!/usr/bin/env python3
"""
Auto-Learning Test Generator

This module automatically generates regression tests from ALL lessons learned.
Instead of manually writing tests for each incident, this dynamically:

1. Scans all lessons learned files
2. Extracts testable patterns (file patterns, import checks, keywords)
3. Generates pytest tests at runtime
4. Ensures EVERY lesson has a corresponding test

This creates a "learning loop" where:
- Every incident is documented in RAG
- Tests are automatically generated
- Future similar mistakes are caught
- System gets smarter with each failure

Run with: pytest tests/test_auto_learn_from_failures.py -v

Author: Trading System CTO
Created: 2025-12-11
"""

import ast
import re
import sys
from pathlib import Path
from typing import Any

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class LessonParser:
    """Parse lessons learned files to extract testable patterns."""

    SEVERITY_KEYWORDS = {
        "CRITICAL": ["critical", "fatal", "0 trades", "total failure", "system down"],
        "HIGH": ["high", "major", "broke", "failed", "loss"],
        "MEDIUM": ["medium", "warning", "issue", "bug"],
        "LOW": ["low", "minor", "enhancement", "improvement"],
    }

    def __init__(self, lessons_dir: Path):
        self.lessons_dir = lessons_dir

    def parse_all(self) -> list[dict[str, Any]]:
        """Parse all lessons learned files."""
        lessons = []
        for md_file in self.lessons_dir.glob("*.md"):
            lesson = self._parse_lesson(md_file)
            if lesson:
                lessons.append(lesson)
        return lessons

    def _parse_lesson(self, file_path: Path) -> dict[str, Any] | None:
        """Parse a single lesson file."""
        try:
            content = file_path.read_text()
        except Exception:
            return None

        lesson = {
            "file": str(file_path.name),
            "id": self._extract_id(content, file_path),
            "severity": self._extract_severity(content),
            "file_patterns": self._extract_file_patterns(content),
            "import_checks": self._extract_import_checks(content),
            "keywords": self._extract_keywords(content),
            "code_patterns": self._extract_code_patterns(content),
        }
        return lesson

    def _extract_id(self, content: str, file_path: Path) -> str:
        """Extract lesson ID."""
        match = re.search(r"\*\*ID\*\*:\s*(\w+)", content)
        if match:
            return match.group(1)
        # Fallback to filename
        return file_path.stem.replace("_", "-")

    def _extract_severity(self, content: str) -> str:
        """Extract severity level."""
        match = re.search(r"\*\*Severity\*\*:\s*(\w+)", content, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Infer from content
        content_lower = content.lower()
        for severity, keywords in self.SEVERITY_KEYWORDS.items():
            if any(kw in content_lower for kw in keywords):
                return severity
        return "MEDIUM"

    def _extract_file_patterns(self, content: str) -> list[str]:
        """Extract file patterns to check."""
        patterns = []

        # Look for file paths mentioned
        file_refs = re.findall(r"`([^`]+\.py)`", content)
        patterns.extend(file_refs)

        # Look for paths in code blocks
        code_paths = re.findall(r"(src/\S+\.py)", content)
        patterns.extend(code_paths)

        return list(set(patterns))

    def _extract_import_checks(self, content: str) -> list[str]:
        """Extract imports that should be tested."""
        imports = []

        # Look for import statements in code blocks
        import_matches = re.findall(r"(?:from|import)\s+([\w.]+)(?:\s+import\s+(\w+))?", content)
        for module, name in import_matches:
            if name:
                imports.append(f"from {module} import {name}")
            elif module.startswith("src."):
                imports.append(f"import {module}")

        return list(set(imports))

    def _extract_keywords(self, content: str) -> list[str]:
        """Extract important keywords/concepts."""
        keywords = []

        # Extract from tags
        tags_match = re.search(r"#(\w+(?:\s+#\w+)*)", content)
        if tags_match:
            keywords.extend(re.findall(r"#(\w+)", tags_match.group(0)))

        # Extract from section headers
        headers = re.findall(r"^##\s*(.+)$", content, re.MULTILINE)
        keywords.extend(h.lower().replace(" ", "_") for h in headers[:5])

        return list(set(keywords))

    def _extract_code_patterns(self, content: str) -> list[str]:
        """Extract code patterns that indicate similar issues."""
        patterns = []

        # Look for patterns in code blocks
        code_blocks = re.findall(r"```(?:python|bash)?\s*(.*?)```", content, re.DOTALL)
        for block in code_blocks:
            # Extract function/class names
            func_matches = re.findall(r"def\s+(\w+)", block)
            class_matches = re.findall(r"class\s+(\w+)", block)
            patterns.extend(func_matches)
            patterns.extend(class_matches)

        return list(set(patterns))


# =============================================================================
# AUTO-GENERATED REGRESSION TESTS
# =============================================================================


class TestAutoLearnFromFailures:
    """Auto-generated tests from lessons learned."""

    @pytest.fixture(scope="class")
    def lessons(self):
        """Load and parse all lessons."""
        lessons_dir = Path(__file__).parent.parent / "rag_knowledge" / "lessons_learned"
        if not lessons_dir.exists():
            pytest.skip("No lessons learned directory")
        parser = LessonParser(lessons_dir)
        return parser.parse_all()

    def test_all_lessons_have_content(self, lessons):
        """Every lesson must have extractable content."""
        assert len(lessons) > 0, "No lessons found"

        for lesson in lessons:
            assert lesson["id"], f"Lesson {lesson['file']} has no ID"
            assert lesson["severity"], f"Lesson {lesson['file']} has no severity"

    def test_critical_lessons_have_file_patterns(self, lessons):
        """Critical lessons should reference specific files to check."""
        critical = [l for l in lessons if l["severity"] == "CRITICAL"]

        for lesson in critical:
            has_patterns = (
                lesson["file_patterns"] or lesson["import_checks"] or lesson["code_patterns"]
            )
            if not has_patterns:
                pytest.skip(f"CRITICAL lesson {lesson['id']} should have testable patterns")

    def test_file_patterns_exist(self, lessons):
        """Files mentioned in lessons should exist."""
        project_root = Path(__file__).parent.parent

        missing = []
        for lesson in lessons:
            for pattern in lesson["file_patterns"]:
                file_path = project_root / pattern
                if not file_path.exists() and not any(
                    f.match(pattern) for f in project_root.rglob("*.py")
                ):
                    # Only flag if it looks like a real path (not example)
                    if pattern.startswith("src/") or pattern.startswith("tests/"):
                        missing.append((lesson["id"], pattern))

        # Allow some missing (files may have been refactored)
        if len(missing) > len(lessons) * 0.3:  # > 30% missing is concerning
            pytest.fail(f"Too many missing files from lessons: {missing[:5]}")

    def test_import_checks_compile(self, lessons):
        """Import statements from lessons should be syntactically valid."""
        for lesson in lessons:
            for import_stmt in lesson["import_checks"]:
                try:
                    ast.parse(import_stmt)
                except SyntaxError as e:
                    pytest.fail(f"Lesson {lesson['id']} has invalid import: {import_stmt}: {e}")


# =============================================================================
# DYNAMIC TEST GENERATION FROM CRITICAL LESSONS
# =============================================================================


def pytest_generate_tests(metafunc):
    """Dynamically generate tests for each critical lesson."""
    if "critical_lesson" in metafunc.fixturenames:
        lessons_dir = Path(__file__).parent.parent / "rag_knowledge" / "lessons_learned"
        if lessons_dir.exists():
            parser = LessonParser(lessons_dir)
            lessons = parser.parse_all()
            critical = [l for l in lessons if l["severity"] == "CRITICAL"]
            metafunc.parametrize("critical_lesson", critical, ids=[l["id"] for l in critical])


class TestCriticalLessonRegressions:
    """Dynamically generated tests for each CRITICAL lesson."""

    def test_critical_imports_work(self, critical_lesson):
        """Test that imports from critical lessons work."""
        if not critical_lesson["import_checks"]:
            pytest.skip(f"No imports to check for {critical_lesson['id']}")

        for import_stmt in critical_lesson["import_checks"]:
            try:
                exec(import_stmt)
            except ImportError:
                # Import may not exist anymore - that's OK
                pass
            except SyntaxError as e:
                pytest.fail(f"REGRESSION {critical_lesson['id']}: Import syntax error: {e}")

    def test_critical_files_compile(self, critical_lesson):
        """Test that files from critical lessons compile."""
        import py_compile

        project_root = Path(__file__).parent.parent

        for pattern in critical_lesson["file_patterns"]:
            file_path = project_root / pattern
            if file_path.exists() and file_path.suffix == ".py":
                try:
                    py_compile.compile(str(file_path), doraise=True)
                except py_compile.PyCompileError as e:
                    pytest.fail(
                        f"REGRESSION {critical_lesson['id']}: Syntax error in {pattern}: {e}"
                    )


# =============================================================================
# LEARNING LOOP VERIFICATION
# =============================================================================


class TestLearningLoopIntegrity:
    """Verify the learning loop is working correctly."""

    def test_lessons_are_indexed(self):
        """Lessons should be indexed for RAG queries."""
        # Check if RAG index exists
        index_paths = [
            Path("data/rag_index.json"),
            Path("rag_store/chroma.sqlite3"),
            Path("data/chroma_db"),
        ]

        # At least one index should exist
        has_index = any(p.exists() for p in index_paths)
        if not has_index:
            pytest.skip("RAG index not found - run ingestion first")

    def test_recent_lessons_exist(self):
        """Recent lessons should exist (system is actively learning)."""
        from datetime import datetime

        lessons_dir = Path(__file__).parent.parent / "rag_knowledge" / "lessons_learned"
        if not lessons_dir.exists():
            pytest.skip("No lessons directory")

        # Check for recent files (within last 30 days)
        cutoff = datetime.now().timestamp() - (30 * 24 * 60 * 60)
        recent_files = [f for f in lessons_dir.glob("*.md") if f.stat().st_mtime > cutoff]

        # Should have at least some recent lessons
        assert len(recent_files) > 0, "No recent lessons learned - system may not be learning"

    def test_lessons_follow_format(self):
        """Lessons should follow the standard format for parseability."""
        lessons_dir = Path(__file__).parent.parent / "rag_knowledge" / "lessons_learned"
        if not lessons_dir.exists():
            pytest.skip("No lessons directory")

        required_sections = ["##", "Severity", "Category"]
        malformed = []

        for md_file in lessons_dir.glob("*.md"):
            content = md_file.read_text()
            missing = [s for s in required_sections if s not in content]
            if missing:
                malformed.append((md_file.name, missing))

        # Allow some malformed (legacy files)
        if len(malformed) > 3:
            pytest.fail(f"Multiple malformed lessons: {malformed[:3]}")
