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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from src.analytics.loss_forensics import (  # noqa: E402
    analyze_loss_clusters as forensics_analyze_loss_clusters,
    build_system_diagnosis,
    diagnosis_to_markdown,
    wing_width as forensics_wing_width,
)
from src.analytics.trade_evidence import (  # noqa: E402
    active_strategy_family,
    build_trade_evidence,
    canonical_strategy,
    row_strategy,
)

PROJECT_ROOT = Path(__file__).parent.parent
TRADES_FILE = PROJECT_ROOT / "data" / "trades.json"
MODEL_FILE = PROJECT_ROOT / "models" / "ml" / "trade_confidence_model.json"
LESSONS_DIR = PROJECT_ROOT / "rag_knowledge" / "lessons_learned"
SYSTEM_STATE_FILE = PROJECT_ROOT / "data" / "system_state.json"
REHAB_PLAN_FILE = PROJECT_ROOT / "data" / "runtime" / "edge_rehabilitation_plan.json"
DIAGNOSIS_FILE = PROJECT_ROOT / "data" / "runtime" / "system_diagnosis_latest.json"
DIAGNOSIS_LESSON_ID = "system_misery_diagnosis_current"
REHAB_LESSON_ID = "strategy_rehabilitation_ic_simple_current"
SUCCESSOR_FAMILY = "spy_put_credit"

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


