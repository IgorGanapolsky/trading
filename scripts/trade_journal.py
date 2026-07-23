#!/usr/bin/env python3
"""Trade Journal — audit trail for the controlled experiment.

Reads ic_entries.json and trades.json to produce a structured record
of every validation-phase trade. Reports protocol violations.

Usage:
    PYTHONPATH=. python3 scripts/trade_journal.py
"""

import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.analytics.trade_evidence import active_strategy_family, build_trade_evidence

PROJECT_ROOT = Path(__file__).parent.parent
ENTRIES_FILE = PROJECT_ROOT / "data" / "ic_entries.json"
TRADES_FILE = PROJECT_ROOT / "data" / "trades.json"


def load_json(path: Path) -> dict | list:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _fmt_number(value: Any, digits: int = 2) -> str:
    parsed = _finite_float(value)
    return "?" if parsed is None else f"{parsed:.{digits}f}"


def main() -> int:
    entries = load_json(ENTRIES_FILE)
    trades_data = load_json(TRADES_FILE)
    closed_trades = trades_data.get("trades", []) if isinstance(trades_data, dict) else []
    if not isinstance(entries, dict):
        entries = {}

    # Never infer controlled-experiment membership from a date. That previously
    # pulled unrelated trades into the denominator and manufactured 6 outcomes
    # from two explicitly labelled validation rows.
    validation_entries = {
        k: v
        for k, v in entries.items()
        if isinstance(v, dict) and v.get("validation_phase") is True
    }

    if not validation_entries:
        print("No explicitly labelled historical iron-condor validation records found.")

    print("=" * 80)
    print("TRADE JOURNAL — Verified Controlled-Experiment Audit")
    print("=" * 80)
    print("Iron condor: RETIRED FOR NEW ENTRIES; open rows are exit-only.")
    print()

    violations: list[str] = []
    trade_num = 0

    for key, entry in sorted(
        validation_entries.items(),
        key=lambda item: str(item[1].get("entry_time") or item[1].get("date") or ""),
    ):
        trade_num += 1
        entry_date = str(entry.get("entry_time") or entry.get("date") or "unknown")
        expiry = entry.get("strikes") if isinstance(entry.get("strikes"), dict) else {}
        sp = expiry.get("short_put", "?")
        sc = expiry.get("short_call", "?")
        lp = expiry.get("long_put", "?")
        lc = expiry.get("long_call", "?")
        credit = _finite_float(entry.get("credit"))
        put_delta = _finite_float(entry.get("put_delta"))
        call_delta = _finite_float(entry.get("call_delta"))
        method = entry.get("selection_method", entry.get("strike_selection_method", "unknown"))
        qty = _finite_float(entry.get("quantity"))
        profile = entry.get("profile_name", "unknown")
        order_id = str(entry.get("order_id") or "unknown")

        # Calculate DTE at entry
        try:
            expiry_str = key.replace("IC_", "")
            if re.fullmatch(r"\d{6}", expiry_str) is None:
                raise ValueError("invalid expiry key")
            exp_date = date(2000 + int(expiry_str[:2]), int(expiry_str[2:4]), int(expiry_str[4:6]))
            entry_dt = (
                datetime.fromisoformat(entry_date).date()
                if entry_date != "unknown"
                else date.today()
            )
            dte_at_entry = (exp_date - entry_dt).days
        except (ValueError, TypeError):
            dte_at_entry = "?"

        # Check for closed trade match
        closed_match = None
        for t in closed_trades:
            if not isinstance(t, dict) or t.get("validation_phase") is not True:
                continue
            sig = t.get("signature", "")
            if key.replace("IC_", "") in sig or entry.get("signature", "") == sig:
                closed_match = t
                break

        status = "OPEN"
        hold_time = "—"
        exit_reason = "—"
        pnl = "—"

        if closed_match:
            status = "CLOSED"
            pnl_value = _finite_float(closed_match.get("realized_pnl"))
            pnl = "?" if pnl_value is None else f"${pnl_value:.2f}"
            exit_reason = closed_match.get("exit_reason", "unknown")
            exit_date = closed_match.get("exit_date", "")
            if exit_date and entry_date != "unknown":
                try:
                    hold_hours = (
                        datetime.fromisoformat(exit_date) - datetime.fromisoformat(entry_date)
                    ).total_seconds() / 3600
                    hold_time = f"{hold_hours:.1f}h"
                    if hold_hours < 24:
                        violations.append(
                            f"Trade {trade_num}: held {hold_hours:.1f}h < 24h minimum"
                        )
                except (ValueError, TypeError):
                    hold_time = "?"

        # Protocol checks
        if qty is None:
            violations.append(f"Trade {trade_num}: quantity missing or invalid")
        elif qty > 1:
            violations.append(f"Trade {trade_num}: qty={qty} > 1-lot maximum")
        if method != "live_delta":
            violations.append(f"Trade {trade_num}: method={method} (should be live_delta)")
        if profile != "spy-core":
            violations.append(f"Trade {trade_num}: profile={profile} (should be spy-core)")
        if put_delta is None or call_delta is None:
            violations.append(f"Trade {trade_num}: entry deltas missing or invalid")
        if credit is None:
            violations.append(f"Trade {trade_num}: entry credit missing or invalid")
        if dte_at_entry != "?" and dte_at_entry < 30:
            violations.append(f"Trade {trade_num}: DTE={dte_at_entry} < 30 minimum")

        print(f"Trade {trade_num}/{30}")
        print(f"  Entry:   {entry_date[:19]}")
        print(f"  Expiry:  {key.replace('IC_', '')}")
        print(f"  Strikes: LP={lp} SP={sp} SC={sc} LC={lc}")
        print(f"  Deltas:  put={_fmt_number(put_delta, 3)} call={_fmt_number(call_delta, 3)}")
        print(f"  Credit:  ${_fmt_number(credit)} x {_fmt_number(qty, 0)}")
        print(f"  DTE:     {dte_at_entry}")
        print(f"  Method:  {method}")
        print(f"  Profile: {profile}")
        print(f"  Status:  {status}")
        print(f"  Hold:    {hold_time}")
        print(f"  Exit:    {exit_reason}")
        print(f"  P/L:     {pnl}")
        print(f"  Order:   {order_id[:12]}...")
        print()

    print("=" * 80)
    print(f"HISTORICAL IRON-CONDOR VALIDATION RECORDS: {trade_num}")
    print("=" * 80)

    if violations:
        print(f"\nPROTOCOL VIOLATIONS ({len(violations)}):")
        for v in violations:
            print(f"  !! {v}")
    else:
        print("\nNo protocol violations detected.")

    # Expectancy summary for closed trades
    explicit_closed_validation = [
        t
        for t in closed_trades
        if isinstance(t, dict)
        and t.get("validation_phase") is True
        and str(t.get("status") or "").lower() == "closed"
    ]
    historical_evidence = build_trade_evidence(
        {"trades": explicit_closed_validation},
        strategy_family="iron_condor",
    )
    if historical_evidence.rows:
        metrics = historical_evidence.metrics
        pnls = [float(row["realized_pnl"]) for row in historical_evidence.rows]
        wins = [pnl_value for pnl_value in pnls if pnl_value > 0]
        losses = [pnl_value for pnl_value in pnls if pnl_value < 0]
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0

        print("\nHISTORICAL IC EXPECTANCY (explicit verified rows only):")
        print(f"  Closed trades: {metrics.closed_trades}")
        print(f"  Win rate:      {metrics.win_rate_pct:.1f}%")
        print(f"  Avg win:       ${avg_win:.2f}")
        print(f"  Avg loss:      ${avg_loss:.2f}")
        print(f"  Profit factor: {metrics.profit_factor}")
        print(f"  Expectancy:    ${metrics.expectancy_per_trade:.2f}/trade")
        print(f"  Total P/L:     ${metrics.total_realized_pnl:.2f}")
        print("\n  GATE: RETIRED — historical IC evidence cannot promote the active strategy")

    active_family = active_strategy_family(PROJECT_ROOT)
    active_evidence = build_trade_evidence(
        trades_data if isinstance(trades_data, dict) else {},
        strategy_family=active_family,
        require_protocol_fields=active_family == "spy_put_credit",
    )
    print(f"\nACTIVE COHORT: {active_family}")
    print(f"  Verified closed: {len(active_evidence.rows)}/30")
    print(f"  Dataset:         {active_evidence.dataset_sha256[:12]}")
    print(f"  Learning ready:  {active_evidence.learning_ready}")
    if active_evidence.issues:
        for issue in active_evidence.issues:
            print(f"  !! {issue}")
    elif len(active_evidence.rows) < 30:
        print(f"  GATE: PENDING — {30 - len(active_evidence.rows)} verified outcomes needed")

    return 1 if violations or active_evidence.issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
