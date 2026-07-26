"""Read-only Mercury API client.

This client is GET-only by construction: it has no method that can create,
mutate, or move money, and its transport helper refuses non-GET verbs. It is
the shared seam for every read surface (scripts/mercury_cli.py,
scripts/mercury_status.py, mcp/servers/mercury.py). Real transfers remain
exclusively behind MercuryBankAdapter and its MERCURY_LIVE_TRANSFERS_ENABLED
hard stop (src/adapters/bank_adapter.py).

Token resolution order:
  1. MERCURY_API_TOKEN environment variable
  2. Vault file (MERCURY_SECRETS_PATH env override, default
     ~/.resume_secrets/mercury.json) under the "MERCURY_API_TOKEN" or legacy
     "api_token" key

The token value is never logged, printed, or included in any return value.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MERCURY_API_BASE_URL = os.environ.get("MERCURY_API_BASE_URL", "https://api.mercury.com/api/v1")
DEFAULT_VAULT_PATH = Path.home() / ".resume_secrets" / "mercury.json"

ACCOUNT_ALIAS_KEYS = {
    "checking": "MERCURY_ACCOUNT_ID",
    "savings": "MERCURY_SAVINGS_ACCOUNT_ID",
}

HttpGet = Callable[[str, dict[str, Any], dict[str, str]], dict[str, Any]]


def _default_http_get(url: str, params: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    import requests

    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def _load_vault(secrets_path: Path | None = None) -> dict[str, Any]:
    env_override = os.environ.get("MERCURY_SECRETS_PATH")
    path = secrets_path or (Path(env_override) if env_override else DEFAULT_VAULT_PATH)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def resolve_token(secrets_path: Path | None = None) -> str | None:
    token = os.environ.get("MERCURY_API_TOKEN")
    if token:
        return token
    vault = _load_vault(secrets_path)
    return vault.get("MERCURY_API_TOKEN") or vault.get("api_token")


def summarize_account(account: dict[str, Any]) -> dict[str, Any]:
    """Reduce a raw account row to a masked, no-secrets summary."""
    number = str(account.get("accountNumber") or "")
    account_id = str(account.get("id") or "")
    return {
        "id_prefix": account_id[:8] or None,
        "name": account.get("name"),
        "kind": account.get("kind"),
        "status": account.get("status"),
        "current_balance_usd": account.get("currentBalance"),
        "available_balance_usd": account.get("availableBalance"),
        "account_number_last4": number[-4:] if number else None,
    }


def summarize_transaction(txn: dict[str, Any]) -> dict[str, Any]:
    """Reduce a raw transaction row to a masked summary."""
    txn_id = str(txn.get("id") or "")
    return {
        "id_prefix": txn_id[:8] or None,
        "amount_usd": txn.get("amount"),
        "kind": txn.get("kind"),
        "status": txn.get("status"),
        "created_at": txn.get("createdAt"),
        "posted_at": txn.get("postedAt"),
        "counterparty": txn.get("counterpartyName"),
        "description": txn.get("bankDescription"),
    }


class MercuryReadOnlyClient:
    """GET-only Mercury API client. No write capability exists on this class."""

    READ_METHODS = ("list_accounts", "get_account", "get_transactions", "snapshot")

    def __init__(
        self,
        api_token: str,
        *,
        account_aliases: dict[str, str] | None = None,
        base_url: str | None = None,
        http_get: HttpGet | None = None,
    ) -> None:
        if not api_token:
            raise ValueError(
                "MercuryReadOnlyClient requires a token: set MERCURY_API_TOKEN or store "
                "MERCURY_API_TOKEN in ~/.resume_secrets/mercury.json"
            )
        self._api_token = api_token
        self._account_aliases = account_aliases or {}
        self._base_url = base_url or MERCURY_API_BASE_URL
        self._http_get = http_get or _default_http_get

    @classmethod
    def from_env(
        cls,
        *,
        secrets_path: Path | None = None,
        http_get: HttpGet | None = None,
    ) -> MercuryReadOnlyClient:
        token = resolve_token(secrets_path)
        if not token:
            raise ValueError(
                "No Mercury token: set MERCURY_API_TOKEN or store it in "
                "~/.resume_secrets/mercury.json"
            )
        vault = _load_vault(secrets_path)
        aliases = {}
        for alias, key in ACCOUNT_ALIAS_KEYS.items():
            account_id = os.environ.get(key) or vault.get(key)
            if account_id:
                aliases[alias] = account_id
        return cls(token, account_aliases=aliases, http_get=http_get)

    def resolve_account_id(self, alias_or_id: str) -> str:
        return self._account_aliases.get(alias_or_id, alias_or_id)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self._api_token}"}
        return self._http_get(f"{self._base_url}{path}", params or {}, headers)

    def list_accounts(self) -> list[dict[str, Any]]:
        payload = self._get("/accounts")
        return [
            summarize_account(a) for a in payload.get("accounts", []) if isinstance(a, dict)
        ]

    def get_account(self, alias_or_id: str) -> dict[str, Any]:
        account_id = self.resolve_account_id(alias_or_id)
        return summarize_account(self._get(f"/account/{account_id}"))

    def get_transactions(
        self, alias_or_id: str, *, limit: int = 20, offset: int = 0
    ) -> dict[str, Any]:
        account_id = self.resolve_account_id(alias_or_id)
        payload = self._get(
            f"/account/{account_id}/transactions",
            {"limit": max(1, min(int(limit), 500)), "offset": max(0, int(offset))},
        )
        return {
            "total": payload.get("total"),
            "transactions": [
                summarize_transaction(t)
                for t in payload.get("transactions", [])
                if isinstance(t, dict)
            ],
        }

    def snapshot(self) -> dict[str, Any]:
        """Masked point-in-time snapshot suitable for data/mercury_state.json."""
        accounts = self.list_accounts()
        total = sum(float(a.get("available_balance_usd") or 0.0) for a in accounts)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "read_only": True,
            "accounts": accounts,
            "total_available_usd": total,
        }
