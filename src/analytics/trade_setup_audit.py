"""Trade setup audit for the canonical closed-trade ledger."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ET_TZ = ZoneInfo("America/New_York")
_DELTA_PROVENANCE_FIELDS = (
    "selection_method",
    "strike_selection_method",
    "target_delta",
    "short_delta",
    "put_delta",
    "call_delta",
)
_HOLD_BUCKET_ORDER = {"<1h": 0, "1-4h": 1, "4-24h": 2, "1-3d": 3, ">3d": 4, "unknown": 5}
_DTE_BUCKET_ORDER = {
    "21-24": 0,
    "25-29": 1,
    "30-34": 2,
    "35-39": 3,
    "40-45": 4,
    "46+": 5,
    "unknown": 6,
}
_QTY_BUCKET_ORDER = {"1": 0, "2": 1, "3+": 2, "unknown": 3}


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${value:,.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}%"


def _normalize_outcome(pnl: float, raw_outcome: Any) -> str:
    text = str(raw_outcome or "").strip().lower()
    if text in {"win", "loss", "breakeven"}:
        return text
    if pnl > 0:
        return "win"
    if pnl < 0:
        return "loss"
    return "breakeven"


def _bucket_hold_hours(hours: float | None) -> str:
    if hours is None:
        return "unknown"
    if hours < 1:
        return "<1h"
    if hours < 4:
        return "1-4h"
    if hours < 24:
        return "4-24h"
    if hours < 72:
        return "1-3d"
    return ">3d"


def _bucket_dte(dte: int | None) -> str:
    if dte is None:
        return "unknown"
    if dte <= 24:
        return "21-24"
    if dte <= 29:
        return "25-29"
    if dte <= 34:
        return "30-34"
    if dte <= 39:
        return "35-39"
    if dte <= 45:
        return "40-45"
    return "46+"


def _bucket_qty(qty: float | None) -> str:
    if qty is None:
        return "unknown"
    qty_int = int(round(qty))
    if qty_int <= 1:
        return "1"
    if qty_int == 2:
        return "2"
    return "3+"


def _profit_factor(gross_profit: float, gross_loss: float) -> float | None:
    if gross_loss == 0:
        return None if gross_profit == 0 else float("inf")
    return gross_profit / gross_loss


def _structure_family(legs: dict[str, Any]) -> str:
    puts = legs.get("put_strikes") if isinstance(legs, dict) else None
    calls = legs.get("call_strikes") if isinstance(legs, dict) else None
    if not isinstance(puts, list) or not isinstance(calls, list) or len(puts) != 2 or len(calls) != 2:
        return "unknown"
    try:
        short_put = int(max(float(puts[0]), float(puts[1])))
        short_call = int(min(float(calls[0]), float(calls[1])))
        width = int(abs(float(puts[1]) - float(puts[0])))
    except (TypeError, ValueError):
        return "unknown"
    return f"P{short_put}/C{short_call} width{width}"


def _candidate_nonzero_float(rows: list[dict[str, Any]], field: str) -> float | None:
    for row in rows:
        value = _safe_float(row.get(field), 0.0)
        if value > 0:
            return value
    return None


def _build_outcome_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    wins = [item for item in items if item.get("outcome") == "win"]
    losses = [item for item in items if item.get("outcome") == "loss"]
    breakeven = [item for item in items if item.get("outcome") == "breakeven"]

    gross_profit = round(sum(_safe_float(item.get("realized_pnl"), 0.0) for item in wins), 2)
    gross_loss = round(
        abs(sum(_safe_float(item.get("realized_pnl"), 0.0) for item in losses)),
        2,
    )
    total_pnl = round(sum(_safe_float(item.get("realized_pnl"), 0.0) for item in items), 2)
    avg_win = round(gross_profit / len(wins), 2) if wins else None
    avg_loss = round(gross_loss / len(losses), 2) if losses else None
    profit_factor = _profit_factor(gross_profit, gross_loss)

    expectancy = None
    break_even_win_rate_pct = None
    if total > 0 and avg_win is not None and avg_loss is not None:
        loss_rate = len(losses) / total
        win_rate = len(wins) / total
        expectancy = round((win_rate * avg_win) - (loss_rate * avg_loss), 2)
        if avg_win + avg_loss > 0:
            break_even_win_rate_pct = round((avg_loss / (avg_win + avg_loss)) * 100, 2)

    return {
        "count": total,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate_pct": round((len(wins) / total) * 100, 2) if total else 0.0,
        "total_pnl": total_pnl,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": None if profit_factor is None else round(profit_factor, 4),
        "expectancy_per_trade": expectancy,
        "break_even_win_rate_pct": break_even_win_rate_pct,
    }


def _normalize_closed_trade_rows(trades: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trade in trades:
        if not isinstance(trade, dict) or str(trade.get("status") or "").lower() != "closed":
            continue

        entry_dt = _parse_iso(trade.get("entry_time"))
        exit_dt = _parse_iso(trade.get("exit_time"))
        legs = trade.get("legs") if isinstance(trade.get("legs"), dict) else {}
        expiry = str(legs.get("expiry") or "").strip() or None
        entry_date = str(trade.get("entry_date") or "").strip() or None
        if not entry_date and entry_dt is not None:
            entry_date = entry_dt.astimezone(ET_TZ).date().isoformat()

        dte = None
        if entry_date and expiry:
            try:
                dte = (date.fromisoformat(expiry) - date.fromisoformat(entry_date)).days
            except ValueError:
                dte = None

        quantity = _safe_float(trade.get("quantity"), 1.0)
        if quantity <= 0:
            quantity = 1.0

        signature = str(trade.get("signature") or trade.get("id") or "UNKNOWN")
        entry_time_raw = str(trade.get("entry_time") or "") or None
        setup_key = f"{entry_time_raw or entry_date or 'unknown'}::{signature}"
        realized_pnl = round(_safe_float(trade.get("realized_pnl"), 0.0), 2)

        rows.append(
            {
                "id": str(trade.get("id") or ""),
                "setup_key": setup_key,
                "entry_time": entry_time_raw,
                "exit_time": str(trade.get("exit_time") or "") or None,
                "entry_dt": entry_dt,
                "exit_dt": exit_dt,
                "entry_date": entry_date,
                "exit_date": str(trade.get("exit_date") or "").strip() or None,
                "entry_hour_et": entry_dt.astimezone(ET_TZ).hour if entry_dt else None,
                "signature": signature,
                "family": _structure_family(legs),
                "expiry": expiry,
                "dte": dte,
                "quantity": quantity,
                "entry_credit": round(_safe_float(trade.get("entry_credit"), 0.0), 2),
                "exit_debit": round(_safe_float(trade.get("exit_debit"), 0.0), 2),
                "realized_pnl": realized_pnl,
                "outcome": _normalize_outcome(realized_pnl, trade.get("outcome")),
                "source": str(trade.get("source") or ""),
                "legs": legs,
                "raw": trade,
            }
        )
    return rows


def _collapse_rows_into_setups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["setup_key"]].append(row)

    setups: list[dict[str, Any]] = []
    for setup_rows in grouped.values():
        entry_row = min(
            setup_rows,
            key=lambda row: (row.get("entry_dt") or datetime.max.replace(tzinfo=timezone.utc)),
        )
        exit_row = max(
            setup_rows,
            key=lambda row: (row.get("exit_dt") or row.get("entry_dt") or datetime.min.replace(tzinfo=timezone.utc)),
        )
        entry_dt = entry_row.get("entry_dt")
        exit_dt = exit_row.get("exit_dt") or entry_dt

        hold_hours = None
        same_day = None
        if entry_dt is not None and exit_dt is not None:
            hold_hours = round((exit_dt - entry_dt).total_seconds() / 3600, 2)
            same_day = entry_dt.astimezone(ET_TZ).date() == exit_dt.astimezone(ET_TZ).date()

        total_pnl = round(sum(_safe_float(row.get("realized_pnl"), 0.0) for row in setup_rows), 2)
        quantity = _candidate_nonzero_float(setup_rows, "quantity")
        entry_credit = _candidate_nonzero_float(setup_rows, "entry_credit")
        outcome = _normalize_outcome(total_pnl, None)

        setups.append(
            {
                "setup_key": entry_row["setup_key"],
                "signature": entry_row["signature"],
                "family": entry_row["family"],
                "entry_time": entry_row["entry_time"],
                "exit_time": exit_dt.isoformat() if exit_dt else None,
                "entry_date": entry_row["entry_date"],
                "exit_date": exit_dt.astimezone(ET_TZ).date().isoformat() if exit_dt else None,
                "entry_hour_et": entry_row["entry_hour_et"],
                "expiry": entry_row["expiry"],
                "dte": entry_row["dte"],
                "dte_bucket": _bucket_dte(entry_row["dte"]),
                "quantity": quantity,
                "qty_bucket": _bucket_qty(quantity),
                "entry_credit": entry_credit,
                "realized_pnl": total_pnl,
                "outcome": outcome,
                "row_count": len(setup_rows),
                "extra_rows_from_partial_exits": max(0, len(setup_rows) - 1),
                "hold_hours": hold_hours,
                "hold_bucket": _bucket_hold_hours(hold_hours),
                "same_day": same_day,
                "sources": sorted({row.get("source") for row in setup_rows if row.get("source")}),
            }
        )

    setups.sort(
        key=lambda setup: (
            setup.get("entry_time") or "",
            setup.get("signature") or "",
        )
    )
    return setups


def _bucketize_setups(
    setups: list[dict[str, Any]],
    *,
    key_name: str,
    count_name: str = "setups",
) -> list[dict[str, Any]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for setup in setups:
        grouped[setup.get(key_name)].append(setup)

    rows: list[dict[str, Any]] = []
    for bucket, bucket_setups in grouped.items():
        summary = _build_outcome_summary(bucket_setups)
        rows.append(
            {
                "bucket": bucket,
                count_name: len(bucket_setups),
                "win_rate_pct": summary["win_rate_pct"],
                "wins": summary["wins"],
                "losses": summary["losses"],
                "breakeven": summary["breakeven"],
                "total_pnl": summary["total_pnl"],
                "avg_pnl_per_setup": round(summary["total_pnl"] / len(bucket_setups), 2),
            }
        )
    return rows


def _sort_bucket_rows(bucket_rows: list[dict[str, Any]], *, bucket_type: str) -> list[dict[str, Any]]:
    if bucket_type == "hold_bucket":
        order = _HOLD_BUCKET_ORDER
        return sorted(bucket_rows, key=lambda row: order.get(str(row.get("bucket")), 999))
    if bucket_type == "dte_bucket":
        order = _DTE_BUCKET_ORDER
        return sorted(bucket_rows, key=lambda row: order.get(str(row.get("bucket")), 999))
    if bucket_type == "qty_bucket":
        order = _QTY_BUCKET_ORDER
        return sorted(bucket_rows, key=lambda row: order.get(str(row.get("bucket")), 999))
    if bucket_type == "entry_hour_et":
        return sorted(bucket_rows, key=lambda row: (row.get("bucket") is None, row.get("bucket")))
    return sorted(
        bucket_rows,
        key=lambda row: (
            -int(row.get("setups", row.get("count", 0))),
            row.get("bucket") or "",
        ),
    )


def _build_same_day_signature_clusters(setups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str | None, str], list[dict[str, Any]]] = defaultdict(list)
    for setup in setups:
        grouped[(setup.get("entry_date"), str(setup.get("signature") or ""))].append(setup)

    rows: list[dict[str, Any]] = []
    for (entry_date, signature), cluster_setups in grouped.items():
        if len(cluster_setups) <= 1:
            continue
        summary = _build_outcome_summary(cluster_setups)
        rows.append(
            {
                "entry_date": entry_date,
                "signature": signature,
                "setups": len(cluster_setups),
                "win_rate_pct": summary["win_rate_pct"],
                "wins": summary["wins"],
                "losses": summary["losses"],
                "total_pnl": summary["total_pnl"],
            }
        )
    return sorted(rows, key=lambda row: (-row["setups"], row["total_pnl"], row["signature"]))


def _build_duplicate_setup_rows(setups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    duplicates = [
        {
            "entry_time": setup.get("entry_time"),
            "signature": setup.get("signature"),
            "rows": setup.get("row_count"),
            "extra_rows_from_partial_exits": setup.get("extra_rows_from_partial_exits"),
            "total_pnl": setup.get("realized_pnl"),
            "hold_hours": setup.get("hold_hours"),
            "sources": setup.get("sources"),
        }
        for setup in setups
        if int(setup.get("row_count") or 0) > 1
    ]
    return sorted(
        duplicates,
        key=lambda row: (-int(row.get("rows") or 0), _safe_float(row.get("total_pnl"), 0.0)),
    )


def _scan_delta_provenance(repo_root: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    ledger_closed_rows = len(rows)
    ledger_rows_with_actual_delta = 0
    ledger_rows_with_selection_method = 0
    for row in rows:
        raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
        if any(raw.get(field) not in (None, "", []) for field in ("put_delta", "call_delta", "short_delta")):
            ledger_rows_with_actual_delta += 1
        if any(raw.get(field) not in (None, "", []) for field in ("selection_method", "strike_selection_method")):
            ledger_rows_with_selection_method += 1

    trajectory_file = repo_root / "data" / "feedback" / "trade_trajectories.jsonl"
    outcome_events = 0
    trajectory_events_with_actual_delta = 0
    trajectory_events_with_selection_method = 0
    if trajectory_file.exists():
        try:
            with trajectory_file.open(encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if str(event.get("strategy") or "").lower() != "iron_condor":
                        continue
                    if str(event.get("event_type") or "").lower() != "outcome":
                        continue
                    outcome_events += 1
                    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
                    if any(
                        metadata.get(field) not in (None, "", [])
                        or event.get(field) not in (None, "", [])
                        for field in ("put_delta", "call_delta", "short_delta")
                    ):
                        trajectory_events_with_actual_delta += 1
                    if any(
                        metadata.get(field) not in (None, "", [])
                        or event.get(field) not in (None, "", [])
                        for field in ("selection_method", "strike_selection_method")
                    ):
                        trajectory_events_with_selection_method += 1
        except OSError:
            pass

    any_provenance = any(
        (
            ledger_rows_with_actual_delta,
            ledger_rows_with_selection_method,
            trajectory_events_with_actual_delta,
            trajectory_events_with_selection_method,
        )
    )
    return {
        "ledger_closed_rows": ledger_closed_rows,
        "ledger_rows_with_actual_delta": ledger_rows_with_actual_delta,
        "ledger_rows_with_selection_method": ledger_rows_with_selection_method,
        "trajectory_outcome_events": outcome_events,
        "trajectory_events_with_actual_delta": trajectory_events_with_actual_delta,
        "trajectory_events_with_selection_method": trajectory_events_with_selection_method,
        "coverage_available": any_provenance,
        "note": (
            "Closed-trade provenance does not record actual selected delta or whether strike selection used live delta vs heuristic fallback."
            if not any_provenance
            else "Some delta-selection provenance exists, but coverage is partial."
        ),
    }


def _top_findings(
    setups: list[dict[str, Any]],
    *,
    expiry_rows: list[dict[str, Any]],
    hold_rows: list[dict[str, Any]],
    qty_rows: list[dict[str, Any]],
    daily_rows: list[dict[str, Any]],
    family_rows: list[dict[str, Any]],
    delta_provenance: dict[str, Any],
) -> list[str]:
    findings: list[str] = []
    total_setups = len(setups)
    if total_setups == 0:
        return findings

    under_1h = next((row for row in hold_rows if row.get("bucket") == "<1h"), None)
    if under_1h is not None:
        share = round((under_1h["setups"] / total_setups) * 100, 2)
        findings.append(
            f"{under_1h['setups']}/{total_setups} setups ({share}%) closed in under 1 hour; those setups won {under_1h['win_rate_pct']:.2f}% and lost {_fmt_money(under_1h['total_pnl'])}."
        )

    if expiry_rows:
        worst_expiry = min(expiry_rows, key=lambda row: _safe_float(row.get("total_pnl"), 0.0))
        share = round((worst_expiry["setups"] / total_setups) * 100, 2)
        findings.append(
            f"Expiry cluster {worst_expiry['bucket']} carried {worst_expiry['setups']}/{total_setups} setups ({share}%) and produced {_fmt_money(worst_expiry['total_pnl'])} at a {worst_expiry['win_rate_pct']:.2f}% win rate."
        )

    qty_two = next((row for row in qty_rows if row.get("bucket") == "2"), None)
    qty_one = next((row for row in qty_rows if row.get("bucket") == "1"), None)
    if qty_two is not None and qty_one is not None:
        findings.append(
            f"Two-lot setups went {qty_two['wins']}W/{qty_two['losses']}L for {_fmt_money(qty_two['total_pnl'])}; one-lot setups went {qty_one['wins']}W/{qty_one['losses']}L for {_fmt_money(qty_one['total_pnl'])}."
        )

    if daily_rows:
        worst_day = min(daily_rows, key=lambda row: _safe_float(row.get("total_pnl"), 0.0))
        findings.append(
            f"Worst entry day was {worst_day['bucket']}: {worst_day['setups']} setups, {worst_day['win_rate_pct']:.2f}% win rate, {_fmt_money(worst_day['total_pnl'])}."
        )

    if family_rows:
        worst_family = min(family_rows, key=lambda row: _safe_float(row.get("total_pnl"), 0.0))
        findings.append(
            f"Most damaging recurring family was {worst_family['bucket']}: {worst_family['setups']} setups, {worst_family['win_rate_pct']:.2f}% win rate, {_fmt_money(worst_family['total_pnl'])}."
        )

    if not delta_provenance.get("coverage_available"):
        findings.append(delta_provenance["note"])

    return findings[:6]


def build_trade_setup_audit(repo_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    now = now or datetime.now(ET_TZ)
    ledger_path = repo_root / "data" / "trades.json"
    payload = _load_json(ledger_path, {})
    if not isinstance(payload, dict):
        return {"available": False, "reason": "trades.json missing or invalid"}

    trades = payload.get("trades")
    if not isinstance(trades, list):
        return {"available": False, "reason": "trades.json missing trades list"}

    rows = _normalize_closed_trade_rows(trades)
    setups = _collapse_rows_into_setups(rows)
    row_summary = _build_outcome_summary(rows)
    setup_summary = _build_outcome_summary(setups)
    partial_exit_extra_rows = sum(
        int(setup.get("extra_rows_from_partial_exits") or 0) for setup in setups
    )
    partial_exit_groups = sum(1 for setup in setups if int(setup.get("row_count") or 0) > 1)

    same_day_setups = [setup for setup in setups if setup.get("same_day") is True]
    under_1h_setups = [setup for setup in setups if (setup.get("hold_hours") or 0) < 1]

    hold_rows = _sort_bucket_rows(
        _bucketize_setups(setups, key_name="hold_bucket"),
        bucket_type="hold_bucket",
    )
    dte_rows = _sort_bucket_rows(
        _bucketize_setups(setups, key_name="dte_bucket"),
        bucket_type="dte_bucket",
    )
    qty_rows = _sort_bucket_rows(
        _bucketize_setups(setups, key_name="qty_bucket"),
        bucket_type="qty_bucket",
    )
    entry_hour_rows = _sort_bucket_rows(
        _bucketize_setups(setups, key_name="entry_hour_et"),
        bucket_type="entry_hour_et",
    )
    expiry_rows = _sort_bucket_rows(
        _bucketize_setups(setups, key_name="expiry"),
        bucket_type="expiry",
    )
    daily_rows = _sort_bucket_rows(
        _bucketize_setups(setups, key_name="entry_date"),
        bucket_type="entry_date",
    )
    signature_rows = _sort_bucket_rows(
        _bucketize_setups(setups, key_name="signature"),
        bucket_type="signature",
    )
    family_rows = _sort_bucket_rows(
        _bucketize_setups(setups, key_name="family"),
        bucket_type="family",
    )
    same_day_signature_clusters = _build_same_day_signature_clusters(setups)
    duplicate_setup_rows = _build_duplicate_setup_rows(setups)
    delta_provenance = _scan_delta_provenance(repo_root, rows)

    top_findings = _top_findings(
        setups,
        expiry_rows=expiry_rows,
        hold_rows=hold_rows,
        qty_rows=qty_rows,
        daily_rows=daily_rows,
        family_rows=family_rows,
        delta_provenance=delta_provenance,
    )

    return {
        "available": True,
        "generated_at_et": now.isoformat(),
        "repo_root": str(repo_root),
        "ledger_path": str(ledger_path),
        "ledger_last_updated": (
            payload.get("meta", {}).get("last_sync")
            if isinstance(payload.get("meta"), dict)
            else None
        )
        or (payload.get("stats", {}).get("last_updated") if isinstance(payload.get("stats"), dict) else None),
        "setup_key_definition": "signature + exact entry_time",
        "row_level": {
            **row_summary,
            "closed_rows": len(rows),
        },
        "setup_level": {
            **setup_summary,
            "distinct_setups": len(setups),
            "partial_exit_groups": partial_exit_groups,
            "partial_exit_extra_rows": partial_exit_extra_rows,
            "same_day_setups": len(same_day_setups),
            "same_day_setup_pct": round((len(same_day_setups) / len(setups)) * 100, 2) if setups else 0.0,
            "under_1h_setups": len(under_1h_setups),
            "under_1h_setup_pct": round((len(under_1h_setups) / len(setups)) * 100, 2) if setups else 0.0,
        },
        "top_findings": top_findings,
        "hold_time_breakdown": hold_rows,
        "dte_breakdown": dte_rows,
        "quantity_breakdown": qty_rows,
        "entry_hour_et_breakdown": entry_hour_rows,
        "expiry_clusters": expiry_rows,
        "entry_day_clusters": daily_rows,
        "signature_breakdown": signature_rows[:15],
        "structure_family_breakdown": family_rows[:15],
        "same_day_signature_clusters": same_day_signature_clusters[:15],
        "duplicate_setup_groups": duplicate_setup_rows,
        "worst_setups": sorted(setups, key=lambda setup: _safe_float(setup.get("realized_pnl"), 0.0))[:10],
        "best_setups": sorted(
            setups,
            key=lambda setup: _safe_float(setup.get("realized_pnl"), 0.0),
            reverse=True,
        )[:10],
        "delta_provenance": delta_provenance,
    }


def render_trade_setup_audit_markdown(audit: dict[str, Any]) -> str:
    if not audit.get("available"):
        return f"# Trade Setup Audit\n\n- Available: `False`\n- Reason: `{audit.get('reason', 'unknown')}`\n"

    row_level = audit.get("row_level") or {}
    setup_level = audit.get("setup_level") or {}
    hold_rows = audit.get("hold_time_breakdown") or []
    qty_rows = audit.get("quantity_breakdown") or []
    expiry_rows = audit.get("expiry_clusters") or []
    reentry_rows = audit.get("same_day_signature_clusters") or []
    worst_rows = audit.get("worst_setups") or []
    provenance = audit.get("delta_provenance") or {}

    lines = [
        "# Trade Setup Audit",
        "",
        f"- Generated at ET: `{audit.get('generated_at_et')}`",
        f"- Ledger last updated: `{audit.get('ledger_last_updated')}`",
        f"- Setup key definition: `{audit.get('setup_key_definition')}`",
        "",
        "## Summary",
        f"- Closed rows: `{row_level.get('closed_rows')}`",
        f"- Distinct setups: `{setup_level.get('distinct_setups')}`",
        f"- Partial-exit extra rows: `{setup_level.get('partial_exit_extra_rows')}` across `{setup_level.get('partial_exit_groups')}` setup groups",
        f"- Setup win rate: `{_fmt_pct(setup_level.get('win_rate_pct'))}`",
        f"- Setup total realized P/L: `{_fmt_money(setup_level.get('total_pnl'))}`",
        f"- Avg winner / loser: `{_fmt_money(setup_level.get('avg_win'))}` / `{_fmt_money(setup_level.get('avg_loss'))}`",
        f"- Break-even win rate at realized payoff: `{_fmt_pct(setup_level.get('break_even_win_rate_pct'))}`",
        f"- Same-day setups: `{setup_level.get('same_day_setups')}` (`{_fmt_pct(setup_level.get('same_day_setup_pct'))}`)",
        f"- Under-1h setups: `{setup_level.get('under_1h_setups')}` (`{_fmt_pct(setup_level.get('under_1h_setup_pct'))}`)",
        "",
        "## Key Findings",
    ]
    lines.extend([f"- {finding}" for finding in audit.get("top_findings", [])] or ["- None"])
    lines.extend(["", "## Hold Time Breakdown"])
    lines.extend(
        [
            f"- `{row.get('bucket')}`: setups `{row.get('setups')}`, win rate `{_fmt_pct(row.get('win_rate_pct'))}`, total P/L `{_fmt_money(row.get('total_pnl'))}`"
            for row in hold_rows
        ]
        or ["- None"]
    )
    lines.extend(["", "## Quantity Breakdown"])
    lines.extend(
        [
            f"- `{row.get('bucket')}` contracts: setups `{row.get('setups')}`, win rate `{_fmt_pct(row.get('win_rate_pct'))}`, total P/L `{_fmt_money(row.get('total_pnl'))}`"
            for row in qty_rows
        ]
        or ["- None"]
    )
    lines.extend(["", "## Expiry Clusters"])
    lines.extend(
        [
            f"- `{row.get('bucket')}`: setups `{row.get('setups')}`, win rate `{_fmt_pct(row.get('win_rate_pct'))}`, total P/L `{_fmt_money(row.get('total_pnl'))}`"
            for row in expiry_rows[:10]
        ]
        or ["- None"]
    )
    lines.extend(["", "## Same-Day Re-entry Clusters"])
    lines.extend(
        [
            f"- `{row.get('entry_date')}` `{row.get('signature')}`: setups `{row.get('setups')}`, win rate `{_fmt_pct(row.get('win_rate_pct'))}`, total P/L `{_fmt_money(row.get('total_pnl'))}`"
            for row in reentry_rows[:10]
        ]
        or ["- None"]
    )
    lines.extend(["", "## Worst Setups"])
    lines.extend(
        [
            f"- `{row.get('entry_date')}` `{row.get('signature')}`: P/L `{_fmt_money(row.get('realized_pnl'))}`, hold `{row.get('hold_hours')}h`, qty `{row.get('quantity')}`, DTE `{row.get('dte')}`"
            for row in worst_rows[:10]
        ]
        or ["- None"]
    )
    lines.extend(
        [
            "",
            "## Delta Provenance",
            f"- Ledger rows with actual delta: `{provenance.get('ledger_rows_with_actual_delta')}` / `{provenance.get('ledger_closed_rows')}`",
            f"- Ledger rows with selection method: `{provenance.get('ledger_rows_with_selection_method')}` / `{provenance.get('ledger_closed_rows')}`",
            f"- Trajectory outcomes with actual delta: `{provenance.get('trajectory_events_with_actual_delta')}` / `{provenance.get('trajectory_outcome_events')}`",
            f"- Trajectory outcomes with selection method: `{provenance.get('trajectory_events_with_selection_method')}` / `{provenance.get('trajectory_outcome_events')}`",
            f"- Note: `{provenance.get('note')}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_trade_setup_audit_artifacts(
    repo_root: Path,
    *,
    json_out: Path,
    markdown_out: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    audit = build_trade_setup_audit(repo_root, now=now)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    markdown_out.write_text(render_trade_setup_audit_markdown(audit), encoding="utf-8")
    return audit