def validation_phase_trades(
    trades_data: dict,
    strategy_family: str | None = None,
) -> list[dict]:
    """Return validation rows for one exact strategy family.

    A date alone is not a cohort definition.  After a strategy pivot, mixing
    later iron-condor rows into a put-credit posterior is target leakage.
    """

    trades = trades_data.get("trades", [])
    target = canonical_strategy(strategy_family) if strategy_family else None
    return [
        trade
        for trade in trades
        if isinstance(trade, dict)
        and _is_validation_phase_trade(trade)
        and (target is None or row_strategy(trade) == target)
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
    """Build Thompson inputs from paired closed structures only.

    ``cohort_unpaired_stats`` is retained for API compatibility and surfaced as
    quarantined diagnostics.  Unmatched order cash must never become wins,
    losses, sample size, expectancy, or Bayesian posterior updates.
    """
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

    input_trades = len(trades)
    closed_trades = len(wins) + len(losses)
    win_rate = (len(wins) / closed_trades * 100) if closed_trades else 0.0
    gross_profit = sum(pnl for pnl in wins if pnl > 0)
    gross_loss = abs(sum(pnl for pnl in losses if pnl < 0))
    total_realized_pnl = sum(wins) + sum(losses)
    quality_denominator = max(input_trades, 1)
    quality_penalty = (skipped_trades + min(missing_pnl_trades, closed_trades)) / quality_denominator
    data_quality_score = round(max(0.0, 1.0 - quality_penalty), 3)

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = math.inf
    else:
        profit_factor = 0.0

    expectancy = total_realized_pnl / closed_trades if closed_trades else 0.0
    unpaired = cohort_unpaired_stats or {}

    return {
        "wins": len(wins),
        "losses": len(losses),
        "closed_trades": closed_trades,
        "input_trades": input_trades,
        "skipped_trades": skipped_trades,
        "ambiguous_outcome_trades": ambiguous_outcome_trades,
        "missing_pnl_trades": missing_pnl_trades,
        "data_quality_score": data_quality_score,
        "win_rate_pct": round(win_rate, 2),
        "avg_win": gross_profit / len(wins) if wins else 0,
        "avg_loss": gross_loss / len(losses) if losses else 0,
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "total_realized_pnl": round(total_realized_pnl, 2),
        "profit_factor": _round_metric(profit_factor),
        "expectancy_per_trade": round(expectancy, 2),
        "metric_unit": "paired_closed_structure",
        "unpaired_attribution_status": "quarantined_not_learning_eligible",
        "quarantined_unpaired_wins": int(unpaired.get("unpaired_cohort_wins", 0) or 0),
        "quarantined_unpaired_losses": int(unpaired.get("unpaired_cohort_losses", 0) or 0),
        "quarantined_unpaired_pnl": _as_float(
            unpaired.get("unpaired_in_cohort_pnl"), 0.0
        ),
    }


def analyze_loss_clusters(trades_data: dict) -> list[dict]:
    """Summarize recurring loss clusters so RAG/ML learns what to stop repeating."""
    return forensics_analyze_loss_clusters(trades_data)

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

    status = "quarantined" if not gate.get("should_trade") else "eligible"
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy_family": "ic_simple",
        "status": status,
        "profitability_objective": "Resume only after a changed-rule validation cohort proves positive expectancy, profit factor above 1.0, and positive realized P/L.",
        "ledger": ledger,
        "gate": {
            "should_trade": bool(gate.get("should_trade")),
            "block_reason": gate.get("block_reason", ""),
            "min_trades_met": bool(gate.get("min_trades_met")),
            "min_win_rate_met": bool(gate.get("min_win_rate_met")),
            "positive_expectancy_met": bool(gate.get("positive_expectancy_met")),
            "min_profit_factor_met": bool(gate.get("min_profit_factor_met")),
        },
        "loss_clusters": clusters,
        "required_rule_changes": changed_rules,
        "next_validation_hypothesis_template": {
            "enabled": False,
            "strategy_family": "ic_simple",
            "hypothesis": (
                "IC Simple remains quarantined. Enable only after replacing this text with "
                "a concrete rule-change thesis backed by the loss clusters in edge_rehabilitation_plan.json."
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


def update_thompson_sampler(
    trades_data: dict,
    model: dict,
    strategy_family: str = "iron_condor",
) -> dict:
    """Update Thompson Sampler with empirical win/loss from canonical ledger.

    Replaces stale Tastytrade priors with actual trade data.
    Uses alpha = wins + 1, beta = losses + 1 (Bayesian uniform prior).
    """
    stats = trades_data.get("stats", {})
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    total = stats.get("closed_trades", 0)
    win_rate = stats.get("win_rate_pct", 0)

    # Empirical priors: alpha = wins + 1, beta = losses + 1
    alpha = wins + 1
    beta_val = losses + 1

    family = canonical_strategy(strategy_family) or "iron_condor"
    old_alpha = model.get(family, {}).get("alpha", 0)
    old_beta = model.get(family, {}).get("beta", 0)
    old_expected = old_alpha / (old_alpha + old_beta) * 100 if (old_alpha + old_beta) > 0 else 0

    model[family] = {
        "alpha": float(alpha),
        "beta": float(beta_val),
        "wins": wins,
        "losses": losses,
        "metric_unit": "paired_closed_structure",
    }
    # ``spy_specific`` historically mixed unrelated strategy families.  Keep
    # it aligned only for the legacy iron-condor model; successor strategies
    # use their own posterior bucket.
    if family == "iron_condor":
        model["spy_specific"] = dict(model[family])

    logger.info("=" * 60)
    logger.info("THOMPSON SAMPLER UPDATE — %s", family)
    logger.info("=" * 60)
    logger.info(f"  Trades: {total} closed ({wins}W / {losses}L)")
    logger.info(f"  Win rate: {win_rate:.1f}%")
    logger.info(f"  Old priors: alpha={old_alpha}, beta={old_beta} (expected {old_expected:.1f}%)")
    logger.info(f"  New priors: alpha={alpha}, beta={beta_val} (expected {win_rate:.1f}%)")

    # Drift detection
    drift = abs(old_expected - win_rate)
    if drift > DRIFT_ALERT_THRESHOLD:
        logger.warning(
            f"  DRIFT ALERT: Model expected {old_expected:.1f}% but realized {win_rate:.1f}% ({drift:.1f}% drift)"
        )

    logger.info("=" * 60)
    return model


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
    active_family = active_strategy_family(PROJECT_ROOT)
    validation_reset = active_family != "iron_condor" or is_validation_reset_model(model)
    evidence = build_trade_evidence(
        trades_data,
        strategy_family=active_family,
        require_protocol_fields=active_family == "spy_put_credit",
    )
    validation_stats = stats_from_trades(evidence.rows)
    logger.info(
        "Active evidence: family=%s verified=%s raw=%s hash=%s",
        active_family,
        len(evidence.rows),
        evidence.raw_row_count,
        evidence.dataset_sha256[:12],
    )
    for issue in evidence.issues:
        logger.warning("EVIDENCE QUARANTINE: %s", issue)

    # 2. Update Thompson Sampler with real data
    # Never let a killed family or unmatched orders update the active model.
    closed_validation_trades = validation_stats["closed_trades"]
    if closed_validation_trades and evidence.learning_ready:
        logger.info(
            "Updating %s Thompson posterior from %s verified trades",
            active_family,
            closed_validation_trades,
        )
        model = update_thompson_sampler(
            {"stats": validation_stats, "trades": evidence.rows},
            model,
            strategy_family=active_family,
        )
    else:
        model.setdefault(
            active_family,
            {
                "alpha": 1.0,
                "beta": 1.0,
                "wins": 0,
                "losses": 0,
                "prior_source": "weak_neutral_cold_start",
                "note": "No verified active-family closed trades yet",
            },
        )
        # Never leave put-credit inheriting IC posterior via missing key
        if active_family == SUCCESSOR_FAMILY and SUCCESSOR_FAMILY not in model:
            model[SUCCESSOR_FAMILY] = dict(model[active_family])
        logger.info(
            "Thompson update skipped: active evidence is empty or quarantined "
            "(verified=%s, issues=%s)",
            closed_validation_trades,
            len(evidence.issues),
        )

    # 3. Check trading gate
    gate_stats = validation_stats
    gate = check_trading_gate(gate_stats)
    gate["validation_reset_active"] = validation_reset
    gate["allow_validation_entries"] = bool(validation_reset and not evidence.issues)
    gate["block_live_new_positions"] = True
    gate["active_strategy_family"] = active_family
    gate["evidence_dataset_sha256"] = evidence.dataset_sha256
    gate["evidence_verified_rows"] = len(evidence.rows)
    gate["evidence_issues"] = list(evidence.issues)

    # 4. Generate post-mortem lessons
    lessons = generate_loss_postmortems(trades_data)
    logger.info(f"\nPost-mortem lessons to write: {len(lessons)}")
    rehabilitation_plan = build_rehabilitation_plan(trades_data, gate)
    if rehabilitation_plan["status"] == "quarantined":
        logger.warning(
            "  STRATEGY REHAB REQUIRED: %s",
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
                f"verified_{active_family}_trades"
                if gate_stats.get("closed_trades", 0) > 0
                else "validation_reset"
            )
        else:
            model["feedback_source"] = "canonical_trades_json"
        model["gate"] = gate
        model["active_strategy_family"] = active_family
        model["evidence_lineage"] = evidence.to_dict()
        MODEL_FILE.write_text(json.dumps(model, indent=2))
        logger.info(f"Updated {MODEL_FILE}")

        # Enforce ML gate via trading halt file (hard gate)
        # BYPASS during validation phase: the model was reset for the controlled
        # experiment (Apr 2026). The old 66-trade data produces should_trade=false
        # but we need to allow paper validation entries to prove edge.
        # See .claude/rules/controlled-experiment.md
        halt_file = PROJECT_ROOT / "data" / "TRADING_HALTED"
        # Family-aware: IC lifetime failure must not block put-credit paper validation.
        # Still never clear non-ML / crisis halt files.
        put_n = int(gate_stats.get("closed_trades", 0) or 0) if active_family == SUCCESSOR_FAMILY else 0
        allow_put_paper = (
            active_family == SUCCESSOR_FAMILY
            and validation_reset
            and not evidence.issues
            and put_n < MIN_TRADES_FOR_GATE
        )
        gate["allow_paper_validation"] = bool(allow_put_paper or gate.get("should_trade"))
        if allow_put_paper:
            if halt_file.exists():
                content = halt_file.read_text()
                if "ML GATE BLOCKED" in content and "spy_put_credit cohort" not in content:
                    halt_file.unlink()
                    logger.info(
                        "  HALT FILE REMOVED: IC aggregate ML halt must not block put-credit paper validation"
                    )
                else:
                    logger.warning(
                        "  HALT FILE PRESERVED: non-ML or put-credit-cohort halt remains"
                    )
            logger.info(
                "  Put-credit paper validation allowed (n=%s/%s). Live remains blocked by kill switch.",
                put_n,
                MIN_TRADES_FOR_GATE,
            )
        elif not gate["should_trade"] and not validation_reset:
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
        elif halt_file.exists():
            # Crisis / operator halt clearing belongs to crisis_monitor after flat book.
            logger.warning(
                "  HALT FILE PRESERVED: ML feedback is not authorized to clear non-ML kill switches"
            )

    written = write_postmortem_lessons(lessons, dry_run)
    rehab_written = write_rehabilitation_plan(rehabilitation_plan, dry_run)
    diagnosis_written = 0
    if not dry_run:
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
            active_family=active_family,
        )
        DIAGNOSIS_FILE.parent.mkdir(parents=True, exist_ok=True)
        DIAGNOSIS_FILE.write_text(json.dumps(diagnosis, indent=2) + "\n")
        LESSONS_DIR.mkdir(parents=True, exist_ok=True)
        (LESSONS_DIR / f"{DIAGNOSIS_LESSON_ID}.md").write_text(diagnosis_to_markdown(diagnosis))
        diagnosis_written = 1
        logger.info("  Wrote system diagnosis: %s", DIAGNOSIS_FILE)
    logger.info(f"Post-mortem lessons written: {written}")
    logger.info(f"Strategy rehabilitation artifacts written: {rehab_written}")
    logger.info(f"System diagnosis artifacts written: {diagnosis_written}")

    # 6. Summary
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    active_posterior = model.get(active_family, {})
    logger.info(
        "  Thompson Sampler (%s): alpha=%s, beta=%s",
        active_family,
        active_posterior.get("alpha", 1.0),
        active_posterior.get("beta", 1.0),
    )
    if validation_reset:
        logger.info(f"  Legacy win rate: {stats.get('win_rate_pct', 0):.1f}%")
        logger.info(f"  Gate cohort: validation_phase ({gate.get('total_trades', 0)} trades)")
    logger.info(f"  Gate win rate: {gate.get('win_rate', 0):.1f}%")
    logger.info(f"  Trading gate: {'OPEN' if gate['should_trade'] else 'BLOCKED'}")
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
