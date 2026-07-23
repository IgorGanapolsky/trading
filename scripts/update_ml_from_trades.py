#!/usr/bin/env python3
"""
Update ML Models from Real Trade Data — Closes the Feedback Loop.

FIX Apr 3, 2026: The Thompson Sampler had stale priors (86/14 from
Tastytrade research) while real trades showed 24% win rate. Trade
outcomes in trade_trajectories.jsonl were never fed back to the model.

This script:
1. Reads canonical trades.json for real win/loss counts
2. Updates Thompson Sampler (trade_confidence_model.json) with empirical priors
3. Checks if win rate warrants trading (auto-blocks if < 50% over 30+ trades)
4. Generates post-mortem lessons from losing trades into RAG
5. Logs drift detection: model expected vs realized win rate

Run daily via cron or after sync_closed_positions.py.

Usage:
    python3 scripts/update_ml_from_trades.py
    python3 scripts/update_ml_from_trades.py --dry-run
"""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.loss_forensics import (  # noqa: E402
    analyze_loss_clusters as forensics_analyze_loss_clusters,
    build_system_diagnosis,
    diagnosis_to_markdown,
    strategy_family,
    wing_width as forensics_wing_width,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
TRADES_FILE = PROJECT_ROOT / "data" / "trades.json"
MODEL_FILE = PROJECT_ROOT / "models" / "ml" / "trade_confidence_model.json"
LESSONS_DIR = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"
SYSTEM_STATE_FILE = PROJECT_ROOT / "data" / "system_state.json"
REHAB_PLAN_FILE = PROJECT_ROOT / "data" / "runtime" / "edge_rehabilitation_plan.json"
DIAGNOSIS_FILE = PROJECT_ROOT / "data" / "runtime" / "system_diagnosis_latest.json"
DIAGNOSIS_LESSON_ID = "system_misery_diagnosis_current"
KILL_SWITCH_FILE = PROJECT_ROOT / "data" / "runtime" / "strategy_kill_switch.json"
REHAB_LESSON_ID = "strategy_rehabilitation_ic_simple_current"
SUCCESSOR_FAMILY = "spy_put_credit"
KILLED_FAMILIES = frozenset({"ic_simple", "iron_condor"})

# Thresholds
MIN_TRADES_FOR_GATE = 30
MIN_WIN_RATE_TO_TRADE = 50.0  # %
MIN_EXPECTANCY_TO_TRADE = 0.0  # $/trade; breakeven is not an edge
MIN_PROFIT_FACTOR_TO_TRADE = 1.0  # breakeven is not an edge
DRIFT_ALERT_THRESHOLD = 20.0  # % divergence between model and realized
VALIDATION_PHASE_START_DATE = "2026-04-10"
VALIDATION_RESET_NOTE = (
    "2026-04-10: Reset for controlled paper validation. Legacy 66-trade data "
    "came from the broken pre-fix system and must not overwrite validation priors."
)


def load_trades() -> dict:
    """Load canonical trades.json."""
    if not TRADES_FILE.exists():
        logger.error(f"Trades file not found: {TRADES_FILE}")
        return {"stats": {}, "trades": []}
    result: dict = json.loads(TRADES_FILE.read_text())
    return result


def load_model() -> dict:
    """Load current Thompson Sampler model."""
    if not MODEL_FILE.exists():
        return {
            "iron_condor": {"alpha": 1.0, "beta": 1.0, "wins": 0, "losses": 0},
            "spy_specific": {"alpha": 1.0, "beta": 1.0, "wins": 0, "losses": 0},
            "regime_adjustments": {"calm": 1.1, "trending": 0.9, "volatile": 0.8, "spike": 0.5},
        }
    result: dict = json.loads(MODEL_FILE.read_text())
    return result


def is_validation_reset_model(model: dict) -> bool:
    """Detect validation-reset mode across old and new model file shapes."""
    return bool(model.get("validation_reset")) or (
        str(model.get("feedback_source") or "").strip().lower() == "validation_reset"
    )


def _is_validation_phase_trade(trade: dict) -> bool:
    if trade.get("validation_phase"):
        return True
    entry_date = (
        trade.get("entry_date")
        or trade.get("opened_at")
        or trade.get("entry_time")
        or trade.get("timestamp")
        or ""
    )
    return str(entry_date)[:10] >= VALIDATION_PHASE_START_DATE


def validation_phase_trades(trades_data: dict) -> list[dict]:
    """Return only validation-phase trades; excludes legacy failure cohort."""
    trades = trades_data.get("trades", [])
    return [
        trade for trade in trades if isinstance(trade, dict) and _is_validation_phase_trade(trade)
    ]


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_metric(value: float, digits: int = 2) -> float:
    return value if math.isinf(value) else round(value, digits)


def _trade_pnl(trade: dict) -> tuple[float, bool]:
    """Return numeric P/L and whether the row had a parseable explicit value."""
    raw = trade.get("realized_pnl")
    if raw is None:
        raw = trade.get("pnl")
    if raw is None or raw == "":
        return 0.0, False
    try:
        return float(raw), True
    except (TypeError, ValueError):
        return 0.0, False


def _holding_hours(trade: dict) -> float | None:
    entry_time = trade.get("entry_time") or trade.get("opened_at")
    exit_time = trade.get("exit_time") or trade.get("closed_at")
    if not entry_time or not exit_time:
        return None
    try:
        opened = datetime.fromisoformat(str(entry_time).replace("Z", "+00:00"))
        closed = datetime.fromisoformat(str(exit_time).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return max(0.0, (closed - opened).total_seconds() / 3600)


def _wing_width(trade: dict) -> float | None:
    """Wing width via shared forensics (structured legs, trade id, OCC symbols)."""
    return forensics_wing_width(trade)


def stats_from_trades(trades: list[dict], cohort_unpaired_stats: dict | None = None) -> dict:
    """Build the stats shape expected by the Thompson updater from trade rows."""
    wins: list[float] = []
    losses: list[float] = []
    skipped_trades = 0
    ambiguous_outcome_trades = 0
    missing_pnl_trades = 0
    for trade in trades:
        outcome = str(trade.get("outcome") or "").strip().lower()
        pnl_float, has_parseable_pnl = _trade_pnl(trade)
        if not has_parseable_pnl:
            missing_pnl_trades += 1

        if outcome not in {"win", "loss"}:
            if pnl_float > 0:
                outcome = "win"
            elif pnl_float < 0:
                outcome = "loss"
            else:
                ambiguous_outcome_trades += 1
                skipped_trades += 1
                continue

        if outcome == "win":
            wins.append(pnl_float)
        elif outcome == "loss":
            losses.append(pnl_float)

    # Fold unpaired singletons if provided
    u_wins = cohort_unpaired_stats.get("unpaired_cohort_wins", 0) if cohort_unpaired_stats else 0
    u_losses = (
        cohort_unpaired_stats.get("unpaired_cohort_losses", 0) if cohort_unpaired_stats else 0
    )
    u_gross_profit = (
        cohort_unpaired_stats.get("unpaired_cohort_gross_profit", 0.0)
        if cohort_unpaired_stats
        else 0.0
    )
    u_gross_loss = (
        cohort_unpaired_stats.get("unpaired_cohort_gross_loss", 0.0)
        if cohort_unpaired_stats
        else 0.0
    )
    u_pnl = (
        cohort_unpaired_stats.get("unpaired_in_cohort_pnl", 0.0) if cohort_unpaired_stats else 0.0
    )

    wins_folded = len(wins) + u_wins
    losses_folded = len(losses) + u_losses
    closed_folded = wins_folded + losses_folded

    input_trades = len(trades)
    win_rate = (wins_folded / closed_folded * 100) if closed_folded else 0.0
    gross_profit_folded = sum(pnl for pnl in wins if pnl > 0) + u_gross_profit
    gross_loss_folded = abs(sum(pnl for pnl in losses if pnl < 0)) + u_gross_loss
    total_realized_pnl_folded = sum(wins) + sum(losses) + u_pnl
    quality_denominator = max(input_trades, 1)
    quality_penalty = (
        skipped_trades + min(missing_pnl_trades, closed_folded)
    ) / quality_denominator
    data_quality_score = round(max(0.0, 1.0 - quality_penalty), 3)

    if gross_loss_folded > 0:
        profit_factor = gross_profit_folded / gross_loss_folded
    elif gross_profit_folded > 0:
        profit_factor = math.inf
    else:
        profit_factor = 0.0

    expectancy = total_realized_pnl_folded / closed_folded if closed_folded else 0.0

    return {
        "wins": wins_folded,
        "losses": losses_folded,
        "closed_trades": closed_folded,
        "input_trades": input_trades,
        "skipped_trades": skipped_trades,
        "ambiguous_outcome_trades": ambiguous_outcome_trades,
        "missing_pnl_trades": missing_pnl_trades,
        "data_quality_score": data_quality_score,
        "win_rate_pct": round(win_rate, 2),
        "avg_win": gross_profit_folded / wins_folded if wins_folded else 0,
        "avg_loss": gross_loss_folded / losses_folded if losses_folded else 0,
        "gross_profit": round(gross_profit_folded, 2),
        "gross_loss": round(gross_loss_folded, 2),
        "total_realized_pnl": round(total_realized_pnl_folded, 2),
        "profit_factor": _round_metric(profit_factor),
        "expectancy_per_trade": round(expectancy, 2),
    }


def analyze_loss_clusters(trades_data: dict) -> list[dict]:
    """Summarize recurring loss clusters so RAG/ML learns what to stop repeating."""
    return forensics_analyze_loss_clusters(trades_data)


def trades_for_family(trades_data: dict, family: str) -> list[dict]:
    """Filter closed-trade rows belonging to a strategy family."""
    wanted = family.strip().lower().replace(" ", "_")
    out: list[dict] = []
    for trade in trades_data.get("trades", []):
        if not isinstance(trade, dict):
            continue
        fam = strategy_family(trade)
        if wanted in {"iron_condor", "ic_simple"} and fam == "iron_condor":
            out.append(trade)
        elif wanted in {"spy_put_credit", "put_credit", "bull_put"} and fam == "spy_put_credit":
            out.append(trade)
        elif fam == wanted:
            out.append(trade)
    return out


def load_active_family() -> str:
    if KILL_SWITCH_FILE.exists():
        try:
            payload = json.loads(KILL_SWITCH_FILE.read_text())
            family = str(payload.get("active_family") or SUCCESSOR_FAMILY)
            if family:
                return family
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return SUCCESSOR_FAMILY


def build_rehabilitation_plan(trades_data: dict, gate: dict) -> dict:
    """Build a machine-readable quarantine and validation plan from the current ledger."""
    stats = trades_data.get("stats", {})
    clusters = analyze_loss_clusters(trades_data)
    top_clusters = clusters[:3]
    changed_rules = [cluster["recommendation"] for cluster in top_clusters]
    if not changed_rules:
        changed_rules = [
            "No recurring loss cluster was detected; require manual root-cause analysis before resuming validation entries."
        ]

    ledger = {
        "closed_trades": int(stats.get("closed_trades") or gate.get("total_trades") or 0),
        "wins": int(stats.get("wins") or 0),
        "losses": int(stats.get("losses") or 0),
        "win_rate_pct": _as_float(stats.get("win_rate_pct"), gate.get("win_rate", 0.0)),
        "profit_factor": _as_float(stats.get("profit_factor"), gate.get("profit_factor", 0.0)),
        "total_realized_pnl": _as_float(
            stats.get("total_realized_pnl"), stats.get("total_pnl", 0.0)
        ),
        "expectancy_per_trade": _as_float(
            stats.get("expectancy_per_trade"), gate.get("expectancy_per_trade", 0.0)
        ),
    }
    if not ledger["expectancy_per_trade"] and ledger["closed_trades"]:
        ledger["expectancy_per_trade"] = round(
            ledger["total_realized_pnl"] / ledger["closed_trades"], 4
        )

    active_family = load_active_family()
    ic_killed = active_family in {SUCCESSOR_FAMILY, "spy_put_credit"} or True
    # IC is always treated as killed once successor is active; rehab plan records that fact.
    status = "killed" if active_family == SUCCESSOR_FAMILY else (
        "quarantined" if not gate.get("should_trade") else "eligible"
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy_family": "ic_simple",
        "status": status,
        "killed_at": datetime.now(timezone.utc).isoformat() if status == "killed" else None,
        "successor_strategy_family": SUCCESSOR_FAMILY,
        "profitability_objective": (
            "IC Simple is removed as a North Star candidate. New paper validation only under "
            f"{SUCCESSOR_FAMILY} with positive expectancy, PF>1, and positive realized P/L over "
            f">={MIN_TRADES_FOR_GATE} trades."
        ),
        "ledger": ledger,
        "gate": {
            "should_trade": False if status == "killed" else bool(gate.get("should_trade")),
            "block_reason": (
                f"STRATEGY_KILLED: IC Simple removed. Use {SUCCESSOR_FAMILY} for new paper validation only."
                if status == "killed"
                else gate.get("block_reason", "")
            ),
            "min_trades_met": bool(gate.get("min_trades_met")),
            "min_win_rate_met": bool(gate.get("min_win_rate_met")),
            "positive_expectancy_met": bool(gate.get("positive_expectancy_met")),
            "min_profit_factor_met": bool(gate.get("min_profit_factor_met")),
        },
        "loss_clusters": clusters,
        "required_rule_changes": changed_rules,
        "next_validation_hypothesis_template": {
            "enabled": active_family == SUCCESSOR_FAMILY,
            "strategy_family": SUCCESSOR_FAMILY,
            "hypothesis": (
                "2-leg SPY bull put credit (1-lot, $5 wide, 15Δ short, 30–45 DTE, 25% TP / 200% stop / "
                "7 DTE exit, min 24h hold) can produce expectancy>0 and PF>1 over 30 clean paper trades."
            ),
            "changed_rules": changed_rules,
            "kill_criteria": {
                "min_closed_trades": MIN_TRADES_FOR_GATE,
                "min_expectancy_per_trade": 0.01,
                "min_profit_factor": 1.01,
                "min_total_realized_pnl": 0.01,
            },
        },
        "rag_ingestion": {
            "lesson_id": REHAB_LESSON_ID,
            "lesson_path": str((LESSONS_DIR / f"{REHAB_LESSON_ID}.md").relative_to(PROJECT_ROOT)),
            "tags": ["rag", "ml", "strategy-quarantine", "profitability", "loss-clusters"],
        },
        "ic_killed": ic_killed,
    }


def write_rehabilitation_plan(plan: dict, dry_run: bool = False) -> int:
    """Persist the strategy-level rehabilitation plan and matching RAG lesson."""
    if dry_run:
        logger.info(f"  [DRY RUN] Would write: {REHAB_PLAN_FILE}")
        logger.info(f"  [DRY RUN] Would write: {LESSONS_DIR / f'{REHAB_LESSON_ID}.md'}")
        return 2

    REHAB_PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
    REHAB_PLAN_FILE.write_text(json.dumps(plan, indent=2) + "\n")
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    ledger = plan["ledger"]
    clusters = plan.get("loss_clusters", [])[:5]
    cluster_lines = "\n".join(
        (
            f"- `{cluster['id']}`: {cluster['sample_size']} trades, "
            f"P/L ${cluster['total_pnl']:.2f}, expectancy ${cluster['expectancy_per_trade']:.2f}/trade, "
            f"loss contribution {cluster['loss_contribution_pct']:.2f}%."
        )
        for cluster in clusters
    )
    rule_lines = "\n".join(f"- {rule}" for rule in plan.get("required_rule_changes", []))
    lesson = f"""# IC Simple Strategy Rehabilitation Plan

Tags: rag, ml, strategy-quarantine, profitability, loss-clusters
Lifecycle: active
Confidence: high

## Ledger Evidence

- Closed trades: {ledger["closed_trades"]}
- Wins / losses: {ledger["wins"]} / {ledger["losses"]}
- Win rate: {ledger["win_rate_pct"]:.2f}%
- Profit factor: {ledger["profit_factor"]:.2f}
- Total realized P/L: ${ledger["total_realized_pnl"]:.2f}
- Expectancy: ${ledger["expectancy_per_trade"]:.2f}/trade

## Decision

IC Simple is not profitable yet. Do not resume autonomous entries from the current rule set. The next cohort must be a changed-rule validation experiment, not a retry of the losing ledger.

## Loss Clusters

{cluster_lines or "- No recurring loss cluster detected."}

## Required Rule Changes Before Validation

{rule_lines}

## Machine-Readable Plan

See `{REHAB_PLAN_FILE.relative_to(PROJECT_ROOT)}`.

Generated by `update_ml_from_trades.py` on {datetime.now(timezone.utc).strftime("%Y-%m-%d")}.
"""
    (LESSONS_DIR / f"{REHAB_LESSON_ID}.md").write_text(lesson)
    logger.info(f"  Wrote rehabilitation plan: {REHAB_PLAN_FILE}")
    logger.info(f"  Wrote rehabilitation RAG lesson: {LESSONS_DIR / f'{REHAB_LESSON_ID}.md'}")
    return 2


def _bucket_from_stats(stats: dict) -> dict:
    wins = int(stats.get("wins", 0) or 0)
    losses = int(stats.get("losses", 0) or 0)
    return {
        "alpha": float(wins + 1),
        "beta": float(losses + 1),
        "wins": wins,
        "losses": losses,
    }


def update_thompson_sampler(trades_data: dict, model: dict) -> dict:
    """Update Thompson Sampler with empirical win/loss from canonical ledger.

    Family-aware:
    - iron_condor / spy_specific reflect IC lifetime (killed family evidence)
    - spy_put_credit is a separate bucket; cold-start weak prior until cohort data exists
    Never copies IC 86% research priors onto the put-credit successor.
    """
    stats = trades_data.get("stats", {})
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    total = stats.get("closed_trades", 0)
    win_rate = stats.get("win_rate_pct", 0)

    old_alpha = model.get("iron_condor", {}).get("alpha", 0)
    old_beta = model.get("iron_condor", {}).get("beta", 0)
    old_expected = old_alpha / (old_alpha + old_beta) * 100 if (old_alpha + old_beta) > 0 else 0

    ic_trades = trades_for_family(trades_data, "iron_condor")
    put_trades = trades_for_family(trades_data, SUCCESSOR_FAMILY)
    ic_stats = stats_from_trades(ic_trades) if ic_trades else stats_from_trades(
        [t for t in trades_data.get("trades", []) if isinstance(t, dict)]
    )
    # If ledger is still 100% IC-labeled, ic_stats ~= overall stats
    if not ic_trades and not put_trades:
        ic_stats = {
            "wins": wins,
            "losses": losses,
            "closed_trades": total,
            "win_rate_pct": win_rate,
        }

    put_stats = stats_from_trades(put_trades) if put_trades else {
        "wins": 0,
        "losses": 0,
        "closed_trades": 0,
        "win_rate_pct": 0.0,
    }

    model["iron_condor"] = _bucket_from_stats(ic_stats)
    # spy_specific tracks SPY IC history for diagnostics — NOT the active successor prior
    model["spy_specific"] = dict(model["iron_condor"])
    model["spy_specific"]["note"] = "SPY iron_condor history only; do not use for put-credit entry"

    if put_stats.get("closed_trades", 0) > 0:
        model[SUCCESSOR_FAMILY] = _bucket_from_stats(put_stats)
        model[SUCCESSOR_FAMILY]["prior_source"] = "put_credit_cohort"
    else:
        # Weak neutral prior — NOT the 86% IC research fantasy
        model[SUCCESSOR_FAMILY] = {
            "alpha": 1.0,
            "beta": 1.0,
            "wins": 0,
            "losses": 0,
            "prior_source": "weak_neutral_cold_start",
            "note": "No closed put-credit trades yet; refuse 86% IC prior inheritance",
        }

    model["families"] = {
        "iron_condor": model["iron_condor"],
        SUCCESSOR_FAMILY: model[SUCCESSOR_FAMILY],
    }
    model["active_family"] = load_active_family()

    logger.info("=" * 60)
    logger.info("THOMPSON SAMPLER UPDATE (family-aware)")
    logger.info("=" * 60)
    logger.info(f"  Overall trades: {total} closed ({wins}W / {losses}L) WR={win_rate:.1f}%")
    logger.info(
        "  IC bucket: alpha=%s beta=%s (wins=%s losses=%s)",
        model["iron_condor"]["alpha"],
        model["iron_condor"]["beta"],
        model["iron_condor"]["wins"],
        model["iron_condor"]["losses"],
    )
    logger.info(
        "  Put-credit bucket: alpha=%s beta=%s prior=%s",
        model[SUCCESSOR_FAMILY]["alpha"],
        model[SUCCESSOR_FAMILY]["beta"],
        model[SUCCESSOR_FAMILY].get("prior_source"),
    )
    logger.info(f"  Old IC expected: {old_expected:.1f}%")

    drift = abs(old_expected - float(win_rate or 0))
    if drift > DRIFT_ALERT_THRESHOLD:
        logger.warning(
            f"  DRIFT ALERT: Model expected {old_expected:.1f}% but realized {win_rate:.1f}% ({drift:.1f}% drift)"
        )

    logger.info("=" * 60)
    return model


def check_family_trading_gate(
    family: str,
    family_stats: dict,
    *,
    family_killed: bool = False,
) -> dict:
    """Gate a single strategy family. Killed families never open."""
    if family_killed or family in KILLED_FAMILIES:
        return {
            "family": family,
            "should_trade": False,
            "allow_paper_validation": False,
            "total_trades": int(family_stats.get("closed_trades", 0) or 0),
            "win_rate": _as_float(family_stats.get("win_rate_pct"), 0.0),
            "expectancy_per_trade": _as_float(
                family_stats.get("expectancy_per_trade"), 0.0
            ),
            "profit_factor": _as_float(family_stats.get("profit_factor"), 0.0),
            "block_reason": f"STRATEGY_KILLED: {family}",
            "min_trades_met": False,
            "min_win_rate_met": False,
            "positive_expectancy_met": False,
            "min_profit_factor_met": False,
        }

    gate = check_trading_gate(family_stats)
    gate["family"] = family
    n = int(family_stats.get("closed_trades", 0) or 0)
    # Successor may paper-validate while n < min trades; live still blocked elsewhere.
    gate["allow_paper_validation"] = n < MIN_TRADES_FOR_GATE or bool(gate.get("should_trade"))
    if n < MIN_TRADES_FOR_GATE:
        gate["block_reason"] = (
            f"Validation cohort incomplete: {n}/{MIN_TRADES_FOR_GATE} closed {family} trades"
        )
        gate["should_trade"] = False  # not "proven"; paper path uses allow_paper_validation
    return gate


def check_trading_gate(stats: dict) -> dict:
    """Check if trading should be allowed based on empirical performance."""
    total = stats.get("closed_trades", 0)
    win_rate = _as_float(stats.get("win_rate_pct"), 0.0)
    avg_win = _as_float(stats.get("avg_win"), 0.0)
    avg_loss = _as_float(stats.get("avg_loss"), 0.0)

    if "expectancy_per_trade" in stats:
        expectancy = _as_float(stats.get("expectancy_per_trade"), 0.0)
    elif "total_realized_pnl" in stats and total > 0:
        expectancy = _as_float(stats.get("total_realized_pnl"), 0.0) / total
    elif total > 0:
        expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)
    else:
        expectancy = 0.0

    profit_factor_raw = stats.get("profit_factor")
    if profit_factor_raw is None:
        gross_profit = _as_float(stats.get("gross_profit"), 0.0)
        gross_loss = _as_float(stats.get("gross_loss"), 0.0)
        if gross_profit <= 0 and avg_win > 0 and total > 0:
            gross_profit = (win_rate / 100) * total * avg_win
        if gross_loss <= 0 and avg_loss > 0 and total > 0:
            gross_loss = ((100 - win_rate) / 100) * total * avg_loss

        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = math.inf
        else:
            profit_factor = 0.0
    else:
        profit_factor = _as_float(profit_factor_raw, 0.0)

    positive_expectancy_met = expectancy > MIN_EXPECTANCY_TO_TRADE
    min_profit_factor_met = profit_factor > MIN_PROFIT_FACTOR_TO_TRADE

    gate = {
        "should_trade": (
            total >= MIN_TRADES_FOR_GATE
            and win_rate >= MIN_WIN_RATE_TO_TRADE
            and positive_expectancy_met
            and min_profit_factor_met
        ),
        "total_trades": total,
        "win_rate": win_rate,
        "expectancy_per_trade": round(expectancy, 2),
        "profit_factor": _round_metric(profit_factor),
        "min_trades_met": total >= MIN_TRADES_FOR_GATE,
        "min_win_rate_met": win_rate >= MIN_WIN_RATE_TO_TRADE,
        "positive_expectancy_met": positive_expectancy_met,
        "min_profit_factor_met": min_profit_factor_met,
    }

    if not gate["should_trade"]:
        reasons = []
        if not gate["min_trades_met"]:
            reasons.append(f"Only {total}/{MIN_TRADES_FOR_GATE} trades")
        if not gate["min_win_rate_met"]:
            reasons.append(f"Win rate {win_rate:.1f}% < {MIN_WIN_RATE_TO_TRADE}%")
        if not gate["positive_expectancy_met"]:
            reasons.append(f"Expectancy ${expectancy:.2f}/trade <= ${MIN_EXPECTANCY_TO_TRADE:.2f}")
        if not gate["min_profit_factor_met"]:
            reasons.append(
                f"Profit factor {_round_metric(profit_factor):.2f} <= {MIN_PROFIT_FACTOR_TO_TRADE:.2f}"
            )
        gate["block_reason"] = "; ".join(reasons)
        logger.warning(f"  TRADING BLOCKED: {gate['block_reason']}")
    else:
        logger.info(
            f"  TRADING ALLOWED: {total} trades, {win_rate:.1f}% win rate, "
            f"${expectancy:.2f}/trade expectancy, {profit_factor:.2f} profit factor"
        )

    return gate


def generate_loss_postmortems(trades_data: dict, max_lessons: int = 5) -> list[dict]:
    """Generate post-mortem lessons from the biggest losing trades.

    Only generates lessons for trades that don't already have one.
    """
    trades = trades_data.get("trades", [])
    losses = [
        t for t in trades if t.get("outcome") == "loss" and (t.get("realized_pnl", 0) or 0) < -20
    ]
    losses.sort(key=lambda t: t.get("realized_pnl", 0) or 0)

    # Check existing lessons to avoid duplicates
    existing_ids = set()
    if LESSONS_DIR.exists():
        for f in LESSONS_DIR.glob("*.md"):
            existing_ids.add(f.stem)

    lessons = []
    for trade in losses[:max_lessons]:
        trade_id = trade.get("id", "unknown")
        lesson_id = f"postmortem_{trade_id[:40]}"
        if lesson_id in existing_ids:
            continue

        pnl = trade.get("realized_pnl", 0)
        entry = trade.get("entry_date", "unknown")
        exit_date = trade.get("exit_date", "unknown")
        entry_time = trade.get("entry_time", "")
        exit_time = trade.get("exit_time", "")
        signature = trade.get("signature", "unknown")

        # Calculate holding period
        holding = "unknown"
        if entry_time and exit_time:
            try:
                t1 = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))
                delta = t2 - t1
                hours = delta.total_seconds() / 3600
                holding = f"{hours:.1f}h" if hours < 24 else f"{delta.days}d"
            except (ValueError, TypeError):
                pass

        # Categorize root cause
        source = trade.get("source", "")
        if "ORPHAN" in source.upper() or "orphan" in str(
            trade.get("order_ids", {}).get("exit", [])
        ):
            root_cause = "ORPHAN_CLEANUP: Position was incomplete/misgrouped and force-closed"
        elif holding != "unknown" and "h" in holding:
            h = float(holding.replace("h", ""))
            if h < 1:
                root_cause = f"PREMATURE_EXIT: Held only {holding} — no time for theta decay"
            elif h < 24:
                root_cause = f"EARLY_EXIT: Held {holding} — below 24h minimum"
            else:
                root_cause = f"MARKET_MOVE: Held {holding} — likely breached stop-loss"
        else:
            root_cause = "UNKNOWN: Insufficient data to determine root cause"

        lesson = {
            "id": lesson_id,
            "trade_id": trade_id,
            "pnl": pnl,
            "entry": entry,
            "exit": exit_date,
            "holding": holding,
            "signature": signature,
            "root_cause": root_cause,
        }
        lessons.append(lesson)

    return lessons


