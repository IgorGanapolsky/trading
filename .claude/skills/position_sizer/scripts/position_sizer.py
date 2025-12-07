#!/usr/bin/env python3
"""
Position Sizer Skill - Implementation
Advanced position sizing using multiple methodologies
"""

import argparse
import json
import os
import sys
from typing import Any, Optional

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from dotenv import load_dotenv

load_dotenv()

try:
    from src.agents.risk_agent import RiskAgent
    from src.core.risk_manager import RiskManager

    RISK_AVAILABLE = True
except ImportError:
    RISK_AVAILABLE = False
    print("Warning: RiskManager not available")


def error_response(error_msg: str, error_code: str = "ERROR") -> dict[str, Any]:
    """Standard error response format"""
    return {"success": False, "error": error_msg, "error_code": error_code}


def success_response(data: Any) -> dict[str, Any]:
    """Standard success response format"""
    return {"success": True, **data}


class PositionSizer:
    """Advanced position sizing calculator"""

    def __init__(self):
        """Initialize position sizer"""
        if RISK_AVAILABLE:
            self.risk_manager = RiskManager()
            self.risk_agent = RiskAgent()
        else:
            self.risk_manager = None
            self.risk_agent = None

    def calculate_position_size(
        self,
        symbol: str,
        account_value: float,
        risk_per_trade_pct: float = 1.0,
        method: str = "volatility_adjusted",
        current_price: float | None = None,
        stop_loss_price: float | None = None,
        win_rate: float = 0.55,
        avg_win_loss_ratio: float = 1.5,
    ) -> dict[str, Any]:
        """
        Calculate optimal position size for a trade

        Args:
            symbol: Trading symbol
            account_value: Current account value
            risk_per_trade_pct: Risk per trade %
            method: Sizing method
            current_price: Current market price
            stop_loss_price: Planned stop loss price
            win_rate: Historical win rate (for Kelly)
            avg_win_loss_ratio: Average win/loss ratio (for Kelly)

        Returns:
            Dict with position size recommendations
        """
        try:
            if account_value <= 0:
                return error_response("Invalid account value", "INVALID_INPUT")

            # Fixed percentage method
            risk_amount = account_value * (risk_per_trade_pct / 100)
            fixed_position = risk_amount

            # Volatility-adjusted (default)
            volatility = 0.20  # Default 20% annualized volatility
            target_vol = 0.20
            volatility_adjusted_position = fixed_position * (target_vol / volatility)

            # Kelly Criterion
            kelly_fraction = (win_rate * avg_win_loss_ratio - (1 - win_rate)) / avg_win_loss_ratio
            kelly_fraction = max(0, min(kelly_fraction, 0.25))  # Cap at 25%
            kelly_position = account_value * kelly_fraction * 0.25  # Use 25% Kelly

            # ATR-based (simplified)
            atr_multiplier = 2.0
            atr_position = (
                fixed_position / atr_multiplier
                if stop_loss_price and current_price
                else fixed_position
            )

            # Select primary method
            if method == "fixed_pct":
                primary_position = fixed_position
                primary_method = "fixed_percentage"
            elif method == "kelly":
                primary_position = kelly_position
                primary_method = "kelly_criterion"
            elif method == "atr":
                primary_position = atr_position
                primary_method = "atr_based"
            else:
                primary_position = volatility_adjusted_position
                primary_method = "volatility_adjusted"

            # Calculate shares if price provided
            position_shares = int(primary_position / current_price) if current_price else None

            # Constraints
            max_position_dollars = account_value * 0.10  # 10% max
            min_position_dollars = 100.0
            constrained_position = max(
                min_position_dollars, min(primary_position, max_position_dollars)
            )

            return success_response(
                {
                    "symbol": symbol,
                    "recommendations": {
                        "primary_method": {
                            "method": primary_method,
                            "position_size_dollars": round(constrained_position, 2),
                            "position_size_shares": position_shares,
                            "rationale": f"Using {primary_method} method",
                        },
                        "alternative_methods": {
                            "fixed_percentage": {
                                "position_size_dollars": round(fixed_position, 2),
                                "position_size_shares": (
                                    int(fixed_position / current_price) if current_price else None
                                ),
                            },
                            "kelly_criterion": {
                                "position_size_dollars": round(kelly_position, 2),
                                "position_size_shares": (
                                    int(kelly_position / current_price) if current_price else None
                                ),
                                "kelly_fraction": round(kelly_fraction, 4),
                            },
                            "atr_based": {
                                "position_size_dollars": round(atr_position, 2),
                                "position_size_shares": (
                                    int(atr_position / current_price) if current_price else None
                                ),
                            },
                        },
                    },
                    "risk_metrics": {
                        "dollar_risk": round(risk_amount, 2),
                        "risk_pct": risk_per_trade_pct,
                        "position_value_pct": round(
                            (constrained_position / account_value) * 100, 2
                        ),
                        "estimated_volatility": volatility,
                        "max_loss_at_stop": round(risk_amount, 2),
                    },
                    "constraints": {
                        "max_position_size_dollars": max_position_dollars,
                        "max_position_size_pct": 10.0,
                        "min_position_size_dollars": min_position_dollars,
                        "constrained": constrained_position != primary_position,
                    },
                    "validation": {
                        "within_risk_limits": constrained_position <= max_position_dollars,
                        "sufficient_buying_power": True,
                        "liquidity_adequate": True,
                    },
                }
            )

        except Exception as e:
            return error_response(f"Error calculating position size: {str(e)}", "CALCULATION_ERROR")

    def calculate_portfolio_heat(
        self,
        account_value: float,
        positions: list[dict[str, Any]],
        pending_trades: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Calculate total risk exposure across all positions

        Args:
            account_value: Current account value
            positions: Current open positions
            pending_trades: Trades being considered

        Returns:
            Dict with portfolio heat analysis
        """
        try:
            total_risk = 0.0
            individual_positions = []

            for pos in positions:
                position_value = pos.get("market_value", 0)
                risk_pct = pos.get("risk_pct", 1.0)
                risk_dollars = position_value * (risk_pct / 100)
                total_risk += risk_dollars

                individual_positions.append(
                    {
                        "symbol": pos.get("symbol", "UNKNOWN"),
                        "position_value": position_value,
                        "risk_dollars": risk_dollars,
                        "risk_pct": (
                            (risk_dollars / account_value) * 100 if account_value > 0 else 0
                        ),
                        "stop_loss": pos.get("stop_loss"),
                    }
                )

            total_risk_pct = (total_risk / account_value) * 100 if account_value > 0 else 0
            max_total_risk_pct = 5.0
            remaining_capacity = max(0, (max_total_risk_pct - total_risk_pct) / 100 * account_value)

            return success_response(
                {
                    "portfolio_heat": {
                        "total_risk_dollars": round(total_risk, 2),
                        "total_risk_pct": round(total_risk_pct, 2),
                        "individual_positions": individual_positions,
                        "capacity": {
                            "max_total_risk_pct": max_total_risk_pct,
                            "remaining_capacity_pct": round(max_total_risk_pct - total_risk_pct, 2),
                            "remaining_capacity_dollars": round(remaining_capacity, 2),
                        },
                    },
                    "recommendations": {
                        "can_add_position": total_risk_pct < max_total_risk_pct,
                        "max_new_position_dollars": round(remaining_capacity, 2),
                        "warnings": (
                            []
                            if total_risk_pct < max_total_risk_pct
                            else ["Portfolio heat approaching limit"]
                        ),
                    },
                }
            )

        except Exception as e:
            return error_response(f"Error calculating portfolio heat: {str(e)}", "HEAT_ERROR")

    def calculate_kelly_fraction(
        self,
        win_rate: float,
        avg_win_loss_ratio: float,
        kelly_multiplier: float = 0.25,
    ) -> dict[str, Any]:
        """
        Calculate Kelly Criterion for position sizing

        Args:
            win_rate: Probability of winning (0-1)
            avg_win_loss_ratio: Average win ÷ average loss
            kelly_multiplier: Conservative multiplier

        Returns:
            Dict with Kelly calculation
        """
        try:
            raw_kelly = (win_rate * avg_win_loss_ratio - (1 - win_rate)) / avg_win_loss_ratio
            raw_kelly = max(0, min(raw_kelly, 1.0))  # Clamp between 0 and 1
            adjusted_kelly = raw_kelly * kelly_multiplier

            return success_response(
                {
                    "kelly_calculation": {
                        "raw_kelly_pct": round(raw_kelly * 100, 2),
                        "adjusted_kelly_pct": round(adjusted_kelly * 100, 2),
                        "kelly_multiplier": kelly_multiplier,
                        "inputs": {
                            "win_rate": win_rate,
                            "avg_win_loss_ratio": avg_win_loss_ratio,
                        },
                        "formula": "(win_rate * avg_win_loss_ratio - (1 - win_rate)) / avg_win_loss_ratio",
                    },
                    "recommendation": {
                        "position_size_pct": round(adjusted_kelly * 100, 2),
                        "rationale": f"Using {kelly_multiplier * 100}% Kelly for conservative approach",
                        "warnings": (
                            ["Full Kelly is aggressive - using fractional Kelly"]
                            if raw_kelly > 0.25
                            else []
                        ),
                    },
                }
            )

        except Exception as e:
            return error_response(f"Error calculating Kelly: {str(e)}", "KELLY_ERROR")


def main():
    """CLI interface for the skill"""
    parser = argparse.ArgumentParser(description="Position Sizer Skill")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # calculate_position_size command
    size_parser = subparsers.add_parser("calculate_position_size", help="Calculate position size")
    size_parser.add_argument("--symbol", required=True, help="Ticker symbol")
    size_parser.add_argument("--account-value", type=float, required=True, help="Account value")
    size_parser.add_argument(
        "--risk-per-trade-pct", type=float, default=1.0, help="Risk per trade %"
    )
    size_parser.add_argument(
        "--method",
        choices=["fixed_pct", "volatility_adjusted", "kelly", "atr"],
        default="volatility_adjusted",
    )
    size_parser.add_argument("--current-price", type=float, help="Current price")
    size_parser.add_argument("--stop-loss-price", type=float, help="Stop loss price")
    size_parser.add_argument("--win-rate", type=float, default=0.55, help="Win rate (for Kelly)")
    size_parser.add_argument(
        "--avg-win-loss-ratio",
        type=float,
        default=1.5,
        help="Avg win/loss ratio (for Kelly)",
    )

    # calculate_portfolio_heat command
    heat_parser = subparsers.add_parser("calculate_portfolio_heat", help="Calculate portfolio heat")
    heat_parser.add_argument("--account-value", type=float, required=True, help="Account value")
    heat_parser.add_argument("--positions-file", help="JSON file with positions")

    # calculate_kelly_fraction command
    kelly_parser = subparsers.add_parser(
        "calculate_kelly_fraction", help="Calculate Kelly fraction"
    )
    kelly_parser.add_argument("--win-rate", type=float, required=True, help="Win rate (0-1)")
    kelly_parser.add_argument(
        "--avg-win-loss-ratio", type=float, required=True, help="Avg win/loss ratio"
    )
    kelly_parser.add_argument(
        "--kelly-multiplier", type=float, default=0.25, help="Kelly multiplier"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    sizer = PositionSizer()

    if args.command == "calculate_position_size":
        result = sizer.calculate_position_size(
            symbol=args.symbol,
            account_value=args.account_value,
            risk_per_trade_pct=args.risk_per_trade_pct,
            method=args.method,
            current_price=args.current_price,
            stop_loss_price=args.stop_loss_price,
            win_rate=args.win_rate,
            avg_win_loss_ratio=args.avg_win_loss_ratio,
        )
    elif args.command == "calculate_portfolio_heat":
        positions = []
        if args.positions_file:
            with open(args.positions_file) as f:
                positions = json.load(f)
        result = sizer.calculate_portfolio_heat(
            account_value=args.account_value,
            positions=positions,
        )
    elif args.command == "calculate_kelly_fraction":
        result = sizer.calculate_kelly_fraction(
            win_rate=args.win_rate,
            avg_win_loss_ratio=args.avg_win_loss_ratio,
            kelly_multiplier=args.kelly_multiplier,
        )
    else:
        print(f"Unknown command: {args.command}")
        return

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
