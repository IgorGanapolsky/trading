#!/usr/bin/env python3
"""Put-credit validation cohort scorecard (edge truth, not marketing).

Outputs kill-criteria progress for the active spy_put_credit family only.
Never invents profitability: n=0 closed → insufficient sample.

Usage:
  .venv/bin/python scripts/put_credit_cohort_scorecard.py
  .venv/bin/python scripts/put_credit_cohort_scorecard.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_TRADES = ROOT / "data" / "trades.json"
DEFAULT_ENTRIES = ROOT / "data" / "put_credit_entries.json"
DEFAULT_KILL = ROOT / "data" / "runtime" / "strategy_kill_switch.json"
DEFAULT_OUT = ROOT / "data" / "audit" / "put_credit_cohort_latest.json"

KILL_N = 30
KILL_MIN_EXPECTANCY = 0.0
KILL_MIN_PF = 1.0


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _trade_rows(trades_payload: Any) -> list[dict[str, Any]]:
    if isinstance(trades_payload, list):
        return [t for t in trades_payload if isinstance(t, dict)]
    if not isinstance(trades_payload, dict):
        return []
    for key in ("trades", "closed_trades", "paired", "trade_history"):
        rows = trades_payload.get(key)
        if isinstance(rows, list):
            return [t for t in rows if isinstance(t, dict)]
    # flat dict of id -> trade
    vals = [v for v in trades_payload.values() if isinstance(v, dict)]
    if vals and any("realized_pnl" in v or "strategy" in v for v in vals[:5]):
        return vals
    return []


def _is_put_credit_trade(row: dict[str, Any]) -> bool:
    blob = " ".join(
        str(row.get(k) or "")
        for k in ("strategy", "strategy_family", "structure", "type", "signature", "id")
    ).lower()
    if "iron_condor" in blob and "put_credit" not in blob and "bull_put" not in blob:
        return False
    return any(
        token in blob
        for token in (
            "spy_put_credit",
            "put_credit",
            "bull_put",
            "bull put",
            "pcs_",
        )
    )


def _is_closed(row: dict[str, Any]) -> bool:
    status = str(row.get("status") or "").lower()
    if status in {"closed", "filled_closed", "done"}:
        return True
    if row.get("exit_time") or row.get("exit_date"):
        return True
    if _as_float(row.get("realized_pnl")) is not None and status != "open":
        return status != "open"
    return False


def _metrics_from_pnls(pnls: list[float]) -> dict[str, Any]:
    n = len(pnls)
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    be = [p for p in pnls if p == 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    total = sum(pnls)
    expectancy = (total / n) if n else None
    pf = (gross_win / gross_loss) if gross_loss > 0 else (None if n == 0 else float("inf"))
    win_rate = (len(wins) / n * 100.0) if n else None
    return {
        "n": n,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(be),
        "win_rate_pct": round(win_rate, 2) if win_rate is not None else None,
        "profit_factor": round(pf, 4) if isinstance(pf, float) and pf != float("inf") else pf,
        "expectancy": round(expectancy, 4) if expectancy is not None else None,
        "total_realized_pnl": round(total, 2) if n else 0.0,
        "avg_win": round(sum(wins) / len(wins), 2) if wins else None,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else None,
    }


def _rolling_windows(pnls: list[float], window: int = 20) -> dict[str, Any]:
    """Stability check: last rolling window metrics (research backlog A2)."""
    if not pnls:
        return {
            "window": window,
            "sample_sufficient": False,
            "last": None,
            "note": "no closed put-credit pnls",
        }
    if len(pnls) < window:
        m = _metrics_from_pnls(pnls)
        return {
            "window": window,
            "sample_sufficient": False,
            "last": m,
            "note": f"need {window} closed trades for full rolling window (have {len(pnls)})",
        }
    last = _metrics_from_pnls(pnls[-window:])
    # sign stability vs full sample
    full = _metrics_from_pnls(pnls)
    sign_flip = False
    if full.get("expectancy") is not None and last.get("expectancy") is not None:
        sign_flip = (full["expectancy"] > 0) != (last["expectancy"] > 0)
    return {
        "window": window,
        "sample_sufficient": True,
        "last": last,
        "sign_flip_vs_full": sign_flip,
        "note": (
            "If sign_flip_vs_full at n>=30, treat edge as unstable (research kill heuristic)."
        ),
    }


def summarize_closed(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [r for r in rows if _is_put_credit_trade(r) and _is_closed(r)]
    # Rolling-window metrics need chronological order; input JSON order is not
    # guaranteed (Greptile #4280 P2). ISO-8601 strings sort chronologically.
    closed.sort(key=lambda r: str(r.get("exit_time") or ""))
    pnls: list[float] = []
    for r in closed:
        pnl = _as_float(r.get("realized_pnl"))
        if pnl is None:
            # reconstruct from entry/exit cash when present
            entry = _as_float(r.get("entry_net_cash")) or _as_float(r.get("entry_credit"))
            exit_ = _as_float(r.get("exit_net_cash"))
            if entry is not None and exit_ is not None:
                # credit entry positive cash in, exit is buy-to-close negative
                pnl = entry + exit_
        if pnl is not None:
            pnls.append(pnl)

    base = _metrics_from_pnls(pnls)
    n = base["n"]
    expectancy = base["expectancy"]
    pf = base["profit_factor"]
    total = base["total_realized_pnl"]

    kill = {
        "n_target": KILL_N,
        "n_closed": n,
        "sample_sufficient": n >= KILL_N,
        "expectancy_gt_0": (expectancy is not None and expectancy > KILL_MIN_EXPECTANCY)
        if n >= KILL_N
        else None,
        "profit_factor_gt_1": (pf is not None and pf > KILL_MIN_PF) if n >= KILL_N else None,
        "total_pnl_gt_0": (total > 0) if n >= KILL_N else None,
        "research_note": (
            "n=30 is an interim floor; Parallel research recommends ~100 trades and "
            "multi-regime coverage before desk-grade confidence. Live still blocked "
            "until EDGE_CANDIDATE; do not deposit capital on interim n alone."
        ),
    }
    if n >= KILL_N:
        kill["pass_all"] = bool(
            kill["expectancy_gt_0"] and kill["profit_factor_gt_1"] and kill["total_pnl_gt_0"]
        )
        kill["verdict"] = "EDGE_CANDIDATE" if kill["pass_all"] else "NO_EDGE_KILL"
    else:
        kill["pass_all"] = None
        kill["verdict"] = "INSUFFICIENT_SAMPLE"

    return {
        "closed_n": n,
        "wins": base["wins"],
        "losses": base["losses"],
        "breakeven": base["breakeven"],
        "win_rate_pct": base["win_rate_pct"],
        "profit_factor": base["profit_factor"],
        "expectancy": base["expectancy"],
        "total_realized_pnl": base["total_realized_pnl"],
        "avg_win": base["avg_win"],
        "avg_loss": base["avg_loss"],
        "kill_criteria": kill,
        "rolling_20": _rolling_windows(pnls, 20),
    }


def summarize_open(entries: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(entries, dict):
        return {"open_n": 0, "entries": []}
    open_rows = []
    for key, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "open").lower()
        if status in {"closed", "exited", "cancelled", "canceled"}:
            continue
        regime = entry.get("regime") if isinstance(entry.get("regime"), dict) else {}
        open_rows.append(
            {
                "key": key,
                "expiry": entry.get("expiry"),
                "credit": entry.get("credit"),
                "quantity": entry.get("quantity"),
                "entry_time": entry.get("entry_time") or entry.get("filled_at"),
                "signature": entry.get("signature"),
                "regime": {
                    "vix": regime.get("vix"),
                    "iv_rank_proxy": regime.get("iv_rank_proxy"),
                    "spy_above_200dma": regime.get("spy_above_200dma"),
                }
                if regime
                else None,
            }
        )
    return {"open_n": len(open_rows), "entries": open_rows}


def build_scorecard(
    *,
    trades_path: Path = DEFAULT_TRADES,
    entries_path: Path = DEFAULT_ENTRIES,
    kill_path: Path = DEFAULT_KILL,
) -> dict[str, Any]:
    trades = _load_json(trades_path)
    entries = _load_json(entries_path)
    kill_switch = _load_json(kill_path) or {}
    closed = summarize_closed(_trade_rows(trades))
    open_ = summarize_open(entries if isinstance(entries, dict) else {})

    try:
        from src.core.trading_profiles import get_put_credit_profile

        profile = get_put_credit_profile()
        profile_view = {
            "name": profile.name,
            "max_daily_structures": profile.max_daily_structures,
            "max_concurrent_positions": profile.max_concurrent_positions,
            "max_contracts_per_trade": profile.max_contracts_per_trade,
            "min_credit": profile.min_credit,
            "take_profit_pct": profile.take_profit_pct,
            "stop_loss_pct": profile.stop_loss_pct,
            "min_hold_hours": profile.min_hold_hours,
        }
    except Exception as exc:  # noqa: BLE001
        profile_view = {"error": str(exc)}

    progress = {
        "closed_toward_n30": closed["closed_n"],
        "remaining_to_gate": max(0, KILL_N - closed["closed_n"]),
        "pct_to_gate": round(min(100.0, closed["closed_n"] / KILL_N * 100.0), 1),
    }

    return {
        "schema_version": "put-credit-cohort-scorecard/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "active_family": kill_switch.get("active_family"),
        "paper_only": kill_switch.get("paper_only"),
        "live_blocked": kill_switch.get("live_blocked"),
        "profile": profile_view,
        "open": open_,
        "closed": closed,
        "progress": progress,
        "honesty": {
            "claim_profitable": False
            if closed["closed_n"] < KILL_N
            else bool(closed["kill_criteria"].get("pass_all")),
            "live_deposit_ready": False,
            "note": (
                "Do not claim profitability or deposit real capital until kill_criteria.verdict "
                f"is EDGE_CANDIDATE (n>={KILL_N}, expectancy>0, PF>1, total PnL>0). "
                "Process upgrades (regime gate, logging) improve validation quality only — "
                "they do not create edge."
            ),
        },
        "process_upgrades": {
            "regime_gate": "IVR>=30 and VIX<=30 hard; SPY 200-DMA soft-flag",
            "entry_regime_logging": True,
            "exit_counterfactuals_tp50_dte21": True,
            "rolling_20_metrics": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    card = build_scorecard()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(card, indent=2))
        return 0

    closed = card["closed"]
    kill = closed["kill_criteria"]
    print("=== PUT CREDIT COHORT SCORECARD ===")
    print(f"active_family: {card.get('active_family')} paper_only={card.get('paper_only')}")
    print(f"open: {card['open']['open_n']}  closed: {closed['closed_n']}/{KILL_N}")
    print(f"progress_to_gate: {card['progress']['pct_to_gate']}%")
    print(
        f"win_rate: {closed['win_rate_pct']}  PF: {closed['profit_factor']}  "
        f"expectancy: {closed['expectancy']}  total_pnl: {closed['total_realized_pnl']}"
    )
    print(f"kill_verdict: {kill['verdict']}")
    print(f"honesty: {card['honesty']['note']}")
    print(f"json_out={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
