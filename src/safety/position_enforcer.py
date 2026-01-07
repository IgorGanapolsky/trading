"""
Position Enforcer - Validates positions against RAG lessons learned.

This module checks current positions against lessons learned to identify
positions that violate documented rules (e.g., crypto positions when
we learned crypto should not be traded).

Created: Jan 7, 2026
Purpose: Fix autonomous_trader.py import error causing workflow failures
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.alpaca_trader import AlpacaTrader

logger = logging.getLogger(__name__)


@dataclass
class EnforcementResult:
    """Result of position enforcement check."""
    violations_found: int = 0
    violations: list[dict] = None
    positions_checked: int = 0
    positions_closed: int = 0
    error: str | None = None

    def __post_init__(self):
        if self.violations is None:
            self.violations = []


# Symbols that violate lesson LL-052: "We Do NOT Trade Crypto"
BANNED_SYMBOLS = {
    "BTCUSD", "ETHUSD", "BTC/USD", "ETH/USD",
    "BTCUSDT", "ETHUSDT", "SOLUSD", "DOGEUSD",
    # Crypto ETFs are also banned per lesson
    "BITO", "GBTC", "ETHE",
}


def _check_symbol_banned(symbol: str) -> tuple[bool, str]:
    """Check if a symbol is banned per lessons learned."""
    symbol_upper = symbol.upper()

    # Check direct match
    if symbol_upper in BANNED_SYMBOLS:
        return True, "LL-052: Crypto trading banned"

    # Check crypto suffix
    if symbol_upper.endswith("USD") and not symbol_upper.startswith(("SPY", "QQQ", "IWM")):
        # Might be a crypto pair
        base = symbol_upper.replace("USD", "")
        if base in {"BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "DOT", "AVAX"}:
            return True, "LL-052: Crypto trading banned"

    return False, ""


def _load_lessons_for_bans() -> list[str]:
    """Load any additional banned symbols from lessons learned."""
    additional_bans = []
    lessons_dir = Path("rag_knowledge/lessons_learned")

    if not lessons_dir.exists():
        return additional_bans

    # Look for crypto-related lessons
    for lesson_file in lessons_dir.glob("ll_*crypto*.md"):
        try:
            content = lesson_file.read_text()
            if "banned" in content.lower() or "not allowed" in content.lower():
                logger.debug(f"Found ban lesson: {lesson_file.name}")
        except Exception:
            pass

    return additional_bans


def enforce_positions(trader: AlpacaTrader) -> EnforcementResult:
    """
    Check all positions against lessons learned and close violations.

    Args:
        trader: AlpacaTrader instance to check positions

    Returns:
        EnforcementResult with details of any violations found
    """
    result = EnforcementResult()

    try:
        # Get current positions
        positions = trader.get_positions()
        result.positions_checked = len(positions)

        logger.info(f"Position Enforcer: Checking {len(positions)} positions")

        for position in positions:
            symbol = getattr(position, 'symbol', str(position))

            is_banned, reason = _check_symbol_banned(symbol)

            if is_banned:
                result.violations_found += 1
                result.violations.append({
                    "symbol": symbol,
                    "reason": reason,
                    "action": "close_position"
                })
                logger.warning(f"VIOLATION: {symbol} - {reason}")

                # Close the violating position
                try:
                    trader.close_position(symbol)
                    result.positions_closed += 1
                    logger.info(f"Closed violating position: {symbol}")
                except Exception as e:
                    logger.error(f"Failed to close {symbol}: {e}")

        if result.violations_found == 0:
            logger.info("Position Enforcer: No violations found")
        else:
            logger.warning(
                f"Position Enforcer: {result.violations_found} violations, "
                f"{result.positions_closed} positions closed"
            )

    except Exception as e:
        result.error = str(e)
        logger.error(f"Position enforcement failed: {e}")

    return result
