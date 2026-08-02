"""After-tax remittance progress toward $1000/mo bank deposits.

Never reports the monthly target as achieved without ledger evidence of
broker_to_mercury remittances (and optional realized P/L inputs).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Iterable

from src.bank.transfer_ledger import TransferDirection, TransferRecord

# Goal remittance target (user: $1000/mo after-tax). Distinct from North Star $6000.
MONTHLY_AFTER_TAX_TARGET_USD = 1000.0

# Conservative default short-term capital gains rate for SPY equity options (federal+state est.)
DEFAULT_SHORT_TERM_TAX_RATE = 0.37


@dataclass(frozen=True)
class RemittanceProgress:
    """Progress toward monthly after-tax bank remittance — ledger facts only."""

    month_yyyy_mm: str
    target_usd: float
    remitted_to_bank_usd: float
    remittance_event_count: int
    in_flight_usd: float
    in_flight_event_count: int
    estimated_after_tax_profit_usd: float | None
    realized_pre_tax_pnl_usd: float | None
    tax_rate_used: float
    pct_of_target: float | None
    target_met: bool
    claim_allowed: bool
    note: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def estimate_after_tax_profit(
    realized_pre_tax_pnl: float,
    *,
    tax_rate: float = DEFAULT_SHORT_TERM_TAX_RATE,
    long_term_fraction: float = 0.0,
    long_term_tax_rate: float = 0.20,
) -> float:
    """Estimate after-tax profit from realized pre-tax P/L (pure function).

    Losses: tax benefit is not auto-assumed as cash remittance — returns pnl
    unchanged when negative (no fabricated refund).
    """
    pnl = float(realized_pre_tax_pnl)
    if pnl <= 0:
        return round(pnl, 2)
    lt = max(0.0, min(1.0, float(long_term_fraction)))
    st = 1.0 - lt
    tax = pnl * (st * float(tax_rate) + lt * float(long_term_tax_rate))
    return round(pnl - tax, 2)


def _month_key(ts: str, *, fallback: str | None = None) -> str:
    if ts:
        # Accept ISO; take first 7 chars YYYY-MM when possible
        try:
            if "T" in ts or "+" in ts or ts.endswith("Z"):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.strftime("%Y-%m")
        except ValueError:
            pass
        if len(ts) >= 7 and ts[4] == "-":
            return ts[:7]
    if fallback:
        return fallback
    return datetime.now(UTC).strftime("%Y-%m")


def compute_remittance_progress(
    records: Iterable[TransferRecord],
    *,
    month_yyyy_mm: str | None = None,
    target_usd: float = MONTHLY_AFTER_TAX_TARGET_USD,
    realized_pre_tax_pnl_usd: float | None = None,
    tax_rate: float = DEFAULT_SHORT_TERM_TAX_RATE,
) -> RemittanceProgress:
    """Compute monthly remittance progress from transfer ledger facts.

    ``target_met`` / ``claim_allowed`` require **confirmed** (dry_run=false)
    broker→Mercury deposits summing to >= target. SUBMITTED is tracked only as
    ``in_flight_usd`` and never unlocks the claim (AC3 / skeptic).
    """
    month = month_yyyy_mm or datetime.now(UTC).strftime("%Y-%m")
    remitted = 0.0
    n_events = 0
    in_flight = 0.0
    n_in_flight = 0
    for rec in records:
        if rec.direction != TransferDirection.BROKER_TO_MERCURY.value:
            continue
        if rec.dry_run:
            continue
        if _month_key(rec.timestamp, fallback=month) != month:
            continue
        status = str(rec.status or "").lower()
        amount = float(rec.amount_usd or 0)
        if status == "confirmed":
            remitted += amount
            n_events += 1
        elif status == "submitted":
            # In-flight ACH — not bank evidence of completed remittance
            in_flight += amount
            n_in_flight += 1

    remitted = round(remitted, 2)
    in_flight = round(in_flight, 2)
    after_tax: float | None = None
    if realized_pre_tax_pnl_usd is not None:
        after_tax = estimate_after_tax_profit(float(realized_pre_tax_pnl_usd), tax_rate=tax_rate)

    target = float(target_usd)
    pct = round(100.0 * remitted / target, 2) if target > 0 else None
    # Confirmed deposits only
    target_met = remitted + 1e-9 >= target and n_events > 0
    claim_allowed = target_met and remitted > 0

    if n_events == 0:
        note = (
            f"No confirmed broker→Mercury remittances in {month}. "
            f"Cannot claim ${target:.0f}/mo after-tax target met."
        )
        if n_in_flight:
            note += f" In-flight (submitted, not confirmed): ${in_flight:.2f}."
    elif not target_met:
        note = (
            f"Confirmed remitted ${remitted:.2f} of ${target:.0f} target in {month} "
            f"({n_events} deposit(s))."
        )
        if n_in_flight:
            note += f" In-flight: ${in_flight:.2f} (not counted toward target)."
    else:
        note = (
            f"Ledger shows ${remitted:.2f} confirmed remitted to bank in {month} "
            f"(>= ${target:.0f} target) across {n_events} deposit(s)."
        )

    return RemittanceProgress(
        month_yyyy_mm=month,
        target_usd=target,
        remitted_to_bank_usd=remitted,
        remittance_event_count=n_events,
        in_flight_usd=in_flight,
        in_flight_event_count=n_in_flight,
        estimated_after_tax_profit_usd=after_tax,
        realized_pre_tax_pnl_usd=(
            float(realized_pre_tax_pnl_usd) if realized_pre_tax_pnl_usd is not None else None
        ),
        tax_rate_used=float(tax_rate),
        pct_of_target=pct,
        target_met=bool(target_met and claim_allowed),
        claim_allowed=claim_allowed,
        note=note,
    )
