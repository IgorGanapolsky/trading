"""
Iron Condor Strategy - Automated Theta Income Generation

Implements automated iron condor execution for consistent premium income.
This is the primary income strategy targeting $100/day.

Entry Criteria:
- IV Rank > 50 (selling expensive premium)
- Expected move < strike width (high probability of profit)
- Days to expiration: 30-45 (optimal theta decay)
- Delta: 16 delta wings (84% probability OTM)

Exit Criteria:
- Profit target: 50% of max profit (lock in gains early)
- Stop loss: 2.0x credit received (McMillan rule for IC)
- Time exit: 21 DTE (avoid gamma risk)
- Delta breach: Close if delta > 30 on either wing

Author: AI Trading System
Date: December 2024
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IronCondorState(Enum):
    """State of an iron condor position."""

    PENDING = "pending"  # Looking for entry
    OPEN = "open"  # Position is active
    PROFIT_TARGET = "profit_target"  # Closed at profit target
    STOP_LOSS = "stop_loss"  # Closed at stop loss
    TIME_EXIT = "time_exit"  # Closed due to DTE
    DELTA_EXIT = "delta_exit"  # Closed due to delta breach
    EXPIRED = "expired"  # Expired worthless (max profit)


@dataclass
class IronCondorPosition:
    """Represents an iron condor position."""

    # Identifiers
    symbol: str
    underlying: str
    opened_at: datetime

    # Put spread (lower side)
    short_put_strike: float
    long_put_strike: float
    put_spread_width: float

    # Call spread (upper side)
    short_call_strike: float
    long_call_strike: float
    call_spread_width: float

    # Trade details
    contracts: int
    expiration: date
    entry_credit: float  # Total credit received per contract
    current_value: float  # Current cost to close

    # Greeks at entry
    entry_delta: float
    current_delta: float
    current_gamma: float
    current_theta: float

    # State
    state: IronCondorState = IronCondorState.OPEN

    @property
    def days_to_expiration(self) -> int:
        """Calculate days to expiration."""
        return (self.expiration - date.today()).days

    @property
    def max_profit(self) -> float:
        """Maximum profit = credit received × 100 × contracts."""
        return self.entry_credit * 100 * self.contracts

    @property
    def max_loss(self) -> float:
        """Maximum loss = (wider spread width - credit) × 100 × contracts."""
        wider_spread = max(self.put_spread_width, self.call_spread_width)
        return (wider_spread - self.entry_credit) * 100 * self.contracts

    @property
    def current_pnl(self) -> float:
        """Current P/L = (entry credit - current value) × 100 × contracts."""
        return (self.entry_credit - self.current_value) * 100 * self.contracts

    @property
    def pnl_percent(self) -> float:
        """P/L as percentage of max profit."""
        if self.max_profit == 0:
            return 0.0
        return (self.current_pnl / self.max_profit) * 100

    @property
    def margin_required(self) -> float:
        """Margin = max of spread widths - credit received."""
        wider_spread = max(self.put_spread_width, self.call_spread_width)
        return (wider_spread - self.entry_credit) * 100 * self.contracts


class IronCondorStrategy:
    """
    Automated iron condor execution for theta income.

    Why Iron Condors for Income:
    - Win rate: 70-80% (much higher than directional trades)
    - Defined risk: Max loss is known at entry
    - Theta positive: Time decay works FOR you
    - Works in range-bound markets (which is most of the time)

    Target: $100/day income through consistent premium collection.
    """

    # Entry parameters
    MIN_IV_RANK = 50  # Only sell premium when it's expensive
    TARGET_DTE_MIN = 30  # Minimum days to expiration
    TARGET_DTE_MAX = 45  # Maximum days to expiration
    TARGET_DELTA = 0.16  # 16 delta wings (84% probability OTM)
    MIN_CREDIT = 0.50  # Minimum credit per contract
    MAX_SPREAD_WIDTH = 5.0  # Maximum width of each spread

    # Exit parameters
    PROFIT_TARGET_PCT = 0.50  # Take profit at 50% of max
    STOP_LOSS_MULTIPLIER = 2.0  # Exit at 2x credit (McMillan IC rule)
    GAMMA_EXIT_DTE = 21  # Close by 21 DTE to avoid gamma risk
    DELTA_BREACH_THRESHOLD = 0.30  # Close if wing delta > 30

    # Position limits
    MAX_POSITIONS = 5  # Maximum concurrent iron condors
    MAX_PORTFOLIO_ALLOCATION = 0.30  # Max 30% of portfolio in IC

    def __init__(
        self,
        portfolio_value: float = 100000.0,
        target_daily_income: float = 100.0,
        paper: bool = True,
    ):
        """
        Initialize iron condor strategy.

        Args:
            portfolio_value: Current portfolio value
            target_daily_income: Daily income target
            paper: If True, use paper trading
        """
        self.portfolio_value = portfolio_value
        self.target_daily_income = target_daily_income
        self.paper = paper
        self.positions: dict[str, IronCondorPosition] = {}

        logger.info(
            f"Iron Condor Strategy initialized: "
            f"portfolio=${portfolio_value:,.0f}, target=${target_daily_income}/day"
        )

    def evaluate_entry(
        self,
        symbol: str,
        current_price: float,
        iv_rank: float,
        expected_move_pct: float,
        available_expirations: list[date],
        options_chain: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        Evaluate if conditions are right for iron condor entry.

        Args:
            symbol: Underlying symbol
            current_price: Current stock price
            iv_rank: IV Rank (0-100)
            expected_move_pct: Expected move percentage
            available_expirations: List of available expiration dates
            options_chain: Options chain data (optional)

        Returns:
            Dict with entry evaluation and recommendation
        """
        evaluation = {
            "symbol": symbol,
            "current_price": current_price,
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "recommendation": None,
            "entry_setup": None,
        }

        # Check 1: IV Rank
        iv_check = iv_rank >= self.MIN_IV_RANK
        evaluation["checks"]["iv_rank"] = {
            "passed": iv_check,
            "value": iv_rank,
            "threshold": self.MIN_IV_RANK,
            "reason": f"IV Rank {iv_rank:.0f}% {'>' if iv_check else '<'} {self.MIN_IV_RANK}% minimum",
        }

        # Check 2: Expected move vs spread width
        # For iron condors, we want expected move to be LESS than our spread width
        # This means the stock is likely to stay within our profit zone
        spread_width = self.MAX_SPREAD_WIDTH
        expected_move_dollars = current_price * (expected_move_pct / 100)
        move_check = expected_move_dollars < spread_width * 1.5  # Some buffer
        evaluation["checks"]["expected_move"] = {
            "passed": move_check,
            "expected_move_pct": expected_move_pct,
            "expected_move_dollars": round(expected_move_dollars, 2),
            "spread_width": spread_width,
            "reason": (
                f"Expected move ${expected_move_dollars:.2f} "
                f"{'<' if move_check else '>'} spread buffer"
            ),
        }

        # Check 3: Find suitable expiration
        suitable_expiration = None
        for exp in available_expirations:
            dte = (exp - date.today()).days
            if self.TARGET_DTE_MIN <= dte <= self.TARGET_DTE_MAX:
                suitable_expiration = exp
                break

        dte_check = suitable_expiration is not None
        evaluation["checks"]["expiration"] = {
            "passed": dte_check,
            "suitable_expiration": suitable_expiration.isoformat() if suitable_expiration else None,
            "dte": (suitable_expiration - date.today()).days if suitable_expiration else None,
            "reason": (
                f"Found expiration {suitable_expiration} "
                if dte_check
                else f"No expiration in {self.TARGET_DTE_MIN}-{self.TARGET_DTE_MAX} DTE range"
            ),
        }

        # Check 4: Position limits
        position_count = len(self.positions)
        position_check = position_count < self.MAX_POSITIONS
        evaluation["checks"]["position_limit"] = {
            "passed": position_check,
            "current_positions": position_count,
            "max_positions": self.MAX_POSITIONS,
            "reason": (
                f"Have {position_count}/{self.MAX_POSITIONS} positions"
                if position_check
                else "Maximum positions reached"
            ),
        }

        # Overall recommendation
        all_checks_passed = all(check["passed"] for check in evaluation["checks"].values())

        if all_checks_passed:
            evaluation["recommendation"] = "ENTER"

            # Calculate strikes
            # Short put: current price - expected move (approximately 16 delta)
            # Long put: short put - spread width
            # Short call: current price + expected move (approximately 16 delta)
            # Long call: short call + spread width

            short_put = round(current_price - expected_move_dollars, 0)
            long_put = short_put - spread_width
            short_call = round(current_price + expected_move_dollars, 0)
            long_call = short_call + spread_width

            # Estimate credit (simplified - in reality would use options chain)
            estimated_credit = 1.50  # Conservative estimate

            evaluation["entry_setup"] = {
                "expiration": suitable_expiration.isoformat(),
                "dte": (suitable_expiration - date.today()).days,
                "put_spread": {
                    "short_strike": short_put,
                    "long_strike": long_put,
                    "width": spread_width,
                },
                "call_spread": {
                    "short_strike": short_call,
                    "long_strike": long_call,
                    "width": spread_width,
                },
                "estimated_credit": estimated_credit,
                "max_profit": estimated_credit * 100,
                "max_loss": (spread_width - estimated_credit) * 100,
                "risk_reward": f"1:{round(estimated_credit / (spread_width - estimated_credit), 2)}",
                "breakevens": {
                    "lower": short_put - estimated_credit,
                    "upper": short_call + estimated_credit,
                },
                "profit_zone": {
                    "low": short_put,
                    "high": short_call,
                    "width_pct": round(((short_call - short_put) / current_price) * 100, 1),
                },
            }
        else:
            failed_checks = [
                name for name, check in evaluation["checks"].items() if not check["passed"]
            ]
            evaluation["recommendation"] = "WAIT"
            evaluation["failed_checks"] = failed_checks

        return evaluation

    def check_exit_conditions(self, position: IronCondorPosition) -> dict[str, Any]:
        """
        Check if any exit conditions are met for a position.

        Exit Rules (in order of priority):
        1. Stop loss: Loss exceeds 2x credit received
        2. Profit target: Profit reaches 50% of max
        3. Time exit: DTE falls below 21 (gamma risk)
        4. Delta breach: Either wing delta exceeds 30

        Args:
            position: The iron condor position to check

        Returns:
            Dict with exit check results
        """
        result = {
            "symbol": position.symbol,
            "should_exit": False,
            "exit_reason": None,
            "urgency": "LOW",
            "checks": {},
        }

        # Check 1: Stop Loss (2x credit)
        loss_multiple = (
            (position.current_value - position.entry_credit) / position.entry_credit
            if position.entry_credit > 0
            else 0
        )
        stop_triggered = loss_multiple >= self.STOP_LOSS_MULTIPLIER

        result["checks"]["stop_loss"] = {
            "triggered": stop_triggered,
            "loss_multiple": round(loss_multiple, 2),
            "threshold": self.STOP_LOSS_MULTIPLIER,
            "current_loss": round(position.current_pnl, 2) if position.current_pnl < 0 else 0,
        }

        if stop_triggered:
            result["should_exit"] = True
            result["exit_reason"] = (
                f"STOP_LOSS: Loss {loss_multiple:.1f}x credit exceeds "
                f"{self.STOP_LOSS_MULTIPLIER}x threshold"
            )
            result["urgency"] = "HIGH"
            return result

        # Check 2: Profit Target (50% of max)
        profit_pct = position.pnl_percent
        profit_triggered = profit_pct >= self.PROFIT_TARGET_PCT * 100

        result["checks"]["profit_target"] = {
            "triggered": profit_triggered,
            "profit_pct": round(profit_pct, 1),
            "target_pct": self.PROFIT_TARGET_PCT * 100,
            "current_profit": round(position.current_pnl, 2),
        }

        if profit_triggered:
            result["should_exit"] = True
            result["exit_reason"] = (
                f"PROFIT_TARGET: {profit_pct:.0f}% profit reached "
                f"(target: {self.PROFIT_TARGET_PCT * 100:.0f}%)"
            )
            result["urgency"] = "MEDIUM"
            return result

        # Check 3: Time Exit (21 DTE gamma risk)
        dte = position.days_to_expiration
        time_triggered = dte <= self.GAMMA_EXIT_DTE

        result["checks"]["time_exit"] = {
            "triggered": time_triggered,
            "dte": dte,
            "threshold": self.GAMMA_EXIT_DTE,
        }

        if time_triggered:
            result["should_exit"] = True
            result["exit_reason"] = (
                f"TIME_EXIT: DTE={dte} below {self.GAMMA_EXIT_DTE} day threshold (gamma risk)"
            )
            result["urgency"] = "MEDIUM"
            return result

        # Check 4: Delta Breach
        delta_triggered = abs(position.current_delta) > self.DELTA_BREACH_THRESHOLD

        result["checks"]["delta_breach"] = {
            "triggered": delta_triggered,
            "current_delta": round(position.current_delta, 3),
            "threshold": self.DELTA_BREACH_THRESHOLD,
        }

        if delta_triggered:
            result["should_exit"] = True
            result["exit_reason"] = (
                f"DELTA_BREACH: Delta {position.current_delta:.2f} exceeds "
                f"±{self.DELTA_BREACH_THRESHOLD} threshold"
            )
            result["urgency"] = "HIGH"
            return result

        return result

    def calculate_position_size(
        self,
        entry_setup: dict[str, Any],
        account_value: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Calculate optimal position size for iron condor.

        Uses the income-based sizing approach:
        - Target $100/day = $500/week = 5 trades/week
        - Each trade needs to contribute ~$100 in premium

        Args:
            entry_setup: Entry setup from evaluate_entry()
            account_value: Account value (uses self.portfolio_value if None)

        Returns:
            Dict with position sizing recommendation
        """
        account = account_value or self.portfolio_value
        credit_per_contract = entry_setup.get("estimated_credit", 1.50)
        max_loss_per_contract = entry_setup.get("max_loss", 350)

        # Target: $100 per trade from premium
        target_premium = 100.0

        # Contracts needed for target premium
        contracts_for_target = max(1, int(target_premium / (credit_per_contract * 100)))

        # Risk check: max 5% account risk per trade
        max_risk_per_trade = account * 0.05
        max_contracts_by_risk = max(1, int(max_risk_per_trade / max_loss_per_contract))

        # Position limit check: max 30% portfolio in IC margin
        max_margin = account * self.MAX_PORTFOLIO_ALLOCATION
        current_margin = sum(pos.margin_required for pos in self.positions.values())
        available_margin = max_margin - current_margin
        margin_per_contract = max_loss_per_contract  # Margin ≈ max loss for IC
        max_contracts_by_margin = max(1, int(available_margin / margin_per_contract))

        # Final contracts = minimum of all limits
        recommended_contracts = min(
            contracts_for_target, max_contracts_by_risk, max_contracts_by_margin
        )

        return {
            "recommended_contracts": recommended_contracts,
            "limiting_factor": (
                "target"
                if recommended_contracts == contracts_for_target
                else "risk"
                if recommended_contracts == max_contracts_by_risk
                else "margin"
            ),
            "calculations": {
                "contracts_for_target": contracts_for_target,
                "max_contracts_by_risk": max_contracts_by_risk,
                "max_contracts_by_margin": max_contracts_by_margin,
            },
            "expected_credit": round(recommended_contracts * credit_per_contract * 100, 2),
            "max_loss": round(recommended_contracts * max_loss_per_contract, 2),
            "margin_required": round(recommended_contracts * margin_per_contract, 2),
            "available_margin": round(available_margin, 2),
        }

    def get_portfolio_summary(self) -> dict[str, Any]:
        """
        Get summary of all iron condor positions.

        Returns:
            Dict with portfolio summary
        """
        if not self.positions:
            return {
                "total_positions": 0,
                "total_margin": 0,
                "total_pnl": 0,
                "positions": [],
            }

        total_margin = sum(pos.margin_required for pos in self.positions.values())
        total_pnl = sum(pos.current_pnl for pos in self.positions.values())

        positions_summary = []
        for symbol, pos in self.positions.items():
            exit_check = self.check_exit_conditions(pos)
            positions_summary.append(
                {
                    "symbol": symbol,
                    "underlying": pos.underlying,
                    "dte": pos.days_to_expiration,
                    "pnl": round(pos.current_pnl, 2),
                    "pnl_pct": round(pos.pnl_percent, 1),
                    "max_profit": round(pos.max_profit, 2),
                    "margin": round(pos.margin_required, 2),
                    "exit_signal": exit_check["should_exit"],
                    "exit_reason": exit_check["exit_reason"],
                }
            )

        return {
            "total_positions": len(self.positions),
            "max_positions": self.MAX_POSITIONS,
            "total_margin": round(total_margin, 2),
            "margin_pct": round((total_margin / self.portfolio_value) * 100, 2),
            "total_pnl": round(total_pnl, 2),
            "positions": positions_summary,
        }


def get_iron_condor_strategy(
    portfolio_value: float = 100000.0,
    target_daily_income: float = 100.0,
    paper: bool = True,
) -> IronCondorStrategy:
    """Get IronCondorStrategy instance."""
    return IronCondorStrategy(
        portfolio_value=portfolio_value,
        target_daily_income=target_daily_income,
        paper=paper,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example usage
    strategy = IronCondorStrategy(portfolio_value=100000, target_daily_income=100)

    # Evaluate entry for SPY
    print("\n=== Iron Condor Entry Evaluation ===")
    evaluation = strategy.evaluate_entry(
        symbol="SPY",
        current_price=450.0,
        iv_rank=55,
        expected_move_pct=3.5,
        available_expirations=[
            date.today() + timedelta(days=30),
            date.today() + timedelta(days=37),
            date.today() + timedelta(days=44),
        ],
    )

    print(f"Symbol: {evaluation['symbol']}")
    print(f"Recommendation: {evaluation['recommendation']}")

    for check_name, check in evaluation["checks"].items():
        status = "PASS" if check["passed"] else "FAIL"
        print(f"  {check_name}: {status} - {check['reason']}")

    if evaluation["entry_setup"]:
        setup = evaluation["entry_setup"]
        print("\nEntry Setup:")
        print(f"  Expiration: {setup['expiration']} ({setup['dte']} DTE)")
        print(
            f"  Put Spread: {setup['put_spread']['long_strike']}/{setup['put_spread']['short_strike']}"
        )
        print(
            f"  Call Spread: {setup['call_spread']['short_strike']}/{setup['call_spread']['long_strike']}"
        )
        print(f"  Est. Credit: ${setup['estimated_credit']:.2f}")
        print(f"  Max Profit: ${setup['max_profit']:.2f}")
        print(f"  Max Loss: ${setup['max_loss']:.2f}")
        print(f"  Profit Zone: {setup['profit_zone']['width_pct']:.1f}% wide")

    # Position sizing
    if evaluation["entry_setup"]:
        print("\n=== Position Sizing ===")
        sizing = strategy.calculate_position_size(evaluation["entry_setup"])
        print(f"  Recommended Contracts: {sizing['recommended_contracts']}")
        print(f"  Limiting Factor: {sizing['limiting_factor']}")
        print(f"  Expected Credit: ${sizing['expected_credit']:.2f}")
        print(f"  Max Loss: ${sizing['max_loss']:.2f}")
        print(f"  Margin Required: ${sizing['margin_required']:.2f}")
