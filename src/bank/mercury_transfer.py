"""Mercury AI bank ↔ brokerage transfer planner/executor.

Default is dry-run. Real transfers require live_bank gate AND MercuryBankAdapter
env vars (MERCURY_API_TOKEN, MERCURY_ACCOUNT_ID, MERCURY_LIVE_TRANSFERS_ENABLED=1,
MERCURY_RECIPIENT_ID). No secrets in code or logs.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.bank.live_gate import evaluate_live_bank_gate
from src.bank.transfer_ledger import (
    TransferDirection,
    TransferStatus,
    append_transfer_record,
    build_transfer_record,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TransferPlanResult:
    ok: bool
    dry_run: bool
    blocked: bool
    record: dict[str, Any]
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "dry_run": self.dry_run,
            "blocked": self.blocked,
            "record": self.record,
            "message": self.message,
        }


def _mercury_api_ready() -> tuple[bool, str]:
    """Check env flags only — never echo secret values.

    Supports both the canonical MercuryBankAdapter env vars and the legacy
    MERCURY_API_ENABLED flag for backward compatibility.
    """
    # Legacy flag (still accepted for backward compat)
    legacy_enabled = os.environ.get("MERCURY_API_ENABLED", "").lower() in {"1", "true", "yes"}

    # Canonical MercuryBankAdapter env vars
    token = (
        os.environ.get("MERCURY_API_TOKEN")
        or os.environ.get("MERCURY_API_KEY")
        or os.environ.get("MERCURY_TOKEN")
    )
    account_id = os.environ.get("MERCURY_ACCOUNT_ID")
    live_enabled = os.environ.get("MERCURY_LIVE_TRANSFERS_ENABLED") == "1"
    recipient_id = os.environ.get("MERCURY_RECIPIENT_ID")

    if not (legacy_enabled or live_enabled):
        return False, "MERCURY_LIVE_TRANSFERS_ENABLED=1 not set (real ACH disabled)"
    if not token:
        return False, "no MERCURY_API_TOKEN/MERCURY_API_KEY/MERCURY_TOKEN set"
    if not account_id:
        return False, "no MERCURY_ACCOUNT_ID set"
    if not recipient_id:
        return False, "no MERCURY_RECIPIENT_ID set"
    return True, "mercury_credentials_present"


def _execute_real_transfer(
    *,
    direction: str,
    amount_usd: float,
    reason: str,
    ledger_path: Path | None,
    gate: Any,
) -> TransferPlanResult:
    """Execute a real Mercury ACH transfer via MercuryBankAdapter.

    MERCURY_TO_BROKER: uses MercuryBankAdapter.send_to_broker() (real ACH push).
    BROKER_TO_MERCURY: uses MercuryBankAdapter.record_incoming_from_broker()
    (reconciliation only — Mercury has no pull API; the broker must initiate
    the return leg).
    """
    from src.adapters.bank_adapter import MercuryBankAdapter

    recipient_id = os.environ.get("MERCURY_RECIPIENT_ID", "")
    try:
        bank = MercuryBankAdapter.from_env(recipient_id=recipient_id)
    except (ValueError, RuntimeError) as exc:
        rec = build_transfer_record(
            direction=direction,
            amount_usd=amount_usd,
            status=TransferStatus.BLOCKED,
            dry_run=False,
            reason=reason or "real_transfer_requested",
            block_reason=f"MercuryBankAdapter construction failed: {exc}",
            metadata={"gate_allowed": gate.allowed},
        )
        append_transfer_record(rec, ledger_path=ledger_path)
        return TransferPlanResult(
            ok=False,
            dry_run=False,
            blocked=True,
            record=rec.as_dict(),
            message=f"BANK TRANSFER REFUSED: {rec.block_reason}",
        )

    idempotency_key = f"income_loop_{uuid.uuid4().hex[:16]}"

    if direction == TransferDirection.MERCURY_TO_BROKER.value:
        # Real ACH push from Mercury to broker
        transfer = bank.send_to_broker(amount_usd, idempotency_key=idempotency_key)
        status = TransferStatus.CONFIRMED if transfer.success else TransferStatus.FAILED
        block_reason = transfer.error or ""
        external_ref = transfer.transfer_id or ""
    else:
        # BROKER_TO_MERCURY: reconciliation only (Mercury can't pull)
        transfer = bank.record_incoming_from_broker(amount_usd)
        status = TransferStatus.CONFIRMED if transfer.success else TransferStatus.FAILED
        block_reason = transfer.error or ""
        external_ref = transfer.transfer_id or ""

    rec = build_transfer_record(
        direction=direction,
        amount_usd=amount_usd,
        status=status,
        dry_run=False,
        reason=reason or "real_transfer_executed",
        block_reason=block_reason,
        external_ref=external_ref,
        metadata={"gate_allowed": gate.allowed},
    )
    append_transfer_record(rec, ledger_path=ledger_path)
    return TransferPlanResult(
        ok=transfer.success,
        dry_run=False,
        blocked=not transfer.success,
        record=rec.as_dict(),
        message=(
            f"REAL {direction} ${amount_usd:.2f} {status.value.upper()}"
            + (f" (ref: {external_ref})" if external_ref else "")
        ),
    )


def plan_transfer(
    *,
    direction: TransferDirection | str,
    amount_usd: float,
    dry_run: bool = True,
    reason: str = "",
    ledger_path: Path | None = None,
    force_execute: bool = False,
) -> TransferPlanResult:
    """Plan (and optionally execute) a Mercury↔broker transfer.

    Real execution requires: dry_run=False, force_execute=True, live gate allowed,
    and Mercury API ready. Otherwise logs a dry_run or blocked record.
    """
    direction_s = direction.value if isinstance(direction, TransferDirection) else str(direction)
    gate = evaluate_live_bank_gate()
    want_real = (not dry_run) and force_execute

    if want_real and not gate.bank_transfer_allowed:
        rec = build_transfer_record(
            direction=direction_s,
            amount_usd=amount_usd,
            status=TransferStatus.BLOCKED,
            dry_run=False,
            reason=reason or "real_transfer_requested",
            block_reason="; ".join(gate.blockers) or "live_bank_gate_denied",
            metadata={"gate": gate.as_dict()},
        )
        append_transfer_record(rec, ledger_path=ledger_path)
        return TransferPlanResult(
            ok=False,
            dry_run=False,
            blocked=True,
            record=rec.as_dict(),
            message=f"BANK TRANSFER REFUSED: {rec.block_reason}",
        )

    if want_real:
        api_ok, api_msg = _mercury_api_ready()
        if not api_ok:
            rec = build_transfer_record(
                direction=direction_s,
                amount_usd=amount_usd,
                status=TransferStatus.BLOCKED,
                dry_run=False,
                reason=reason or "real_transfer_requested",
                block_reason=api_msg,
                metadata={"gate_allowed": gate.allowed},
            )
            append_transfer_record(rec, ledger_path=ledger_path)
            return TransferPlanResult(
                ok=False,
                dry_run=False,
                blocked=True,
                record=rec.as_dict(),
                message=f"BANK TRANSFER REFUSED: {api_msg}",
            )
        # Execute real transfer via MercuryBankAdapter
        return _execute_real_transfer(
            direction=direction_s,
            amount_usd=amount_usd,
            reason=reason,
            ledger_path=ledger_path,
            gate=gate,
        )

    # Dry-run / plan path — always allowed for operator readiness
    rec = build_transfer_record(
        direction=direction_s,
        amount_usd=amount_usd,
        status=TransferStatus.DRY_RUN,
        dry_run=True,
        reason=reason or "dry_run_plan",
        metadata={
            "gate_allowed": gate.allowed,
            "gate_blockers": list(gate.blockers),
            "would_execute_if_gates_clear": True,
        },
    )
    append_transfer_record(rec, ledger_path=ledger_path)
    return TransferPlanResult(
        ok=True,
        dry_run=True,
        blocked=False,
        record=rec.as_dict(),
        message=(
            f"DRY-RUN {direction_s} ${float(amount_usd):.2f} planned and logged "
            f"(live gate allowed={gate.allowed})"
        ),
    )


def plan_fund_from_mercury(
    amount_usd: float, *, dry_run: bool = True, **kwargs: Any
) -> TransferPlanResult:
    return plan_transfer(
        direction=TransferDirection.MERCURY_TO_BROKER,
        amount_usd=amount_usd,
        dry_run=dry_run,
        reason=kwargs.pop("reason", "fund_broker_from_mercury"),
        **kwargs,
    )


def plan_remit_to_mercury(
    amount_usd: float, *, dry_run: bool = True, **kwargs: Any
) -> TransferPlanResult:
    return plan_transfer(
        direction=TransferDirection.BROKER_TO_MERCURY,
        amount_usd=amount_usd,
        dry_run=dry_run,
        reason=kwargs.pop("reason", "remit_proceeds_to_mercury"),
        **kwargs,
    )
