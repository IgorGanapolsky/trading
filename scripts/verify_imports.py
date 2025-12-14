#!/usr/bin/env python3
"""
Verify critical imports resolve (CI-safe).

This script exists because import-time failures have repeatedly blocked trading
(see lessons learned ll_009 / ll_011). It provides a single command that can be
used in CI and locally.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    try:
        from src.verification.pre_merge_verifier import PreMergeVerifier
    except Exception as e:
        print(f"❌ Could not import PreMergeVerifier: {e}", file=sys.stderr)
        return 2

    verifier = PreMergeVerifier(project_root=project_root)
    result = verifier.check_critical_imports()
    if result.get("passed"):
        print("✅ Critical imports verified (syntax/import-time errors not detected)")
        return 0

    print("❌ Critical imports check failed:", file=sys.stderr)
    for err in result.get("errors", []):
        print(f"  - {err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

