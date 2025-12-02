#!/usr/bin/env python3
"""
Manual Dashboard Update Script

This script manually updates the GitHub Wiki dashboard when the automated
workflow isn't running. Use this as a workaround until the workflow is fixed.

Usage:
    python3 scripts/manual_dashboard_update.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def main():
    print("=" * 70)
    print("📊 MANUAL DASHBOARD UPDATE")
    print("=" * 70)

    # Step 1: Generate dashboard
    print("\n1️⃣  Generating dashboard...")
    try:
        from scripts.generate_progress_dashboard import main as generate_dashboard

        generate_dashboard()
        print("   ✅ Dashboard generated successfully")
    except Exception as e:
        print(f"   ❌ Error generating dashboard: {e}")
        return 1

    # Step 2: Check if wiki directory exists
    wiki_dir = Path("wiki")
    dashboard_file = wiki_dir / "Progress-Dashboard.md"

    if not dashboard_file.exists():
        print(f"   ❌ Dashboard file not found: {dashboard_file}")
        return 1

    print(f"   ✅ Dashboard file: {dashboard_file}")

    # Step 3: Show instructions for manual wiki update
    print("\n2️⃣  Manual Wiki Update Instructions")
    print("   Since we can't push to wiki from here (needs GitHub token),")
    print("   you have two options:")
    print()
    print("   OPTION A: Use GitHub Actions (Recommended)")
    print("   1. Go to: https://github.com/IgorGanapolsky/trading/actions")
    print("   2. Click 'Daily Trading Execution'")
    print("   3. Click 'Run workflow' → 'Run workflow'")
    print("   4. This will update the wiki automatically")
    print()
    print("   OPTION B: Manual Wiki Edit")
    print("   1. Go to: https://github.com/IgorGanapolsky/trading/wiki")
    print("   2. Click 'Progress Dashboard'")
    print("   3. Click 'Edit'")
    print("   4. Copy content from: wiki/Progress-Dashboard.md")
    print("   5. Paste and save")
    print()

    # Step 4: Show the generated content preview
    print("3️⃣  Generated Dashboard Preview:")
    print("   " + "=" * 66)
    with open(dashboard_file) as f:
        lines = f.readlines()
        for _i, line in enumerate(lines[:30]):  # First 30 lines
            print(f"   {line.rstrip()}")
        if len(lines) > 30:
            print(f"   ... ({len(lines) - 30} more lines)")
    print("   " + "=" * 66)

    print("\n✅ Dashboard file ready for upload!")
    print(f"   Location: {dashboard_file.absolute()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
