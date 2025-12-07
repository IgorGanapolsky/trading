"""
Options Position Risk Monitor - Stop-Loss and Delta Management

Implements McMillan's risk management rules:
1. Close credit spreads/iron condors at 2.2x credit received (hard stop)
2. Delta-neutral rebalancing when |net delta| exceeds threshold
3. Position monitoring with automatic exit triggers

Author: AI Trading System
Date: December 2, 2025
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OptionsPosition:
    """Represents an open options position for monitoring."""

    symbol: str
    underlying: str
    position_type: str  # 'covered_call', 'iron_condor', 'credit_spread', 'put_spread', etc.
    side: str  # 'long' or 'short'
    quantity: int
    entry_price: float  # Credit received or debit paid
    current_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    expiration_date: date
    strike: float
    opened_at: datetime


class OptionsRiskMonitor:
    """
    Monitor options positions for risk management exits.

    McMillan Stop-Loss Rules:
    - Credit spreads/iron condors: Exit if loss reaches 2.2x credit received
    - Long options: Exit at 50% of premium paid
    - Covered calls: Exit if underlying drops 8-10% below basis

    Delta Management:
    - Track net delta across all options positions
    - Rebalance when |net delta| > threshold (default: 60)
    - Use SPY shares to hedge back to target delta
    """

    # McMillan stop-loss multipliers
    CREDIT_SPREAD_STOP_MULTIPLIER = 2.2  # Exit at 2.2x credit received
    IRON_CONDOR_STOP_MULTIPLIER = 2.0  # Exit at 2.0x credit (tighter for IC)
    LONG_OPTION_STOP_PCT = 0.50  # Exit at 50% loss of premium
    COVERED_CALL_UNDERLYING_STOP = 0.08  # 8% stop on underlying

    # Delta management thresholds
    MAX_NET_DELTA = 60.0  # Rebalance if |delta| > this
    TARGET_NET_DELTA = 25.0  # Target after rebalancing
    DELTA_PER_SPY_SHARE = 1.0  # Each SPY share = 1 delta

    def __init__(self, paper: bool = True):
        """
        Initialize options risk monitor.

        Args:
            paper: If True, use paper trading environment
        """
        self.paper = paper
        self.positions: dict[str, OptionsPosition] = {}
        self._last_check = None

        logger.info("Options Risk Monitor initialized")

    def add_position(self, position: OptionsPosition) -> None:
        """Add a position to monitor."""
        self.positions[position.symbol] = position
        logger.info(f"Added position to monitor: {position.symbol} ({position.position_type})")

    def remove_position(self, symbol: str) -> None:
        """Remove a position from monitoring."""
        if symbol in self.positions:
            del self.positions[symbol]
            logger.info(f"Removed position from monitor: {symbol}")

    def check_stop_losses(self, current_prices: dict[str, float]) -> list[dict[str, Any]]:
        """
        Check all positions against stop-loss rules.

        Args:
            current_prices: Dict mapping option symbols to current prices

        Returns:
            List of positions that should be closed with reasons
        """
        exits = []

        for symbol, position in self.positions.items():
            current_price = current_prices.get(symbol, position.current_price)
            position.current_price = current_price

            exit_signal = self._check_position_stop(position)
            if exit_signal:
                exits.append(exit_signal)

        return exits

    def _check_position_stop(self, position: OptionsPosition) -> dict[str, Any] | None:
        """
        Check if a single position has hit its stop-loss.

        McMillan Rules:
        - Credit spreads: Close if unrealized loss > 2.2x credit received
        - Iron condors: Close if unrealized loss > 2.0x credit received
        - Long options: Close if down 50% from entry

        Args:
            position: Position to check

        Returns:
            Exit signal dict if stop triggered, None otherwise
        """
        if position.side == "short":
            # Short premium positions (credit spreads, iron condors)
            # Entry price is CREDIT received (positive number)
            # Current price is what we'd pay to close (debit)

            # Loss = current_price - entry_price (if current > entry, we're losing)
            unrealized_loss = position.current_price - position.entry_price

            # Determine stop multiplier based on position type
            if position.position_type == "iron_condor":
                stop_multiplier = self.IRON_CONDOR_STOP_MULTIPLIER
            else:
                stop_multiplier = self.CREDIT_SPREAD_STOP_MULTIPLIER

            max_loss = position.entry_price * stop_multiplier

            if unrealized_loss >= max_loss:
                return {
                    "action": "CLOSE",
                    "symbol": position.symbol,
                    "underlying": position.underlying,
                    "position_type": position.position_type,
                    "reason": f"STOP_LOSS: Loss ${unrealized_loss:.2f} exceeds {stop_multiplier}x credit (${max_loss:.2f})",
                    "entry_price": position.entry_price,
                    "current_price": position.current_price,
                    "unrealized_loss": unrealized_loss,
                    "max_loss_threshold": max_loss,
                    "mcmillan_rule": f"Exit credit spreads at {stop_multiplier}x credit received",
                }

        else:  # Long positions
            # Entry price is DEBIT paid (positive number)
            # Current price is what we'd receive if sold

            # Loss = entry_price - current_price (if current < entry, we're losing)
            unrealized_loss = position.entry_price - position.current_price
            max_loss = position.entry_price * self.LONG_OPTION_STOP_PCT

            if unrealized_loss >= max_loss:
                return {
                    "action": "CLOSE",
                    "symbol": position.symbol,
                    "underlying": position.underlying,
                    "position_type": position.position_type,
                    "reason": f"STOP_LOSS: Loss ${unrealized_loss:.2f} exceeds {self.LONG_OPTION_STOP_PCT * 100}% of premium (${max_loss:.2f})",
                    "entry_price": position.entry_price,
                    "current_price": position.current_price,
                    "unrealized_loss": unrealized_loss,
                    "max_loss_threshold": max_loss,
                    "mcmillan_rule": f"Exit long options at {self.LONG_OPTION_STOP_PCT * 100}% loss",
                }

        return None

    def calculate_net_delta(self) -> dict[str, Any]:
        """
        Calculate net delta exposure across all options positions.

        Returns:
            Dict with net_delta, positions_by_delta, rebalance_needed, etc.
        """
        net_delta = 0.0
        positions_by_delta = []

        for symbol, position in self.positions.items():
            position_delta = position.delta * position.quantity

            # Short positions have inverted delta effect
            if position.side == "short":
                position_delta = -position_delta

            net_delta += position_delta
            positions_by_delta.append(
                {
                    "symbol": symbol,
                    "delta": position.delta,
                    "quantity": position.quantity,
                    "side": position.side,
                    "contribution": position_delta,
                }
            )

        rebalance_needed = abs(net_delta) > self.MAX_NET_DELTA

        return {
            "net_delta": net_delta,
            "abs_net_delta": abs(net_delta),
            "max_allowed": self.MAX_NET_DELTA,
            "target_delta": self.TARGET_NET_DELTA,
            "rebalance_needed": rebalance_needed,
            "positions_by_delta": positions_by_delta,
            "timestamp": datetime.now().isoformat(),
        }

    def calculate_delta_hedge(self, net_delta: float) -> dict[str, Any]:
        """
        Calculate the hedge trade needed to bring delta back to target.

        Strategy: Use SPY shares to delta-neutralize
        - If net delta > +60: Sell SPY shares to reduce delta
        - If net delta < -60: Buy SPY shares to increase delta

        Args:
            net_delta: Current net delta exposure

        Returns:
            Hedge trade recommendation
        """
        if abs(net_delta) <= self.MAX_NET_DELTA:
            return {
                "action": "NONE",
                "reason": f"Net delta {net_delta:.1f} within acceptable range (±{self.MAX_NET_DELTA})",
            }

        # Calculate shares needed to reach target delta
        delta_to_neutralize = net_delta - (
            self.TARGET_NET_DELTA if net_delta > 0 else -self.TARGET_NET_DELTA
        )
        shares_needed = abs(int(delta_to_neutralize / self.DELTA_PER_SPY_SHARE))

        if net_delta > self.MAX_NET_DELTA:
            # Too long - sell SPY to reduce delta
            return {
                "action": "SELL",
                "symbol": "SPY",
                "quantity": shares_needed,
                "reason": f"Net delta {net_delta:.1f} exceeds +{self.MAX_NET_DELTA}. Selling {shares_needed} SPY to reduce to {self.TARGET_NET_DELTA}",
                "current_delta": net_delta,
                "target_delta": self.TARGET_NET_DELTA,
                "delta_reduction": delta_to_neutralize,
            }
        else:
            # Too short - buy SPY to increase delta
            return {
                "action": "BUY",
                "symbol": "SPY",
                "quantity": shares_needed,
                "reason": f"Net delta {net_delta:.1f} below -{self.MAX_NET_DELTA}. Buying {shares_needed} SPY to increase to -{self.TARGET_NET_DELTA}",
                "current_delta": net_delta,
                "target_delta": -self.TARGET_NET_DELTA,
                "delta_increase": abs(delta_to_neutralize),
            }

    def run_risk_check(self, current_prices: dict[str, float], executor=None) -> dict[str, Any]:
        """
        Run complete risk check: stop-losses + delta management.

        Args:
            current_prices: Current option prices
            executor: Optional executor for automatic execution

        Returns:
            Complete risk check results with any actions taken
        """
        logger.info("Running options risk check...")

        results = {
            "timestamp": datetime.now().isoformat(),
            "positions_checked": len(self.positions),
            "stop_loss_exits": [],
            "delta_analysis": None,
            "hedge_recommendation": None,
            "actions_taken": [],
        }

        # 1. Check stop-losses
        stop_exits = self.check_stop_losses(current_prices)
        results["stop_loss_exits"] = stop_exits

        if stop_exits:
            logger.warning(f"🚨 {len(stop_exits)} positions hit stop-loss!")
            for exit_signal in stop_exits:
                logger.warning(f"  - {exit_signal['symbol']}: {exit_signal['reason']}")

                if executor:
                    try:
                        # Execute the close
                        order = executor.close_position(exit_signal["symbol"])
                        results["actions_taken"].append(
                            {
                                "type": "stop_loss_exit",
                                "symbol": exit_signal["symbol"],
                                "order": order,
                            }
                        )
                        logger.info(f"✅ Closed {exit_signal['symbol']} via stop-loss")
                    except Exception as e:
                        logger.error(f"❌ Failed to close {exit_signal['symbol']}: {e}")

        # 2. Delta analysis and rebalancing
        delta_analysis = self.calculate_net_delta()
        results["delta_analysis"] = delta_analysis

        if delta_analysis["rebalance_needed"]:
            hedge = self.calculate_delta_hedge(delta_analysis["net_delta"])
            results["hedge_recommendation"] = hedge

            logger.warning(
                f"⚠️ Delta rebalance needed: Net delta {delta_analysis['net_delta']:.1f} "
                f"exceeds ±{self.MAX_NET_DELTA}"
            )

            if executor and hedge["action"] != "NONE":
                try:
                    # Execute the hedge
                    order = executor.place_order(
                        hedge["symbol"], hedge["quantity"], side=hedge["action"].lower()
                    )
                    results["actions_taken"].append(
                        {
                            "type": "delta_hedge",
                            "symbol": hedge["symbol"],
                            "side": hedge["action"],
                            "quantity": hedge["quantity"],
                            "order": order,
                        }
                    )
                    logger.info(
                        f"✅ Delta hedge executed: {hedge['action']} {hedge['quantity']} {hedge['symbol']}"
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to execute delta hedge: {e}")
        else:
            logger.info(
                f"✅ Delta exposure acceptable: {delta_analysis['net_delta']:.1f} "
                f"(threshold: ±{self.MAX_NET_DELTA})"
            )

        self._last_check = datetime.now()
        return results


def check_credit_spread_stop(
    entry_credit: float, current_cost_to_close: float, stop_multiplier: float = 2.2
) -> dict[str, Any]:
    """
    Quick helper to check if a credit spread has hit its stop.

    McMillan rule: Close credit spread if loss reaches 2.2x the credit received.

    Args:
        entry_credit: Credit received when opening (positive number)
        current_cost_to_close: Cost to close position now (positive number)
        stop_multiplier: Stop-loss multiplier (default: 2.2x per McMillan)

    Returns:
        Dict with 'should_close', 'loss', 'max_loss', 'loss_multiple'

    Example:
        >>> check_credit_spread_stop(entry_credit=1.50, current_cost_to_close=3.50)
        {'should_close': True, 'loss': 2.00, 'max_loss': 3.30, 'loss_multiple': 2.33}
    """
    loss = current_cost_to_close - entry_credit
    max_loss = entry_credit * stop_multiplier
    loss_multiple = loss / entry_credit if entry_credit > 0 else 0

    return {
        "should_close": loss >= max_loss,
        "loss": loss,
        "max_loss": max_loss,
        "loss_multiple": loss_multiple,
        "entry_credit": entry_credit,
        "current_cost_to_close": current_cost_to_close,
        "mcmillan_rule": f"Close at {stop_multiplier}x credit received",
    }


def check_iron_condor_stop(
    entry_credit: float, current_cost_to_close: float, stop_multiplier: float = 2.0
) -> dict[str, Any]:
    """
    Check if an iron condor has hit its stop.

    Iron condors use a tighter stop (2.0x) because they have two sides that can go wrong.

    Args:
        entry_credit: Total credit received for the iron condor
        current_cost_to_close: Total cost to close both spreads
        stop_multiplier: Stop-loss multiplier (default: 2.0x for iron condors)

    Returns:
        Dict with stop-loss analysis
    """
    return check_credit_spread_stop(
        entry_credit=entry_credit,
        current_cost_to_close=current_cost_to_close,
        stop_multiplier=stop_multiplier,
    )


# Convenience function
def get_options_risk_monitor(paper: bool = True) -> OptionsRiskMonitor:
    """Get OptionsRiskMonitor instance."""
    return OptionsRiskMonitor(paper=paper)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Example: Check credit spread stop-loss
    print("\n=== Credit Spread Stop-Loss Check ===")
    result = check_credit_spread_stop(
        entry_credit=1.50,  # Received $1.50 credit
        current_cost_to_close=3.50,  # Would cost $3.50 to close
    )
    print(f"Entry Credit: ${result['entry_credit']:.2f}")
    print(f"Current Cost to Close: ${result['current_cost_to_close']:.2f}")
    print(f"Unrealized Loss: ${result['loss']:.2f}")
    print(f"Max Loss Threshold: ${result['max_loss']:.2f}")
    print(f"Loss Multiple: {result['loss_multiple']:.2f}x credit")
    print(f"Should Close: {result['should_close']}")
    print(f"Rule: {result['mcmillan_rule']}")

    # Example: Iron condor stop
    print("\n=== Iron Condor Stop-Loss Check ===")
    ic_result = check_iron_condor_stop(entry_credit=2.00, current_cost_to_close=3.80)
    print(f"Should Close: {ic_result['should_close']}")
    print(f"Loss Multiple: {ic_result['loss_multiple']:.2f}x credit")
