#!/usr/bin/env python3
"""Exit-only high-ROI trading loop.

This operator wraps the existing iron-condor exit manager with:
- a hard entry gate sourced from TRADING_HALTED and North Star guard state
- repeatable one-shot or scheduled monitoring
- append-only JSONL evidence for every pass

It does not open new positions. In default dry-run mode it never submits orders.
Use --execute only when the operator intentionally wants eligible exits sent.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.safety.north_star_guard import get_guard_context  # noqa: E402
from src.safety.trading_halt import get_trading_halt_state  # noqa: E402

from scripts.manage_iron_condor_positions import (  # noqa: E402
    IC_EXIT_CONFIG,
    calculate_dte,
    check_exit_conditions,
    close_iron_condor,
    get_alpaca_credentials,
    get_iron_condor_positions,
    group_iron_condors,
    record_trade_outcome,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JOURNAL_PATH = PROJECT_ROOT / "data" / "runtime" / "high_roi_trading_loop.jsonl"
DEFAULT_LATEST_PATH = PROJECT_ROOT / "data" / "runtime" / "high_roi_trading_loop_latest.json"
DEFAULT_INTERVAL_SECONDS = 15 * 60

logger = logging.getLogger("high_roi_trading_loop")


def utc_now_iso() -> str:
    """Return an ISO UTC timestamp with a Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def load_json(path: Path, default: Any) -> Any:
    """Load JSON from disk, returning default on missing/invalid files."""
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def build_entry_gate_summary(repo_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Build a fail-closed summary for new-entry permissions.

    This loop is exit-only even when the North Star guard would allow validation
    entries. The explicit summary makes that operationally visible in each
    journal event.
    """
    halt = get_trading_halt_state(repo_root)
    state_path = repo_root / "data" / "system_state.json"
    hypothesis_path = repo_root / "data" / "runtime" / "strategy_validation_hypothesis.json"

    guard_error = ""
    try:
        guard = get_guard_context(state_path=state_path, hypothesis_path=hypothesis_path)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        guard = {
            "enabled": False,
            "mode": "unavailable",
            "block_new_positions": True,
            "block_reason": f"North Star guard unavailable: {exc}",
            "reasons": [],
        }
        guard_error = str(exc)

    system_state = load_json(state_path, {})
    weekly_gate = (
        system_state.get("north_star_weekly_gate", {})
        if isinstance(system_state, dict)
        else {}
    )
    quarantine = (
        weekly_gate.get("strategy_quarantine", {})
        if isinstance(weekly_gate, dict) and isinstance(weekly_gate.get("strategy_quarantine"), dict)
        else {}
    )

    reasons: list[str] = []
    if halt.active:
        reasons.append(f"{halt.kind}: {halt.reason}")
    if guard.get("block_new_positions"):
        reasons.append(str(guard.get("block_reason") or "North Star guard blocked entries."))
    if isinstance(weekly_gate, dict) and weekly_gate.get("block_new_positions"):
        reasons.append(str(weekly_gate.get("reason") or "Weekly gate blocked entries."))
    if isinstance(quarantine, dict) and quarantine.get("block_new_positions"):
        reasons.append(str(quarantine.get("reason") or "Strategy quarantine blocked entries."))
    if not reasons:
        reasons.append("Loop policy is exit-only; no new entries are opened by this operator.")

    new_entries_blocked = bool(
        halt.active
        or guard.get("block_new_positions", True)
        or (isinstance(weekly_gate, dict) and weekly_gate.get("block_new_positions"))
        or (isinstance(quarantine, dict) and quarantine.get("block_new_positions"))
        or guard_error
    )

    return {
        "exit_only": True,
        "entries_allowed_by_loop": False,
        "new_entries_blocked": True,
        "new_entries_blocked_by_state": new_entries_blocked,
        "halt": {
            "active": halt.active,
            "kind": halt.kind,
            "path": halt.path,
            "reason": halt.reason,
        },
        "north_star_guard": {
            "enabled": bool(guard.get("enabled")),
            "mode": guard.get("mode"),
            "block_new_positions": bool(guard.get("block_new_positions", True)),
            "allow_validation_entries": bool(guard.get("allow_validation_entries", False)),
            "block_live_new_positions": bool(guard.get("block_live_new_positions", False)),
            "max_position_pct": guard.get("max_position_pct"),
            "block_reason": guard.get("block_reason", ""),
            "reasons": guard.get("reasons", []),
        },
        "weekly_gate_mode": weekly_gate.get("mode") if isinstance(weekly_gate, dict) else None,
        "reasons": reasons,
    }


def summarize_account(client: Any) -> dict[str, Any]:
    """Return a small account snapshot when the client supports it."""
    if not hasattr(client, "get_account"):
        return {"available": False, "reason": "client has no get_account"}

    try:
        account = client.get_account()
    except Exception as exc:
        return {"available": False, "reason": str(exc)}

    fields = ("account_number", "status", "equity", "last_equity", "cash", "buying_power")
    snapshot: dict[str, Any] = {"available": True}
    for field in fields:
        value = getattr(account, field, None)
        if value is not None:
            snapshot[field] = str(value)
    return snapshot


def _summarize_leg(leg: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": leg.get("symbol"),
        "qty": _safe_float(leg.get("qty")),
        "type": leg.get("type"),
        "strike": _safe_float(leg.get("strike")),
        "unrealized_pl": _safe_float(leg.get("unrealized_pl")),
        "market_value": _safe_float(leg.get("market_value")),
    }


def build_exit_decision(ic: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one iron condor and return an order-free decision object."""
    credit = _safe_float(ic.get("credit_received"))
    pl = _safe_float(ic.get("total_pl"))
    dte = calculate_dte(ic["expiry"])
    pl_pct = pl / credit if credit > 0 else None
    should_exit, reason, details = check_exit_conditions(ic)

    # Missing entry dates should not prevent hard risk exits. The base manager
    # holds by default when entry_date is absent to avoid same-day churn; this
    # operator preserves that for profit-taking but still protects stop-loss
    # and 7-DTE exits.
    if (
        not should_exit
        and credit > 0
        and str(details).lower().startswith("no entry_date recorded")
    ):
        if dte <= IC_EXIT_CONFIG["exit_dte"]:
            should_exit = True
            reason = "DTE_EXIT"
            details = (
                f"{dte} DTE (threshold: {IC_EXIT_CONFIG['exit_dte']}); "
                "hard risk exit overrides missing entry_date"
            )
        elif pl_pct is not None and pl_pct <= -IC_EXIT_CONFIG["stop_loss_pct"]:
            should_exit = True
            reason = "STOP_LOSS"
            details = (
                f"{pl_pct * 100:.1f}% loss "
                f"(stop: {IC_EXIT_CONFIG['stop_loss_pct'] * 100:.0f}%); "
                "hard risk exit overrides missing entry_date"
            )

    return {
        "underlying": ic.get("underlying"),
        "expiry": ic.get("expiry_str"),
        "legs": len(ic.get("legs", [])),
        "dte": dte,
        "credit_received": round(credit, 2),
        "total_pl": round(pl, 2),
        "pl_pct_of_credit": round(pl_pct, 4) if pl_pct is not None else None,
        "should_exit": bool(should_exit),
        "exit_reason": reason,
        "details": details,
        "thresholds": IC_EXIT_CONFIG,
        "leg_symbols": [leg.get("symbol") for leg in ic.get("legs", [])],
        "leg_summary": [_summarize_leg(leg) for leg in ic.get("legs", [])],
    }


def append_jsonl(path: Path, event: dict[str, Any]) -> None:
    """Append a JSON event to path and create parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, default=_json_default) + "\n")


def write_latest(path: Path, event: dict[str, Any]) -> None:
    """Write the latest event snapshot for dashboards and operator readback."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(event, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def create_trading_client() -> Any:
    """Create the paper Alpaca TradingClient with canonical credentials."""
    try:
        from alpaca.trading.client import TradingClient
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("alpaca-py is not installed") from exc

    api_key, secret_key = get_alpaca_credentials()
    if not api_key or not secret_key:
        raise RuntimeError("Alpaca credentials not found")
    return TradingClient(api_key, secret_key, paper=True)


def run_once(
    *,
    client: Any | None = None,
    execute: bool = False,
    repo_root: Path = PROJECT_ROOT,
    journal_path: Path = DEFAULT_JOURNAL_PATH,
    latest_path: Path = DEFAULT_LATEST_PATH,
) -> dict[str, Any]:
    """Run one exit-only monitoring pass and persist evidence."""
    mode = "execute" if execute else "dry_run"
    client = client or create_trading_client()
    gate = build_entry_gate_summary(repo_root)
    account = summarize_account(client)

    positions = get_iron_condor_positions(client)
    iron_condors = group_iron_condors(positions)

    decisions: list[dict[str, Any]] = []
    exits_triggered = 0
    exits_submitted = 0
    exits_failed = 0

    for ic in iron_condors:
        decision = build_exit_decision(ic)
        action = "hold"
        close_result = None

        if decision["should_exit"]:
            exits_triggered += 1
            action = "would_close"
            if execute:
                close_result = bool(close_iron_condor(client, ic, decision["exit_reason"], dry_run=False))
                if close_result:
                    exits_submitted += 1
                    action = "closed"
                    record_trade_outcome(
                        ic,
                        decision["exit_reason"],
                        won=decision["exit_reason"] == "PROFIT_TARGET",
                    )
                else:
                    exits_failed += 1
                    action = "close_failed"

        decision["action"] = action
        decision["close_submitted"] = bool(close_result) if close_result is not None else False
        decisions.append(decision)

    event = {
        "timestamp": utc_now_iso(),
        "source": "high_roi_trading_loop",
        "mode": mode,
        "repo_root": str(repo_root),
        "entry_gate": gate,
        "account": account,
        "option_legs_seen": len(positions),
        "iron_condors_evaluated": len(iron_condors),
        "exits_triggered": exits_triggered,
        "exits_submitted": exits_submitted,
        "exits_failed": exits_failed,
        "decisions": decisions,
    }
    append_jsonl(journal_path, event)
    write_latest(latest_path, event)
    return event


def run_loop(
    *,
    execute: bool,
    interval_seconds: int,
    max_iterations: int | None,
    journal_path: Path,
    latest_path: Path,
    repo_root: Path,
) -> int:
    """Run scheduled monitoring until interrupted or max_iterations is reached."""
    iterations = 0
    while True:
        iterations += 1
        event = run_once(
            execute=execute,
            repo_root=repo_root,
            journal_path=journal_path,
            latest_path=latest_path,
        )
        logger.info(
            "pass=%s mode=%s condors=%s exits_triggered=%s exits_submitted=%s",
            iterations,
            event["mode"],
            event["iron_condors_evaluated"],
            event["exits_triggered"],
            event["exits_submitted"],
        )

        if max_iterations is not None and iterations >= max_iterations:
            return 0
        time.sleep(interval_seconds)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run exit-only high-ROI trading loop")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview exits without submitting orders")
    mode.add_argument("--execute", action="store_true", help="Submit eligible exit orders only")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Delay between loop passes",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=1,
        help="Stop after this many passes; use with --loop or one-shot dry runs",
    )
    parser.add_argument("--journal-path", type=Path, default=DEFAULT_JOURNAL_PATH)
    parser.add_argument("--latest-path", type=Path, default=DEFAULT_LATEST_PATH)
    parser.add_argument("--repo-root", type=Path, default=PROJECT_ROOT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    args = parse_args(argv)
    execute = bool(args.execute)
    max_iterations = args.max_iterations if args.loop else 1
    return run_loop(
        execute=execute,
        interval_seconds=max(1, int(args.interval_seconds)),
        max_iterations=max_iterations,
        journal_path=args.journal_path,
        latest_path=args.latest_path,
        repo_root=args.repo_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
