#!/usr/bin/env python3
"""Auto-clear stale TRADING_HALTED when no option positions are open.

This is intentionally conservative:
- Keep halt if any source reports open option positions.
- Clear only when all available sources report zero option positions.

Sources used:
1) data/system_state.json
2) Alpaca paper positions (when ALPACA_API_KEY/ALPACA_SECRET_KEY are set)
3) Alpaca live positions (when ALPACA_BROKERAGE_TRADING_API_KEY/_SECRET are set)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


def _is_option_symbol(symbol: str) -> bool:
    text = str(symbol or "").strip().upper()
    return len(text) > 10 and any(ch.isdigit() for ch in text)


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _count_option_positions_from_state(state: dict[str, Any]) -> int | None:
    if not state:
        return None

    top_level_positions = state.get("positions")
    top_level_count = None
    if isinstance(top_level_positions, list):
        top_level_count = sum(
            1 for item in top_level_positions if _is_option_symbol(str(item.get("symbol", "")))
        )

    # Fallback signals from account summaries.
    paper_count = state.get("paper_account", {}).get("positions_count")
    live_count = state.get("live_account", {}).get("positions_count")
    summary_count = 0
    summary_seen = False
    for value in (paper_count, live_count):
        if isinstance(value, (int, float)):
            summary_count = max(summary_count, int(value))
            summary_seen = True

    if top_level_count is None and not summary_seen:
        return None
    if top_level_count is None:
        return summary_count
    if not summary_seen:
        return top_level_count
    return max(top_level_count, summary_count)


def _count_option_positions_from_alpaca(*, paper: bool, key: str, secret: str) -> int | None:
    if not key or not secret:
        return None
    try:
        from alpaca.trading.client import TradingClient
    except Exception:
        return None

    try:
        client = TradingClient(key, secret, paper=paper)
        positions = client.get_all_positions()
    except Exception:
        return None

    count = 0
    for pos in positions:
        symbol = getattr(pos, "symbol", "")
        if _is_option_symbol(symbol):
            count += 1
    return count


@dataclass
class ClearResult:
    status: str
    reason: str
    cleared: bool
    open_option_positions: int | None
    source_counts: dict[str, int | None]
    backup_file: str = ""


def auto_clear_stale_halt(
    *,
    halt_file: Path,
    state_file: Path,
    backup_dir: Path,
    dry_run: bool = False,
) -> ClearResult:
    if not halt_file.exists():
        return ClearResult(
            status="no_halt_file",
            reason="TRADING_HALTED does not exist.",
            cleared=False,
            open_option_positions=0,
            source_counts={},
        )

    state = _load_state(state_file)
    state_count = _count_option_positions_from_state(state)

    paper_count = _count_option_positions_from_alpaca(
        paper=True,
        key=os.environ.get("ALPACA_API_KEY", ""),
        secret=os.environ.get("ALPACA_SECRET_KEY", ""),
    )
    live_count = _count_option_positions_from_alpaca(
        paper=False,
        key=os.environ.get("ALPACA_BROKERAGE_TRADING_API_KEY", ""),
        secret=os.environ.get("ALPACA_BROKERAGE_TRADING_API_SECRET", ""),
    )

    source_counts = {
        "state": state_count,
        "alpaca_paper": paper_count,
        "alpaca_live": live_count,
    }
    observed = [count for count in source_counts.values() if count is not None]
    if not observed:
        return ClearResult(
            status="insufficient_evidence",
            reason="No reliable position source available; keeping halt.",
            cleared=False,
            open_option_positions=None,
            source_counts=source_counts,
        )

    open_option_positions = max(observed)
    if open_option_positions > 0:
        return ClearResult(
            status="halt_retained_open_positions",
            reason=f"Detected {open_option_positions} open option position(s); keeping halt.",
            cleared=False,
            open_option_positions=open_option_positions,
            source_counts=source_counts,
        )

    if dry_run:
        return ClearResult(
            status="dry_run_clearable",
            reason="No open option positions detected; halt is clearable.",
            cleared=False,
            open_option_positions=0,
            source_counts=source_counts,
        )

    original = halt_file.read_text(encoding="utf-8", errors="ignore")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_file = backup_dir / f"crisis_cleared_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    backup_file.write_text(
        "Auto-cleared stale TRADING_HALTED.\n\n"
        f"Timestamp: {datetime.now().isoformat()}\n"
        f"Source counts: {json.dumps(source_counts, sort_keys=True)}\n\n"
        "Original halt content:\n"
        f"{original}",
        encoding="utf-8",
    )
    halt_file.unlink()

    return ClearResult(
        status="halt_cleared",
        reason="No open option positions detected. Cleared stale halt.",
        cleared=True,
        open_option_positions=0,
        source_counts=source_counts,
        backup_file=str(backup_file),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Auto-clear stale TRADING_HALTED if flat.")
    parser.add_argument(
        "--halt-file",
        default="data/TRADING_HALTED",
        help="Path to TRADING_HALTED file.",
    )
    parser.add_argument(
        "--state-file",
        default="data/system_state.json",
        help="Path to system_state.json.",
    )
    parser.add_argument(
        "--backup-dir",
        default="data",
        help="Directory where clear-audit backups are written.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show decision without clearing.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    result = auto_clear_stale_halt(
        halt_file=Path(args.halt_file),
        state_file=Path(args.state_file),
        backup_dir=Path(args.backup_dir),
        dry_run=bool(args.dry_run),
    )

    payload = {
        "status": result.status,
        "reason": result.reason,
        "cleared": result.cleared,
        "open_option_positions": result.open_option_positions,
        "source_counts": result.source_counts,
        "backup_file": result.backup_file,
    }
    if args.json:
        print(json.dumps(payload))
    else:
        print(f"[{result.status}] {result.reason}")
        print(f"source_counts={result.source_counts}")
        if result.backup_file:
            print(f"backup_file={result.backup_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
