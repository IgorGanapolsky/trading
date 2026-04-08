#!/usr/bin/env python3
"""Enforce minimum test coverage on critical trading files.

Reads coverage.xml and checks that specific high-risk files meet
per-file coverage thresholds. Fails CI if any file is below its minimum.

Usage: python scripts/ci/check_critical_coverage.py [coverage.xml]
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

COVERAGE_XML = sys.argv[1] if len(sys.argv) > 1 else "coverage.xml"

# Critical files and their minimum coverage thresholds.
# These are files where bugs cause real money loss (credit estimation,
# order execution, safety gates, ML pipeline).
# Start conservative, ratchet up as tests are added.
CRITICAL_FILES = {
    "scripts/ic_simple.py": 30,
    "src/ml/reward.py": 70,
    "src/ml/trade_confidence.py": 60,
    "src/rag/vector_store.py": 40,
    "src/markets/option_chain.py": 30,
    "src/safety/mandatory_trade_gate.py": 15,
}


def main():
    xml_path = Path(COVERAGE_XML)
    if not xml_path.exists():
        print(f"WARNING: {COVERAGE_XML} not found — skipping critical coverage check")
        sys.exit(0)

    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Build filename -> line_rate map from coverage.xml
    file_coverage = {}
    for package in root.findall(".//package"):
        for cls in package.findall(".//class"):
            filename = cls.get("filename", "")
            line_rate = float(cls.get("line-rate", 0)) * 100
            file_coverage[filename] = line_rate

    failures = []
    passes = []

    for filepath, minimum in CRITICAL_FILES.items():
        actual = file_coverage.get(filepath)
        if actual is None:
            # Try matching with different path formats
            for key in file_coverage:
                if key.endswith(filepath) or filepath.endswith(key):
                    actual = file_coverage[key]
                    break

        if actual is None:
            failures.append(f"  {filepath}: NOT FOUND in coverage report (min {minimum}%)")
        elif actual < minimum:
            failures.append(f"  {filepath}: {actual:.0f}% < {minimum}% minimum")
        else:
            passes.append(f"  {filepath}: {actual:.0f}% >= {minimum}% ✓")

    print("=" * 60)
    print("CRITICAL FILE COVERAGE CHECK")
    print("=" * 60)

    if passes:
        print("\nPassing:")
        for p in passes:
            print(p)

    if failures:
        print("\nFAILING:")
        for f in failures:
            print(f)
        print(f"\n❌ {len(failures)} critical file(s) below coverage minimum")
        sys.exit(1)
    else:
        print(f"\n✅ All {len(passes)} critical files meet coverage minimums")
        sys.exit(0)


if __name__ == "__main__":
    main()
