import logging
from dataclasses import dataclass, field

from src.safety.mandatory_trade_gate import safe_close_position

logger = logging.getLogger(__name__)


@dataclass
class EnforcementResult:
    """Result of position enforcement."""

    violations_found: int = 0
    positions_closed: int = 0
    closed_symbols: list[str] = field(default_factory=list)
    total_value_closed: float = 0.0


def enforce_positions(trader) -> EnforcementResult:
    """
    Enforces 'Phil Town Rule #1' and 'Lessons Learned' on active positions.
    Closes positions that violate defined rules.
    """
    result = EnforcementResult()

    try:
        positions = trader.get_all_positions()
        if not positions:
            return result

        # Rule: Liquid ETFs only (SPY, QQQ, IWM, SPX, XSP)
        # Note: We are allowing VIX-based underlyings for the new strategy
        allowed_underlyings = ["SPY", "QQQ", "IWM", "SPX", "XSP", "VIX", "UVXY", "SVXY"]

        for pos in positions:
            symbol = pos.symbol
            # Check if it's an option or the underlying
            underlying = symbol
            if len(symbol) > 5:  # Likely an option symbol
                # Extract underlying from option symbol
                if symbol.startswith("SPY"):
                    underlying = "SPY"
                elif symbol.startswith("QQQ"):
                    underlying = "QQQ"
                elif symbol.startswith("IWM"):
                    underlying = "IWM"
                elif symbol.startswith("SPX"):
                    underlying = "SPX"
                elif symbol.startswith("XSP"):
                    underlying = "XSP"
                elif symbol.startswith("VIX"):
                    underlying = "VIX"
                elif symbol.startswith("UVXY"):
                    underlying = "UVXY"
                elif symbol.startswith("SVXY"):
                    underlying = "SVXY"

            if underlying not in allowed_underlyings:
                logger.warning(f"🚨 PositionEnforcer: {symbol} violates 'Liquid ETF Only' rule.")
                result.violations_found += 1

                # Close the position
                try:
                    safe_close_position(trader, symbol)
                    result.positions_closed += 1
                    result.closed_symbols.append(symbol)
                    logger.info(f"✅ Closed violating position: {symbol}")
                except Exception as e:
                    logger.error(f"❌ Failed to close violating position {symbol}: {e}")

    except Exception as e:
        logger.error(f"Error during position enforcement: {e}")

    return result
