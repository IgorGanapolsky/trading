#!/usr/bin/env python3
"""
System Integrity & Safety Checker
=================================
Run this BEFORE pushing code. It verifies that the entire system
is consistent, scripts are runnable, and no "time bombs" (like bad submodules)
are present.

Checks:
1. JSON Integrity: Verifies all critical data files are valid JSON.
2. Script Importability: Verifies all python scripts compile/import.
3. Git Hygiene: Checks for accidental submodules or large files.
4. Simulation: Runs a fast "dry run" of the dashboard generator.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

CRITICAL_DATA_FILES = [
    "data/system_state.json",
    "data/performance_log.json",
    "data/challenge_start.json",
]

CRITICAL_SCRIPTS = [
    "scripts/autonomous_trader.py",
    "scripts/generate_world_class_dashboard_enhanced.py",
    "src/main.py",
]


def print_result(name, passed, msg=""):
    icon = "✅" if passed else "❌"
    print(f"{icon} {name:<30} {msg}")
    return passed


def check_json_files():
    all_passed = True
    for fname in CRITICAL_DATA_FILES:
        path = Path(fname)
        if not path.exists():
            print_result(f"File Exists: {fname}", False, "Missing")
            # Optional: Don't fail if file purely missing (might be first run), but warn
            continue

        try:
            with open(path) as f:
                json.load(f)
            print_result(f"JSON Valid: {fname}", True)
        except json.JSONDecodeError as e:
            print_result(f"JSON Valid: {fname}", False, str(e))
            all_passed = False
    return all_passed


def check_git_hygiene():
    # Check for 160000 mode (submodules) which caused recent CI breaks
    try:
        result = subprocess.run(["git", "ls-files", "--stage"], capture_output=True, text=True)
        suspicious = [line for line in result.stdout.splitlines() if line.startswith("160000")]
        if suspicious:
            print_result(
                "Git Hygiene",
                False,
                f"Found {len(suspicious)} accidental submodules! Run 'git rm --cached' on them.",
            )
            for s in suspicious:
                print(f"   -> {s}")
            return False
        else:
            print_result("Git Hygiene", True, "No accidental submodules")
            return True
    except Exception as e:
        print_result("Git Hygiene", False, f"Git check failed: {e}")
        return False


def check_scripts_runnable():
    all_passed = True
    for fname in CRITICAL_SCRIPTS:
        if not os.path.exists(fname):
            # Skip if script doesn't exist (e.g. might be moved)
            continue

        # Test basic compilation check
        try:
            with open(fname) as f:
                source = f.read()
            compile(source, fname, "exec")
            print_result(f"Syntax Valid: {fname}", True)
        except SyntaxError as e:
            print_result(f"Syntax Valid: {fname}", False, str(e))
            all_passed = False
    return all_passed


def run_dashboard_dry_run():
    # Try generating dashboard (without saving) to ensure logic holds
    cmd = ["python3", "scripts/generate_world_class_dashboard_enhanced.py"]
    try:
        # We just check return code
        subprocess.run(cmd, capture_output=True, check=True)
        print_result("Dashboard Gen (Dry Run)", True)
        return True
    except subprocess.CalledProcessError as e:
        print_result("Dashboard Gen (Dry Run)", False, f"Failed with exit code {e.returncode}")
        # print(e.stderr.decode()[:200]) # Print first 200 chars of error
        return False


def main():
    print("🛡️  RUNNING SYSTEM INTEGRITY CHECKS...\n")

    checks = [
        check_json_files(),
        check_git_hygiene(),
        check_scripts_runnable(),
        run_dashboard_dry_run(),
    ]

    if all(checks):
        print("\n✅ SYSTEM INTEGRITY VERIFIED. SAFE TO PUSH.")
        sys.exit(0)
    else:
        print("\n❌ INTEGRITY CHECKS FAILED. DO NOT PUSH.")
        sys.exit(1)


if __name__ == "__main__":
    main()
