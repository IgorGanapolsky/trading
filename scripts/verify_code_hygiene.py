#!/usr/bin/env python3
"""
Code Hygiene Verification Script

Automated detection of:
- Temporary/proof files that shouldn't be committed
- Unused Python imports (via ruff)
- Stale archive folders
- Debug files and test logs
- __pycache__ directories

Usage:
    python3 scripts/verify_code_hygiene.py [--fix]

Exit codes:
    0: All checks passed
    1: Issues found (fix required)

RAG Keywords: code-hygiene, dead-code, unused-imports, cleanup
Lesson Learned: ll_042_code_hygiene_automated_prevention_dec15.md
"""

import subprocess
import sys
from pathlib import Path

# Patterns for files that should NOT exist in repo
FORBIDDEN_PATTERNS = [
    ".ai_proof*.md",
    ".ai_*_FINAL.md",
    ".*_summary*.md",
    "*proof_of_fix*.md",
    "debug_*.py",
    "*.bak",
    "*.orig",
    "*.swp",
    "*~",
]

# Directories that should NOT exist
FORBIDDEN_DIRS = [
    "docs/_archive",
    "test_logs",
    "__pycache__",
]

# Ruff rules for unused code detection
RUFF_RULES = ["F401", "F841"]  # Unused imports, unused variables


def check_forbidden_files(root: Path) -> list[str]:
    """Check for files matching forbidden patterns."""
    issues = []
    for pattern in FORBIDDEN_PATTERNS:
        matches = list(root.glob(f"**/{pattern}"))
        # Exclude .git directory
        matches = [m for m in matches if ".git" not in str(m)]
        for match in matches:
            issues.append(f"Forbidden file found: {match}")
    return issues


def check_forbidden_dirs(root: Path) -> list[str]:
    """Check for directories that shouldn't exist."""
    issues = []
    for dirname in FORBIDDEN_DIRS:
        if dirname == "__pycache__":
            # Check for any __pycache__ in tree
            matches = list(root.glob("**/__pycache__"))
            matches = [m for m in matches if ".git" not in str(m)]
            for match in matches:
                issues.append(f"__pycache__ found (should be in .gitignore): {match}")
        else:
            dir_path = root / dirname
            if dir_path.exists():
                issues.append(f"Forbidden directory found: {dir_path}")
    return issues


def check_unused_imports(root: Path, fix: bool = False) -> list[str]:
    """Run ruff to check for unused imports."""
    issues = []
    rules = ",".join(RUFF_RULES)

    cmd = ["ruff", "check", "--select", rules]
    if fix:
        cmd.append("--fix")
    cmd.extend(["src/", "scripts/"])

    try:
        result = subprocess.run(
            cmd,
            cwd=root,
            capture_output=True,
            text=True
        )
        if result.returncode != 0 and result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line and not line.startswith("Found"):
                    issues.append(f"Ruff: {line}")
    except FileNotFoundError:
        issues.append("Ruff not installed - run: pip install ruff")

    return issues


def check_large_files(root: Path, max_size_kb: int = 500) -> list[str]:
    """Check for uncommonly large files that might be data/logs."""
    issues = []
    for path in root.glob("**/*"):
        if path.is_file() and ".git" not in str(path):
            size_kb = path.stat().st_size / 1024
            if size_kb > max_size_kb:
                # Allow certain expected large files
                if not any(ext in path.suffix for ext in [".png", ".jpg", ".json", ".csv"]):
                    issues.append(f"Large file ({size_kb:.0f}KB): {path}")
    return issues


def main():
    fix_mode = "--fix" in sys.argv
    root = Path(__file__).parent.parent

    print("=" * 60)
    print("CODE HYGIENE VERIFICATION")
    print("=" * 60)

    all_issues = []

    # Check 1: Forbidden files
    print("\n[1/4] Checking for temporary/proof files...")
    issues = check_forbidden_files(root)
    all_issues.extend(issues)
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  PASS")

    # Check 2: Forbidden directories
    print("\n[2/4] Checking for forbidden directories...")
    issues = check_forbidden_dirs(root)
    all_issues.extend(issues)
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  PASS")

    # Check 3: Unused imports
    print(f"\n[3/4] Checking for unused imports (ruff F401, F841){'... fixing' if fix_mode else ''}...")
    issues = check_unused_imports(root, fix=fix_mode)
    if not fix_mode:
        all_issues.extend(issues)
    if issues and not fix_mode:
        print(f"  Found {len(issues)} issues (run with --fix to auto-fix)")
        for issue in issues[:10]:
            print(f"  {issue}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more")
    else:
        print("  PASS" if not fix_mode else "  FIXED")

    # Check 4: Large files
    print("\n[4/4] Checking for unusually large files...")
    issues = check_large_files(root)
    all_issues.extend(issues)
    if issues:
        for issue in issues:
            print(f"  {issue}")
    else:
        print("  PASS")

    # Summary
    print("\n" + "=" * 60)
    if all_issues:
        print(f"HYGIENE CHECK FAILED: {len(all_issues)} issue(s) found")
        print("\nTo fix:")
        print("  1. Delete forbidden files/dirs manually")
        print("  2. Run: python3 scripts/verify_code_hygiene.py --fix")
        print("  3. Add __pycache__ to .gitignore")
        sys.exit(1)
    else:
        print("HYGIENE CHECK PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
