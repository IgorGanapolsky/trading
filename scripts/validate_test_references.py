#!/usr/bin/env python3
"""
Validate Test File References in Workflows

This script checks that all test files referenced in GitHub Actions workflows
actually exist. This prevents CI failures due to missing test files.

Usage:
    python3 scripts/validate_test_references.py
    python3 scripts/validate_test_references.py --fix  # Remove invalid references

Created: 2026-01-13
Reason: ll_148 and ll_153 - Missing test files blocked trading for 74+ days
"""

import re
import sys
from pathlib import Path


def find_test_references():
    """Find all test file references in workflow files."""
    workflows_dir = Path(".github/workflows")
    references = []

    if not workflows_dir.exists():
        print("⚠️ .github/workflows directory not found")
        return references

    # Pattern to match test file references
    pattern = re.compile(r"tests/test_[\w]+\.py")

    for workflow_file in workflows_dir.glob("*.yml"):
        content = workflow_file.read_text()
        matches = pattern.findall(content)

        for match in matches:
            references.append({"file": match, "workflow": workflow_file.name})

    return references


def validate_references(references):
    """Check if referenced test files exist."""
    missing = []
    valid = []

    for ref in references:
        test_file = Path(ref["file"])
        if test_file.exists():
            valid.append(ref)
        else:
            missing.append(ref)

    return valid, missing


def main():
    print("=" * 60)
    print("VALIDATE TEST FILE REFERENCES")
    print("=" * 60)
    print()

    references = find_test_references()
    print(f"Found {len(references)} test file references in workflows")
    print()

    if not references:
        print("✅ No test file references found")
        return 0

    valid, missing = validate_references(references)

    if valid:
        print(f"✅ {len(valid)} valid references:")
        for ref in valid:
            print(f"   {ref['file']} (in {ref['workflow']})")
        print()

    if missing:
        print(f"❌ {len(missing)} MISSING test files:")
        for ref in missing:
            print(f"   {ref['file']} (referenced in {ref['workflow']})")
        print()
        print("🚨 These missing files will cause CI to FAIL!")
        print("🚨 This is what blocked trading for 74+ days (ll_148)")
        print()
        print("Fix by either:")
        print("  1. Creating the missing test files")
        print("  2. Removing references from workflows")
        return 1

    print("✅ All test file references are valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
