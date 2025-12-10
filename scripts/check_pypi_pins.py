#!/usr/bin/env python3
"""Verify that pinned versions in requirements.txt exist on PyPI."""

import json
import re
import sys
import urllib.request
from pathlib import Path


def main() -> int:
    missing = []
    pattern = re.compile(r"^\s*([A-Za-z0-9_.-]+)==([\w\.\-]+)\s*$")

    for raw in Path("requirements.txt").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = pattern.match(line)
        if not m:
            continue  # only check strict pins
        pkg, ver = m.group(1), m.group(2)
        url = f"https://pypi.org/pypi/{pkg}/json"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.load(resp)
        except Exception as exc:  # pragma: no cover - network issues
            missing.append(f"{pkg}=={ver} (lookup failed: {exc})")
            continue

        if ver not in data.get("releases", {}):
            missing.append(f"{pkg}=={ver} (version not published)")

    if missing:
        print("❌ Missing pins:")
        for item in missing:
            print(f" - {item}")
        return 1

    print("✅ All pinned versions found on PyPI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
