"""
Options Accumulation Strategy - NVDA Focus

This strategy accelerates accumulation of NVDA shares specifically for options trading.
It runs daily and prioritizes NVDA purchases to reach the 50-share threshold faster.

Strategy:
- Daily investment: $25/day (configurable via OPTIONS_ACCUMULATION_DAILY env)
- Target: 50 shares of NVDA
- Once threshold reached, switches to maintenance mode
- Integrates with existing options strategy for covered calls
"""

import logging
import os
from typing import Optional

import yfinance as yf
from src.core.alpaca_trader import AlpacaTrader

logger = logging.getLogger(__name__)


class OptionsAccumulationStrategy:
    """
    Options Accumulation Strategy - Focused on NVDA for fastest path to covered calls.

    This strategy:
    1. Tracks NVDA position accumulation
    2. Executes daily purchases to accelerate toward 50-share threshold
    3. Monitors progress and reports status
    4. Integrates with OptionsStrategy once threshold reached
    """

    def __init__(self, paper: bool = True):
        """
        Initialize Options Accumulation Strategy.

        Args:
            paper: If True, use paper trading environment
        """
        self.paper = paper
        self.trader = AlpacaTrader(paper=paper)

        # Strategy configuration
        self.target_symbol = "NVDA"
        self.target_shares = int(os.getenv("OPTIONS_MIN_SHARES", "50"))
        self.daily_amount = float(os.getenv("OPTIONS_ACCUMULATION_DAILY", "25.0"))

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
            nvda_position = None

            for pos in positions:
                if pos.get("symbol") == self.target_symbol and pos.get("side") == "long":
                    nvda_position = pos
                    break

            current_shares = float(nvda_position["qty"]) if nvda_position else 0.0
            current_price = (
                float(nvda_position["current_price"])
                if nvda_position
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

    def execute_daily(self) -> Optional[dict]:
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

            logger.info(f"Current NVDA position: {current_shares:.2f} shares")
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
