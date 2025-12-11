#!/usr/bin/env python3
"""
Auto-Generate Regression Tests from Lessons Learned

This script reads the RAG lessons learned directory and automatically
generates pytest test cases to prevent known failures from recurring.

The Learning Loop:
1. Incident occurs
2. Document in rag_knowledge/lessons_learned/ll_XXX_*.md
3. Run this script to generate regression test
4. Test prevents recurrence

Usage:
    python scripts/generate_regression_tests.py
    python scripts/generate_regression_tests.py --lesson ll_009

Author: Trading System CTO
Created: 2025-12-11
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class LessonParser:
    """Parse lessons learned markdown files."""

    def __init__(self, lessons_dir: Path | None = None):
        self.lessons_dir = lessons_dir or Path(__file__).parent.parent / "rag_knowledge" / "lessons_learned"

    def parse_lesson(self, file_path: Path) -> dict[str, Any]:
        """Parse a single lesson learned file."""
        content = file_path.read_text()

        lesson = {
            "file": file_path.name,
            "id": None,
            "title": None,
            "date": None,
            "severity": None,
            "category": None,
            "impact": None,
            "root_cause": None,
            "fix": None,
            "prevention_rules": [],
            "verification_tests": [],
            "tags": [],
        }

        # Extract ID
        id_match = re.search(r"\*\*ID\*\*:\s*(\w+)", content)
        if id_match:
            lesson["id"] = id_match.group(1)

        # Extract title from first header
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if title_match:
            lesson["title"] = title_match.group(1).strip()

        # Extract date
        date_match = re.search(r"\*\*Date\*\*:\s*([^\n]+)", content)
        if date_match:
            lesson["date"] = date_match.group(1).strip()

        # Extract severity
        severity_match = re.search(r"\*\*Severity\*\*:\s*(\w+)", content)
        if severity_match:
            lesson["severity"] = severity_match.group(1).upper()

        # Extract category
        category_match = re.search(r"\*\*Category\*\*:\s*([^\n]+)", content)
        if category_match:
            lesson["category"] = category_match.group(1).strip()

        # Extract impact
        impact_match = re.search(r"\*\*Impact\*\*:\s*([^\n]+)", content)
        if impact_match:
            lesson["impact"] = impact_match.group(1).strip()

        # Extract verification tests (code blocks after "Verification Tests")
        tests_section = re.search(
            r"##\s*Verification Tests\s*\n(.*?)(?=\n##|\Z)",
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if tests_section:
            code_blocks = re.findall(
                r"```python\s*(.*?)\s*```",
                tests_section.group(1),
                re.DOTALL,
            )
            lesson["verification_tests"] = code_blocks

        # Extract tags
        tags_match = re.search(r"#(\w+(?:\s+#\w+)*)", content)
        if tags_match:
            lesson["tags"] = [t.strip() for t in re.findall(r"#(\w+)", content)]

        return lesson

    def parse_all_lessons(self) -> list[dict[str, Any]]:
        """Parse all lessons learned files."""
        lessons = []

        if not self.lessons_dir.exists():
            return lessons

        for md_file in sorted(self.lessons_dir.glob("ll_*.md")):
            try:
                lesson = self.parse_lesson(md_file)
                lessons.append(lesson)
            except Exception as e:
                print(f"Error parsing {md_file}: {e}")

        return lessons


class TestGenerator:
    """Generate pytest test code from lessons learned."""

    TEST_TEMPLATE = '''
def test_{test_id}_{test_name}():
    """
    REGRESSION TEST: {lesson_id} - {title}

    Severity: {severity}
    Category: {category}
    Impact: {impact}

    Auto-generated from: {source_file}
    """
{test_code}
'''

    def __init__(self, output_path: Path | None = None):
        self.output_path = output_path or Path(__file__).parent.parent / "tests" / "test_auto_regression.py"

    def generate_test_from_lesson(self, lesson: dict[str, Any]) -> str:
        """Generate test code from a parsed lesson."""
        tests = []

        lesson_id = lesson.get("id", "unknown")
        title = lesson.get("title", "Unknown Lesson")

        # If lesson has verification tests, use those
        if lesson.get("verification_tests"):
            for i, test_code in enumerate(lesson["verification_tests"]):
                # Clean up the test code
                test_code = self._clean_test_code(test_code)

                test_name = f"{lesson_id.lower()}_verification_{i + 1}"
                tests.append(
                    self.TEST_TEMPLATE.format(
                        test_id=lesson_id.lower(),
                        test_name=f"verification_{i + 1}",
                        lesson_id=lesson_id,
                        title=title,
                        severity=lesson.get("severity", "UNKNOWN"),
                        category=lesson.get("category", "Unknown"),
                        impact=lesson.get("impact", "Unknown"),
                        source_file=lesson.get("file", "unknown.md"),
                        test_code=self._indent_code(test_code, 4),
                    )
                )
        else:
            # Generate a basic existence test
            test_code = f'''
    # Basic check that lesson {lesson_id} is documented
    lessons_dir = Path(__file__).parent.parent / "rag_knowledge" / "lessons_learned"
    lesson_files = list(lessons_dir.glob("{lesson_id}*.md"))
    assert len(lesson_files) >= 1, "Lesson {lesson_id} documentation missing"
'''
            tests.append(
                self.TEST_TEMPLATE.format(
                    test_id=lesson_id.lower(),
                    test_name="documentation_exists",
                    lesson_id=lesson_id,
                    title=title,
                    severity=lesson.get("severity", "UNKNOWN"),
                    category=lesson.get("category", "Unknown"),
                    impact=lesson.get("impact", "Unknown"),
                    source_file=lesson.get("file", "unknown.md"),
                    test_code=test_code,
                )
            )

        return "\n".join(tests)

    def _clean_test_code(self, code: str) -> str:
        """Clean up test code extracted from markdown."""
        # Remove function definition if present (we'll wrap it)
        lines = code.strip().split("\n")

        # Check if it's a function definition
        if lines[0].strip().startswith("def test_"):
            # Extract body only
            body_lines = []
            in_body = False
            for line in lines:
                if in_body:
                    # Remove one level of indentation
                    if line.startswith("    "):
                        body_lines.append(line[4:])
                    else:
                        body_lines.append(line)
                elif line.strip().endswith(":"):
                    in_body = True
            return "\n".join(body_lines)

        return code

    def _indent_code(self, code: str, spaces: int) -> str:
        """Indent code by specified spaces."""
        indent = " " * spaces
        lines = code.split("\n")
        return "\n".join(indent + line if line.strip() else line for line in lines)

    def generate_test_file(self, lessons: list[dict[str, Any]]) -> str:
        """Generate complete test file from all lessons."""
        header = f'''#!/usr/bin/env python3
"""
Auto-Generated Regression Tests from Lessons Learned

