"""Deeper edge analysis on data/trades.json (paired closed iron condors).

Companion to scripts/research/edge_analysis_2026_05_19.py (PR #4024).

This goes further than the first pass:
- single-dim: day-of-week, week-of-month, calendar month, DTE bucket,
  hold-time bucket, credit/width quartile.
- 2D interactions: day-of-week x DTE-bucket, day-of-week x hold-time-bucket,
  month x DTE-bucket (only cells with n >= 5 are tested).
- sequence effects: win-rate conditional on the prior chronological trade
  outcome (autocorrelation lag-1).
- "cluster days" via SPY ATR: SKIPPED — yfinance not installed and the
  local data/historical SPY CSVs do not cover the Jan-Apr 2026 trading
  window; documented in the docs writeup.

Reporting contract:
- n is reported in every cell. Cells with n<5 are flagged INSUFFICIENT
  and excluded from the multi-comparison K count.
- For every cell with n>=5 we compute Wilson 95% CI, raw one-sided
  binomial p (P(X >= wins | n, baseline_p=0.2319)), and Bonferroni-
  adjusted p across the full K of tested cells.
- The script is reproducible: `python3 scripts/research/edge_analysis_deeper_2026_05_19.py`
  reads data/trades.json and writes nothing.

Functions every numeric claim cites:
  load_trades, cohort_stats, wilson_ci, binom_p_geq,
  single_dim_report, two_d_report, sequence_lag1, bonferroni_adjust.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scipy.stats import binomtest  # type: ignore

    HAVE_SCIPY = True
except Exception:  # pragma: no cover
    HAVE_SCIPY = False


REPO_ROOT = Path(__file__).resolve().parents[2]
TRADES_PATH = REPO_ROOT / "data" / "trades.json"

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% CI for a binomial proportion. (0,0) when n==0."""
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    lo = (center - spread) / denom
    hi = (center + spread) / denom
    return (max(0.0, lo), min(1.0, hi))


def binom_p_geq(k: int, n: int, p: float) -> float:
    """One-sided P(X >= k | n, p). Uses scipy.binomtest where available."""
    if n == 0:
        return 1.0
    if HAVE_SCIPY:
        return float(binomtest(k, n, p, alternative="greater").pvalue)
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return total


def bonferroni_adjust(p: float, k: int) -> float:
    """Standard Bonferroni: capped at 1.0."""
    if k <= 0:
        return p
    return min(1.0, p * k)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


@dataclass
class Trade:
    raw: dict[str, Any]
    entry_dt: datetime
    exit_dt: datetime
    expiry_date: datetime | None
    realized_pnl: float
    outcome: str
    entry_credit: float
    dte_at_entry: int | None
    hold_hours: float
    width: float | None


def _parse_iso(s: str) -> datetime:
    if len(s) == 10:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(s)


