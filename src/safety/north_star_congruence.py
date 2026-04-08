"""Shared North Star congruence checks across weekly gate and public surfaces."""

from __future__ import annotations

from typing import Any

DEFAULT_MIN_CLOSED_TRADES_FOR_CONFIRMED_EDGE = 30


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on", "pass", "passed"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", "fail", "failed"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _derive_stats_from_trades(payload: dict[str, Any]) -> dict[str, Any]:
    trades = _as_list(payload.get("trades"))
    closed = []
    for row in trades:
        if not isinstance(row, dict):
            continue
        if str(row.get("status") or "").lower() != "closed":
            continue
        pnl = _as_float(row.get("realized_pnl"))
        if pnl is None:
            pnl = _as_float(row.get("pnl"))
        if pnl is None:
            continue
        closed.append(pnl)

    wins = sum(1 for pnl in closed if pnl > 0)
    losses = sum(1 for pnl in closed if pnl < 0)
    breakeven = sum(1 for pnl in closed if pnl == 0)
    gross_profit = sum(pnl for pnl in closed if pnl > 0)
    gross_loss = abs(sum(pnl for pnl in closed if pnl < 0))
    profit_factor = None
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = float("inf")

    return {
        "closed_trades": len(closed),
        "wins": wins,
        "losses": losses,
        "breakeven": breakeven,
        "total_realized_pnl": sum(closed) if closed else None,
        "profit_factor": profit_factor,
        "win_rate_pct": (wins / len(closed) * 100.0) if closed else None,
    }


def assess_lifetime_ledger(
    trades_payload: dict[str, Any] | None,
    *,
    min_closed_trades: int = DEFAULT_MIN_CLOSED_TRADES_FOR_CONFIRMED_EDGE,
) -> dict[str, Any]:
    """Summarize whether the paired-trade ledger actually confirms edge."""
    payload = trades_payload if isinstance(trades_payload, dict) else {}
    stats = _as_dict(payload.get("stats"))
    derived = _derive_stats_from_trades(payload)

    closed_trades = _as_int(stats.get("closed_trades"), derived["closed_trades"])
    win_rate_pct = _as_float(stats.get("win_rate_pct"))
    if win_rate_pct is None:
        win_rate_pct = _as_float(derived["win_rate_pct"])
    profit_factor = _as_float(stats.get("profit_factor"))
    if profit_factor is None:
        profit_factor = _as_float(derived["profit_factor"])
    total_realized_pnl = _as_float(stats.get("total_realized_pnl"))
    if total_realized_pnl is None:
        total_realized_pnl = _as_float(stats.get("total_pnl"))
    if total_realized_pnl is None:
        total_realized_pnl = _as_float(derived["total_realized_pnl"])

    expectancy_per_trade = None
    if closed_trades > 0 and total_realized_pnl is not None:
        expectancy_per_trade = round(total_realized_pnl / closed_trades, 4)

    has_min_sample = closed_trades >= min_closed_trades
    positive_expectancy = expectancy_per_trade is not None and expectancy_per_trade > 0
    positive_total_realized_pnl = total_realized_pnl is not None and total_realized_pnl > 0
    profit_factor_passed = profit_factor is not None and profit_factor >= 1.0
    edge_confirmed = bool(
        has_min_sample
        and positive_expectancy
        and positive_total_realized_pnl
        and profit_factor_passed
    )

    return {
        "closed_trades": closed_trades,
        "win_rate_pct": win_rate_pct,
        "profit_factor": profit_factor,
        "total_realized_pnl": total_realized_pnl,
        "expectancy_per_trade": expectancy_per_trade,
        "has_min_sample": has_min_sample,
        "positive_expectancy": positive_expectancy,
        "positive_total_realized_pnl": positive_total_realized_pnl,
        "profit_factor_passed": profit_factor_passed,
        "edge_confirmed": edge_confirmed,
        "min_closed_trades_for_confirmed_edge": min_closed_trades,
    }


def assess_gate_congruence(
    weekly_gate: dict[str, Any] | None,
    trades_payload: dict[str, Any] | None,
    *,
    min_closed_trades: int = DEFAULT_MIN_CLOSED_TRADES_FOR_CONFIRMED_EDGE,
) -> dict[str, Any]:
    """Return effective edge/scale answers plus contradiction diagnostics."""
    gate = weekly_gate if isinstance(weekly_gate, dict) else {}
    cadence = _as_dict(gate.get("cadence_kpi"))
    scaling = _as_dict(gate.get("scaling_sample_gate"))
    lifetime = assess_lifetime_ledger(trades_payload, min_closed_trades=min_closed_trades)

    weekly_verified = _as_bool(gate.get("verified_edge_available"))
    block_new_positions = _as_bool(gate.get("block_new_positions"))
    block_new_positions_present = "block_new_positions" in gate
    cadence_passed = _as_bool(cadence.get("passed"))
    scaling_passed = _as_bool(scaling.get("passed"))
    weekly_mode = str(gate.get("mode") or "unknown").lower()

    readiness_claimed = bool(
        weekly_verified
        or scaling_passed
        or (block_new_positions_present and not block_new_positions)
        or weekly_mode == "expansion_candidate"
    )

    contradiction_detected = bool(not lifetime["edge_confirmed"] and readiness_claimed)

    contradiction_reason = None
    if contradiction_detected:
        expectancy_text = (
            f"${lifetime['expectancy_per_trade']:.2f}/trade"
            if lifetime["expectancy_per_trade"] is not None
            else "n/a"
        )
        profit_factor_text = (
            f"{lifetime['profit_factor']:.2f}" if lifetime["profit_factor"] is not None else "n/a"
        )
        pnl_text = (
            f"${lifetime['total_realized_pnl']:.2f}"
            if lifetime["total_realized_pnl"] is not None
            else "n/a"
        )
        if lifetime["has_min_sample"]:
            contradiction_reason = (
                "CRITICAL: Weekly gate conflicts with lifetime paired-trade ledger. "
                f"Lifetime ledger shows {lifetime['closed_trades']} closed trades, expectancy "
                f"{expectancy_text}, profit factor {profit_factor_text}, total realized P/L "
                f"{pnl_text}. Block new positions until lifetime edge is positive."
            )
        else:
            contradiction_reason = (
                "CRITICAL: Weekly gate claims verified/scalable status before the lifetime ledger "
                f"has the minimum {lifetime['min_closed_trades_for_confirmed_edge']} closed trades."
            )

    effective_verified_edge_available = lifetime["edge_confirmed"]
    effective_scale_allowed = bool(
        effective_verified_edge_available
        and not block_new_positions
        and cadence_passed
        and scaling_passed
        and not contradiction_detected
        and weekly_mode != "defensive"
    )

    return {
        "lifetime_ledger": lifetime,
        "contradiction_detected": contradiction_detected,
        "contradiction_reason": contradiction_reason,
        "effective_verified_edge_available": effective_verified_edge_available,
        "effective_scale_allowed": effective_scale_allowed,
    }
