#!/usr/bin/env python3
"""
Documentation Freshness Checker - Enforces LL_044 Documentation Hygiene Mandate.

This script checks that critical documentation files are not stale.
Run before commits to ensure docs stay current.

Usage:
    python3 scripts/check_doc_freshness.py
    python3 scripts/check_doc_freshness.py --strict  # Fails on any staleness
    python3 scripts/check_doc_freshness.py --fix     # Shows what needs updating

Created: Dec 15, 2025
Lesson: LL_044 - Documentation Hygiene Mandate
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Critical files and their max staleness (in days)
CRITICAL_FILES = {
    "README.md": 7,
    "dashboard.md": 3,
    "claude-progress.txt": 3,
    "config/portfolio_allocation.yaml": 7,
    "data/system_state.json": 1,
}

# Files that should be checked but not fail the build
WARNING_FILES = {
    "AGENTS.md": 14,
    "docs/PLAN.md": 7,
}


def get_file_last_modified(filepath: Path) -> datetime | None:
    """Get last modified time from git or filesystem."""
    try:
        # Try git first (more accurate for commits)
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ci", str(filepath)],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Parse git date format: 2025-12-15 10:30:00 -0500
            date_str = result.stdout.strip()
            # Remove timezone for simpler parsing
            date_str = date_str.rsplit(" ", 1)[0]
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    # Fallback to filesystem
    full_path = PROJECT_ROOT / filepath
    if full_path.exists():
        return datetime.fromtimestamp(full_path.stat().st_mtime)

    return None


def check_freshness(strict: bool = False, fix: bool = False) -> int:
    """Check all critical files for freshness."""
    now = datetime.now()
    issues = []
    warnings = []

    print("=" * 70)
    print("📋 DOCUMENTATION FRESHNESS CHECK")
    print(f"   Date: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # Check critical files
    print("🔴 CRITICAL FILES (must be current):")
    print("-" * 70)
    
    for filepath, max_days in CRITICAL_FILES.items():
        full_path = PROJECT_ROOT / filepath
        
        if not full_path.exists():
            issues.append(f"MISSING: {filepath}")
            print(f"  ❌ {filepath:<40} MISSING!")
            continue
        
        last_modified = get_file_last_modified(Path(filepath))
        
        if last_modified is None:
            warnings.append(f"UNKNOWN DATE: {filepath}")
            print(f"  ⚠️  {filepath:<40} Unknown last modified date")
            continue
        
        age_days = (now - last_modified).days
        status = "✅" if age_days <= max_days else "❌"
        
        if age_days > max_days:
            issues.append(f"STALE ({age_days}d): {filepath} (max: {max_days}d)")
        
        print(f"  {status} {filepath:<40} {age_days}d old (max: {max_days}d)")

    print()
    
    # Check warning files
    print("🟡 WARNING FILES (should be current):")
    print("-" * 70)
    
    for filepath, max_days in WARNING_FILES.items():
        full_path = PROJECT_ROOT / filepath
        
        if not full_path.exists():
            print(f"  ⚠️  {filepath:<40} Not found (optional)")
            continue
        
        last_modified = get_file_last_modified(Path(filepath))
        
        if last_modified is None:
            print(f"  ⚠️  {filepath:<40} Unknown date")
            continue
        
        age_days = (now - last_modified).days
        status = "✅" if age_days <= max_days else "⚠️"
        
        if age_days > max_days:
            warnings.append(f"STALE ({age_days}d): {filepath}")
        
        print(f"  {status} {filepath:<40} {age_days}d old (max: {max_days}d)")

    print()
    print("=" * 70)
    
    # Summary
    if issues:
        print("❌ CRITICAL ISSUES FOUND:")
        for issue in issues:
            print(f"   • {issue}")
        print()
    
    if warnings:
        print("⚠️  WARNINGS:")
        for warning in warnings:
            print(f"   • {warning}")
        print()
    
    if fix and (issues or warnings):
        print("📝 TO FIX:")
        print("   1. Update stale files with current information")
        print("   2. Commit changes: git add -A && git commit -m 'docs: update stale documentation'")
        print("   3. Re-run this check to verify")
        print()
    
    # Exit code
    if issues:
        print("❌ FRESHNESS CHECK FAILED")
        print("   Critical documentation is stale. Update before committing.")
        return 1
    elif warnings and strict:
        print("⚠️  FRESHNESS CHECK FAILED (strict mode)")
        return 1
    else:
        print("✅ FRESHNESS CHECK PASSED")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Check documentation freshness")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too")
    parser.add_argument("--fix", action="store_true", help="Show fix instructions")
    args = parser.parse_args()
    
    return check_freshness(strict=args.strict, fix=args.fix)


if __name__ == "__main__":
    sys.exit(main())
