#!/usr/bin/env python3
"""CLI: Decisions UO FORMAT process record for spy_put_credit (no Decisions product)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ops.put_credit_govern import build_process_record, readiness_ok  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Process record: state/control/next for paper put-credit (instructions are not control)"
    )
    parser.add_argument("--check-ready", action="store_true")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args(argv)
    record = build_process_record(Path(args.project_root))
    if args.check_ready:
        ok = readiness_ok(record)
        print(json.dumps({"ok": ok, "stuck": record["observability"]["stuck"]}, ensure_ascii=True))
        return 0 if ok else 2
    print(json.dumps(record, ensure_ascii=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
