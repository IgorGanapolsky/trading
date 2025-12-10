"""
Options Accumulation Strategy - Accelerated Share Building

This strategy accelerates accumulation of shares for options trading (covered calls).
It runs daily and prioritizes share purchases to reach the 50-share threshold faster.

Strategy (Updated Dec 9, 2025):
- Daily investment: $100/day (configurable via OPTIONS_ACCUMULATION_DAILY env)
- Target: 50 shares (configurable via OPTIONS_MIN_SHARES env)
- Default symbol: INTC (~$24/share) - can reach 50 shares in ~12 days
- Alternative symbols ranked by time-to-50-shares at $100/day:
  * INTC: ~12 days ($24/share)
  * AMD: ~65 days ($130/share)
  * NVDA: ~70 days ($140/share)
- Once threshold reached, switches to maintenance mode
- Integrates with existing options strategy for covered calls
"""

import logging
import os

import yfinance as yf

from src.core.alpaca_trader import AlpacaTrader

logger = logging.getLogger(__name__)

# Recommended accumulation symbols ranked by cost efficiency
ACCUMULATION_CANDIDATES = [
    {"symbol": "INTC", "approx_price": 24, "days_at_100": 12, "options_liquidity": "HIGH"},
    {"symbol": "F", "approx_price": 11, "days_at_100": 6, "options_liquidity": "HIGH"},
    {"symbol": "AMD", "approx_price": 130, "days_at_100": 65, "options_liquidity": "HIGH"},
    {"symbol": "NVDA", "approx_price": 140, "days_at_100": 70, "options_liquidity": "HIGH"},
    {"symbol": "AAPL", "approx_price": 195, "days_at_100": 98, "options_liquidity": "HIGH"},
]