def load_trades(path: Path = TRADES_PATH) -> list[Trade]:
    raw = json.loads(path.read_text())
    out: list[Trade] = []
    for t in raw["trades"]:
        if t.get("status") != "closed":
            continue
        entry_dt = _parse_iso(t["entry_time"])
        exit_dt = _parse_iso(t["exit_time"])
        legs = t.get("legs") or {}
        expiry_s = legs.get("expiry")
        expiry_dt = _parse_iso(expiry_s) if expiry_s else None
        dte = (expiry_dt.date() - entry_dt.date()).days if expiry_dt else None
        hold_h = (exit_dt - entry_dt).total_seconds() / 3600.0
        put_strikes = legs.get("put_strikes") or []
        call_strikes = legs.get("call_strikes") or []
        width: float | None = None
        if len(put_strikes) == 2 and len(call_strikes) == 2:
            pw = abs(put_strikes[1] - put_strikes[0])
            cw = abs(call_strikes[1] - call_strikes[0])
            width = (pw + cw) / 2.0
        out.append(
            Trade(
                raw=t,
                entry_dt=entry_dt,
                exit_dt=exit_dt,
                expiry_date=expiry_dt,
                realized_pnl=float(t["realized_pnl"]),
                outcome=t["outcome"],
                entry_credit=float(t["entry_credit"]),
                dte_at_entry=dte,
                hold_hours=hold_h,
                width=width,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Cohort + bucketers
# ---------------------------------------------------------------------------


def cohort_stats(trades: list[Trade]) -> dict[str, Any]:
    n = len(trades)
    wins = [t.realized_pnl for t in trades if t.outcome == "win"]
    losses = [t.realized_pnl for t in trades if t.outcome == "loss"]
    n_w, n_l = len(wins), len(losses)
    win_rate = n_w / n if n else 0.0
    avg_win = statistics.mean(wins) if wins else 0.0
    avg_loss = statistics.mean(losses) if losses else 0.0
    total_w, total_l = sum(wins), sum(losses)
    pf = (total_w / abs(total_l)) if total_l != 0 else None
    expectancy = (sum(t.realized_pnl for t in trades) / n) if n else 0.0
    lo, hi = wilson_ci(n_w, n)
    return {
        "n": n, "wins": n_w, "losses": n_l,
        "win_rate": win_rate, "win_rate_ci95": (lo, hi),
        "avg_win": avg_win, "avg_loss": avg_loss,
        "profit_factor": pf, "expectancy": expectancy,
        "total_pnl": sum(t.realized_pnl for t in trades),
    }


def _dte_bucket(d: int | None) -> str:
    if d is None:
        return "unknown"
    if d <= 21:
        return "<=21"
    if d <= 30:
        return "22-30"
    if d <= 45:
        return "31-45"
    return ">45"


def _hold_bucket(h: float) -> str:
    if h < 24:
        return "<24h"
    if h < 72:
        return "1-3d"
    if h < 168:
        return "3-7d"
    return ">7d"


def _wom_bucket(dt: datetime) -> str:
    """Week-of-month: 1..5 based on (day-1)//7+1."""
    return f"W{(dt.day - 1) // 7 + 1}"


def _credit_width_quartile(trades: list[Trade]) -> dict[int, str]:
    """Return {trade index in trades: quartile label}. Trades missing width
    are mapped to 'unknown'.
    """
    out: dict[int, str] = {}
    have_idx = [i for i, t in enumerate(trades) if t.width and t.width > 0]
    if not have_idx:
        for i in range(len(trades)):
            out[i] = "unknown"
        return out
    ratios = sorted(
        (trades[i].entry_credit / (trades[i].width * 100.0)) for i in have_idx
    )
    n = len(ratios)
    q1, q2, q3 = ratios[n // 4], ratios[n // 2], ratios[(3 * n) // 4]
    for i, t in enumerate(trades):
        if t.width and t.width > 0:
            r = t.entry_credit / (t.width * 100.0)
            if r <= q1:
                out[i] = f"Q1 (<= {q1:.3f})"
            elif r <= q2:
                out[i] = f"Q2 ({q1:.3f} - {q2:.3f}]"
            elif r <= q3:
                out[i] = f"Q3 ({q2:.3f} - {q3:.3f}]"
            else:
                out[i] = f"Q4 (> {q3:.3f})"
        else:
            out[i] = "unknown"
    return out


# ---------------------------------------------------------------------------
# Reporting primitives
# ---------------------------------------------------------------------------


def _row_for_bucket(label: str, ts: list[Trade], baseline_p: float) -> dict[str, Any]:
    n = len(ts)
    wins = sum(1 for t in ts if t.outcome == "win")
    wr = wins / n if n else 0.0
    lo, hi = wilson_ci(wins, n)
    exp = (sum(t.realized_pnl for t in ts) / n) if n else 0.0
    pnl = sum(t.realized_pnl for t in ts)
    p_geq = binom_p_geq(wins, n, baseline_p) if n > 0 else None
    return {
        "bucket": label, "n": n, "wins": wins, "win_rate": wr,
        "ci_lo": lo, "ci_hi": hi, "expectancy": exp, "total_pnl": pnl,
        "p_raw": p_geq, "insufficient": n < 5,
    }


def single_dim_report(
    name: str, groups: dict[Any, list[Trade]],
    baseline_p: float, order_keys: list[Any] | None = None,
    label_fn=str,
) -> dict[str, Any]:
    keys = order_keys if order_keys is not None else list(groups.keys())
    rows = [_row_for_bucket(label_fn(k), groups.get(k, []), baseline_p) for k in keys]
    return {"name": name, "baseline_win_rate": baseline_p, "rows": rows}


def two_d_report(
    name: str, trades: list[Trade], baseline_p: float,
    key_fn_a, key_fn_b, order_a: list, order_b: list,
    label_a=str, label_b=str,
) -> dict[str, Any]:
    cell: dict[tuple, list[Trade]] = defaultdict(list)
    for t in trades:
        cell[(key_fn_a(t), key_fn_b(t))].append(t)
    rows = []
    for a in order_a:
        for b in order_b:
            ts = cell.get((a, b), [])
            rows.append(_row_for_bucket(f"{label_a(a)} | {label_b(b)}", ts, baseline_p))
    return {"name": name, "baseline_win_rate": baseline_p, "rows": rows}


def sequence_lag1(trades: list[Trade], baseline_p: float) -> dict[str, Any]:
    """For each trade k (sorted by exit time), what is the outcome of trade k+1
    conditional on trade k's outcome? Pearson chi-square is overkill here;
    we report a 2x2 of (prev_win|prev_loss) x (win|loss) plus binomial p
    for each conditional row vs the cohort baseline.
    """
    seq = sorted(trades, key=lambda t: t.exit_dt)
    after_win: list[Trade] = []
    after_loss: list[Trade] = []
    for prev, nxt in zip(seq, seq[1:]):
        if prev.outcome == "win":
            after_win.append(nxt)
        elif prev.outcome == "loss":
            after_loss.append(nxt)
    return {
        "name": "Sequence: outcome conditional on prior trade",
        "baseline_win_rate": baseline_p,
        "rows": [
            _row_for_bucket("after_win", after_win, baseline_p),
            _row_for_bucket("after_loss", after_loss, baseline_p),
        ],
    }


# ---------------------------------------------------------------------------
# Markdown formatting
# ---------------------------------------------------------------------------


def fmt_pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def fmt_money(x: float | None) -> str:
    return "n/a" if x is None else f"${x:,.2f}"


def fmt_p(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def to_md(report: dict[str, Any], k_for_bonf: int) -> str:
    lines = [
        f"### {report['name']} (baseline win rate {fmt_pct(report['baseline_win_rate'])})",
        "",
        f"| Bucket | n | wins | win_rate | 95% Wilson CI | expectancy | raw p | bonf adj_p (K={k_for_bonf}) | Note |",
        "|---|---:|---:|---:|---|---:|---:|---:|---|",
    ]
    for r in report["rows"]:
        note = "INSUFFICIENT (n<5)" if r["insufficient"] else ""
        adj = bonferroni_adjust(r["p_raw"], k_for_bonf) if (r["p_raw"] is not None and not r["insufficient"]) else None
        lines.append(
            f"| {r['bucket']} | {r['n']} | {r['wins']} | {fmt_pct(r['win_rate'])} | "
            f"[{fmt_pct(r['ci_lo'])}, {fmt_pct(r['ci_hi'])}] | "
            f"{fmt_money(r['expectancy'])} | {fmt_p(r['p_raw'])} | {fmt_p(adj)} | {note} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def run() -> dict[str, Any]:
    trades = load_trades()
    baseline = cohort_stats(trades)
    p0 = baseline["win_rate"]

    # Single-dim families
    g_dow = defaultdict(list)
    g_wom = defaultdict(list)
    g_month = defaultdict(list)
    g_dte = defaultdict(list)
    g_hold = defaultdict(list)
    for t in trades:
        g_dow[t.entry_dt.weekday()].append(t)
        g_wom[_wom_bucket(t.entry_dt)].append(t)
        g_month[t.entry_dt.strftime("%Y-%m")].append(t)
        g_dte[_dte_bucket(t.dte_at_entry)].append(t)
        g_hold[_hold_bucket(t.hold_hours)].append(t)

    # Credit/width quartile
    cw_label = _credit_width_quartile(trades)
    g_cw: dict[str, list[Trade]] = defaultdict(list)
    for i, t in enumerate(trades):
        g_cw[cw_label[i]].append(t)

    dow_rep = single_dim_report(
        "By entry day-of-week", g_dow, p0,
        order_keys=[0, 1, 2, 3, 4], label_fn=lambda k: DAY_NAMES[k],
    )
    wom_rep = single_dim_report(
        "By week-of-month (entry)", g_wom, p0,
        order_keys=["W1", "W2", "W3", "W4", "W5"],
    )
    month_rep = single_dim_report(
        "By calendar month (entry)", g_month, p0,
        order_keys=sorted(g_month.keys()),
    )
    dte_rep = single_dim_report(
        "By DTE at entry", g_dte, p0,
        order_keys=["<=21", "22-30", "31-45", ">45", "unknown"],
    )
    hold_rep = single_dim_report(
        "By hold time", g_hold, p0,
        order_keys=["<24h", "1-3d", "3-7d", ">7d"],
    )
    cw_rep = single_dim_report(
        "By credit / (width*100) quartile", g_cw, p0,
        order_keys=sorted(g_cw.keys()),
    )

    # 2D interactions — only families where both dims have multiple n>=15 cells
    # in the marginals are worth examining at this sample size. We test:
    #   day-of-week x DTE-bucket
    #   day-of-week x hold-time-bucket
    #   month x DTE-bucket
    dow_keys = [0, 1, 2, 3, 4]
    dte_keys = ["22-30", "31-45"]  # only the populated DTE buckets
    hold_keys = ["<24h", "1-3d", "3-7d", ">7d"]
    month_keys = sorted(g_month.keys())

    dow_x_dte = two_d_report(
        "2D: day-of-week x DTE", trades, p0,
        key_fn_a=lambda t: t.entry_dt.weekday(),
        key_fn_b=lambda t: _dte_bucket(t.dte_at_entry),
        order_a=dow_keys, order_b=dte_keys,
        label_a=lambda k: DAY_NAMES[k],
    )
    dow_x_hold = two_d_report(
        "2D: day-of-week x hold-time", trades, p0,
        key_fn_a=lambda t: t.entry_dt.weekday(),
        key_fn_b=lambda t: _hold_bucket(t.hold_hours),
        order_a=dow_keys, order_b=hold_keys,
        label_a=lambda k: DAY_NAMES[k],
    )
    month_x_dte = two_d_report(
        "2D: month x DTE", trades, p0,
        key_fn_a=lambda t: t.entry_dt.strftime("%Y-%m"),
        key_fn_b=lambda t: _dte_bucket(t.dte_at_entry),
        order_a=month_keys, order_b=dte_keys,
    )

    seq_rep = sequence_lag1(trades, p0)

    # Compute K = total tested cells with n>=5 across all families
    all_reports = [
        dow_rep, wom_rep, month_rep, dte_rep, hold_rep, cw_rep,
        dow_x_dte, dow_x_hold, month_x_dte, seq_rep,
    ]
    tested_cells: list[tuple[str, str, int, int, float]] = []
    for rep in all_reports:
        for r in rep["rows"]:
            if r["n"] >= 5 and r["p_raw"] is not None:
                tested_cells.append((rep["name"], r["bucket"], r["n"], r["wins"], r["p_raw"]))
    K = len(tested_cells)
    tested_cells.sort(key=lambda x: x[4])

    # Slices that survive Bonferroni at alpha=0.05
    survivors = [c for c in tested_cells if bonferroni_adjust(c[4], K) < 0.05]
    # Positive direction but failing significance — wr > baseline AND raw_p < 0.5
    positive_failing = []
    for rep in all_reports:
        for r in rep["rows"]:
            if r["n"] >= 5 and r["p_raw"] is not None:
                if r["win_rate"] > p0 and r["p_raw"] < 0.5 and bonferroni_adjust(r["p_raw"], K) >= 0.05:
                    positive_failing.append({
                        "family": rep["name"], **r,
                        "bonf_adj_p": bonferroni_adjust(r["p_raw"], K),
                    })

    return {
        "baseline": baseline,
        "reports": {
            "dow": dow_rep, "wom": wom_rep, "month": month_rep,
            "dte": dte_rep, "hold": hold_rep, "credit_width": cw_rep,
            "dow_x_dte": dow_x_dte, "dow_x_hold": dow_x_hold,
            "month_x_dte": month_x_dte, "sequence": seq_rep,
        },
        "multi_comparison": {
            "K_tests_with_n_ge_5": K,
            "min_p_cell": tested_cells[0] if tested_cells else None,
            "survivors_bonf_alpha_0p05": [
                {"family": c[0], "bucket": c[1], "n": c[2], "wins": c[3],
                 "raw_p": c[4], "bonf_adj_p": bonferroni_adjust(c[4], K)}
                for c in survivors
            ],
            "positive_direction_failing_significance": positive_failing,
        },
    }


def _print_md(res: dict[str, Any]) -> None:
    b = res["baseline"]
    K = res["multi_comparison"]["K_tests_with_n_ge_5"]
    print("=" * 78)
    print("DEEPER EDGE ANALYSIS — data/trades.json")
    pf = b["profit_factor"]
    print(
        f"baseline: n={b['n']} wins={b['wins']} losses={b['losses']} "
        f"win_rate={fmt_pct(b['win_rate'])} expectancy={fmt_money(b['expectancy'])} "
        f"PF={'n/a' if pf is None else f'{pf:.3f}'} total_pnl={fmt_money(b['total_pnl'])}"
    )
    print(f"K tested cells (n>=5): {K}")
    print("=" * 78)
    for key in ("dow", "wom", "month", "dte", "hold", "credit_width",
                "dow_x_dte", "dow_x_hold", "month_x_dte", "sequence"):
        print(to_md(res["reports"][key], K))
        print()
    mc = res["multi_comparison"]
    print(f"Survivors at Bonferroni alpha=0.05 (K={K}): {len(mc['survivors_bonf_alpha_0p05'])}")
    for s in mc["survivors_bonf_alpha_0p05"]:
        print(f"  - {s['family']} :: {s['bucket']} "
              f"(n={s['n']}, wins={s['wins']}, raw_p={s['raw_p']:.4f}, "
              f"adj_p={s['bonf_adj_p']:.4f})")
    print(f"Positive-direction-but-failing-significance candidates: "
          f"{len(mc['positive_direction_failing_significance'])}")
    for s in mc["positive_direction_failing_significance"]:
        print(f"  - {s['family']} :: {s['bucket']} "
              f"(n={s['n']}, wins={s['wins']}, wr={fmt_pct(s['win_rate'])}, "
              f"raw_p={s['p_raw']:.4f}, adj_p={s['bonf_adj_p']:.4f})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=str, default=None, help="Optional JSON dump path")
    args = ap.parse_args()
    res = run()
    _print_md(res)
    if args.json:
        # Convert Counter / tuple keys to JSON-safe types
        Path(args.json).write_text(json.dumps(res, indent=2, default=str))
        print(f"Wrote JSON results to {args.json}")


if __name__ == "__main__":
    main()
