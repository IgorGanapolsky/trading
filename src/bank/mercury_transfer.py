"""Mercury AI bank ↔ brokerage transfer planner/executor.

Default is dry-run. Real transfers require live_bank gate AND MERCURY_API_ENABLED=1
plus vaulted credentials. No secrets in code or logs.
"""

from __future__ import annotations

import logging
import os
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
    """Check env flags only — never echo secret values."""
    enabled = os.environ.get("MERCURY_API_ENABLED", "").lower() in {"1", "true", "yes"}
    if not enabled:
        return False, "MERCURY_API_ENABLED not set (real ACH disabled)"
    # Credential presence without loading secrets into logs
    key_set = bool(os.environ.get("MERCURY_API_KEY") or os.environ.get("MERCURY_TOKEN"))
    if not key_set:
        # Optional vault file path presence
        vault = Path.home() / ".resume_secrets" / "mercury.json"
        if not vault.is_file():
            return False, "no MERCURY_API_KEY/MERCURY_TOKEN and no ~/.resume_secrets/mercury.json"
    return True, "mercury_credentials_present"


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
    direction_s = (
        direction.value if isinstance(direction, TransferDirection) else str(direction)
    )
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
        # Real Mercury ACH is not implemented without vendor API contract.
        # Fail closed rather than pretend a transfer succeeded.
        rec = build_transfer_record(
            direction=direction_s,
            amount_usd=amount_usd,
            status=TransferStatus.FAILED,
            dry_run=False,
            reason=reason or "real_transfer_requested",
            block_reason=(
                "Mercury live ACH executor not configured for production API; "
                "refusing fabricated transfer receipt"
            ),
            metadata={"api": api_msg},
        )
        append_transfer_record(rec, ledger_path=ledger_path)
        return TransferPlanResult(
            ok=False,
            dry_run=False,
            blocked=True,
            record=rec.as_dict(),
            message=rec.block_reason,
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
