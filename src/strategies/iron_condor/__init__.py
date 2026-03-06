"""
Iron Condor Vertical Slice Controller
Orchestrates Signal -> Risk -> Execution.
"""

import logging
from datetime import date
from typing import Any

from src.constants.trading_thresholds import RiskThresholds

from .executor import IronCondorExecutor
from .risk import IronCondorRisk
from .signal import IronCondorSignal

logger = logging.getLogger(__name__)


class IronCondorController:
    """
    Vertical Slice Controller for Iron Condors.
    """

    def __init__(self, trading_client):
        self.signal = IronCondorSignal()
        self.risk = IronCondorRisk()
        self.executor = IronCondorExecutor(trading_client)

    def run_cycle(
        self, market_data: dict[str, Any], account_info: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute one full cycle of the strategy.
        """
        symbol = market_data.get("symbol", "SPY")

        # 1. SIGNAL
        signal_result = self.signal.generate_signal(market_data)
        if not signal_result.should_entry:
            return {"status": "SKIPPED", "reason": signal_result.reason}

        # 2. RISK & POSITION SIZING
        positions = account_info.get("positions", [])

        if not self.risk.validate_exposure(positions, symbol):
            return {"status": "SKIPPED", "reason": "Max exposure reached for ticker"}

        # 3. EXECUTION
        # Note: In production, the signal layer would provide actual symbols from a chain provider.
        # This is a structural demonstration.
        try:
            # qty = self.risk.calculate_quantity(equity, max_risk=1000)
            # order = self.executor.build_mleg_order(symbol, legs, qty)
            # result = self.executor.execute(order)
            return {
                "status": "READY_TO_TRADE",
                "signal": signal_result.reason,
                "confidence": signal_result.confidence,
            }
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {"status": "ERROR", "error": str(e)}

    def check_exits(self, positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Check open iron condor positions for exit conditions.

        Evaluates each position against three exit rules from trading_thresholds:
        1. Take profit at 50% of credit received
        2. Stop loss at 200% of credit received
        3. Time exit at 7 DTE regardless of P/L

        Args:
            positions: List of position dicts, each containing:
                - symbol: str
                - entry_credit: float (credit received per share)
                - current_price: float (current cost to close per share)
                - expiration_date: date

        Returns:
            List of dicts for positions that should be closed, each with:
                - symbol, action, reason, entry_credit, current_price
        """
        exits: list[dict[str, Any]] = []
        today = date.today()

        for pos in positions:
            symbol = pos["symbol"]
            entry_credit = pos["entry_credit"]
            current_price = pos["current_price"]
            expiration = pos["expiration_date"]

            dte = (expiration - today).days
            current_profit = entry_credit - current_price
            profit_target = entry_credit * RiskThresholds.IRON_CONDOR_TAKE_PROFIT_PCT
            max_loss = entry_credit * RiskThresholds.IRON_CONDOR_STOP_LOSS_MULTIPLIER
            current_loss = current_price - entry_credit

            # 1. Take profit
            if current_profit >= profit_target:
                logger.info(
                    f"🎯 Profit target hit for {symbol}: "
                    f"${current_profit:.2f} >= ${profit_target:.2f}"
                )
                exits.append(
                    {
                        "symbol": symbol,
                        "action": "CLOSE",
                        "reason": (
                            f"50% profit target: profit ${current_profit:.2f} "
                            f">= target ${profit_target:.2f}"
                        ),
                        "entry_credit": entry_credit,
                        "current_price": current_price,
                    }
                )
                continue

            # 2. Stop loss
            if current_loss >= max_loss:
                logger.warning(
                    f"🛑 Stop loss triggered for {symbol}: "
                    f"loss ${current_loss:.2f} >= ${max_loss:.2f}"
                )
                exits.append(
                    {
                        "symbol": symbol,
                        "action": "CLOSE",
                        "reason": (
                            f"200% stop loss: loss ${current_loss:.2f} >= max ${max_loss:.2f}"
                        ),
                        "entry_credit": entry_credit,
                        "current_price": current_price,
                    }
                )
                continue

            # 3. DTE exit
            if dte <= RiskThresholds.EXIT_AT_DTE:
                logger.info(f"⏰ DTE exit for {symbol}: {dte} DTE <= {RiskThresholds.EXIT_AT_DTE}")
                exits.append(
                    {
                        "symbol": symbol,
                        "action": "CLOSE",
                        "reason": f"DTE exit: {dte} days <= {RiskThresholds.EXIT_AT_DTE} DTE threshold",
                        "entry_credit": entry_credit,
                        "current_price": current_price,
                    }
                )

        return exits
