"""
Spread Margin Calculator - Track Buying Power for Options Spreads

Calculates margin requirements for various options spread strategies
to prevent over-allocation of capital.

Margin Types:
- Credit Spread: Width of spread - credit received
- Iron Condor: Max of (put spread width, call spread width) - credit
- Debit Spread: Debit paid (no additional margin)
- Naked Options: Much higher margin requirements (broker-specific)

Author: AI Trading System
Date: December 2024
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SpreadType(Enum):
    """Types of options spreads."""

    CREDIT_SPREAD = "credit_spread"  # Bull put or bear call spread
    IRON_CONDOR = "iron_condor"  # Put spread + call spread
    DEBIT_SPREAD = "debit_spread"  # Bull call or bear put spread
    CALENDAR_SPREAD = "calendar_spread"  # Same strike, different expirations
    BUTTERFLY = "butterfly"  # 3 strikes, defined risk
    STRADDLE = "straddle"  # ATM call + ATM put
    STRANGLE = "strangle"  # OTM call + OTM put
    COVERED_CALL = "covered_call"  # Long stock + short call
    CASH_SECURED_PUT = "cash_secured_put"  # Cash + short put


@dataclass
class SpreadPosition:
    """Represents a spread position with margin tracking."""

    symbol: str
    spread_type: SpreadType
    contracts: int

    # Credit/Debit
    premium: float  # Credit received (positive) or debit paid (negative)
    is_credit: bool

    # Spread structure
    short_strike: Optional[float] = None
    long_strike: Optional[float] = None
    spread_width: float = 0.0

    # For iron condors
    put_spread_width: Optional[float] = None
    call_spread_width: Optional[float] = None

    # Calculated values
    margin_required: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0


class SpreadMarginCalculator:
    """
    Calculate margin requirements for options spreads.

    This ensures proper capital allocation and prevents over-leveraging.
    Critical for income-focused trading where we want consistent returns,
    not margin calls.
    """

    def __init__(self, portfolio_value: float = 100000.0):
        """
        Initialize margin calculator.

        Args:
            portfolio_value: Total portfolio value for allocation checks
        """
        self.portfolio_value = portfolio_value
        self.positions: dict[str, SpreadPosition] = {}
        self._total_margin_used = 0.0

        logger.info(f"Spread Margin Calculator initialized: ${portfolio_value:,.0f}")

    def calculate_credit_spread_margin(
        self,
        short_strike: float,
        long_strike: float,
        credit_received: float,
        contracts: int = 1,
    ) -> dict[str, Any]:
        """
        Calculate margin for credit spread (bull put or bear call).

        Credit Spread Margin = Width of spread - credit received

        Example:
        - Sell 450 put, buy 445 put for $1.50 credit
        - Width = $5, Credit = $1.50
        - Margin = ($5 - $1.50) × 100 × contracts = $350 per contract

        Args:
            short_strike: Strike price of short option
            long_strike: Strike price of long option
            credit_received: Credit received per contract
            contracts: Number of contracts

        Returns:
            Dict with margin calculation
        """
        width = abs(short_strike - long_strike)
        margin_per_contract = (width - credit_received) * 100
        total_margin = margin_per_contract * contracts
        max_profit = credit_received * 100 * contracts
        max_loss = total_margin

        # Breakevens
        if short_strike > long_strike:  # Bear call spread
            breakeven = short_strike + credit_received
        else:  # Bull put spread
            breakeven = short_strike - credit_received

        return {
            "spread_type": "credit_spread",
            "margin_required": round(total_margin, 2),
            "margin_per_contract": round(margin_per_contract, 2),
            "max_profit": round(max_profit, 2),
            "max_loss": round(max_loss, 2),
            "risk_reward": f"1:{round(max_profit / max_loss, 2) if max_loss > 0 else 'inf'}",
            "breakeven": round(breakeven, 2),
            "structure": {
                "short_strike": short_strike,
                "long_strike": long_strike,
                "width": width,
                "credit": credit_received,
                "contracts": contracts,
            },
        }

    def calculate_iron_condor_margin(
        self,
        short_put: float,
        long_put: float,
        short_call: float,
        long_call: float,
        total_credit: float,
        contracts: int = 1,
    ) -> dict[str, Any]:
        """
        Calculate margin for iron condor.

        Iron Condor Margin = Max(put spread width, call spread width) - credit
        Note: Only one side can lose, so margin is the LARGER spread minus credit.

        Example:
        - Put spread: 440/445 (5 wide)
        - Call spread: 455/460 (5 wide)
        - Credit: $2.00
        - Margin = ($5 - $2) × 100 = $300 per contract

        Args:
            short_put: Strike of short put
            long_put: Strike of long put
            short_call: Strike of short call
            long_call: Strike of long call
            total_credit: Total credit received
            contracts: Number of contracts

        Returns:
            Dict with margin calculation
        """
        put_width = abs(short_put - long_put)
        call_width = abs(long_call - short_call)
        wider_spread = max(put_width, call_width)

        margin_per_contract = (wider_spread - total_credit) * 100
        total_margin = margin_per_contract * contracts
        max_profit = total_credit * 100 * contracts
        max_loss = total_margin

        # Breakevens
        lower_breakeven = short_put - total_credit
        upper_breakeven = short_call + total_credit

        return {
            "spread_type": "iron_condor",
            "margin_required": round(total_margin, 2),
            "margin_per_contract": round(margin_per_contract, 2),
            "max_profit": round(max_profit, 2),
            "max_loss": round(max_loss, 2),
            "risk_reward": f"1:{round(max_profit / max_loss, 2) if max_loss > 0 else 'inf'}",
            "breakevens": {
                "lower": round(lower_breakeven, 2),
                "upper": round(upper_breakeven, 2),
            },
            "profit_zone_width": round(upper_breakeven - lower_breakeven, 2),
            "structure": {
                "put_spread": {"short": short_put, "long": long_put, "width": put_width},
                "call_spread": {"short": short_call, "long": long_call, "width": call_width},
                "wider_spread": wider_spread,
                "credit": total_credit,
                "contracts": contracts,
            },
        }

    def calculate_debit_spread_margin(
        self,
        long_strike: float,
        short_strike: float,
        debit_paid: float,
        contracts: int = 1,
    ) -> dict[str, Any]:
        """
        Calculate margin for debit spread (bull call or bear put).

        Debit Spread Margin = Debit paid (no additional margin needed)

        Example:
        - Buy 450 call, sell 455 call for $2.00 debit
        - Margin = $2.00 × 100 × contracts = $200 per contract

        Args:
            long_strike: Strike of long option
            short_strike: Strike of short option
            debit_paid: Debit paid per contract (positive number)
            contracts: Number of contracts

        Returns:
            Dict with margin calculation
        """
        width = abs(long_strike - short_strike)
        total_debit = debit_paid * 100 * contracts
        max_profit = (width - debit_paid) * 100 * contracts
        max_loss = total_debit

        # Breakeven
        if long_strike < short_strike:  # Bull call spread
            breakeven = long_strike + debit_paid
        else:  # Bear put spread
            breakeven = long_strike - debit_paid

        return {
            "spread_type": "debit_spread",
            "margin_required": round(total_debit, 2),  # Debit is the margin
            "margin_per_contract": round(debit_paid * 100, 2),
            "max_profit": round(max_profit, 2),
            "max_loss": round(max_loss, 2),
            "risk_reward": f"{round(max_profit / max_loss, 2) if max_loss > 0 else 'inf'}:1",
            "breakeven": round(breakeven, 2),
            "structure": {
                "long_strike": long_strike,
                "short_strike": short_strike,
                "width": width,
                "debit": debit_paid,
                "contracts": contracts,
            },
        }

    def calculate_cash_secured_put_margin(
        self,
        strike: float,
        premium_received: float,
        contracts: int = 1,
    ) -> dict[str, Any]:
        """
        Calculate margin for cash-secured put.

        CSP Margin = Strike × 100 × contracts (full cash to buy shares)

        Example:
        - Sell 450 put for $3.00 premium
        - Margin = $450 × 100 = $45,000 per contract

        Args:
            strike: Strike price of the put
            premium_received: Premium received per contract
            contracts: Number of contracts

        Returns:
            Dict with margin calculation
        """
        margin_per_contract = strike * 100
        total_margin = margin_per_contract * contracts
        max_profit = premium_received * 100 * contracts
        cost_basis = strike - premium_received

        return {
            "spread_type": "cash_secured_put",
            "margin_required": round(total_margin, 2),
            "margin_per_contract": round(margin_per_contract, 2),
            "max_profit": round(max_profit, 2),
            "max_loss": round((cost_basis * 100 * contracts), 2),  # If stock goes to 0
            "breakeven": round(cost_basis, 2),
            "cost_basis_if_assigned": round(cost_basis, 2),
            "structure": {
                "strike": strike,
                "premium": premium_received,
                "contracts": contracts,
            },
            "note": "Full cash required to potentially buy shares at strike",
        }

    def add_position(self, position: SpreadPosition) -> None:
        """Add a position and update total margin."""
        self.positions[position.symbol] = position
        self._recalculate_total_margin()
        logger.info(f"Added position {position.symbol}: margin=${position.margin_required:,.2f}")

    def remove_position(self, symbol: str) -> None:
        """Remove a position and update total margin."""
        if symbol in self.positions:
            del self.positions[symbol]
            self._recalculate_total_margin()
            logger.info(f"Removed position {symbol}")

    def _recalculate_total_margin(self) -> None:
        """Recalculate total margin used."""
        self._total_margin_used = sum(pos.margin_required for pos in self.positions.values())

    def get_buying_power_summary(self) -> dict[str, Any]:
        """
        Get summary of buying power and margin usage.

        Returns:
            Dict with buying power analysis
        """
        available_margin = self.portfolio_value - self._total_margin_used
        margin_utilization = (
            (self._total_margin_used / self.portfolio_value) * 100
            if self.portfolio_value > 0
            else 0
        )

        # Categorize positions by type
        by_type: dict[str, list] = {}
        for pos in self.positions.values():
            type_name = pos.spread_type.value
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(
                {
                    "symbol": pos.symbol,
                    "margin": pos.margin_required,
                    "contracts": pos.contracts,
                }
            )

        return {
            "portfolio_value": round(self.portfolio_value, 2),
            "total_margin_used": round(self._total_margin_used, 2),
            "available_margin": round(available_margin, 2),
            "margin_utilization_pct": round(margin_utilization, 2),
            "total_positions": len(self.positions),
            "positions_by_type": by_type,
            "can_open_new_position": available_margin > 0,
            "recommended_max_margin": round(self.portfolio_value * 0.50, 2),  # 50% max
            "warnings": self._generate_warnings(margin_utilization),
            "timestamp": datetime.now().isoformat(),
        }

    def _generate_warnings(self, utilization: float) -> list[str]:
        """Generate warnings based on margin utilization."""
        warnings = []

        if utilization > 80:
            warnings.append("CRITICAL: Margin utilization over 80%! High risk of margin call.")
        elif utilization > 60:
            warnings.append("WARNING: Margin utilization over 60%. Consider reducing exposure.")
        elif utilization > 50:
            warnings.append("CAUTION: Margin utilization over 50%. Monitor positions closely.")

        return warnings

    def check_new_position_margin(
        self,
        required_margin: float,
        max_utilization_pct: float = 50.0,
    ) -> dict[str, Any]:
        """
        Check if a new position can be opened within margin limits.

        Args:
            required_margin: Margin required for new position
            max_utilization_pct: Maximum margin utilization allowed

        Returns:
            Dict with approval status and details
        """
        current_utilization = (
            (self._total_margin_used / self.portfolio_value) * 100
            if self.portfolio_value > 0
            else 0
        )

        new_total = self._total_margin_used + required_margin
        new_utilization = (
            (new_total / self.portfolio_value) * 100 if self.portfolio_value > 0 else 0
        )

        approved = new_utilization <= max_utilization_pct

        return {
            "approved": approved,
            "required_margin": round(required_margin, 2),
            "current_margin_used": round(self._total_margin_used, 2),
            "new_total_margin": round(new_total, 2),
            "current_utilization_pct": round(current_utilization, 2),
            "new_utilization_pct": round(new_utilization, 2),
            "max_utilization_pct": max_utilization_pct,
            "available_margin": round(self.portfolio_value - self._total_margin_used, 2),
            "reason": (
                "Position approved within margin limits"
                if approved
                else f"Position would exceed {max_utilization_pct}% margin limit"
            ),
        }


def get_spread_margin_calculator(portfolio_value: float = 100000.0) -> SpreadMarginCalculator:
    """Get SpreadMarginCalculator instance."""
    return SpreadMarginCalculator(portfolio_value=portfolio_value)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    calc = SpreadMarginCalculator(portfolio_value=100000)

    # Example: Credit spread margin
    print("\n=== Credit Spread Margin ===")
    credit_margin = calc.calculate_credit_spread_margin(
        short_strike=450,
        long_strike=445,
        credit_received=1.50,
        contracts=2,
    )
    print(f"Margin Required: ${credit_margin['margin_required']:,.2f}")
    print(f"Max Profit: ${credit_margin['max_profit']:,.2f}")
    print(f"Max Loss: ${credit_margin['max_loss']:,.2f}")
    print(f"Risk/Reward: {credit_margin['risk_reward']}")

    # Example: Iron condor margin
    print("\n=== Iron Condor Margin ===")
    ic_margin = calc.calculate_iron_condor_margin(
        short_put=440,
        long_put=435,
        short_call=460,
        long_call=465,
        total_credit=2.00,
        contracts=3,
    )
    print(f"Margin Required: ${ic_margin['margin_required']:,.2f}")
    print(f"Max Profit: ${ic_margin['max_profit']:,.2f}")
    print(f"Max Loss: ${ic_margin['max_loss']:,.2f}")
    print(f"Profit Zone: ${ic_margin['breakevens']['lower']} - ${ic_margin['breakevens']['upper']}")

    # Example: Cash-secured put margin
    print("\n=== Cash-Secured Put Margin ===")
    csp_margin = calc.calculate_cash_secured_put_margin(
        strike=450,
        premium_received=3.00,
        contracts=1,
    )
    print(f"Margin Required: ${csp_margin['margin_required']:,.2f}")
    print(f"Max Profit: ${csp_margin['max_profit']:,.2f}")
    print(f"Cost Basis if Assigned: ${csp_margin['cost_basis_if_assigned']:.2f}")

    # Check buying power
    print("\n=== Buying Power Summary ===")
    summary = calc.get_buying_power_summary()
    print(f"Portfolio: ${summary['portfolio_value']:,.2f}")
    print(f"Margin Used: ${summary['total_margin_used']:,.2f}")
    print(f"Available: ${summary['available_margin']:,.2f}")
    print(f"Utilization: {summary['margin_utilization_pct']:.1f}%")
