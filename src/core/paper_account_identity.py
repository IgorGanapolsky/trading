"""Pin the validation paper book so the $30k/$5k accounts cannot count toward n=30.

The BrowserOS account switcher (2026-09-07) showed three paper books plus live:

- PA3C5AG0CECQ — validation paper (~$94,181.95, SPY 261016 put credit)
- PA3PYE08C9MN — $30k paper (does not count toward the cohort)
- PA36N5ZP8S40 — $5k paper (deprecated)
- 979807421 — live brokerage (blocked)

Entries on the wrong paper account must not update the validation ledger or
open new risk. This module never logs credentials.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VALIDATION_PAPER_ACCOUNT_NUMBER = "PA3C5AG0CECQ"
FORBIDDEN_PAPER_ACCOUNTS: dict[str, str] = {
    "PA3PYE08C9MN": "30k_paper_not_validation",
    "PA36N5ZP8S40": "5k_paper_not_validation",
    "979807421": "live_brokerage_blocked",
}

# Equity band that fingerprints the $30k paper book when account_number is absent.
_THIRTY_K_EQUITY_MIN = 20_000.0
_THIRTY_K_EQUITY_MAX = 40_000.0


class PaperAccountIdentityError(RuntimeError):
    """Broker or ledger identity is not the validation paper account."""


def normalize_account_number(value: object) -> str:
    return str(value or "").strip().upper()


def assert_broker_is_validation_paper(
    account_number: object,
    *,
    equity: object = None,
) -> str:
    """Require the live broker snapshot to be the validation paper account."""
    number = normalize_account_number(account_number)
    if not number:
        raise PaperAccountIdentityError(
            "PAPER identity missing: broker snapshot has no account_number. "
            f"Refusing to treat this session as {VALIDATION_PAPER_ACCOUNT_NUMBER}."
        )
    if number == VALIDATION_PAPER_ACCOUNT_NUMBER:
        return number
    label = FORBIDDEN_PAPER_ACCOUNTS.get(number, "unknown_account")
    equity_txt = ""
    try:
        if equity is not None:
            equity_txt = f" equity={float(equity):.2f}"
    except (TypeError, ValueError):
        equity_txt = ""
    raise PaperAccountIdentityError(
        f"WRONG_PAPER_ACCOUNT {number} ({label}){equity_txt}; "
        f"expected {VALIDATION_PAPER_ACCOUNT_NUMBER}. "
        "Entries on this book do not count toward n=30."
    )


def paper_identity_block_reason(
    *,
    broker_account_number: object = None,
    state: dict[str, Any] | None = None,
) -> str | None:
    """Return a gateway block reason, or None when identity is unspecified or valid.

    Live broker account_number wins. Ledger paper_account.account_number is next.
    A $30k equity fingerprint on the ledger blocks even when the number is missing.
    Missing both (unit tests, empty tmp trees) is unspecified and does not block.
    """
    broker_number = normalize_account_number(broker_account_number)
    if broker_number:
        if broker_number == VALIDATION_PAPER_ACCOUNT_NUMBER:
            return None
        label = FORBIDDEN_PAPER_ACCOUNTS.get(broker_number, "unknown_account")
        return (
            f"WRONG_PAPER_ACCOUNT {broker_number} ({label}); "
            f"expected {VALIDATION_PAPER_ACCOUNT_NUMBER}"
        )

    paper = state.get("paper_account") if isinstance(state, dict) else None
    if not isinstance(paper, dict) or not paper:
        return None

    ledger_number = normalize_account_number(paper.get("account_number"))
    if ledger_number:
        if ledger_number == VALIDATION_PAPER_ACCOUNT_NUMBER:
            return None
        label = FORBIDDEN_PAPER_ACCOUNTS.get(ledger_number, "unknown_account")
        return (
            f"WRONG_PAPER_ACCOUNT {ledger_number} ({label}); "
            f"expected {VALIDATION_PAPER_ACCOUNT_NUMBER}"
        )

    try:
        equity = float(paper.get("equity") or paper.get("current_equity") or 0)
    except (TypeError, ValueError):
        equity = 0.0
    if _THIRTY_K_EQUITY_MIN <= equity <= _THIRTY_K_EQUITY_MAX:
        return (
            f"WRONG_PAPER_ACCOUNT equity={equity:.2f} matches the $30k book fingerprint; "
            f"expected {VALIDATION_PAPER_ACCOUNT_NUMBER}"
        )
    return None


def default_system_state_path() -> Path:
    """Canonical ledger path written by scripts/sync_alpaca_state.py."""
    return Path(__file__).resolve().parents[2] / "data" / "system_state.json"


def load_system_state(path: Path | None = None) -> dict[str, Any] | None:
    """Load system_state.json.

    Returns None only when the file is absent (unit tests, empty trees).
    Read or JSON failures raise PaperAccountIdentityError so callers fail closed.
    """
    state_path = path or default_system_state_path()
    if not state_path.exists():
        return None
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PaperAccountIdentityError(
            f"system_state unreadable at {state_path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise PaperAccountIdentityError(
            f"system_state is not an object at {state_path}"
        )
    return raw
