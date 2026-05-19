"""Edge analysis on data/trades.json (paired closed iron condors).

Question 1 (PRIMARY): Does Thursday entry have a materially higher win rate
than other weekdays, surviving multi-comparison correction?
Question 2: Does any other conditional slice (DTE bin, hold-time bucket,
credit/width quartile) carry a real edge on this sample?

Constraints honored:
- No synthetic data; uses only fields present in data/trades.json.
- No projections; reports realized stats only.
- n is reported in every cell; cells with n<5 are flagged "INSUFFICIENT".
- Uses scipy if present, falls back to stdlib math for binomial CDF and
  Wilson CI.

Run:
    python3 scripts/research/edge_analysis_2026_05_19.py [--json out.json]

Outputs a Markdown-ready text block to stdout and (optionally) a JSON
dump for the docs writer.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
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
# Statistics helpers
# ---------------------------------------------------------------------------


def wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% confidence interval for a binomial proportion.

    Returns (lo, hi) in [0,1]. If n==0 returns (0,0).
    """
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    lo = (center - spread) / denom
    hi = (center + spread) / denom
    return (max(0.0, lo), min(1.0, hi))


def binom_logcdf_geq(k: int, n: int, p: float) -> float:
    """One-sided binomial test: P(X >= k | n, p), stdlib fallback.

    Uses scipy if available for precision.
    """
    if HAVE_SCIPY:
        return float(binomtest(k, n, p, alternative="greater").pvalue)
    # stdlib: sum_{i=k..n} C(n,i) p^i (1-p)^(n-i)
    total = 0.0
    for i in range(k, n + 1):
        total += math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    return total


# ---------------------------------------------------------------------------
# Data loading and feature derivation
# ---------------------------------------------------------------------------


@dataclass
class Trade:
    """Normalized closed iron-condor record."""

    raw: dict[str, Any]
    entry_dt: datetime
    exit_dt: datetime
    expiry_date: datetime | None
    realized_pnl: float
    outcome: str  # "win" | "loss" | "breakeven"
    entry_credit: float
    # Derived
    dte_at_entry: int | None
    hold_hours: float
    width: float | None  # strike width in dollars (assumes equal put/call width)


def parse_iso(s: str) -> datetime:
    # Handle "2026-01-22T17:48:41.448722+00:00" and "2026-01-22"
    if len(s) == 10:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(s)


def load_trades(path: Path = TRADES_PATH) -> list[Trade]:
    raw = json.loads(path.read_text())
    out: list[Trade] = []
    for t in raw["trades"]:
        if t.get("status") != "closed":
            continue
        entry_dt = parse_iso(t["entry_time"])
        exit_dt = parse_iso(t["exit_time"])
        legs = t.get("legs") or {}
        expiry_s = legs.get("expiry")
        expiry_dt = parse_iso(expiry_s) if expiry_s else None
        dte = (expiry_dt.date() - entry_dt.date()).days if expiry_dt else None
        hold_h = (exit_dt - entry_dt).total_seconds() / 3600.0
        put_strikes = legs.get("put_strikes") or []
        call_strikes = legs.get("call_strikes") or []
        width: float | None = None
        if len(put_strikes) == 2 and len(call_strikes) == 2:
            pw = abs(put_strikes[1] - put_strikes[0])
            cw = abs(call_strikes[1] - call_strikes[0])
            # Use average if they ever diverge.
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
# Aggregations
# ---------------------------------------------------------------------------