DO NOT EDIT MANUALLY - This file is auto-generated by:
    python scripts/generate_regression_tests.py

Generated: {datetime.now().isoformat()}
Total Lessons: {len(lessons)}

These tests ensure past mistakes don't recur.
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

'''
        test_code = header

        # Group by severity
        critical = [l for l in lessons if l.get("severity") == "CRITICAL"]
        high = [l for l in lessons if l.get("severity") == "HIGH"]
        other = [l for l in lessons if l.get("severity") not in ["CRITICAL", "HIGH"]]

        if critical:
            test_code += "\n# ============ CRITICAL SEVERITY ============\n"
            for lesson in critical:
                test_code += self.generate_test_from_lesson(lesson)

        if high:
            test_code += "\n# ============ HIGH SEVERITY ============\n"
            for lesson in high:
                test_code += self.generate_test_from_lesson(lesson)

        if other:
            test_code += "\n# ============ OTHER LESSONS ============\n"
            for lesson in other:
                test_code += self.generate_test_from_lesson(lesson)

        return test_code

    def write_test_file(self, lessons: list[dict[str, Any]]):
        """Write generated tests to file."""
        test_code = self.generate_test_file(lessons)

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(test_code)

        print(f"Generated {len(lessons)} regression tests to {self.output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate regression tests from lessons learned")
    parser.add_argument(
        "--lesson",
        type=str,
        help="Generate test for specific lesson ID (e.g., ll_009)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tests/test_auto_regression.py",
        help="Output file path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print tests without writing file",
    )
    args = parser.parse_args()

    # Parse lessons
    lesson_parser = LessonParser()
    lessons = lesson_parser.parse_all_lessons()

    if not lessons:
        print("No lessons learned found in rag_knowledge/lessons_learned/")
        return 1

    # Filter if specific lesson requested
    if args.lesson:
        lessons = [l for l in lessons if l.get("id", "").lower() == args.lesson.lower()]
        if not lessons:
            print(f"Lesson {args.lesson} not found")
            return 1

    # Generate tests
    generator = TestGenerator(output_path=Path(args.output))

    if args.dry_run:
        print(generator.generate_test_file(lessons))
    else:
        generator.write_test_file(lessons)

    # Summary
    print("\n" + "=" * 60)
    print("REGRESSION TEST GENERATION SUMMARY")
    print("=" * 60)
    print(f"Total Lessons Processed: {len(lessons)}")
    print(f"Critical:               {len([l for l in lessons if l.get('severity') == 'CRITICAL'])}")
    print(f"High:                   {len([l for l in lessons if l.get('severity') == 'HIGH'])}")
    print(f"Output:                 {args.output}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
