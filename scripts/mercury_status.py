#!/usr/bin/env python3
"""Read-only Mercury bank status via the real Mercury API.

Prints account names, kinds, and balances as JSON. This path is read-only by
construction twice over: the code only ever issues GET requests, and the
vaulted token it loads was created with read_only permissions (2026-07-26,
nickname "trading-readonly") - Mercury's API rejects any transfer attempt made
with it. Wiring real transfers remains a separate, explicit change gated by
MercuryBankAdapter's MERCURY_LIVE_TRANSFERS_ENABLED requirement
(src/adapters/bank_adapter.py).

Token resolution order:
  1. MERCURY_API_TOKEN environment variable
  2. ~/.resume_secrets/mercury.json (chmod 600 vault file, "api_token" key)

The token value is never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

MERCURY_API_BASE_URL = "https://api.mercury.com/api/v1"
VAULT_PATH = Path.home() / ".resume_secrets" / "mercury.json"


def load_token() -> str:
    token = os.environ.get("MERCURY_API_TOKEN")
    if token:
        return token
    if VAULT_PATH.is_file():
        try:
            payload = json.loads(VAULT_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Failed to read {VAULT_PATH}: {exc}") from exc
        token = payload.get("api_token")
        if token:
            return token
    raise SystemExit(
        "No Mercury token: set MERCURY_API_TOKEN or store api_token in ~/.resume_secrets/mercury.json"
    )


def summarize_accounts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Reduce the raw /accounts response to a masked, no-secrets summary."""
    summary = []
    for account in payload.get("accounts", []):
        if not isinstance(account, dict):
            continue
        number = str(account.get("accountNumber") or "")
        summary.append(
            {
                "name": account.get("name"),
                "kind": account.get("kind"),
                "status": account.get("status"),
                "current_balance_usd": account.get("currentBalance"),
                "available_balance_usd": account.get("availableBalance"),
                "account_number_last4": number[-4:] if number else None,
            }
        )
    return summary


def fetch_accounts(token: str) -> dict[str, Any]:
    import requests

    response = requests.get(
        f"{MERCURY_API_BASE_URL}/accounts",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    accounts = summarize_accounts(fetch_accounts(load_token()))
    total = sum(float(a.get("available_balance_usd") or 0.0) for a in accounts)
    report = {"accounts": accounts, "total_available_usd": total, "read_only": True}

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=== MERCURY BANK STATUS (read-only) ===")
        for a in accounts:
            print(
                f"  {a['name']} [{a['kind']}] {a['status']}: "
                f"${float(a['available_balance_usd'] or 0):,.2f} available"
            )
        print(f"  TOTAL available: ${total:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
