#!/usr/bin/env python3
"""Enhanced Python syntax validation.

Prevents ll_024 and ll_025 type failures by catching:
1. Python syntax errors (nested f-strings, invalid operators, etc.)
2. Common patterns that break in production
3. Module-level syntax issues

This runs before merge to catch issues that standard linters miss.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path


def find_python_files() -> list[Path]:
    """Find all Python files in src/ and scripts/."""
    files = []
    for directory in ["src", "scripts"]:
        if Path(directory).exists():
            files.extend(Path(directory).rglob("*.py"))
    return sorted(files)


def validate_python_syntax(file_path: Path) -> tuple[bool, str]:
    """Validate Python syntax by compiling the file."""
    try:
        # First try: compile using py_compile
        result = subprocess.run(
            ["python3", "-m", "py_compile", str(file_path)],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return False, f"Syntax error:\n{result.stderr}"

        # Second try: parse with AST to catch additional issues
        content = file_path.read_text(encoding="utf-8")
        ast.parse(content, filename=str(file_path))

        return True, ""

    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def check_nested_fstrings(file_path: Path) -> tuple[bool, list[str]]:
    """Check for problematic nested f-string patterns.

    Only catches truly problematic patterns:
    - f-string inside another f-string's braces with quotes
    - Patterns that caused ll_024 syntax error

    Ignores valid patterns:
    - String concatenation: f"..." + f"..."
    - Ternary operators: f"..." if x else f"..."
    """
    content = file_path.read_text(encoding="utf-8")
    issues = []

    # STRICT pattern: f"{ ... f"..." or f'{ ... f'...'
    # This is the actual problematic pattern from ll_024
    # Must have: opening f-string quote, then {, then f-string inside
    # Exclude false positives: string concat (+), ternary (if/else)

    lines = content.split("\n")
    for i, line in enumerate(lines, start=1):
        # Skip lines with string concatenation or ternary operators
        if " + " in line or " if " in line or " else " in line:
            continue

        # Check for f"{...f"..." or f'{...f'...'  pattern
        # This regex is very specific to catch nested f-strings in braces
        if re.search(r'f["\'][^"\']*\{[^}]*\bf["\'][^}]*\}', line):
            snippet = line.strip()[:60]
            issues.append(f"Line {i}: Problematic nested f-string: {snippet}...")

    return len(issues) == 0, issues


def check_common_pitfalls(file_path: Path) -> tuple[bool, list[str]]:
    """Check for common Python pitfalls that break in production."""
    content = file_path.read_text(encoding="utf-8")
    issues = []

    # Check 1: Bare except: that might hide syntax errors
    if re.search(r"^\s*except\s*:\s*$", content, re.MULTILINE):
        issues.append("Bare 'except:' found (prefer 'except Exception:')")

    # Check 2: eval() usage (security risk)
    if "eval(" in content and "# safe eval" not in content.lower():
        matches = re.finditer(r"eval\(", content)
        for match in matches:
            line_num = content[: match.start()].count("\n") + 1
            issues.append(f"Line {line_num}: eval() usage detected (security risk)")

    return len(issues) == 0, issues


def main():
    """Run all syntax validation checks."""
    print("=" * 70)
    print("ENHANCED SYNTAX VALIDATION")
    print("=" * 70)
    print()

    files = find_python_files()
    print(f"Found {len(files)} Python files to validate\n")

    total_errors = 0
    files_with_errors = []

    # Phase 1: Python syntax validation
    print("Phase 1: Python Syntax Validation")
    print("-" * 70)
    syntax_errors = 0

    for file_path in files:
        valid, error_msg = validate_python_syntax(file_path)
        if not valid:
            print(f"❌ {file_path}")
            print(f"   {error_msg}")
            syntax_errors += 1
            files_with_errors.append(str(file_path))

    if syntax_errors == 0:
        print(f"✅ All {len(files)} files have valid Python syntax")
    else:
        print(f"\n❌ Found {syntax_errors} files with syntax errors")
        total_errors += syntax_errors

    print()

    # Phase 2: Nested f-string detection (warnings only for Python 3.11 compatibility)
    print("Phase 2: Nested F-String Detection (Warnings)")
    print("-" * 70)
    fstring_warnings = 0

    for file_path in files:
        valid, issues = check_nested_fstrings(file_path)
        if not valid:
            fstring_warnings += len(issues)
            for issue in issues:
                print(f"⚠️  {file_path}: {issue}")

    if fstring_warnings == 0:
        print(f"✅ No nested f-string patterns detected in {len(files)} files")
    else:
        print(f"\n⚠️  Found {fstring_warnings} nested f-strings (non-blocking)")

    print()

    # Phase 3: Common pitfalls (warnings only, don't fail)
    print("Phase 3: Common Pitfalls (Warnings Only)")
    print("-" * 70)
    pitfall_warnings = 0

    for file_path in files:
        valid, issues = check_common_pitfalls(file_path)
        if not valid:
            pitfall_warnings += len(issues)
            for issue in issues:
                print(f"⚠️  {file_path}: {issue}")

    if pitfall_warnings == 0:
        print("✅ No common pitfalls detected")
    else:
        print(f"\n⚠️  Found {pitfall_warnings} potential issues (non-blocking)")

    print()
    print("=" * 70)

    if total_errors > 0:
        print(f"❌ VALIDATION FAILED: {total_errors} critical issues found")
        print()
        print("Files with errors:")
        for file_path in files_with_errors:
            print(f"  - {file_path}")
        print()
        print("Fix these issues before committing.")
        print("=" * 70)
        sys.exit(1)
    else:
        print("✅ ALL VALIDATION CHECKS PASSED")
        print(f"   {len(files)} files validated successfully")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    main()
