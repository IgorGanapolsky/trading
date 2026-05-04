#!/usr/bin/env python3
"""Trade Journal — audit trail for the controlled experiment.

Reads ic_entries.json and trades.json to produce a structured record
of every validation-phase trade. Reports protocol violations.

Usage:
    PYTHONPATH=. python3 scripts/trade_journal.py
"""

import json
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ENTRIES_FILE = PROJECT_ROOT / "data" / "ic_entries.json"
TRADES_FILE = PROJECT_ROOT / "data" / "trades.json"


def load_json(path: Path) -> dict | list:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def main():
    entries = load_json(ENTRIES_FILE)
    trades_data = load_json(TRADES_FILE)
    closed_trades = trades_data.get("trades", []) if isinstance(trades_data, dict) else []

    # Filter validation-phase entries
    validation_entries = {
        k: v
        for k, v in entries.items()
        if v.get("validation_phase") or v.get("date", "") >= "2026-04-10"
    }

    if not validation_entries:
        print("No validation-phase trades found.")
        print("The controlled experiment has not started yet.")
        return

    print("=" * 80)
    print("TRADE JOURNAL — Controlled Experiment (30-Trade Validation)")
    print("=" * 80)
    print()

    violations = []
    trade_num = 0

    for key, entry in sorted(validation_entries.items(), key=lambda x: x[1].get("date", "")):
        trade_num += 1
        entry_date = entry.get("date", "unknown")
        expiry = entry.get("strikes", {})
        sp = expiry.get("short_put", "?")
        sc = expiry.get("short_call", "?")
        lp = expiry.get("long_put", "?")
        lc = expiry.get("long_call", "?")
        credit = entry.get("credit", 0)
        put_delta = entry.get("put_delta", 0)
        call_delta = entry.get("call_delta", 0)
        method = entry.get("selection_method", entry.get("strike_selection_method", "unknown"))
        qty = entry.get("quantity", 1)
        profile = entry.get("profile_name", "unknown")
        order_id = entry.get("order_id", "unknown")

        # Calculate DTE at entry
        try:
            expiry_str = key.replace("IC_", "")
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
            pnl = f"${closed_match.get('realized_pnl', 0):.2f}"
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
        if qty > 1:
            violations.append(f"Trade {trade_num}: qty={qty} > 1-lot maximum")
        if method != "live_delta":
            violations.append(f"Trade {trade_num}: method={method} (should be live_delta)")
        if profile != "spy-core":
            violations.append(f"Trade {trade_num}: profile={profile} (should be spy-core)")
        if dte_at_entry != "?" and dte_at_entry < 30:
            violations.append(f"Trade {trade_num}: DTE={dte_at_entry} < 30 minimum")

        print(f"Trade {trade_num}/{30}")
        print(f"  Entry:   {entry_date[:19]}")
        print(f"  Expiry:  {key.replace('IC_', '')}")
        print(f"  Strikes: LP={lp} SP={sp} SC={sc} LC={lc}")
        print(f"  Deltas:  put={put_delta:.3f} call={call_delta:.3f}")
        print(f"  Credit:  ${credit:.2f} x {qty}")
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
    print(f"VALIDATION PROGRESS: {trade_num}/30 trades")
    print("=" * 80)

    if violations:
        print(f"\nPROTOCOL VIOLATIONS ({len(violations)}):")
        for v in violations:
            print(f"  !! {v}")
    else:
        print("\nNo protocol violations detected.")

    # Expectancy summary for closed trades
    closed_validation = [
        t
        for t in closed_trades
        if t.get("validation_phase") or t.get("entry_date", "") >= "2026-04-10"
    ]
    if closed_validation:
        pnls = [t.get("realized_pnl", 0) for t in closed_validation]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        total_pnl = sum(pnls)
        win_rate = len(wins) / len(pnls) * 100 if pnls else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        profit_factor = sum(wins) / abs(sum(losses)) if losses else float("inf")
        expectancy = total_pnl / len(pnls) if pnls else 0

        print("\nEXPECTANCY REPORT (validation trades only):")
        print(f"  Closed trades: {len(pnls)}")
        print(f"  Win rate:      {win_rate:.1f}%")
        print(f"  Avg win:       ${avg_win:.2f}")
        print(f"  Avg loss:      ${avg_loss:.2f}")
        print(f"  Profit factor: {profit_factor:.2f}")
        print(f"  Expectancy:    ${expectancy:.2f}/trade")
        print(f"  Total P/L:     ${total_pnl:.2f}")

        if expectancy > 0 and profit_factor > 1 and len(pnls) >= 30:
            print("\n  GATE: PASSED — positive expectancy over 30+ trades")
        elif len(pnls) >= 30:
            print("\n  GATE: FAILED — expectancy <= 0 or profit factor <= 1")
        else:
            print(f"\n  GATE: PENDING — {30 - len(pnls)} more trades needed")


if __name__ == "__main__":
    main()
