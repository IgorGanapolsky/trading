"""Bank adapter abstraction for the Mercury withdraw/deposit income loop.

BankAdapter is the seam between orchestration logic (scripts/mercury_income_loop.py)
and a real bank API. PaperBankAdapter is safe by construction - it never makes a
network call and never touches real money, so it is the default everywhere.
MercuryBankAdapter wraps the real Mercury API and refuses to construct without
explicit credentials; nothing in this repo wires it up to run automatically.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MERCURY_API_BASE_URL = "https://backend.mercury.com/api/v1"


@dataclass(frozen=True)
class TransferResult:
    """Outcome of a single push-payment attempt."""

    success: bool
    transfer_id: str | None
    amount_usd: float
    direction: str  # "to_broker" or "to_bank"
    initiated_at: str
    error: str | None = None


@dataclass(frozen=True)
class BankBalance:
    account_id: str
    available_usd: float
    observed_at: str


class BankAdapter(ABC):
    """Minimal interface an income-loop orchestrator needs from a bank."""

    @abstractmethod
    def get_balance(self) -> BankBalance:
        """Return current available balance."""

    @abstractmethod
    def send_to_broker(self, amount_usd: float, idempotency_key: str) -> TransferResult:
        """Push funds from the bank to the configured brokerage recipient."""

    @abstractmethod
    def record_incoming_from_broker(self, amount_usd: float) -> TransferResult:
        """Record funds that the broker has pushed back to this bank account.

        Mercury has no "pull from an external account" API (confirmed 2026-07-25
        research) - the return leg must be initiated on the broker's side. This
        method exists so the orchestrator has one call to make either way; real
        adapters implement it as a reconciliation/confirmation step, not a pull.
        """


class PaperBankAdapter(BankAdapter):
    """In-memory simulation. No network calls. Safe default for all runs."""

    def __init__(self, starting_balance_usd: float = 0.0):
        self._balance = starting_balance_usd
        self._transfers: list[TransferResult] = []

    def get_balance(self) -> BankBalance:
        return BankBalance(
            account_id="paper-mercury-sim",
            available_usd=self._balance,
            observed_at=datetime.now(UTC).isoformat(),
        )

    def send_to_broker(self, amount_usd: float, idempotency_key: str) -> TransferResult:
        if amount_usd <= 0:
            result = TransferResult(
                success=False,
                transfer_id=None,
                amount_usd=amount_usd,
                direction="to_broker",
                initiated_at=datetime.now(UTC).isoformat(),
                error="amount_usd must be positive",
            )
            self._transfers.append(result)
            return result
        if amount_usd > self._balance:
            result = TransferResult(
                success=False,
                transfer_id=None,
                amount_usd=amount_usd,
                direction="to_broker",
                initiated_at=datetime.now(UTC).isoformat(),
                error=f"insufficient balance: have ${self._balance:.2f}, need ${amount_usd:.2f}",
            )
            self._transfers.append(result)
            return result
        self._balance -= amount_usd
        result = TransferResult(
            success=True,
            transfer_id=f"paper-{idempotency_key}",
            amount_usd=amount_usd,
            direction="to_broker",
            initiated_at=datetime.now(UTC).isoformat(),
        )
        self._transfers.append(result)
        return result

    def record_incoming_from_broker(self, amount_usd: float) -> TransferResult:
        self._balance += amount_usd
        result = TransferResult(
            success=True,
            transfer_id=f"paper-{uuid.uuid4()}",
            amount_usd=amount_usd,
            direction="to_bank",
            initiated_at=datetime.now(UTC).isoformat(),
        )
        self._transfers.append(result)
        return result


@dataclass
class MercuryBankAdapter(BankAdapter):
    """Real Mercury API wrapper. Never used unless explicitly constructed with a
    live token AND MERCURY_LIVE_TRANSFERS_ENABLED=1 is set - this is the same
    "paper by default, explicit opt-in for real money" pattern the rest of this
    repo uses for the live Alpaca account.
    """

    account_id: str
    recipient_id: str
    _api_token: str = field(repr=False)
    _live_enabled: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if not self._api_token:
            raise ValueError(
                "MercuryBankAdapter requires MERCURY_API_TOKEN. Never hardcode this; "
                "load it via an env var, same as get_alpaca_credentials()."
            )
        if not self._live_enabled:
            raise RuntimeError(
                "MercuryBankAdapter constructed without MERCURY_LIVE_TRANSFERS_ENABLED=1. "
                "This is a deliberate hard stop: real money must never move because a "
                "script imported this class. Set the env var only after explicit sign-off "
                "on a specific transfer plan."
            )

    @classmethod
    def from_env(cls, recipient_id: str, secrets_path: Path | None = None) -> MercuryBankAdapter:
        token = os.environ.get("MERCURY_API_TOKEN")
        account_id = os.environ.get("MERCURY_ACCOUNT_ID")
        live_enabled = os.environ.get("MERCURY_LIVE_TRANSFERS_ENABLED") == "1"

        if not token or not account_id:
            env_secrets_path = os.environ.get("MERCURY_SECRETS_PATH")
            path = secrets_path or (
                Path(env_secrets_path)
                if env_secrets_path
                else Path.home() / ".resume_secrets" / "mercury.json"
            )
            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        secrets = json.load(handle)
                        token = token or secrets.get("MERCURY_API_TOKEN")
                        account_id = account_id or secrets.get("MERCURY_ACCOUNT_ID")
                except Exception:
                    pass

        if not token or not account_id:
            raise ValueError("MERCURY_API_TOKEN and MERCURY_ACCOUNT_ID must be set")
        return cls(
            account_id=account_id,
            recipient_id=recipient_id,
            _api_token=token,
            _live_enabled=live_enabled,
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_token}"}

    def get_balance(self) -> BankBalance:
        import requests

        resp = requests.get(
            f"{MERCURY_API_BASE_URL}/account/{self.account_id}",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        payload: dict[str, Any] = resp.json()
        return BankBalance(
            account_id=self.account_id,
            available_usd=float(payload.get("availableBalance", 0.0)),
            observed_at=datetime.now(UTC).isoformat(),
        )

    def send_to_broker(self, amount_usd: float, idempotency_key: str) -> TransferResult:
        import requests

        try:
            resp = requests.post(
                f"{MERCURY_API_BASE_URL}/account/{self.account_id}/transactions",
                headers={**self._headers(), "Idempotency-Key": idempotency_key},
                json={
                    "recipientId": self.recipient_id,
                    "amount": amount_usd,
                    "paymentMethod": "ach",
                },
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
            return TransferResult(
                success=True,
                transfer_id=str(payload.get("id")),
                amount_usd=amount_usd,
                direction="to_broker",
                initiated_at=datetime.now(UTC).isoformat(),
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to caller via result, not raised
            logger.error("Mercury transfer failed: %s", exc)
            return TransferResult(
                success=False,
                transfer_id=None,
                amount_usd=amount_usd,
                direction="to_broker",
                initiated_at=datetime.now(UTC).isoformat(),
                error=str(exc),
            )

    def record_incoming_from_broker(self, amount_usd: float) -> TransferResult:
        # Mercury cannot pull; this only reconciles a webhook-confirmed deposit
        # that the broker already pushed. See module docstring.
        return TransferResult(
            success=True,
            transfer_id=f"reconcile-{uuid.uuid4()}",
            amount_usd=amount_usd,
            direction="to_bank",
            initiated_at=datetime.now(UTC).isoformat(),
        )
