#!/usr/bin/env python3
"""CLI for deterministic trading context gists."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ops.context_gist import gist_context  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--goal", required=True)
    p.add_argument("--in-scope", required=True)
    p.add_argument("--out-scope", required=True)
    p.add_argument("--ac", action="append", default=[], help="Repeatable AC (≥2 required)")
    p.add_argument("--constraint", action="append", default=[])
    p.add_argument("--extra", action="append", default=[])
    p.add_argument("--token-budget", type=int, default=1200)
    p.add_argument("--compact", action="store_true")
    args = p.parse_args(argv)
    gist = gist_context(
        goal=args.goal,
        in_scope=args.in_scope,
        out_scope=args.out_scope,
        acceptance_criteria=args.ac,
        constraints=args.constraint,
        extras=args.extra,
        token_budget=args.token_budget,
    )
    if args.compact:
        print(gist.compact())
    else:
        print(json.dumps(gist.to_dict(), indent=2, sort_keys=True))
    return 0 if gist.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