class OptionsAccumulationStrategy:
    """
    Options Accumulation Strategy - Accelerated path to covered calls.

    This strategy:
    1. Tracks position accumulation for configurable symbol (default: INTC)
    2. Executes daily purchases to accelerate toward 50-share threshold
    3. Monitors progress and reports status
    4. Integrates with OptionsStrategy once threshold reached

    Updated Dec 9, 2025:
    - Default symbol changed from NVDA to INTC (faster accumulation)
    - Daily amount increased from $25 to $100
    - Added candidate ranking for alternative symbols
    """

    def __init__(self, paper: bool = True, symbol: str | None = None):
        """
        Initialize Options Accumulation Strategy.

        Args:
            paper: If True, use paper trading environment
            symbol: Target symbol (default: from env or INTC)
        """
        self.paper = paper
        self.trader = AlpacaTrader(paper=paper)

        # Strategy configuration - Updated Dec 9, 2025
        # Default to INTC for faster accumulation (~12 days vs 280 days for NVDA at old rate)
        self.target_symbol = symbol or os.getenv("OPTIONS_ACCUMULATION_SYMBOL", "INTC")
        self.target_shares = int(os.getenv("OPTIONS_MIN_SHARES", "50"))
        self.daily_amount = float(os.getenv("OPTIONS_ACCUMULATION_DAILY", "100.0"))

        logger.info(
            f"Options Accumulation Strategy initialized: "
            f"Target={self.target_symbol}, "
            f"Threshold={self.target_shares} shares, "
            f"Daily=${self.daily_amount:.2f}"
        )

    def get_current_status(self) -> dict:
        """
        Get current accumulation status.

        Returns:
            Dictionary with current status, progress, and recommendations
        """
        try:
            positions = self.trader.get_positions()
            target_position = None

            for pos in positions:
                if pos.get("symbol") == self.target_symbol and pos.get("side") == "long":
                    target_position = pos
                    break
            else:
                target_position = None

            current_shares = float(target_position["qty"]) if target_position else 0.0
            current_price = (
                float(target_position["current_price"])
                if target_position
                else self._get_current_price()
            )

            shares_needed = max(0, self.target_shares - current_shares)
            cost_to_target = shares_needed * current_price
            days_to_target = (
                cost_to_target / self.daily_amount if self.daily_amount > 0 else float("inf")
            )

            progress_pct = (
                (current_shares / self.target_shares * 100) if self.target_shares > 0 else 0
            )

            status = {
                "target_symbol": self.target_symbol,
                "target_shares": self.target_shares,
                "current_shares": current_shares,
                "current_price": current_price,
                "shares_needed": shares_needed,
                "cost_to_target": cost_to_target,
                "days_to_target": days_to_target,
                "progress_pct": progress_pct,
                "daily_amount": self.daily_amount,
                "status": "complete" if current_shares >= self.target_shares else "accumulating",
                "position_value": current_shares * current_price,
            }

            return status

        except Exception as e:
            logger.error(f"Error getting accumulation status: {e}")
            return {"error": str(e), "status": "error"}

    def execute_daily(self) -> dict | None:
        """
        Execute daily accumulation purchase.

        Returns:
            Dictionary with execution results, or None if no action taken
        """
        logger.info("=" * 80)
        logger.info("EXECUTING OPTIONS ACCUMULATION STRATEGY")
        logger.info("=" * 80)

        try:
            # Get current status
            status = self.get_current_status()

            if status.get("status") == "complete":
                logger.info(
                    f"✅ Target reached: {status['current_shares']:.2f} shares of {self.target_symbol} "
                    f"(target: {self.target_shares} shares)"
                )
                logger.info("Options accumulation complete - covered calls can now be activated")
                return {
                    "action": "complete",
                    "status": status,
                    "message": "Target threshold reached",
                }

            if status.get("status") == "error":
                logger.error(f"Error getting status: {status.get('error')}")
                return None

            # Check if we should buy today
            current_shares = status["current_shares"]
            shares_needed = status["shares_needed"]

            if shares_needed <= 0:
                logger.info("Target already reached")
                return {"action": "complete", "status": status}

            # Calculate shares to buy today
            current_price = status["current_price"]
            shares_to_buy = self.daily_amount / current_price

            logger.info(f"Current {self.target_symbol} position: {current_shares:.2f} shares")
            logger.info(f"Target: {self.target_shares} shares")
            logger.info(f"Shares needed: {shares_needed:.2f}")
            logger.info(
                f"Today's purchase: ${self.daily_amount:.2f} = {shares_to_buy:.4f} shares @ ${current_price:.2f}"
            )
            logger.info(f"Progress: {status['progress_pct']:.1f}%")
            logger.info(f"Days to target: {status['days_to_target']:.0f} days")

            # Execute purchase
            try:
                order_result = self.trader.buy_market(
                    symbol=self.target_symbol, amount=self.daily_amount
                )

                if order_result.get("success"):
                    logger.info(f"✅ Purchased {shares_to_buy:.4f} shares of {self.target_symbol}")

                    # Update status after purchase
                    new_status = self.get_current_status()

                    return {
                        "action": "purchased",
                        "order": order_result,
                        "shares_purchased": shares_to_buy,
                        "amount": self.daily_amount,
                        "status_before": status,
                        "status_after": new_status,
                    }
                else:
                    logger.warning(f"Purchase failed: {order_result.get('error', 'Unknown error')}")
                    return {
                        "action": "failed",
                        "error": order_result.get("error"),
                        "status": status,
                    }

            except Exception as e:
                logger.error(f"Error executing purchase: {e}")
                return {
                    "action": "error",
                    "error": str(e),
                    "status": status,
                }

        except Exception as e:
            logger.error(f"Error in options accumulation execution: {e}", exc_info=True)
            return {
                "action": "error",
                "error": str(e),
            }

    def _get_current_price(self) -> float:
        """Get current price of target symbol."""
        try:
            ticker = yf.Ticker(self.target_symbol)
            info = ticker.info
            return info.get("currentPrice", info.get("regularMarketPrice", 0))
        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return 0.0
