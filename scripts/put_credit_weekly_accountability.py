#!/usr/bin/env python3
"""Weekly put-credit accountability packet (EYL-style ritual, ledger-only).

Usage:
  .venv/bin/python scripts/put_credit_weekly_accountability.py
  .venv/bin/python scripts/put_credit_weekly_accountability.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analytics.put_credit_milestones import (  # noqa: E402
    build_weekly_accountability_packet,
    render_weekly_markdown,
)

from scripts.put_credit_cohort_scorecard import build_scorecard  # noqa: E402

DEFAULT_JSON = ROOT / "data" / "audit" / "put_credit_weekly_accountability_latest.json"
DEFAULT_MD = ROOT / "data" / "audit" / "put_credit_weekly_accountability_latest.md"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    p.add_argument("--out-json", type=Path, default=DEFAULT_JSON)
    p.add_argument("--out-md", type=Path, default=DEFAULT_MD)
    args = p.parse_args()

    card = build_scorecard()
    packet = build_weekly_accountability_packet(card)
    md = render_weekly_markdown(packet)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(packet, indent=2, default=str) + "\n", encoding="utf-8")
    args.out_md.write_text(md + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(packet, indent=2, default=str))
    else:
        print(md)
        print(f"\njson_out={args.out_json}")
        print(f"md_out={args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
