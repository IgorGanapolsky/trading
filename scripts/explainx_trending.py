#!/usr/bin/env python3
"""Honest ExplainX trending mapper + two-ceiling + planner/executor doctor.

Always prints JSON. Fixture by default in tests; --fetch hits the live page.
Never auto-installs third-party skills/MCP. Never invents rankings.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.intel.explainx.ceilings import build_ceiling_report  # noqa: E402
from src.intel.explainx.harness_split import classify_command  # noqa: E402
from src.intel.explainx.map_rails import map_items  # noqa: E402
from src.intel.explainx.parse import (  # noqa: E402
    TRENDING_URL,
    UNAVAILABLE,
    ExplainXParseError,
    fetch_trending_html,
    parse_trending_html,
)

ENTRIES_FILE = REPO_ROOT / "data" / "put_credit_entries.json"
TRADES_FILE = REPO_ROOT / "data" / "trades.json"


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, help="Local HTML fixture (offline)")
    parser.add_argument("--fetch", action="store_true", help="Fetch live explainx.ai/trending")
    parser.add_argument("--url", default=TRENDING_URL)
    parser.add_argument("--ceilings", action="store_true", help="Two-ceiling honesty report")
    parser.add_argument("--harness", action="store_true", help="Classify a command")
    parser.add_argument("--command", default="", help="Command string for --harness")
    parser.add_argument("--limit", type=int, default=0, help="Max mapped items (0 = all)")
    return parser


def _trending_payload(html: str, *, source: str) -> dict[str, Any]:
    items = parse_trending_html(html)
    mapped = map_items(items)
    return {
        "ok": bool(items),
        "status": "ok" if items else UNAVAILABLE,
        "source": source,
        "url": TRENDING_URL,
        "fetched_at": datetime.now(UTC).isoformat(),
        "n": len(items),
        "auto_install": False,
        "explainx_score_is_not_trading_roi": True,
        "items": [item.as_dict() for item in items],
        "mapped": mapped,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload: dict[str, Any]

    if args.harness:
        payload = classify_command(args.command)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload.get("role") != "unknown" else 2

    if args.ceilings:
        entries = _load_json(ENTRIES_FILE)
        trades_doc = _load_json(TRADES_FILE)
        trades = trades_doc.get("trades") if isinstance(trades_doc, dict) else None
        payload = build_ceiling_report(
            entries=entries if isinstance(entries, dict) else None,
            trades=trades if isinstance(trades, list) else None,
            entries_present=isinstance(entries, dict),
            trades_present=isinstance(trades, list),
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    html = ""
    source = "empty"
    try:
        if args.fixture:
            html = args.fixture.read_text(encoding="utf-8")
            source = str(args.fixture)
        elif args.fetch:
            html = fetch_trending_html(args.url)
            source = args.url
        else:
            payload = {
                "ok": False,
                "status": UNAVAILABLE,
                "error": "pass --fixture or --fetch",
                "auto_install": False,
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 2
    except (OSError, ExplainXParseError) as exc:
        payload = {
            "ok": False,
            "status": UNAVAILABLE,
            "error": str(exc),
            "auto_install": False,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2

    payload = _trending_payload(html, source=source)
    if args.limit and args.limit > 0:
        payload["mapped"] = payload["mapped"][: args.limit]
        payload["items"] = payload["items"][: args.limit]
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
