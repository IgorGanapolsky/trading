#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class Metric:
    name: str
    value: str
    status: str
    note: str


def safe_read_json(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def parse_kv_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip()
    return values


def max_drawdown_pct(equity_points: list[float]) -> float | None:
    if not equity_points:
        return None
    peak = equity_points[0]
    worst = 0.0
    for e in equity_points:
        if e > peak:
            peak = e
        if peak > 0:
            dd = ((peak - e) / peak) * 100.0
            worst = max(worst, dd)
    return worst


def status_by_threshold(
    value: float | None, *, good_max: float | None = None, good_min: float | None = None
) -> str:
    if value is None:
        return "UNKNOWN"
    if good_max is not None:
        return "PASS" if value <= good_max else "WARN"
    if good_min is not None:
        return "PASS" if value >= good_min else "WARN"
    return "UNKNOWN"


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    for candidate in (v, v + "T00:00:00", v.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue
    return None


def seven_day_delta_from_points(
    points: list[tuple[datetime, float]],
) -> tuple[float | None, float | None, float | None, int]:
    if len(points) < 2:
        return None, None, None, 0
    points.sort(key=lambda x: x[0])
    latest_dt, latest_eq = points[-1]
    target_dt = latest_dt - timedelta(days=7)

    baseline_dt, baseline_eq = points[0]
    for dt, eq in reversed(points):
        if dt <= target_dt:
            baseline_dt, baseline_eq = dt, eq
            break

    days = max(1, int((latest_dt - baseline_dt).total_seconds() // 86400))
    delta = latest_eq - baseline_eq
    delta_pct = (delta / baseline_eq * 100.0) if baseline_eq else None
    monthly_run_rate = (delta / days) * 30.0 if days > 0 else None
    return delta, delta_pct, monthly_run_rate, days


def points_from_rows(rows: list[dict]) -> list[tuple[datetime, float]]:
    points: list[tuple[datetime, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        dt = parse_dt(str(row.get("timestamp") or row.get("date") or ""))
        if dt is None:
            continue
        try:
            equity = float(row.get("equity"))
        except Exception:
            continue
        points.append((dt, equity))
    return points


def estimate_gateway_cost(prompt_tokens: int, completion_tokens: int) -> float | None:
    """Estimate gateway cost using default envs or hardcoded safe fallback."""
    import os

    # Try env vars first
    try:
        input_cost = float(os.environ.get("TARS_INPUT_COST_PER_1M", "0.50"))  # $/1M tokens
        output_cost = float(os.environ.get("TARS_OUTPUT_COST_PER_1M", "1.50"))
    except Exception:
        input_cost = 0.50
        output_cost = 1.50
    # Compute cost
    cost = (prompt_tokens / 1_000_000) * input_cost + (completion_tokens / 1_000_000) * output_cost
    return round(cost, 8) if cost > 0 else None


def _as_float(value) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def expectancy_metrics_from_trades_json(repo_root: Path) -> dict[str, float | int | str | None]:
    """Read expectancy metrics from data/trades.json when available."""
    payload = safe_read_json(repo_root / "data/trades.json")
    trades = payload.get("trades", []) if isinstance(payload, dict) else []
    if not isinstance(trades, list) or not trades:
        return {
            "sample_size": 0,
            "wins": 0,
            "losses": 0,
            "avg_winner": None,
            "avg_loser": None,
            "profit_factor": None,
            "source": "data/trades.json (missing_or_empty)",
        }

    win_pnls: list[float] = []
    loss_pnls: list[float] = []
    for row in trades:
        if not isinstance(row, dict):
            continue
        outcome = str(row.get("outcome", "")).strip().lower()
        pnl = _as_float(row.get("realized_pnl"))

        if pnl is None:
            continue
        if pnl > 0 or outcome == "win":
            win_pnls.append(pnl if pnl > 0 else abs(pnl))
        elif pnl < 0 or outcome == "loss":
            loss_pnls.append(abs(pnl))

    wins = len(win_pnls)
    losses = len(loss_pnls)
    sample = wins + losses
    if sample == 0:
        return {
            "sample_size": 0,
            "wins": 0,
            "losses": 0,
            "avg_winner": None,
            "avg_loser": None,
            "profit_factor": None,
            "source": "data/trades.json (no_closed_pnl)",
        }

    gross_win = sum(win_pnls)
    gross_loss = sum(loss_pnls)
    avg_winner = (gross_win / wins) if wins > 0 else None
    avg_loser = (gross_loss / losses) if losses > 0 else None
    if gross_loss > 0:
        profit_factor = gross_win / gross_loss
    elif gross_win > 0:
        profit_factor = float("inf")
    else:
        profit_factor = None

    return {
        "sample_size": sample,
        "wins": wins,
        "losses": losses,
        "avg_winner": avg_winner,
        "avg_loser": avg_loser,
        "profit_factor": profit_factor,
        "source": "data/trades.json",
    }


def expectancy_metrics_fallback_from_system_state(
    system_state: dict,
) -> dict[str, float | int | str | None]:
    """Fallback expectancy metrics from system_state strategy milestones."""
    milestones = (
        system_state.get("strategy_milestones", {}) if isinstance(system_state, dict) else {}
    )
    families = milestones.get("strategy_families", {}) if isinstance(milestones, dict) else {}
    options_income = families.get("options_income", {}) if isinstance(families, dict) else {}
    metrics = options_income.get("metrics", {}) if isinstance(options_income, dict) else {}

    wins = int(metrics.get("wins", 0) or 0)
    losses = int(metrics.get("losses", 0) or 0)
    sample = int(metrics.get("samples", wins + losses) or (wins + losses))
    total_pnl = _as_float(metrics.get("total_pnl"))

    if sample <= 0:
        return {
            "sample_size": 0,
            "wins": 0,
            "losses": 0,
            "avg_winner": None,
            "avg_loser": None,
            "profit_factor": None,
            "source": "system_state.strategy_milestones (missing)",
        }

    # Fallback can only estimate averages partially when only aggregate pnl is available.
    avg_winner = (
        (total_pnl / wins) if (total_pnl is not None and wins > 0 and losses == 0) else None
    )
    avg_loser = (
        (abs(total_pnl) / losses) if (total_pnl is not None and losses > 0 and wins == 0) else None
    )
    if wins > 0 and losses == 0:
        profit_factor = float("inf")
    elif losses > 0 and wins == 0:
        profit_factor = 0.0
    else:
        profit_factor = None

    return {
        "sample_size": sample,
        "wins": wins,
        "losses": losses,
        "avg_winner": avg_winner,
        "avg_loser": avg_loser,
        "profit_factor": profit_factor,
        "source": "system_state.strategy_milestones",
    }


def expectancy_metrics_from_system_state_history(
    system_state: dict,
) -> dict[str, float | int | str | None]:
    """Calculate expectancy from raw trade history in system_state."""
    history = system_state.get("trade_history", [])
    if not history or not isinstance(history, list):
        return {
            "sample_size": 0,
            "wins": 0,
            "losses": 0,
            "avg_winner": None,
            "avg_loser": None,
            "profit_factor": None,
            "source": "system_state.trade_history (empty)",
        }

    # Group by date to aggregate IC legs
    days: dict[str, float] = {}
    for trade in history:
        pnl = _as_float(trade.get("pnl") or trade.get("realized_pnl"))
        if pnl is None:
            continue
        date = str(trade.get("filled_at") or trade.get("timestamp") or "")[:10]
        if not date:
            continue
        days[date] = days.get(date, 0.0) + pnl

    win_pnls = [v for v in days.values() if v > 0]
    loss_pnls = [abs(v) for v in days.values() if v < 0]

    wins = len(win_pnls)
    losses = len(loss_pnls)
    sample = wins + losses

    if sample == 0:
        return {
            "sample_size": 0,
            "wins": 0,
            "losses": 0,
            "avg_winner": None,
            "avg_loser": None,
            "profit_factor": None,
            "source": "system_state.trade_history (no_pnl)",
        }

    gross_win = sum(win_pnls)
    gross_loss = sum(loss_pnls)
    avg_winner = (gross_win / wins) if wins > 0 else None
    avg_loser = (gross_loss / losses) if losses > 0 else None
    profit_factor = (
        (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else None)
    )

    return {
        "sample_size": sample,
        "wins": wins,
        "losses": losses,
        "avg_winner": avg_winner,
        "avg_loser": avg_loser,
        "profit_factor": profit_factor,
        "source": "system_state.trade_history",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate profit readiness scorecard.")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument(
        "--artifact-dir", default="artifacts/devloop", help="Devloop artifact directory"
    )
    parser.add_argument("--out", default="", help="Output markdown path")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    artifact_dir = Path(args.artifact_dir).resolve()
    out = Path(args.out) if args.out else artifact_dir / "profit_readiness_scorecard.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    system_state = safe_read_json(repo_root / "data/system_state.json")
    smoke_usage = safe_read_json(repo_root / "artifacts/tars/smoke_response.json")
    smoke_metrics = parse_kv_file(repo_root / "artifacts/tars/smoke_metrics.txt")
    loop_status = parse_kv_file(artifact_dir / "status.txt")
    performance_log = safe_read_json(repo_root / "data/performance_log.json")

    paper = system_state.get("paper_account", {}) if isinstance(system_state, dict) else {}
    weekly_gate = (
        system_state.get("north_star_weekly_gate", {}) if isinstance(system_state, dict) else {}
    )
    cadence_kpi = weekly_gate.get("cadence_kpi", {}) if isinstance(weekly_gate, dict) else {}
    no_trade_diagnostic = (
        weekly_gate.get("no_trade_diagnostic", {}) if isinstance(weekly_gate, dict) else {}
    )
    gate_status = (
        no_trade_diagnostic.get("gate_status", {}) if isinstance(no_trade_diagnostic, dict) else {}
    )
    ai_credit_stress = (
        gate_status.get("ai_credit_stress", {}) if isinstance(gate_status, dict) else {}
    )
    win_rate = paper.get("win_rate")
    sample_size = paper.get("win_rate_sample_size")

    history = (
        (((system_state.get("sync_health") or {}).get("history")) or [])
        if isinstance(system_state, dict)
        else []
    )
    equity_series: list[float] = []
    for row in history:
        if not isinstance(row, dict):
            continue
        try:
            equity_series.append(float(row.get("equity")))
        except Exception:
            continue
    drawdown = max_drawdown_pct(equity_series)

    trade_history = (
        (system_state.get("trade_history") or []) if isinstance(system_state, dict) else []
    )
    valid = 0
    total = 0
    for row in trade_history[:100]:
        if not isinstance(row, dict):
            continue
        total += 1
        symbol = str(row.get("symbol") or "").strip().lower()
        side = str(row.get("side") or "").strip().lower()
        if symbol and symbol != "none" and side and side != "none":
            valid += 1
    execution_quality = (valid / total * 100.0) if total > 0 else None

    latency_ms = None
    if "latency_ms" in smoke_metrics:
        try:
            latency_ms = float(smoke_metrics["latency_ms"])
        except Exception:
            latency_ms = None

    total_cost = None
    if "estimated_total_cost_usd" in smoke_metrics:
        try:
            total_cost = float(smoke_metrics["estimated_total_cost_usd"])
        except Exception:
            total_cost = None

    if total_cost is None and isinstance(smoke_usage, dict):
        usage = smoke_usage.get("usage", {})
        try:
            prompt_tokens = int(usage.get("prompt_tokens", 0))
            completion_tokens = int(usage.get("completion_tokens", 0))
            if prompt_tokens + completion_tokens > 0:
                total_cost = estimate_gateway_cost(prompt_tokens, completion_tokens)
        except Exception:
            pass

    metrics = [
        Metric(
            name="Win Rate",
            value=f"{float(win_rate):.2f}%" if win_rate is not None else "N/A",
            status=status_by_threshold(
                float(win_rate) if win_rate is not None else None, good_min=55.0
            ),
            note=f"sample_size={sample_size}" if sample_size is not None else "sample_size=N/A",
        ),
        Metric(
            name="Max Drawdown (sync history)",
            value=f"{drawdown:.2f}%" if drawdown is not None else "N/A",
            status=status_by_threshold(drawdown, good_max=5.0),
            note=f"equity_points={len(equity_series)}",
        ),
        Metric(
            name="Execution Quality (valid trade records)",
            value=f"{execution_quality:.2f}%" if execution_quality is not None else "N/A",
            status=status_by_threshold(execution_quality, good_min=95.0),
            note=f"valid={valid}/{total}",
        ),
        Metric(
            name="Gateway Latency",
            value=f"{latency_ms:.0f} ms" if latency_ms is not None else "N/A",
            status=status_by_threshold(latency_ms, good_max=2500.0),
            note="from artifacts/tars/smoke_metrics.txt",
        ),
        Metric(
            name="Gateway Cost (smoke call)",
            value=f"${total_cost:.6f}" if total_cost is not None else "N/A",
            status="PASS" if total_cost is not None else "UNKNOWN",
            note="set TARS_INPUT_COST_PER_1M and TARS_OUTPUT_COST_PER_1M for estimate",
        ),
    ]

    # Try sources in order of specificity
    expectancy = expectancy_metrics_from_system_state_history(system_state)
    if int(expectancy.get("sample_size", 0) or 0) == 0:
        expectancy = expectancy_metrics_from_trades_json(repo_root)
    if int(expectancy.get("sample_size", 0) or 0) == 0:
        expectancy = expectancy_metrics_fallback_from_system_state(system_state)

    pf = expectancy.get("profit_factor")
    avg_winner = expectancy.get("avg_winner")
    avg_loser = expectancy.get("avg_loser")
    exp_sample = int(expectancy.get("sample_size", 0) or 0)
    exp_wins = int(expectancy.get("wins", 0) or 0)
    exp_losses = int(expectancy.get("losses", 0) or 0)
    exp_source = str(expectancy.get("source", "unknown"))

    if pf is None:
        pf_value = "N/A"
        pf_status = "UNKNOWN"
    elif pf == float("inf"):
        pf_value = "Inf"
        pf_status = "PASS"
    else:
        pf_value = f"{float(pf):.2f}"
        pf_status = status_by_threshold(float(pf), good_min=1.5)

    metrics.extend(
        [
            Metric(
                name="Profit Factor",
                value=pf_value,
                status=pf_status,
                note=f"wins={exp_wins} losses={exp_losses} sample={exp_sample} source={exp_source}",
            ),
            Metric(
                name="Average Winner",
                value=f"${float(avg_winner):.2f}" if avg_winner is not None else "N/A",
                status="PASS" if avg_winner is not None else "UNKNOWN",
                note=f"source={exp_source}",
            ),
            Metric(
                name="Average Loser",
                value=f"${float(avg_loser):.2f}" if avg_loser is not None else "N/A",
                status="PASS" if avg_loser is not None else "UNKNOWN",
                note=f"source={exp_source}",
            ),
        ]
    )
    setups_observed = cadence_kpi.get("qualified_setups_observed")
    setups_min = cadence_kpi.get("min_qualified_setups_per_week")
    trades_observed = cadence_kpi.get("closed_trades_observed")
    trades_min = cadence_kpi.get("min_closed_trades_per_week")
    setups_status = "UNKNOWN"
    if isinstance(setups_observed, int) and isinstance(setups_min, int):
        setups_status = "PASS" if setups_observed >= setups_min else "WARN"
    trades_status = "UNKNOWN"
    if isinstance(trades_observed, int) and isinstance(trades_min, int):
        trades_status = "PASS" if trades_observed >= trades_min else "WARN"
    metrics.extend(
        [
            Metric(
                name="Weekly Qualified Setups",
                value=(
                    f"{int(setups_observed)}/{int(setups_min)}"
                    if isinstance(setups_observed, int) and isinstance(setups_min, int)
                    else "N/A"
                ),
                status=setups_status,
                note="north_star_weekly_gate.cadence_kpi",
            ),
            Metric(
                name="Weekly Closed Trades",
                value=(
                    f"{int(trades_observed)}/{int(trades_min)}"
                    if isinstance(trades_observed, int) and isinstance(trades_min, int)
                    else "N/A"
                ),
                status=trades_status,
                note="north_star_weekly_gate.cadence_kpi",
            ),
        ]
    )
    ai_status_raw = str(ai_credit_stress.get("status") or "unknown").strip().lower()
    ai_score = ai_credit_stress.get("severity_score")
    ai_status = "UNKNOWN"
    if ai_status_raw == "pass":
        ai_status = "PASS"
    elif ai_status_raw in {"watch", "blocked"}:
        ai_status = "WARN"

    ai_value = ai_status_raw
    if isinstance(ai_score, (int, float)):
        ai_value = f"{ai_status_raw} (score={float(ai_score):.1f})"

    metrics.append(
        Metric(
            name="AI Credit Stress Gate",
            value=ai_value,
            status=ai_status,
            note="north_star_weekly_gate.no_trade_diagnostic.gate_status.ai_credit_stress",
        )
    )

    delta_7d = None
    delta_7d_pct = None
    monthly_run_rate = None
    delta_days = 0
    delta_source = "none"
    sync_points = points_from_rows(history if isinstance(history, list) else [])
    if len(sync_points) >= 2:
        delta_7d, delta_7d_pct, monthly_run_rate, delta_days = seven_day_delta_from_points(
            sync_points
        )
        delta_source = "sync_health.history"
    elif isinstance(performance_log, list):
        perf_points = points_from_rows(performance_log)
        if len(perf_points) >= 2:
            delta_7d, delta_7d_pct, monthly_run_rate, delta_days = seven_day_delta_from_points(
                perf_points
            )
            delta_source = "performance_log"

    ruff_exit = loop_status.get("ruff_exit", "N/A")
    pytest_exit = loop_status.get("pytest_exit", "N/A")

    lines: list[str] = []
    lines.append("# Profit Readiness Scorecard")
    lines.append("")
    lines.append("## Gate Health")
    lines.append(f"- lint_exit: {ruff_exit}")
    lines.append(f"- test_exit: {pytest_exit}")
    lines.append("")
    lines.append("## Metrics")
    for m in metrics:
        lines.append(f"- {m.name}: {m.value} [{m.status}] ({m.note})")
    lines.append("")
    lines.append("## 7-Day Delta")
    if delta_7d is None:
        lines.append("- Equity delta: N/A [UNKNOWN] (insufficient history)")
        lines.append("- Monthly run-rate estimate: N/A [UNKNOWN]")
    else:
        delta_status = "PASS" if delta_7d > 0 else "WARN"
        run_rate_status = (
            "PASS" if monthly_run_rate is not None and monthly_run_rate >= 6000 else "WARN"
        )
        delta_pct_text = f"{delta_7d_pct:.2f}%" if delta_7d_pct is not None else "N/A"
        run_rate_text = f"${monthly_run_rate:,.2f}/month" if monthly_run_rate is not None else "N/A"
        lines.append(
            f"- Equity delta ({delta_days}d): ${delta_7d:,.2f} ({delta_pct_text}) [{delta_status}]"
        )
        lines.append(f"- Monthly run-rate estimate: {run_rate_text} [{run_rate_status}]")
        lines.append(f"- Data source: {delta_source}")
        lines.append("- North Star target: $6,000/month after tax")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("- PASS means metric is within current readiness threshold.")
    lines.append("- WARN means metric needs improvement before scaling risk.")
    lines.append("- UNKNOWN means data is not yet captured for this metric.")
    lines.append("")
    lines.append("## Weekly Cadence & No-Trade Diagnostic")
    cadence_summary = str(cadence_kpi.get("summary") or "Cadence KPI not available.")
    lines.append(f"- Cadence Summary: {cadence_summary}")
    blocked_categories = no_trade_diagnostic.get("blocked_categories", [])
    if isinstance(blocked_categories, list) and blocked_categories:
        lines.append(f"- Blocked Gate Categories: {', '.join(str(x) for x in blocked_categories)}")
    else:
        lines.append("- Blocked Gate Categories: none")
    diagnostic_summary = str(
        no_trade_diagnostic.get("summary") or "No weekly diagnostic available."
    )
    lines.append(f"- Diagnostic Summary: {diagnostic_summary}")
    lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"ok: scorecard generated -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
