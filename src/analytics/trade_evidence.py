"""Verified trade evidence shared by analytics, ML, RAG, and health checks.

The broker order stream contains fills, legs, cancellations, and unmatched cash
flows.  Those records are useful for reconciliation, but they are not completed
trade outcomes.  This module keeps that boundary explicit:

* only paired, closed rows with numeric realized P/L enter performance metrics;
* unmatched orders remain quarantined reconciliation evidence;
* active-strategy learning can require the controlled-experiment fields; and
* every derived dataset carries deterministic lineage.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

STRATEGY_ALIASES = {
    "bull_put_credit": "spy_put_credit",
    "put_credit": "spy_put_credit",
    "spy_bull_put_credit": "spy_put_credit",
    "spy_put_credit": "spy_put_credit",
    "ic_simple": "iron_condor",
    "iron_condor": "iron_condor",
}

PUT_CREDIT_EXIT_REASONS = {
    "profit_target",
    "stop_loss",
    "dte_exit",
    "assignment_failsafe",
}


@dataclass(frozen=True)
class EvidenceMetrics:
    closed_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate_pct: float | None
    gross_profit: float
    gross_loss: float
    total_realized_pnl: float
    expectancy_per_trade: float | None
    profit_factor: float | None


@dataclass
class TradeEvidence:
    """Audited evidence and lineage for one optional strategy family."""

    strategy_family: str | None
    rows: list[dict[str, Any]]
    rejected_by_reason: dict[str, int]
    issues: list[str]
    warnings: list[str]
    metrics: EvidenceMetrics
    raw_row_count: int
    quarantined_unpaired_orders: int
    quarantined_unpaired_cash: float
    dataset_sha256: str
    protocol_fields_required: bool
    learning_ready: bool = field(init=False)

    def __post_init__(self) -> None:
        self.learning_ready = bool(self.rows) and not self.issues

    def to_dict(self, *, include_rows: bool = False) -> dict[str, Any]:
        payload = {
            "strategy_family": self.strategy_family,
            "metrics": asdict(self.metrics),
            "raw_row_count": self.raw_row_count,
            "verified_row_count": len(self.rows),
            "rejected_by_reason": dict(self.rejected_by_reason),
            "issues": list(self.issues),
            "warnings": list(self.warnings),
            "quarantined_unpaired_orders": self.quarantined_unpaired_orders,
            "quarantined_unpaired_cash": self.quarantined_unpaired_cash,
            "dataset_sha256": self.dataset_sha256,
            "protocol_fields_required": self.protocol_fields_required,
            "learning_ready": self.learning_ready,
        }
        if include_rows:
            payload["rows"] = self.rows
        return payload


def canonical_strategy(value: Any) -> str:
    """Normalize strategy labels without guessing unknown families."""

    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return STRATEGY_ALIASES.get(normalized, normalized)


def row_strategy(row: dict[str, Any]) -> str:
    return canonical_strategy(row.get("strategy_family") or row.get("strategy"))


def active_strategy_family(project_root: Path) -> str:
    """Resolve the active family from the machine-readable kill switch."""

    kill_path = project_root / "data" / "runtime" / "strategy_kill_switch.json"
    try:
        payload = json.loads(kill_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "iron_condor"
    return canonical_strategy(payload.get("active_family")) or "iron_condor"


def _as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 10:
        text = f"{text}T00:00:00"
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_expiry(row: dict[str, Any]) -> datetime | None:
    legs = row.get("legs") if isinstance(row.get("legs"), dict) else {}
    expiry = row.get("expiry") or legs.get("expiry")
    return _parse_timestamp(expiry)


def _put_credit_protocol_reasons(row: dict[str, Any]) -> list[str]:
    """Return controlled-experiment violations for a closed put credit."""

    reasons: list[str] = []
    if row.get("validation_phase") is not True:
        reasons.append("not_validation_phase")
    if str(row.get("profile_name") or "") != "spy-put-credit":
        reasons.append("wrong_profile")
    selection = str(
        row.get("selection_method") or row.get("strike_selection_method") or ""
    ).lower()
    if selection != "live_delta":
        reasons.append("unverified_strike_selection")

    delta = _as_float(row.get("put_delta", row.get("short_delta")))
    if delta is None or not 0.10 <= abs(delta) <= 0.22:
        reasons.append("delta_outside_protocol")

    quantity = _as_float(row.get("quantity"))
    if quantity is None or abs(quantity - 1.0) > 1e-9:
        reasons.append("quantity_outside_protocol")

    entry = _parse_timestamp(
        row.get("entry_time") or row.get("opened_at") or row.get("entry_date")
    )
    exit_at = _parse_timestamp(
        row.get("exit_time") or row.get("closed_at") or row.get("exit_date")
    )
    expiry = _extract_expiry(row)
    if entry is None or exit_at is None or expiry is None:
        reasons.append("missing_protocol_timestamps")
    else:
        dte = (expiry.date() - entry.date()).days
        if not 30 <= dte <= 45:
            reasons.append("dte_outside_protocol")
        hold_hours = (exit_at - entry).total_seconds() / 3600
        exit_reason = str(row.get("exit_reason") or "").lower()
        if hold_hours < 24 and exit_reason not in {"stop_loss", "assignment_failsafe"}:
            reasons.append("hold_under_24h")

    exit_reason = str(row.get("exit_reason") or "").lower()
    if exit_reason not in PUT_CREDIT_EXIT_REASONS:
        reasons.append("missing_or_invalid_exit_reason")

    strikes = row.get("strikes") if isinstance(row.get("strikes"), dict) else {}
    legs = row.get("legs") if isinstance(row.get("legs"), dict) else {}
    short_put = _as_float(strikes.get("short_put"))
    long_put = _as_float(strikes.get("long_put"))
    if short_put is None or long_put is None:
        put_strikes = legs.get("put_strikes") or []
        if isinstance(put_strikes, list) and len(put_strikes) == 2:
            parsed = [_as_float(value) for value in put_strikes]
            if all(value is not None for value in parsed):
                long_put, short_put = min(parsed), max(parsed)
    if short_put is None or long_put is None or abs((short_put - long_put) - 5.0) > 1e-9:
        reasons.append("wing_width_outside_protocol")

    return reasons


def _metrics(rows: list[dict[str, Any]]) -> EvidenceMetrics:
    pnls = [float(row["realized_pnl"]) for row in rows]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    breakeven = len(pnls) - len(wins) - len(losses)
    gross_profit = round(sum(wins), 2)
    gross_loss = round(abs(sum(losses)), 2)
    total = round(sum(pnls), 2)
    closed = len(pnls)
    return EvidenceMetrics(
        closed_trades=closed,
        wins=len(wins),
        losses=len(losses),
        breakeven=breakeven,
        win_rate_pct=round(len(wins) / closed * 100, 2) if closed else None,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        total_realized_pnl=total,
        expectancy_per_trade=round(total / closed, 2) if closed else None,
        profit_factor=round(gross_profit / gross_loss, 4) if gross_loss else None,
    )


def build_trade_evidence(
    payload: dict[str, Any],
    *,
    strategy_family: str | None = None,
    require_protocol_fields: bool = False,
) -> TradeEvidence:
    """Build a deterministic, row-derived trade dataset.

    ``stats`` is treated as a claim to audit, never as training labels.  The
    physical rows are always the source for derived performance metrics.
    """

    target = canonical_strategy(strategy_family) if strategy_family else None
    issues: list[str] = []
    warnings: list[str] = []
    rejected: Counter[str] = Counter()

    if not isinstance(payload, dict):
        payload = {}
        issues.append("ledger_payload_not_object")
    raw_rows = payload.get("trades", [])
    if not isinstance(raw_rows, list):
        raw_rows = []
        issues.append("ledger_trades_not_list")

    verified_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    invalid_candidate_rows = 0
    for raw in raw_rows:
        if not isinstance(raw, dict):
            rejected["row_not_object"] += 1
            continue
        if str(raw.get("status") or "").strip().lower() != "closed":
            rejected["not_closed"] += 1
            continue

        family = row_strategy(raw)
        if not family:
            rejected["missing_strategy_family"] += 1
            if target is None:
                invalid_candidate_rows += 1
            continue
        if target and family != target:
            rejected["different_strategy_family"] += 1
            continue

        trade_id = str(raw.get("id") or "").strip()
        if not trade_id:
            rejected["missing_trade_id"] += 1
            invalid_candidate_rows += 1
            continue
        if trade_id in seen_ids:
            rejected["duplicate_trade_id"] += 1
            issues.append(f"duplicate_trade_id:{trade_id}")
            invalid_candidate_rows += 1
            continue
        seen_ids.add(trade_id)

        pnl = _as_float(raw.get("realized_pnl"))
        if pnl is None:
            rejected["missing_or_invalid_realized_pnl"] += 1
            invalid_candidate_rows += 1
            continue

        entry = _parse_timestamp(
            raw.get("entry_time") or raw.get("opened_at") or raw.get("entry_date")
        )
        exit_at = _parse_timestamp(
            raw.get("exit_time") or raw.get("closed_at") or raw.get("exit_date")
        )
        if entry is None or exit_at is None or exit_at < entry:
            rejected["invalid_trade_timestamps"] += 1
            invalid_candidate_rows += 1
            continue

        outcome = str(raw.get("outcome") or "").strip().lower()
        expected_outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"
        if outcome and outcome != expected_outcome:
            rejected["outcome_pnl_mismatch"] += 1
            invalid_candidate_rows += 1
            continue

        if require_protocol_fields and family == "spy_put_credit":
            protocol_reasons = _put_credit_protocol_reasons(raw)
            if protocol_reasons:
                for reason in set(protocol_reasons):
                    rejected[reason] += 1
                invalid_candidate_rows += 1
                continue

        normalized = dict(raw)
        normalized["strategy_family"] = family
        normalized["realized_pnl"] = pnl
        normalized["outcome"] = expected_outcome
        normalized["evidence_status"] = "verified_paired_closed_trade"
        verified_rows.append(normalized)

    stats = payload.get("stats", {}) if isinstance(payload.get("stats"), dict) else {}
    unpaired_count = int(_as_float(stats.get("unpaired_order_count")) or 0)
    unpaired_cash = float(_as_float(stats.get("unpaired_realized_pnl")) or 0.0)
    reported_closed = int(_as_float(stats.get("closed_trades")) or 0)
    reported_total = _as_float(stats.get("total_realized_pnl", stats.get("total_pnl")))

    physical_metrics = _metrics(
        [
            {
                **row,
                "realized_pnl": float(row.get("realized_pnl") or 0.0),
            }
            for row in raw_rows
            if isinstance(row, dict)
            and str(row.get("status") or "").lower() == "closed"
            and _as_float(row.get("realized_pnl")) is not None
        ]
    )
    if unpaired_count:
        warnings.append(
            f"{unpaired_count} unmatched orders are quarantined from edge and learning metrics"
        )
    if invalid_candidate_rows:
        issues.append(
            f"{invalid_candidate_rows} closed "
            f"{target or 'ledger'} row(s) failed evidence validation"
        )
    if reported_closed and reported_closed != physical_metrics.closed_trades:
        if reported_closed == physical_metrics.closed_trades + unpaired_count:
            issues.append("reported closed_trades mixes paired trades with unmatched orders")
        else:
            issues.append(
                "reported closed_trades does not reconcile with physical closed rows "
                f"({reported_closed} != {physical_metrics.closed_trades})"
            )
    if reported_total is not None and abs(
        reported_total - physical_metrics.total_realized_pnl
    ) > 0.01:
        if abs(
            reported_total - (physical_metrics.total_realized_pnl + unpaired_cash)
        ) <= 0.01:
            issues.append("reported total_realized_pnl mixes paired P/L with unmatched cash")
        else:
            issues.append(
                "reported total_realized_pnl does not reconcile with physical rows "
                f"({reported_total:.2f} != {physical_metrics.total_realized_pnl:.2f})"
            )

    if not verified_rows:
        warnings.append(
            f"no verified closed rows for {target or 'any strategy'}"
        )

    serialized = json.dumps(
        verified_rows,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    digest = hashlib.sha256(serialized).hexdigest()
    return TradeEvidence(
        strategy_family=target,
        rows=verified_rows,
        rejected_by_reason=dict(sorted(rejected.items())),
        issues=issues,
        warnings=warnings,
        metrics=_metrics(verified_rows),
        raw_row_count=len(raw_rows),
        quarantined_unpaired_orders=unpaired_count,
        quarantined_unpaired_cash=round(unpaired_cash, 2),
        dataset_sha256=digest,
        protocol_fields_required=require_protocol_fields,
    )
