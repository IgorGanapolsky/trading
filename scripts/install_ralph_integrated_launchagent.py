#!/usr/bin/env python3
"""Render LaunchAgent plist from template into ~/Library/LaunchAgents and load it."""

from __future__ import annotations

import os
import subprocess  # nosec B404
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scripts" / "launchd" / "com.igor.trading.ralph-gsd-integrated.plist.example"
LABEL = "com.igor.trading.ralph-gsd-integrated"


def main() -> int:
    home = Path.home()
    trading = ROOT
    text = TEMPLATE.read_text()
    text = text.replace("__HOME__", str(home)).replace("__TRADING_ROOT__", str(trading))
    dest = home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    dest.parent.mkdir(parents=True, exist_ok=True)
    (home / "Library" / "Logs" / "trading").mkdir(parents=True, exist_ok=True)
    dest.write_text(text)
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], check=False)  # nosec B603 B607
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(dest)], check=False)  # nosec B603 B607
    subprocess.run(["launchctl", "enable", f"gui/{uid}/{LABEL}"], check=False)  # nosec B603 B607
    print(json_dumps({"ok": True, "dest": str(dest), "label": LABEL}))
    return 0


def json_dumps(obj: dict) -> str:
    import json

    return json.dumps(obj, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