def write_postmortem_lessons(lessons: list[dict], dry_run: bool = False) -> int:
    """Write post-mortem lessons to RAG knowledge base."""
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0

    for lesson in lessons:
        filename = LESSONS_DIR / f"{lesson['id']}.md"
        if filename.exists():
            continue

        content = f"""# Post-Mortem: {lesson["signature"]}

- **Trade ID**: {lesson["trade_id"][:60]}
- **P/L**: ${lesson["pnl"]:.2f}
- **Entry**: {lesson["entry"]}
- **Exit**: {lesson["exit"]}
- **Holding Period**: {lesson["holding"]}
- **Root Cause**: {lesson["root_cause"]}

## Prevention

{_prevention_for_cause(lesson["root_cause"])}

## Generated

Auto-generated by `update_ml_from_trades.py` on {datetime.now(timezone.utc).strftime("%Y-%m-%d")}.
Severity: {"CRITICAL" if (lesson["pnl"] or 0) < -100 else "HIGH"}
"""
        if dry_run:
            logger.info(f"  [DRY RUN] Would write: {filename.name}")
        else:
            filename.write_text(content)
            logger.info(f"  Wrote lesson: {filename.name} (${lesson['pnl']:.2f})")
        written += 1

    return written


def _prevention_for_cause(root_cause: str) -> str:
    """Generate prevention recommendation based on root cause."""
    if "ORPHAN" in root_cause:
        return "Ensure all IC legs fill atomically via MLEG orders. 24h grace period before orphan cleanup."
    if "PREMATURE" in root_cause:
        return "Enforce 24h minimum holding period. Place GTC profit close order at entry."
    if "EARLY" in root_cause:
        return "Hold positions longer for theta decay. Minimum 24h hold enforced."
    if "MARKET_MOVE" in root_cause:
        return "Review stop-loss levels. Consider wider wings or lower delta for more cushion."
    return "Investigate trade logs for execution details."


