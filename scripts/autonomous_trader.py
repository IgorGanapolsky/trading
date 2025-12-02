"""Bootstrap entry point for the hybrid trading orchestrator."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

# Ensure src is on the path when executed via GitHub Actions
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.utils.error_monitoring import init_sentry
from src.utils.logging_config import setup_logging


def _parse_tickers() -> list[str]:
    raw = os.getenv("TARGET_TICKERS", "SPY,QQQ,VOO")
    return [ticker.strip().upper() for ticker in raw.split(",") if ticker.strip()]


def is_weekend() -> bool:
    """Check if today is Saturday or Sunday."""
    return datetime.now().weekday() in [5, 6]  # Saturday=5, Sunday=6


def is_market_holiday() -> bool:
    """
    Check if today is a market holiday (market closed on a weekday).

    Uses Alpaca's clock API to determine if market is closed.
    If market is closed AND it's a weekday, it's a holiday.
    """
    try:
        from src.core.alpaca_trader import AlpacaTrader

        is_weekday = datetime.now().weekday() < 5  # Monday=0, Friday=4
        if not is_weekday:
            return False  # Weekends are not holidays, they're weekends

        trader = AlpacaTrader(paper=True)
        clock = trader.trading_client.get_clock()
        return not clock.is_open  # Market closed on weekday = holiday
    except Exception as e:
        logger = setup_logging()
        logger.warning(f"Could not check market holiday status: {e}. Assuming not a holiday.")
        return False  # Fail safe: assume not a holiday if check fails


def crypto_enabled() -> bool:
    """Feature flag for the legacy crypto branch."""
    return os.getenv("ENABLE_CRYPTO_AGENT", "false").lower() in {"1", "true", "yes"}


def execute_crypto_trading() -> None:
    """Execute crypto trading strategy."""
    from src.core.alpaca_trader import AlpacaTrader
    from src.risk.unified import UnifiedRiskManager as RiskManager
    from src.strategies.crypto_strategy import CryptoStrategy

    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("CRYPTO TRADING MODE")
    logger.info("=" * 80)

    try:
        # Initialize crypto strategy
        trader = AlpacaTrader(paper=True)
        risk_manager = RiskManager(
            full_params=dict(
                max_daily_loss_pct=2.0,
                max_position_size_pct=CryptoStrategy.MAX_POSITION_PCT * 100,
                max_drawdown_pct=15.0,
                max_consecutive_losses=3,
            )
        )

        crypto_strategy = CryptoStrategy(
            trader=trader,
            risk_manager=risk_manager,
            daily_amount=float(os.getenv("CRYPTO_DAILY_AMOUNT", "0.50")),
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
    init_sentry()
    logger = setup_logging()

    crypto_allowed = crypto_enabled()
    is_holiday = is_market_holiday()
    is_weekend_day = is_weekend()
    should_run_crypto = (
        not args.skip_crypto
        and crypto_allowed
        and (args.crypto_only or is_weekend_day or is_holiday)
    )

    if args.crypto_only and not crypto_allowed:
        logger.warning(
            "Crypto-only requested but ENABLE_CRYPTO_AGENT is not true. Skipping crypto branch."
        )

    if should_run_crypto:
        reason = []
        if args.crypto_only:
            reason.append("--crypto-only flag")
        if is_weekend_day:
            reason.append("weekend")
        if is_holiday:
            reason.append("market holiday")
        logger.info(f"Crypto branch enabled ({', '.join(reason)}) - executing crypto trading.")
        execute_crypto_trading()
        logger.info("Crypto trading session completed.")
        if args.crypto_only or is_weekend_day or is_holiday:
            return
    elif (is_weekend_day or is_holiday) and not args.skip_crypto:
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
