#!/usr/bin/env python3
"""Deprecated name. Official SuperMemory ops live in scripts/supermemory_ops.py.

The previous untracked lookalike used the wrong SDK class and a memories-create
RPC. That is not the official product. This shim forwards to the official CLI.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_OPS = Path(__file__).resolve().parent / "supermemory_ops.py"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        args = ["status"]
    spec = importlib.util.spec_from_file_location("supermemory_ops", _OPS)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_OPS}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print("integrate_supermemory.py is a shim; use scripts/supermemory_ops.py", file=sys.stderr)
    return int(module.main(args))


if __name__ == "__main__":
    raise SystemExit(main())
