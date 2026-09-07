#!/usr/bin/env python3
"""Agent-facing ledger schema preflight (Polars 2 collect_schema analog).

Validates trades.json structure without computing edge claims.
Exit 0 when schema-ok; exit 2 on SchemaError/ShapeError/LosslessCoercionError.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.strict_tabular import (  # noqa: E402
    LosslessCoercionError,
    SchemaError,
    ShapeError,
    collect_row_schema,
    parse_optional_strict_int,
)

REQUIRED_TRADE_FIELDS = (
    "id",
    "status",
    "realized_pnl",
)
NUMERIC_TRADE_FIELDS = ("realized_pnl", "quantity")


def _load_trades(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SchemaError("trades.json root must be an object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trades",
        type=Path,
        default=ROOT / "data" / "trades.json",
        help="Path to trades.json",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row cap for schema scan (default: all)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args(argv)

    try:
        payload = _load_trades(args.trades)
        rows = payload.get("trades")
        if not isinstance(rows, list):
            raise SchemaError("trades.json missing list field 'trades'")
        schema = collect_row_schema(
            rows,
            required=REQUIRED_TRADE_FIELDS,
            numeric_fields=NUMERIC_TRADE_FIELDS,
            max_rows=args.max_rows,
        )
        stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
        stats_counts = {
            "closed_trades": parse_optional_strict_int(
                stats.get("closed_trades"), field="stats.closed_trades"
            ),
            "unpaired_order_count": parse_optional_strict_int(
                stats.get("unpaired_order_count"), field="stats.unpaired_order_count"
            ),
        }
        report = {
            "ok": True,
            "path": str(args.trades),
            "schema": schema,
            "stats_counts": stats_counts,
            "steal": "polars-2-fail-fast-schema-height-id",
        }
    except (SchemaError, ShapeError, LosslessCoercionError) as exc:
        report = {
            "ok": False,
            "path": str(args.trades),
            "error": str(exc),
            "error_type": type(exc).__name__,
            "steal": "polars-2-fail-fast-schema-height-id",
        }
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(f"STRICT_LEDGER_SCHEMA_FAIL: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"STRICT_LEDGER_SCHEMA_OK rows={schema['inspected_rows']} "
            f"closed_trades={stats_counts['closed_trades']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