def write_system_diagnosis(trades_data: dict, dry_run: bool = False) -> int:
    """Persist DS root-cause diagnosis + RAG lesson (agentic memory)."""
    state: dict = {}
    if SYSTEM_STATE_FILE.exists():
        try:
            state = json.loads(SYSTEM_STATE_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            state = {}
    paper = state.get("paper_account") or state.get("account") or {}
    equity = paper.get("current_equity") or paper.get("equity")
    starting = paper.get("starting_balance")
    diagnosis = build_system_diagnosis(
        trades_data,
        equity=float(equity) if equity is not None else None,
        starting_equity=float(starting) if starting is not None else None,
        active_family=load_active_family(),
    )
    md = diagnosis_to_markdown(diagnosis)
    if dry_run:
        logger.info("  [DRY RUN] Would write: %s", DIAGNOSIS_FILE)
        logger.info("  [DRY RUN] Would write: %s", LESSONS_DIR / f"{DIAGNOSIS_LESSON_ID}.md")
        return 0
    DIAGNOSIS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DIAGNOSIS_FILE.write_text(json.dumps(diagnosis, indent=2) + "\n")
    LESSONS_DIR.mkdir(parents=True, exist_ok=True)
    (LESSONS_DIR / f"{DIAGNOSIS_LESSON_ID}.md").write_text(md)
    logger.info("  Wrote system diagnosis: %s", DIAGNOSIS_FILE)
    logger.info("  Wrote diagnosis RAG lesson: %s", DIAGNOSIS_LESSON_ID)
    return 1


def main(dry_run: bool = False):
    """Main feedback loop update."""
    logger.info("=" * 70)
    logger.info("ML FEEDBACK LOOP UPDATE")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 70)

    # 1. Load data
    trades_data = load_trades()
    model = load_model()
    stats = trades_data.get("stats", {})
    validation_reset = is_validation_reset_model(model)
    validation_stats: dict | None = None
    active_family = load_active_family()

    if not stats.get("closed_trades"):
        logger.warning("No closed trades found — nothing to update")
        return

    # 2. Update Thompson Sampler with real data
    # SKIP during validation phase: the old 66-trade data would overwrite
    # the Beta(86,14) prior reset. Only update from validation-phase trades.
    if validation_reset:
        validation_trades = validation_phase_trades(trades_data)
        cohort_unpaired = {
            "unpaired_cohort_wins": stats.get("unpaired_cohort_wins", 0),
            "unpaired_cohort_losses": stats.get("unpaired_cohort_losses", 0),
            "unpaired_cohort_gross_profit": stats.get("unpaired_cohort_gross_profit", 0.0),
            "unpaired_cohort_gross_loss": stats.get("unpaired_cohort_gross_loss", 0.0),
            "unpaired_in_cohort_pnl": stats.get("unpaired_in_cohort_pnl", 0.0),
        }
        validation_stats = stats_from_trades(validation_trades, cohort_unpaired)
        closed_validation_trades = validation_stats["closed_trades"]
        if closed_validation_trades:
            logger.info(f"Updating Thompson from {closed_validation_trades} validation trades only")
            model = update_thompson_sampler(
                {"stats": validation_stats, "trades": validation_trades}, model
            )
        else:
            logger.info("Thompson update skipped: no validation-phase closed trades yet")
            # Still ensure put-credit cold-start bucket exists
            model = update_thompson_sampler(trades_data, model)
    else:
        model = update_thompson_sampler(trades_data, model)

    # 3. Family-aware trading gates
    # Lifetime IC stats must NOT globally halt the put-credit paper successor.
    ic_stats = stats_from_trades(trades_for_family(trades_data, "iron_condor"))
    if ic_stats.get("closed_trades", 0) == 0:
        # Ledger may still be 100% IC under strategy=iron_condor
        ic_stats = stats if stats else ic_stats
    put_stats = stats_from_trades(trades_for_family(trades_data, SUCCESSOR_FAMILY))

    ic_gate = check_family_trading_gate("iron_condor", ic_stats, family_killed=True)
    put_gate = check_family_trading_gate(SUCCESSOR_FAMILY, put_stats, family_killed=False)

    gate_stats = validation_stats if validation_reset and validation_stats is not None else stats
    # Legacy aggregate gate retained for diagnostics only
    gate = check_trading_gate(gate_stats)
    gate["legacy_aggregate"] = True
    gate["active_family"] = active_family
    gate["family_gates"] = {
        "iron_condor": ic_gate,
        SUCCESSOR_FAMILY: put_gate,
    }
    # Effective entry policy follows active family
    if active_family == SUCCESSOR_FAMILY:
        gate["should_trade"] = bool(put_gate.get("should_trade"))
        gate["allow_paper_validation"] = bool(put_gate.get("allow_paper_validation"))
        gate["block_reason"] = put_gate.get("block_reason", gate.get("block_reason"))
        gate["block_live_new_positions"] = True
    else:
        gate["allow_paper_validation"] = False
    if validation_reset:
        gate["validation_reset_active"] = True
        gate["allow_validation_entries"] = True
        gate["block_live_new_positions"] = True

    # 4. Generate post-mortem lessons
    lessons = generate_loss_postmortems(trades_data)
    logger.info(f"\nPost-mortem lessons to write: {len(lessons)}")
    rehabilitation_plan = build_rehabilitation_plan(trades_data, ic_gate)
    if rehabilitation_plan["status"] in {"quarantined", "killed"}:
        logger.warning(
            "  STRATEGY REHAB / KILL: %s",
            rehabilitation_plan["gate"].get("block_reason", "unknown"),
        )
        for cluster in rehabilitation_plan.get("loss_clusters", [])[:3]:
            logger.warning(
                "  Loss cluster %s: %s trades, P/L $%.2f, expectancy $%.2f/trade",
                cluster["id"],
                cluster["sample_size"],
                cluster["total_pnl"],
                cluster["expectancy_per_trade"],
            )

    # 5. Write everything
    if not dry_run:
        model["last_updated"] = datetime.now(timezone.utc).isoformat()
        if validation_reset:
            model.setdefault("validation_reset", VALIDATION_RESET_NOTE)
            model["feedback_source"] = (
                "validation_trades"
                if gate_stats.get("closed_trades", 0) > 0
                else "validation_reset"
            )
        else:
            model["feedback_source"] = "canonical_trades_json_family_aware"
        model["gate"] = gate
        model["active_family"] = active_family
        MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
        MODEL_FILE.write_text(json.dumps(model, indent=2))
        logger.info(f"Updated {MODEL_FILE}")

        # Family-aware halt policy:
        # - Never use killed IC lifetime metrics to block put-credit paper validation.
        # - Halt successor only after its own n>=30 cohort fails gates.
        # - Always keep live blocked (enforced by kill switch + allow flags).
        halt_file = PROJECT_ROOT / "data" / "TRADING_HALTED"
        put_n = int(put_stats.get("closed_trades", 0) or 0)
        put_failed_after_sample = (
            put_n >= MIN_TRADES_FOR_GATE and not put_gate.get("should_trade")
        )
        if active_family == SUCCESSOR_FAMILY and put_gate.get("allow_paper_validation") and not put_failed_after_sample:
            if halt_file.exists():
                content = halt_file.read_text()
                # Clear ML halts that were written from IC aggregate metrics
                if "ML GATE BLOCKED" in content:
                    halt_file.unlink()
                    logger.info(
                        "  HALT FILE REMOVED: IC aggregate ML halt must not block put-credit paper validation"
                    )
            logger.info(
                "  Put-credit paper validation allowed (n=%s/%s). Live remains blocked by kill switch.",
                put_n,
                MIN_TRADES_FOR_GATE,
            )
        elif put_failed_after_sample:
            halt_file.write_text(
                f"ML GATE BLOCKED (spy_put_credit cohort): {put_gate.get('block_reason', 'unknown')}\n"
                f"Updated: {datetime.now(timezone.utc).isoformat()}\n"
                f"Win rate: {put_stats.get('win_rate_pct', 0):.1f}% | Trades: {put_n}\n"
                f"Family: {SUCCESSOR_FAMILY} | Live blocked | Paper blocked after failed cohort\n"
            )
            logger.warning("  HALT FILE WRITTEN for failed put-credit cohort: %s", halt_file)
        elif not gate["should_trade"] and not validation_reset and active_family != SUCCESSOR_FAMILY:
            halt_file.write_text(
                f"ML GATE BLOCKED: {gate.get('block_reason', 'unknown')}\n"
                f"Updated: {datetime.now(timezone.utc).isoformat()}\n"
                f"Win rate: {stats.get('win_rate_pct', 0):.1f}% | Trades: {stats.get('closed_trades', 0)}\n"
                f"Unblock: improve win rate above {MIN_WIN_RATE_TO_TRADE}% over {MIN_TRADES_FOR_GATE}+ trades"
            )
            logger.warning(f"  HALT FILE WRITTEN: {halt_file}")
        elif not gate["should_trade"] and validation_reset:
            logger.info(
                "  ML gate would halt, but validation_reset active — allowing paper validation entries"
            )
        elif halt_file.exists() and gate.get("should_trade"):
            content = halt_file.read_text()
            if "ML GATE BLOCKED" in content:
                halt_file.unlink()
                logger.info("  HALT FILE REMOVED: ML gate passed")

    written = write_postmortem_lessons(lessons, dry_run)
    rehab_written = write_rehabilitation_plan(rehabilitation_plan, dry_run)
    diagnosis_written = write_system_diagnosis(trades_data, dry_run)
    logger.info(f"Post-mortem lessons written: {written}")
    logger.info(f"Strategy rehabilitation artifacts written: {rehab_written}")
    logger.info(f"System diagnosis artifacts written: {diagnosis_written}")

    # 6. Summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info(
        f"  Thompson IC: alpha={model['iron_condor']['alpha']}, beta={model['iron_condor']['beta']}"
    )
    pc = model.get(SUCCESSOR_FAMILY, {})
    logger.info(
        "  Thompson put-credit: alpha=%s beta=%s prior=%s",
        pc.get("alpha"),
        pc.get("beta"),
        pc.get("prior_source"),
    )
    logger.info(f"  Active family: {active_family}")
    if validation_reset:
        logger.info(f"  Legacy win rate: {stats.get('win_rate_pct', 0):.1f}%")
        logger.info(f"  Gate cohort: validation_phase ({gate.get('total_trades', 0)} trades)")
    logger.info(f"  Aggregate gate win rate: {gate.get('win_rate', 0):.1f}%")
    logger.info(
        "  Put-credit paper validation: %s",
        "ALLOWED" if gate.get("allow_paper_validation") else "BLOCKED",
    )
    logger.info(f"  Proven edge gate: {'OPEN' if gate['should_trade'] else 'BLOCKED'}")
    if not gate["should_trade"]:
        logger.info(f"  Block reason: {gate.get('block_reason', 'unknown')}")
    logger.info(f"  Rehabilitation status: {rehabilitation_plan['status']}")
    logger.info(f"  Post-mortems: {written} new lessons")
    logger.info("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Update ML models from trade data")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
