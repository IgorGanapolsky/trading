#!/usr/bin/env python3
"""
Options Live Simulation Script

Executes theta harvest opportunities in paper trading mode based on:
- Account equity gates ($5k/$10k/$25k thresholds)
- IV percentile filters (>50% required)
- Market regime (calm regime for iron condors)
- Daily premium target ($10/day)

This script runs alongside daily equity trading to add options premium
to the portfolio, accelerating progress toward $100/day net goal.

Integration:
- Called from autonomous_trader.py after equity execution
- Results logged to data/options_signals/theta_harvest_*.json
- Metrics tracked in system_state.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Ensure src is on the path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.analytics.options_profit_planner import ThetaHarvestExecutor
from src.core.alpaca_trader import AlpacaTrader
from src.utils.logging_config import setup_logging
from src.utils.regime_detector import RegimeDetector

logger = logging.getLogger(__name__)


def get_account_equity(trader: AlpacaTrader) -> float:
    """Get current account equity."""
    try:
        account = trader.get_account()
        equity = float(account.get("equity", account.get("portfolio_value", 0.0)))
        return equity
    except Exception as e:
        logger.error(f"Failed to get account equity: {e}")
        # Fallback to system_state.json
        state_path = Path("data/system_state.json")
        if state_path.exists():
            try:
                with state_path.open() as f:
                    state = json.load(f)
                    equity = float(state.get("account", {}).get("current_equity", 0.0))
                    logger.info(f"Using equity from system_state.json: ${equity:,.2f}")
                    return equity
            except Exception as e2:
                logger.error(f"Failed to read system_state.json: {e2}")
        return 0.0


def get_market_regime() -> str:
    """Detect current market regime."""
    try:
        detector = RegimeDetector()
        regime = detector.detect_regime()
        regime_label = regime.get("regime", "calm")
        logger.info(f"Market regime detected: {regime_label}")
        return regime_label
    except Exception as e:
        logger.warning(f"Regime detection failed: {e}. Defaulting to 'calm'.")
        return "calm"


def execute_theta_harvest(
    account_equity: float,
    regime_label: str,
    paper: bool = True,
    symbols: list[str] | None = None,
) -> dict:
    """
    Execute theta harvest simulation.

    Args:
        account_equity: Current account equity
        regime_label: Market regime (calm/trend/vol/spike)
        paper: Paper trading mode
        symbols: Symbols to evaluate (default: SPY, QQQ, IWM)

    Returns:
        Dict with execution results and plan
    """
    executor = ThetaHarvestExecutor(paper=paper)
    symbols = symbols or ["SPY", "QQQ", "IWM"]

    # Generate theta harvest plan
    plan = executor.generate_theta_plan(
        account_equity=account_equity,
        regime_label=regime_label,
        symbols=symbols,
    )

    # Log plan summary
    logger.info("=" * 80)
    logger.info("THETA HARVEST SIMULATION")
    logger.info("=" * 80)
    logger.info(f"Account Equity: ${account_equity:,.2f}")
    logger.info(f"Market Regime: {regime_label}")
    logger.info(f"Equity Gate Status: {plan.get('equity_gate', {})}")
    logger.info(f"Target Daily Premium: ${plan.get('target_daily_premium', 0):.2f}")
    logger.info(f"Total Estimated Premium: ${plan.get('total_estimated_premium', 0):.2f}/day")
    logger.info(f"Premium Gap: ${plan.get('premium_gap', 0):.2f}")
    logger.info(f"Opportunities Found: {len(plan.get('opportunities', []))}")

    # Log individual opportunities
    for opp in plan.get("opportunities", []):
        logger.info(
            f"  🎯 {opp['symbol']} - {opp['strategy']} x{opp['contracts']} "
            f"(${opp['estimated_premium']:.2f} premium, IV: {opp.get('iv_percentile', 'N/A')}%)"
        )

    # Persist plan to disk
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    output_dir = Path("data/options_signals")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"theta_harvest_{timestamp}.json"

    with output_path.open("w") as f:
        json.dump(plan, f, indent=2)

    logger.info(f"✅ Theta harvest plan saved to {output_path}")

    return plan


def update_system_state(plan: dict) -> None:
    """Update system_state.json with options metrics."""
    state_path = Path("data/system_state.json")
    if not state_path.exists():
        logger.warning("system_state.json not found - skipping update")
        return

    try:
        with state_path.open() as f:
            state = json.load(f)

        # Add options metrics to state
        if "options" not in state:
            state["options"] = {}

        state["options"]["last_theta_harvest"] = plan.get("generated_at")
        state["options"]["account_equity"] = plan.get("account_equity", 0.0)
        state["options"]["equity_gate"] = plan.get("equity_gate", {})
        state["options"]["target_daily_premium"] = plan.get("target_daily_premium", 0.0)
        state["options"]["total_estimated_premium"] = plan.get("total_estimated_premium", 0.0)
        state["options"]["premium_gap"] = plan.get("premium_gap", 0.0)
        state["options"]["opportunities_count"] = len(plan.get("opportunities", []))
        state["options"]["on_track"] = plan.get("on_track", False)

        # Update meta
        state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()

        with state_path.open("w") as f:
            json.dump(state, f, indent=2)

        logger.info("✅ Updated system_state.json with options metrics")

    except Exception as e:
        logger.error(f"Failed to update system_state.json: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Options live simulation")
    parser.add_argument(
        "--paper",
        action="store_true",
        default=True,
        help="Run in paper trading mode (default: True)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run in live trading mode (overrides --paper)",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["SPY", "QQQ", "IWM"],
        help="Symbols to evaluate (default: SPY QQQ IWM)",
    )
    parser.add_argument(
        "--skip-update",
        action="store_true",
        help="Skip updating system_state.json",
    )
    args = parser.parse_args()

    load_dotenv()
    setup_logging()

    paper = not args.live

    logger.info("=" * 80)
    logger.info("OPTIONS LIVE SIMULATION")
    logger.info(f"Mode: {'PAPER' if paper else 'LIVE'}")
    logger.info("=" * 80)

    try:
        # Initialize trader
        trader = AlpacaTrader(paper=paper)

        # Get account equity
        account_equity = get_account_equity(trader)
        if account_equity == 0:
            logger.error("❌ Could not determine account equity. Exiting.")
            sys.exit(1)

        logger.info(f"Account Equity: ${account_equity:,.2f}")

        # Check equity gate
        executor = ThetaHarvestExecutor(paper=paper)
        gate = executor.check_equity_gate(account_equity)

        if not gate["theta_enabled"]:
            logger.warning(
                f"⚠️  Theta strategies disabled - equity ${account_equity:,.2f} "
                f"below minimum ${gate.get('gap_to_next_tier', 0):,.2f}"
            )
            logger.info("💡 Options unlock at $5k equity for poor man's covered calls")
            sys.exit(0)

        logger.info(f"✅ Theta strategies enabled - {gate['enabled_strategies']}")

        # Detect market regime
        regime_label = get_market_regime()

        # Execute theta harvest
        plan = execute_theta_harvest(
            account_equity=account_equity,
            regime_label=regime_label,
            paper=paper,
            symbols=args.symbols,
        )

        # Update system state
        if not args.skip_update:
            update_system_state(plan)

        # Summary
        logger.info("=" * 80)
        logger.info("SIMULATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Summary: {plan.get('summary', 'N/A')}")
        logger.info(f"On Track: {'✅ YES' if plan.get('on_track') else '⚠️  NO'}")
        logger.info(f"Premium Gap: ${plan.get('premium_gap', 0):.2f}/day")

        if plan.get("on_track"):
            logger.info("🎉 Theta harvest plan meets daily premium target!")
        else:
            logger.info(
                f"💡 Need ${plan.get('premium_gap', 0):.2f}/day more premium "
                f"to hit ${plan.get('target_daily_premium', 0):.2f}/day target"
            )

    except Exception as e:
        logger.error(f"❌ Options simulation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
