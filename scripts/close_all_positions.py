#!/usr/bin/env python3
"""Backward-compatible wrapper for emergency-all position closing."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    target = Path(__file__).with_name("close_positions.py")
    cmd = [sys.executable, str(target), "--mode", "emergency-all", *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
