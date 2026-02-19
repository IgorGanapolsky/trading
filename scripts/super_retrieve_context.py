#!/usr/bin/env python3
"""Query the precomputed context-engine index via one super-retrieve call."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.memory.context_bundle_engine import ContextBundleEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Super retrieve context bundles for a query.")
    parser.add_argument("query", help="Natural-language query")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--top-k", type=int, default=8, help="Top results to return")
    parser.add_argument("--min-score", type=float, default=0.01, help="Minimum normalized score")
    args = parser.parse_args()

    engine = ContextBundleEngine(project_root=Path(args.project_root).resolve())
    result = engine.super_retrieve(
        args.query,
        top_k=max(1, args.top_k),
        min_score=max(0.0, min(1.0, args.min_score)),
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

