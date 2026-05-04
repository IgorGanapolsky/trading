#!/usr/bin/env python3
"""
Post-Market Analysis — Runs after market close daily.

Combines:
1. Regime-aware Thompson Sampler updates (separate alpha/beta per VIX regime)
2. Position P&L analysis
3. Next-day trading plan generation
4. Research state consumption

Usage:
    python3 scripts/post_market_analysis.py
    python3 scripts/post_market_analysis.py --dry-run
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
TRADES_FILE = PROJECT_ROOT / "data" / "trades.json"
MODEL_FILE = PROJECT_ROOT / "models" / "ml" / "trade_confidence_model.json"
RESEARCH_STATE_FILE = PROJECT_ROOT / "data" / "research_state.json"
ANALYSIS_DIR = PROJECT_ROOT / "data" / "post_market_analysis"


def load_json(path: Path) -> dict:
    """Load JSON file safely."""
    if not path.exists():
        return {}
    result: dict = json.loads(path.read_text())
    return result


def classify_trade_regime(trade: dict) -> str:
    """Classify which VIX regime a trade was entered in.

    Uses the decision trace if available, otherwise estimates from entry date.
    """
    trace = trade.get("decision_trace", {})
    vix = trace.get("market_context", {}).get("vix")

    if vix is not None:
        if vix < 15:
            return "calm"
        if vix < 20:
            return "normal"
        if vix < 25:
            return "elevated"
        if vix < 30:
            return "volatile"
        return "spike"

    # Fallback: use entry credit as proxy (higher credit = higher vol)
    credit = trade.get("entry_credit") or trade.get("credit_received", 0)
    if credit > 300:
        return "volatile"
    if credit > 200:
        return "elevated"
    if credit > 100:
        return "normal"
    return "calm"


def update_regime_thompson_samplers(trades_data: dict, model: dict) -> dict:
    """Update separate Thompson Samplers per VIX regime.

    Instead of one global model, we track win rates per regime.
    This lets the system know: "we win 80% in calm markets but only 30% in volatile."
    """
    trades = trades_data.get("trades", [])

    # Count wins/losses per regime
    regime_stats: dict[str, dict[str, int]] = {
        "calm": {"wins": 0, "losses": 0},
        "normal": {"wins": 0, "losses": 0},
        "elevated": {"wins": 0, "losses": 0},
        "volatile": {"wins": 0, "losses": 0},
        "spike": {"wins": 0, "losses": 0},
    }

    for trade in trades:
        if trade.get("status") != "closed":
            continue
        regime = classify_trade_regime(trade)
        if trade.get("outcome") == "win":
            regime_stats[regime]["wins"] += 1
        elif trade.get("outcome") == "loss":
            regime_stats[regime]["losses"] += 1

    # Update model with per-regime Thompson Samplers
    if "regime_samplers" not in model:
        model["regime_samplers"] = {}

    for regime, stats in regime_stats.items():
        alpha = stats["wins"] + 1  # Bayesian uniform prior
        beta = stats["losses"] + 1
        total = stats["wins"] + stats["losses"]
        win_rate = stats["wins"] / total * 100 if total > 0 else 0

        model["regime_samplers"][regime] = {
            "alpha": float(alpha),
            "beta": float(beta),
            "wins": stats["wins"],
            "losses": stats["losses"],
            "total": total,
            "win_rate_pct": round(win_rate, 1),
            "should_trade": total >= 10 and win_rate >= 50,
        }

        if total > 0:
            logger.info(
                f"  {regime:10s}: {stats['wins']}W/{stats['losses']}L = {win_rate:.1f}% {'✅' if win_rate >= 50 else '❌'}"
            )
        else:
            logger.info(f"  {regime:10s}: no trades")

    return model


def generate_next_day_plan(model: dict, research: dict) -> dict:
    """Generate trading plan for next market day based on regime + research."""
    current_regime = research.get("recommendations", {}).get("regime", "unknown")
    sampler = model.get("regime_samplers", {}).get(current_regime, {})
    should_trade = sampler.get("should_trade", False)
    win_rate = sampler.get("win_rate_pct", 0)
    total = sampler.get("total", 0)

    # Gate: need research + regime data + positive expectancy
    research_says_trade = research.get("recommendations", {}).get("should_trade", False)
    gate = model.get("gate", {})
    global_gate_open = gate.get("should_trade", False)

    plan = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "current_regime": current_regime,
        "regime_win_rate": win_rate,
        "regime_sample_size": total,
        "regime_allows_trading": should_trade,
        "research_allows_trading": research_says_trade,
        "global_gate_open": global_gate_open,
        "action": "TRADE"
        if (should_trade and research_says_trade and global_gate_open)
        else "HOLD",
        "suggested_delta": research.get("recommendations", {}).get("suggested_delta", 15),
        "suggested_profit_target": research.get("recommendations", {}).get(
            "suggested_profit_target", 0.50
        ),
    }

    if plan["action"] == "HOLD":
        reasons = []
        if not should_trade:
            reasons.append(
                f"Regime '{current_regime}' win rate {win_rate:.0f}% (need 50%+, {total} trades)"
            )
        if not research_says_trade:
            reasons.append("Research says avoid (VIX regime unfavorable)")
        if not global_gate_open:
            reasons.append(f"Global gate blocked: {gate.get('block_reason', 'unknown')}")
        plan["hold_reasons"] = reasons

    return plan


def main(dry_run: bool = False):
    """Run post-market analysis."""
    logger.info("=" * 70)
    logger.info("POST-MARKET ANALYSIS")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 70)

    # 1. Load data
    trades_data = load_json(TRADES_FILE)
    model = load_json(MODEL_FILE)
    research = load_json(RESEARCH_STATE_FILE)

    if not trades_data.get("trades"):
        logger.warning("No trades found — skipping analysis")
        return

    # 2. Update regime-aware Thompson Samplers
    logger.info("\nREGIME-AWARE THOMPSON SAMPLERS:")
    model = update_regime_thompson_samplers(trades_data, model)

    # 3. Generate next-day plan
    plan = generate_next_day_plan(model, research)
    logger.info(f"\nNEXT DAY PLAN: {plan['action']}")
    if plan["action"] == "HOLD":
        for reason in plan.get("hold_reasons", []):
            logger.info(f"  - {reason}")
    else:
        logger.info(f"  Regime: {plan['current_regime']}")
        logger.info(f"  Delta: {plan['suggested_delta']}")
        logger.info(f"  Profit target: {plan['suggested_profit_target'] * 100:.0f}%")

    # 4. Save
    if not dry_run:
        model["last_updated"] = datetime.now(timezone.utc).isoformat()
        MODEL_FILE.write_text(json.dumps(model, indent=2))
        logger.info(f"\nModel updated: {MODEL_FILE}")

        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        plan_file = ANALYSIS_DIR / f"plan_{today}.json"
        plan_file.write_text(json.dumps(plan, indent=2))
        logger.info(f"Plan saved: {plan_file}")

    logger.info("=" * 70)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Post-market analysis")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
