"""Bootstrap entry point for the hybrid trading orchestrator."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import List

from dotenv import load_dotenv

# Ensure src is on the path when executed via GitHub Actions
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.utils.logging_config import setup_logging


def _parse_tickers() -> List[str]:
    raw = os.getenv("TARGET_TICKERS", "SPY,QQQ,VOO")
    return [ticker.strip().upper() for ticker in raw.split(",") if ticker.strip()]


def is_weekend() -> bool:
    """Check if today is Saturday or Sunday."""
    return datetime.now().weekday() in [5, 6]  # Saturday=5, Sunday=6


def crypto_enabled() -> bool:
    """Feature flag for the legacy crypto branch."""
    return os.getenv("ENABLE_CRYPTO_AGENT", "false").lower() in {"1", "true", "yes"}


def execute_crypto_trading() -> None:
    """Execute crypto trading strategy."""
    from src.core.alpaca_trader import AlpacaTrader
    from src.core.risk_manager import RiskManager
    from src.strategies.crypto_strategy import CryptoStrategy
    
    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("CRYPTO TRADING MODE")
    logger.info("=" * 80)
    
    try:
        # Initialize crypto strategy
        trader = AlpacaTrader(paper=True)
        risk_manager = RiskManager()
        
        crypto_strategy = CryptoStrategy(
            trader=trader,
            risk_manager=risk_manager,
            daily_amount=float(os.getenv("CRYPTO_DAILY_AMOUNT", "0.50"))
        )
        
        # Execute crypto trading
        order = crypto_strategy.execute_daily()
        
        if order:
            logger.info(f"✅ Crypto trade executed: {order.symbol} for ${order.amount:.2f}")
        else:
            logger.info("⚠️  No crypto trade executed (market conditions not favorable)")
            
    except Exception as e:
        logger.error(f"❌ Crypto trading failed: {e}", exc_info=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Trading orchestrator entrypoint")
    parser.add_argument(
        "--crypto-only",
        action="store_true",
        help="Force crypto trading even on weekdays (requires ENABLE_CRYPTO_AGENT=true)",
    )
    parser.add_argument(
        "--skip-crypto",
        action="store_true",
        help="Skip legacy crypto flow even on weekends.",
    )
    args = parser.parse_args()
    
    load_dotenv()
    logger = setup_logging()

    crypto_allowed = crypto_enabled()
    should_run_crypto = not args.skip_crypto and crypto_allowed and (args.crypto_only or is_weekend())

    if args.crypto_only and not crypto_allowed:
        logger.warning("Crypto-only requested but ENABLE_CRYPTO_AGENT is not true. Skipping crypto branch.")

    if should_run_crypto:
        logger.info("Crypto branch enabled - executing crypto trading.")
        execute_crypto_trading()
        logger.info("Crypto trading session completed.")
        if args.crypto_only:
            return
    elif is_weekend() and not args.skip_crypto:
        logger.info("Weekend detected but crypto branch disabled. Proceeding with hybrid funnel.")

    # Normal stock trading - import only when needed
    from src.orchestrator.main import TradingOrchestrator
    
    logger.info("Starting hybrid funnel orchestrator entrypoint.")
    tickers = _parse_tickers()

    orchestrator = TradingOrchestrator(tickers=tickers)
    orchestrator.run()
    logger.info("Trading session completed.")


if __name__ == "__main__":
    main()
