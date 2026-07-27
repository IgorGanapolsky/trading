#!/usr/bin/env python3
"""Mercury Bank CLI - read-only operator surface.

Subcommands:
  accounts       List accounts with balances (masked)
  transactions   Recent transactions for one account
  sync           Write a masked snapshot to data/mercury_state.json
  health         Exit 0 if the Mercury API is reachable with the vault token

All commands are read-only by construction (MercuryReadOnlyClient is GET-only).
Money movement stays behind MercuryBankAdapter's MERCURY_LIVE_TRANSFERS_ENABLED
hard stop and is not reachable from this CLI. The token is never printed.

Examples:
  .venv/bin/python scripts/mercury_cli.py accounts
  .venv/bin/python scripts/mercury_cli.py transactions --account savings --limit 10
  .venv/bin/python scripts/mercury_cli.py sync
  .venv/bin/python scripts/mercury_cli.py health
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adapters.mercury_readonly import MercuryReadOnlyClient  # noqa: E402

DEFAULT_STATE_PATH = ROOT / "data" / "mercury_state.json"


def cmd_accounts(client: MercuryReadOnlyClient, args: argparse.Namespace) -> None:
    snapshot = client.snapshot()
    if args.json:
        print(json.dumps(snapshot, indent=2))
        return
    print("=== MERCURY ACCOUNTS (read-only) ===")
    for a in snapshot["accounts"]:
        print(
            f"  {a['name']} [{a['kind']}] {a['status']}: "
            f"${float(a['available_balance_usd'] or 0):,.2f} available"
        )
    print(f"  TOTAL available: ${snapshot['total_available_usd']:,.2f}")


def cmd_transactions(client: MercuryReadOnlyClient, args: argparse.Namespace) -> None:
    result = client.get_transactions(args.account, limit=args.limit)
    if args.json:
        print(json.dumps(result, indent=2))
        return
    rows = result["transactions"]
    print(f"=== MERCURY TRANSACTIONS [{args.account}] ({len(rows)} of {result['total']}) ===")
    for t in rows:
        amount = float(t["amount_usd"] or 0)
        print(
            f"  {t['created_at']} {t['kind'] or '?'} ${amount:,.2f} "
            f"{t['status'] or '?'} {t['counterparty'] or t['description'] or ''}"
        )
    if not rows:
        print("  (no transactions)")


def cmd_sync(client: MercuryReadOnlyClient, args: argparse.Namespace) -> None:
    snapshot = client.snapshot()
    args.state_path.parent.mkdir(parents=True, exist_ok=True)
    args.state_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(
        f"✅ Mercury sync complete: {len(snapshot['accounts'])} accounts, "
        f"${snapshot['total_available_usd']:,.2f} available -> {args.state_path}"
    )


def cmd_health(client: MercuryReadOnlyClient, args: argparse.Namespace) -> None:
    accounts = client.list_accounts()
    active = sum(1 for a in accounts if a.get("status") == "active")
    print(f"✅ Mercury API reachable: {len(accounts)} accounts ({active} active)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_accounts = sub.add_parser("accounts", help="List accounts with balances")
    p_accounts.add_argument("--json", action="store_true")
    p_accounts.set_defaults(func=cmd_accounts)

    p_txn = sub.add_parser("transactions", help="Recent transactions for one account")
    p_txn.add_argument("--account", default="checking", help="checking|savings|<account id>")
    p_txn.add_argument("--limit", type=int, default=20)
    p_txn.add_argument("--json", action="store_true")
    p_txn.set_defaults(func=cmd_transactions)

    p_sync = sub.add_parser("sync", help="Write snapshot to data/mercury_state.json")
    p_sync.add_argument("--state-path", type=Path, default=DEFAULT_STATE_PATH)
    p_sync.set_defaults(func=cmd_sync)

    p_health = sub.add_parser("health", help="Exit 0 if Mercury API is reachable")
    p_health.set_defaults(func=cmd_health)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        client = MercuryReadOnlyClient.from_env()
    except ValueError as exc:
        print(f"❌ Mercury credentials missing: {exc}")
        return 1
    # Operator CLI: report failures as messages, never tracebacks.
    try:
        args.func(client, args)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Mercury {args.command} failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
