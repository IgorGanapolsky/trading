"""Bootstrap entry point for the hybrid trading orchestrator."""

from __future__ import annotations

import os
import sys
from typing import List

from dotenv import load_dotenv

# Ensure src is on the path when executed via GitHub Actions
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.orchestrator.main import TradingOrchestrator
from src.utils.logging_config import setup_logging


def _parse_tickers() -> List[str]:
    raw = os.getenv("TARGET_TICKERS", "SPY,QQQ,VOO")
    return [ticker.strip().upper() for ticker in raw.split(",") if ticker.strip()]


def main() -> None:
    load_dotenv()
    logger = setup_logging()

    logger.info("Starting hybrid funnel orchestrator entrypoint.")
    tickers = _parse_tickers()

    orchestrator = TradingOrchestrator(tickers=tickers)
    orchestrator.run()
    logger.info("Trading session completed.")


if __name__ == "__main__":
    main()
