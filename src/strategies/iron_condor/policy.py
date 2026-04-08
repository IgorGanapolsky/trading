"""
Iron Condor Exit Policy Engine - Step 5 of Strategy Upgrade.
Pure logic for evaluating exit rules against a position snapshot.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.constants.trading_thresholds import RiskThresholds
from src.core.trading_constants import IC_PROFIT_TARGET_PCT, IRON_CONDOR_STOP_LOSS_MULTIPLIER

from .position import IronCondorPosition

logger = logging.getLogger(__name__)


@dataclass
class ExitDecision:
    should_exit: bool
    reason: Optional[str] = None
    rule_name: Optional[str] = None


class ExitPolicyEngine:
    """Evaluates exit policies against IronCondorPosition state."""

    def __init__(
        self,
        profit_target: float = IC_PROFIT_TARGET_PCT,
        stop_loss_mult: float = IRON_CONDOR_STOP_LOSS_MULTIPLIER,
        time_exit_dte: int = RiskThresholds.EXIT_AT_DTE,
    ):
        self.profit_target = profit_target
        self.stop_loss_mult = stop_loss_mult
        self.time_exit_dte = time_exit_dte

    def evaluate(self, pos: IronCondorPosition, current_mark: float) -> ExitDecision:
        pnl_pct = pos.get_pnl_pct(current_mark)

        # 1. Profit Exit
        if pnl_pct >= self.profit_target:
            return ExitDecision(
                should_exit=True,
                reason=f"Target hit: {pnl_pct:.1%} >= {self.profit_target:.1%}",
                rule_name="PROFIT_TARGET",
            )

        # 2. Stop Exit (Credit Spread Rule: current value > stop_loss_mult * entry_credit)
        # Note: entry_credit is collected (positive).
        # Loss = current_mark - entry_credit.
        # If loss >= entry_credit * stop_loss_mult.
        loss_pct = (current_mark - pos.entry_credit) / pos.entry_credit
        if loss_pct >= self.stop_loss_mult:
            return ExitDecision(
                should_exit=True,
                reason=f"Stop hit: loss {loss_pct:.1%} >= {self.stop_loss_mult:.1%}",
                rule_name="STOP_LOSS",
            )

        # 3. Time Exit
        if pos.dte <= self.time_exit_dte:
            return ExitDecision(
                should_exit=True,
                reason=f"Time exit: {pos.dte} DTE <= {self.time_exit_dte} threshold",
                rule_name="TIME_EXIT",
            )

        return ExitDecision(should_exit=False)
