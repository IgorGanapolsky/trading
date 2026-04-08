#!/usr/bin/env python3
"""
GSD Framework - Tactical SPY Iron Condor Runner.
Implements the 4-DTE Reddit Strategy + Upgraded Guardrails.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.trading_constants import IC_PROFIT_TARGET_PCT
from src.safety.rag_safety_guard import RAGSafetyGuard
from src.signals.vix_mean_reversion_signal import get_vix_entry_signal
from src.strategies.core_strategy import IronCondorStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def gsd_ship_it(live: bool = False):
    """Execution cycle for Tactical SPY IC."""
    logger.info("🚀 GSD: Starting Tactical SPY Iron Condor Runner...")

    # REDDIT STRATEGY: Scaled intraday entries (10, 12, 14:00)
    now = datetime.now()
    hour = now.hour
    if hour not in [10, 12, 14]:
        logger.info(
            f"⏭️ GSD: Skipping. Not an entry hour (current: {hour}). Strategy calls for 10, 12, 14:00."
        )
        return

    # 1. INITIALIZE UPGRADED STRATEGY
    strategy = IronCondorStrategy()
    strategy.config["target_dte"] = 4  # Target 4-DTE per Reddit strategy
    strategy.config["min_dte"] = 1  # Allow short-dated
    strategy.config["max_dte"] = 7
    strategy.config["take_profit_pct"] = IC_PROFIT_TARGET_PCT  # Canonical 50%

    # 2. VIX/IV/RV GATE (STEP 3)
    signal = get_vix_entry_signal()
    if signal.signal == "AVOID":
        logger.warning(f"🛑 GSD HALT: VIX/IV/RV conditions unsafe: {signal.reason}")
        return

    # 3. RAG SAFETY CONSULT (STEP 6)
    rag_guard = RAGSafetyGuard()
    safety = rag_guard.check_safety("SPY", signal.current_vix, 0.15)
    if safety.get("warning"):
        logger.warning(f"⚠️ RAG ADVISORY: {safety['reason']}")

    # 4. FIND TRADE (STEP 1: LIVE DELTA CHAIN + STEP 4: DYNAMIC WIDTH)
    try:
        trade = strategy.find_trade()
        if not trade:
            logger.info("⏭️ GSD: No liquid 15-delta strikes found at this time.")
            return

        logger.info("✅ GSD: TRADE IDENTIFIED")
        logger.info(f"   Symbol: {trade.underlying}")
        logger.info(f"   Expiry: {trade.expiry} ({trade.dte} DTE)")
        logger.info(
            f"   Strikes: PUT {trade.long_put}/{trade.short_put} | CALL {trade.short_call}/{trade.long_call}"
        )
        logger.info(f"   Credit: ${trade.credit_received:.2f} | Max Risk: ${trade.max_risk:.2f}")

        # 5. EXECUTE (STEP 7: STRUCTURED TRACE)
        if live:
            logger.info("💸 GSD: SUBMITTING LIVE MLEG ORDER...")
            result = strategy.execute(trade, live=True, entry_reason="Reddit 4-DTE Enhanced")
            logger.info(f"📝 GSD: EXECUTION RESULT: {result}")
        else:
            logger.info("🧪 GSD: DRY-RUN SUCCESSFUL. READY FOR LIVE DEPLOYMENT.")

    except Exception as e:
        logger.error(f"❌ GSD ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    gsd_ship_it(live="--live" in sys.argv)