def cohort_stats(trades: list[Trade]) -> dict[str, Any]:
    """Aggregate win_rate, avg_win, avg_loss, profit_factor, expectancy, total_pnl.

    Breakeven (pnl == 0) trades are counted in `n` but not in wins/losses.
    Profit factor = sum(wins) / |sum(losses)| (None if no losses).
    Expectancy = mean(realized_pnl).
    """
    n = len(trades)
    wins = [t.realized_pnl for t in trades if t.outcome == "win"]
    losses = [t.realized_pnl for t in trades if t.outcome == "loss"]
    n_w = len(wins)
    n_l = len(losses)
    win_rate = n_w / n if n else 0.0
    avg_win = statistics.mean(wins) if wins else 0.0
    avg_loss = statistics.mean(losses) if losses else 0.0  # negative
    total_w = sum(wins)
    total_l = sum(losses)
    pf: float | None = None
    if total_l != 0:
        pf = total_w / abs(total_l)
    expectancy = (sum(t.realized_pnl for t in trades) / n) if n else 0.0
    lo, hi = wilson_ci(n_w, n)
    return {
        "n": n,
        "wins": n_w,
        "losses": n_l,
        "win_rate": win_rate,
        "win_rate_ci95": (lo, hi),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": pf,
        "expectancy": expectancy,
        "total_pnl": sum(t.realized_pnl for t in trades),
    }


def group_by_weekday(trades: list[Trade]) -> dict[int, list[Trade]]:
    """Group trades by entry_dt.weekday() (0=Mon..6=Sun)."""
    g: dict[int, list[Trade]] = defaultdict(list)
    for t in trades:
        g[t.entry_dt.weekday()].append(t)
    return g


def group_by_dte(trades: list[Trade]) -> dict[str, list[Trade]]:
    """DTE buckets: <=21, 22-30, 31-45, >45, unknown."""
    g: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        d = t.dte_at_entry
        if d is None:
            g["unknown"].append(t)
        elif d <= 21:
            g["<=21"].append(t)
        elif d <= 30:
            g["22-30"].append(t)
        elif d <= 45:
            g["31-45"].append(t)
        else:
            g[">45"].append(t)
    return g


def group_by_hold(trades: list[Trade]) -> dict[str, list[Trade]]:
    """Hold-time buckets in hours."""
    g: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        h = t.hold_hours
        if h < 24:
            g["<24h"].append(t)
        elif h < 72:
            g["1-3d"].append(t)
        elif h < 168:
            g["3-7d"].append(t)
        else:
            g[">7d"].append(t)
    return g


