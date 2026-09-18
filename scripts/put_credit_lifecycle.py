#!/usr/bin/env python3
"""CLI: Senpi 5-phase FORMAT receipt from local put-credit ledgers (no Hyperliquid)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ops.put_credit_lifecycle import build_lifecycle, readiness_ok  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Discover/Decide/Execute/Manage/Exit receipt (Senpi FORMAT, local ledgers)"
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON (default)")
    parser.add_argument(
        "--check-ready",
        action="store_true",
        help="Exit 0 if paper-only spy_put_credit confluence is cited",
    )
    parser.add_argument("--project-root", default=".", help="Repo root")
    args = parser.parse_args(argv)

    receipt = build_lifecycle(Path(args.project_root))
    if args.check_ready:
        ok = readiness_ok(receipt)
        print(json.dumps({"ok": ok, "ticker": receipt["ticker"]}, ensure_ascii=True))
        return 0 if ok else 2
    print(json.dumps(receipt, ensure_ascii=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
