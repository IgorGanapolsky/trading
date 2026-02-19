#!/usr/bin/env python3
"""Build precomputed context-engine bundles index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.memory.context_bundle_engine import ContextBundleEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Build context-engine index from local sources.")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--top-per-source", type=int, default=500, help="Max docs per source")
    args = parser.parse_args()

    engine = ContextBundleEngine(project_root=Path(args.project_root).resolve())
    result = engine.build_index(top_per_source=max(1, args.top_per_source))
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