def group_by_credit_width_ratio(trades: list[Trade]) -> dict[str, list[Trade]]:
    """Bucket by quartiles of credit/width. Trades without width go to 'unknown'."""
    have = [t for t in trades if t.width and t.width > 0]
    miss = [t for t in trades if not (t.width and t.width > 0)]
    if not have:
        return {"unknown": miss}
    # Credit is per-contract dollars; iron-condor credit collected on $X-wide
    # spread means max-loss = (width * 100) - credit. Here we use the ratio
    # credit / (width*100) which is "fraction of max risk collected".
    ratios = sorted(t.entry_credit / (t.width * 100.0) for t in have)
    n = len(ratios)
    q1 = ratios[n // 4]
    q2 = ratios[n // 2]
    q3 = ratios[(3 * n) // 4]
    g: dict[str, list[Trade]] = defaultdict(list)
    for t in have:
        r = t.entry_credit / (t.width * 100.0)
        if r <= q1:
            g[f"Q1 (<= {q1:.3f})"].append(t)
        elif r <= q2:
            g[f"Q2 ({q1:.3f} - {q2:.3f}]"].append(t)
        elif r <= q3:
            g[f"Q3 ({q2:.3f} - {q3:.3f}]"].append(t)
        else:
            g[f"Q4 (> {q3:.3f})"].append(t)
    if miss:
        g["unknown"].append(miss[0])  # tag presence but don't pollute
        g["unknown"] = miss
    return g


def streaks(trades: list[Trade]) -> tuple[int, int]:
    """Return (max_consecutive_wins, max_consecutive_losses) in chronological order."""
    by_time = sorted(trades, key=lambda t: t.exit_dt)
    max_w = max_l = 0
    cur_w = cur_l = 0
    for t in by_time:
        if t.outcome == "win":
            cur_w += 1
            cur_l = 0
            max_w = max(max_w, cur_w)
        elif t.outcome == "loss":
            cur_l += 1
            cur_w = 0
            max_l = max(max_l, cur_l)
        else:
            cur_w = cur_l = 0
    return (max_w, max_l)


def field_coverage(path: Path = TRADES_PATH) -> tuple[int, dict[str, int]]:
    raw = json.loads(path.read_text())
    trades = raw["trades"]
    cov: Counter[str] = Counter()
    for t in trades:
        for k, v in t.items():
            if v not in (None, "", [], {}):
                cov[k] += 1
    return len(trades), dict(cov)


# ---------------------------------------------------------------------------
# Main reporting
# ---------------------------------------------------------------------------


def stratification_report(
    name: str,
    groups: dict[Any, list[Trade]],
    baseline_p: float,
    order_keys: list[Any] | None = None,
) -> dict[str, Any]:
    """For each bucket compute n, wins, win_rate, Wilson CI, expectancy, and
    one-sided binomial p-value vs `baseline_p`.

    p-value uses P(X >= wins | n, baseline_p); for a low-win-rate slice this
    will be ~1, which is the correct semantics.
    """
    rows = []
    keys = order_keys if order_keys is not None else list(groups.keys())
    for k in keys:
        ts = groups.get(k, [])
        n = len(ts)
        wins = sum(1 for t in ts if t.outcome == "win")
        wr = wins / n if n else 0.0
        lo, hi = wilson_ci(wins, n)
        exp = (sum(t.realized_pnl for t in ts) / n) if n else 0.0
        if n > 0:
            pval_high = binom_logcdf_geq(wins, n, baseline_p)
        else:
            pval_high = None
        rows.append(
            {
                "bucket": str(k),
                "n": n,
                "wins": wins,
                "win_rate": wr,
                "ci_lo": lo,
                "ci_hi": hi,
                "expectancy": exp,
                "p_one_sided_greater_than_baseline": pval_high,
                "insufficient": n < 5,
            }
        )
    return {"name": name, "baseline_win_rate": baseline_p, "rows": rows}


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{100*x:.1f}%"


def fmt_money(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"${x:,.2f}"


def to_markdown_table(report: dict[str, Any]) -> str:
    lines = [
        f"### {report['name']} (baseline win rate {fmt_pct(report['baseline_win_rate'])})",
        "",
        "| Bucket | n | wins | win_rate | 95% Wilson CI | expectancy | p (>= vs baseline) | Note |",
        "|---|---:|---:|---:|---|---:|---:|---|",
    ]
    for r in report["rows"]:
        note = "INSUFFICIENT (n<5)" if r["insufficient"] else ""
        pval = r["p_one_sided_greater_than_baseline"]
        pval_str = "n/a" if pval is None else f"{pval:.3f}"
        lines.append(
            f"| {r['bucket']} | {r['n']} | {r['wins']} | {fmt_pct(r['win_rate'])} | "
            f"[{fmt_pct(r['ci_lo'])}, {fmt_pct(r['ci_hi'])}] | "
            f"{fmt_money(r['expectancy'])} | {pval_str} | {note} |"
        )
    return "\n".join(lines)


def run() -> dict[str, Any]:
    trades = load_trades()
    n_total, coverage = field_coverage()

    baseline = cohort_stats(trades)
    base_p = baseline["win_rate"]

    weekday_groups = group_by_weekday(trades)
    weekday_rep = stratification_report(
        "By entry day-of-week",
        weekday_groups,
        base_p,
        order_keys=[0, 1, 2, 3, 4, 5, 6],
    )
    # Re-label bucket names
    for row, idx in zip(weekday_rep["rows"], [0, 1, 2, 3, 4, 5, 6]):
        row["bucket"] = DAY_NAMES[idx]

    dte_rep = stratification_report(
        "By DTE at entry",
        group_by_dte(trades),
        base_p,
        order_keys=["<=21", "22-30", "31-45", ">45", "unknown"],
    )
    hold_rep = stratification_report(
        "By hold time",
        group_by_hold(trades),
        base_p,
        order_keys=["<24h", "1-3d", "3-7d", ">7d"],
    )
    cw_groups = group_by_credit_width_ratio(trades)
    cw_rep = stratification_report(
        "By credit/(width*100) ratio quartile",
        cw_groups,
        base_p,
        order_keys=list(cw_groups.keys()),
    )

    max_w, max_l = streaks(trades)

    # Multi-comparison: K stratifications (we examine 4 distinct families).
    # Within each family, pick the minimum p-value; apply Bonferroni over the
    # total number of buckets actually tested (n>=1).
    all_pvals = []
    for rep in (weekday_rep, dte_rep, hold_rep, cw_rep):
        for r in rep["rows"]:
            if r["n"] >= 5 and r["p_one_sided_greater_than_baseline"] is not None:
                all_pvals.append((rep["name"], r["bucket"], r["n"], r["wins"], r["p_one_sided_greater_than_baseline"]))
    K = len(all_pvals)
    if all_pvals:
        all_pvals.sort(key=lambda x: x[4])
        min_p_name, min_p_bucket, min_p_n, min_p_w, min_p_val = all_pvals[0]
        bonferroni_p = min(1.0, min_p_val * K)
    else:
        min_p_name = min_p_bucket = None
        min_p_n = min_p_w = 0
        min_p_val = bonferroni_p = None

    return {
        "n_total_records": n_total,
        "field_coverage": coverage,
        "baseline": baseline,
        "weekday": weekday_rep,
        "dte": dte_rep,
        "hold": hold_rep,
        "credit_width": cw_rep,
        "streaks": {"max_consecutive_wins": max_w, "max_consecutive_losses": max_l},
        "multi_comparison": {
            "K_tests_with_n_ge_5": K,
            "min_p_family": min_p_name,
            "min_p_bucket": min_p_bucket,
            "min_p_n": min_p_n,
            "min_p_wins": min_p_w,
            "min_p_value": min_p_val,
            "bonferroni_adjusted_p": bonferroni_p,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=str, default=None, help="Optional path to dump JSON results")
    args = ap.parse_args()
    res = run()
    # Pretty print to stdout
    b = res["baseline"]
    print("=" * 78)
    print("EDGE ANALYSIS — data/trades.json")
    print(f"Records in file:   {res['n_total_records']}")
    print(f"Closed trades:     n={b['n']}")
    pf_val = b["profit_factor"]
    pf_str = "n/a" if pf_val is None else f"{pf_val:.3f}"
    ci_lo, ci_hi = b["win_rate_ci95"]
    print(
        f"Baseline: win_rate={fmt_pct(b['win_rate'])} CI95=[{fmt_pct(ci_lo)}, "
        f"{fmt_pct(ci_hi)}] expectancy={fmt_money(b['expectancy'])} "
        f"PF={pf_str} total_pnl={fmt_money(b['total_pnl'])} "
        f"avg_win={fmt_money(b['avg_win'])} avg_loss={fmt_money(b['avg_loss'])}"
    )
    print("=" * 78)
    print(to_markdown_table(res["weekday"]))
    print()
    print(to_markdown_table(res["dte"]))
    print()
    print(to_markdown_table(res["hold"]))
    print()
    print(to_markdown_table(res["credit_width"]))
    print()
    mc = res["multi_comparison"]
    print(
        f"Streaks: max_consecutive_wins={res['streaks']['max_consecutive_wins']} "
        f"max_consecutive_losses={res['streaks']['max_consecutive_losses']}"
    )
    print(
        f"Multi-comparison: K={mc['K_tests_with_n_ge_5']} min p-value={mc['min_p_value']} "
        f"family='{mc['min_p_family']}' bucket='{mc['min_p_bucket']}' "
        f"(n={mc['min_p_n']}, wins={mc['min_p_wins']}) "
        f"Bonferroni adj_p={mc['bonferroni_adjusted_p']}"
    )
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2, default=str))
        print(f"Wrote JSON results to {args.json}")


if __name__ == "__main__":
    main()
