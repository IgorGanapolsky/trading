#!/usr/bin/env python3
"""
Placeholder Code Detector (LL-034 Prevention)

Pre-commit hook to detect placeholder/stub code patterns that indicate
unfinished features. Prevents accumulation of dead code.

Usage:
    python scripts/detect_placeholders.py [files...]

Exit codes:
    0 - No placeholders found
    1 - Placeholders detected (blocks commit)
"""

import re
import sys
from pathlib import Path

# Patterns that indicate UNFINISHED FEATURE code (the LL-034 antipattern)
# NOTE: Simple placeholder values like "price = 100.0  # Placeholder" are OK
# We only catch patterns that indicate DEAD FEATURES that should be removed
PLACEHOLDER_PATTERNS = [
    # Functions that return "not implemented" - indicates dead feature
    (r'return\s+["\'].*not\s+(?:yet\s+)?implemented.*["\']', "Returns 'not implemented' string"),
    # Error messages about not implemented - dead feature
    (r'error=["\'].*not\s+(?:yet\s+)?implemented', "Not implemented error message"),
    # Disabled feature flags with "not implemented" comment
    (r'enable_\w+\s*[=:]\s*False\s*,?\s*#\s*[Nn]ot\s+(?:yet\s+)?implemented', "Disabled feature flag (not implemented)"),
    # Module-level "not yet implemented" in docstrings (indicates stub module)
    (r'^"""[^"]*[Nn]ot\s+(?:yet\s+)?implemented[^"]*"""$', "Module stub docstring"),
]

# Files/directories to skip
SKIP_PATTERNS = [
    r'\.git/',
    r'__pycache__/',
    r'\.pyc$',
    r'node_modules/',
    r'\.env',
    r'venv/',
    r'\.venv/',
    r'migrations/',
    # Allow in test files (mocking is OK)
    r'test_.*\.py$',
    r'conftest\.py$',
    # Allow in this script itself
    r'detect_placeholders\.py$',
    # Allow in lessons learned (documenting the pattern)
    r'lessons_learned/',
]


def should_skip(filepath: str) -> bool:
    """Check if file should be skipped."""
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, filepath):
            return True
    return False


def scan_file(filepath: Path) -> list[tuple[int, str, str]]:
    """
    Scan a file for placeholder patterns.

    Returns:
        List of (line_number, line_content, pattern_description)
    """
    findings = []

    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        lines = content.split('\n')

        for line_num, line in enumerate(lines, 1):
            for pattern, description in PLACEHOLDER_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append((line_num, line.strip(), description))
                    break  # One finding per line is enough

    except Exception as e:
        print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)

    return findings


def main(files: list[str] = None) -> int:
    """
    Main entry point.

    Args:
        files: List of files to check. If None, checks all Python files.

    Returns:
        Exit code (0 = clean, 1 = findings)
    """
    if files:
        file_list = [Path(f) for f in files if f.endswith('.py')]
    else:
        # Scan entire src/ directory
        file_list = list(Path('src').rglob('*.py'))

    all_findings = []

    for filepath in file_list:
        if should_skip(str(filepath)):
            continue

        findings = scan_file(filepath)
        if findings:
            all_findings.append((filepath, findings))

    if all_findings:
        print("\n🚨 PLACEHOLDER CODE DETECTED (LL-034 Violation)\n")
        print("The following files contain placeholder/stub patterns:")
        print("=" * 70)

        for filepath, findings in all_findings:
            print(f"\n📄 {filepath}")
            for line_num, line, description in findings:
                print(f"   Line {line_num}: {description}")
                print(f"   > {line[:80]}{'...' if len(line) > 80 else ''}")

        print("\n" + "=" * 70)
        print("❌ Commit blocked. Remove placeholder code before committing.")
        print("   See: rag_knowledge/lessons_learned/ll_034_placeholder_code_antipattern.md")
        print()

        return 1

    return 0


if __name__ == "__main__":
    # Accept file arguments from pre-commit
    files = sys.argv[1:] if len(sys.argv) > 1 else None
    sys.exit(main(files))
