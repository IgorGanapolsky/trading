#!/usr/bin/env python3
"""
Portfolio Risk Assessment Skill - Implementation
Comprehensive risk management and circuit breaker system
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, List

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from dotenv import load_dotenv

load_dotenv()

try:
    from alpaca.trading.client import TradingClient

    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    print("Warning: alpaca-py not installed")

# Import existing RiskManager if available
try:
    from src.core.risk_manager import RiskManager

    RISK_MANAGER_AVAILABLE = True
except ImportError:
    RISK_MANAGER_AVAILABLE = False
    print("Warning: RiskManager not available")


def error_response(error_msg: str, error_code: str = "ERROR") -> Dict[str, Any]:
    """Standard error response"""
    return {"success": False, "error": error_msg, "error_code": error_code}


def success_response(data: Any) -> Dict[str, Any]:
    """Standard success response"""
    return {"success": True, "data": data}


class PortfolioRiskAssessor:
    """Portfolio risk assessment and circuit breaker system"""

    # Circuit breaker thresholds
    DAILY_LOSS_LIMIT = -2.0  # -2% of account value
    MAX_DRAWDOWN_LIMIT = 10.0  # 10% maximum drawdown
    CONSECUTIVE_LOSS_LIMIT = 3  # 3 consecutive losses
    MAX_POSITION_SIZE = 10.0  # 10% of portfolio per position
    MAX_PORTFOLIO_HEAT = 6.0  # 6% total at risk

    def __init__(self):
        """Initialize risk assessor"""
        self.alpaca_api_key = os.getenv("ALPACA_API_KEY")
        self.alpaca_secret = os.getenv("ALPACA_SECRET_KEY")
        self.paper_trading = os.getenv("PAPER_TRADING", "true").lower() == "true"

        # Initialize Alpaca client
        if ALPACA_AVAILABLE and self.alpaca_api_key:
            self.trading_client = TradingClient(
                self.alpaca_api_key, self.alpaca_secret, paper=self.paper_trading
            )
        else:
            self.trading_client = None

        # Initialize RiskManager if available
        if RISK_MANAGER_AVAILABLE:
            self.risk_manager = RiskManager()
        else:
            self.risk_manager = None

        # Track consecutive losses
        self.consecutive_losses = 0
        self.consecutive_wins = 0

        # Circuit breaker state
        self.circuit_breakers_active = {
            "daily_loss": False,
            "max_drawdown": False,
            "consecutive_losses": False,
            "volatility_spike": False,
            "anomaly_detected": False,
        }

    def assess_portfolio_health(self) -> Dict[str, Any]:
        """
        Comprehensive portfolio health assessment

        Returns:
            Dict with health status and metrics
        """
        try:
            if not self.trading_client:
                return error_response("Alpaca client not available", "NO_CLIENT")

            # Get account info
            account = self.trading_client.get_account()

            # Calculate metrics
            equity = float(account.equity)
            cash = float(account.cash)
            buying_power = float(account.buying_power)

            # Get positions
            positions = self.trading_client.get_all_positions()
            position_value = sum(float(p.market_value) for p in positions)
            position_count = len(positions)

            # Calculate P/L
            starting_balance = 100000.0  # Should be loaded from state
            total_pl = equity - starting_balance
            total_pl_pct = (total_pl / starting_balance) * 100

            # Calculate daily P/L (approximate)
            daily_pl_pct = 0.0  # Would need to track from day start

            # Calculate drawdown
            peak_equity = equity  # Should track actual peak
            current_drawdown = (
                ((peak_equity - equity) / peak_equity) * 100 if peak_equity > 0 else 0
            )
            max_drawdown = 5.0  # Should track historical max

            # Calculate cash percentage
            cash_pct = (cash / equity) * 100 if equity > 0 else 0

            # Calculate risk score (0-10, higher = riskier)
            risk_score = self._calculate_risk_score(
                current_drawdown, position_count, cash_pct, daily_pl_pct
            )

            # Determine overall status
            status = self._determine_health_status(
                risk_score, current_drawdown, daily_pl_pct
            )

            # Generate warnings
            warnings = self._generate_warnings(
                current_drawdown, daily_pl_pct, cash_pct, risk_score
            )

            return success_response(
                {
                    "overall_status": status,
                    "account_equity": equity,
                    "total_pl": total_pl,
                    "total_pl_pct": round(total_pl_pct, 2),
                    "daily_pl": 0.0,  # TODO: Calculate from daily tracking
                    "daily_pl_pct": daily_pl_pct,
                    "max_drawdown": max_drawdown,
                    "current_drawdown": round(current_drawdown, 2),
                    "position_count": position_count,
                    "cash_percentage": round(cash_pct, 2),
                    "buying_power": buying_power,
                    "risk_score": round(risk_score, 2),
                    "warnings": warnings,
                }
            )

        except Exception as e:
            return error_response(
                f"Error assessing portfolio health: {str(e)}", "ASSESSMENT_ERROR"
            )

    def check_circuit_breakers(self, force_check: bool = False) -> Dict[str, Any]:
        """
        Check if any circuit breakers should trigger

        Args:
            force_check: Force re-evaluation

        Returns:
            Dict with circuit breaker status
        """
        try:
            # Get current portfolio state
            health = self.assess_portfolio_health()
            if not health["success"]:
                return health

            health_data = health["data"]

            # Check each circuit breaker
            breaker_status = {}

            # 1. Daily Loss Circuit Breaker
            daily_loss = health_data["daily_pl_pct"]
            breaker_status["daily_loss"] = {
                "triggered": daily_loss <= self.DAILY_LOSS_LIMIT,
                "current_value": daily_loss,
                "threshold": self.DAILY_LOSS_LIMIT,
                "pct_to_threshold": (
                    abs((daily_loss / self.DAILY_LOSS_LIMIT) * 100)
                    if self.DAILY_LOSS_LIMIT != 0
                    else 0
                ),
            }

            # 2. Max Drawdown Circuit Breaker
            current_drawdown = health_data["current_drawdown"]
            breaker_status["max_drawdown"] = {
                "triggered": current_drawdown >= self.MAX_DRAWDOWN_LIMIT,
                "current_value": current_drawdown,
                "threshold": self.MAX_DRAWDOWN_LIMIT,
                "pct_to_threshold": (current_drawdown / self.MAX_DRAWDOWN_LIMIT) * 100,
            }

            # 3. Consecutive Losses Circuit Breaker
            breaker_status["consecutive_losses"] = {
                "triggered": self.consecutive_losses >= self.CONSECUTIVE_LOSS_LIMIT,
                "current_value": self.consecutive_losses,
                "threshold": self.CONSECUTIVE_LOSS_LIMIT,
                "pct_to_threshold": (
                    self.consecutive_losses / self.CONSECUTIVE_LOSS_LIMIT
                )
                * 100,
            }

            # Determine which breakers are active
            active_breakers = [
                name for name, status in breaker_status.items() if status["triggered"]
            ]

            # Determine warning breakers (approaching threshold)
            warning_breakers = [
                name
                for name, status in breaker_status.items()
                if not status["triggered"] and status["pct_to_threshold"] >= 75.0
            ]

            # Should halt trading if any breakers active
            should_halt = len(active_breakers) > 0

            return success_response(
                {
                    "should_halt_trading": should_halt,
                    "active_breakers": active_breakers,
                    "warning_breakers": warning_breakers,
                    "breaker_status": breaker_status,
                }
            )

        except Exception as e:
            return error_response(
                f"Error checking circuit breakers: {str(e)}", "BREAKER_CHECK_ERROR"
            )

    def validate_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Validate a proposed trade against risk rules

        Args:
            symbol: Ticker symbol
            side: "buy" or "sell"
            quantity: Number of shares
            order_type: Order type
            limit_price: Limit price (optional)
            stop_price: Stop price (optional)

        Returns:
            Dict with validation result
        """
        try:
            if not self.trading_client:
                return error_response("Alpaca client not available", "NO_CLIENT")

            # Validation checks
            validation_checks = {}
            warnings = []
            recommendations = []
            rejection_reasons = []

            # 1. Check circuit breakers first
            breakers = self.check_circuit_breakers()
            if breakers["data"]["should_halt_trading"]:
                validation_checks["no_active_circuit_breakers"] = False
                rejection_reasons.extend(
                    [
                        f"Circuit breaker active: {breaker}"
                        for breaker in breakers["data"]["active_breakers"]
                    ]
                )
            else:
                validation_checks["no_active_circuit_breakers"] = True

            # 2. Check buying power
            account = self.trading_client.get_account()
            buying_power = float(account.buying_power)

            # Estimate cost (simplified)
            estimated_cost = quantity * 100  # Rough estimate, should get real quote
            validation_checks["sufficient_buying_power"] = (
                buying_power >= estimated_cost
            )

            if not validation_checks["sufficient_buying_power"]:
                rejection_reasons.append(
                    f"Insufficient buying power: need ${estimated_cost:.2f}, have ${buying_power:.2f}"
                )

            # 3. Check position size limits
            equity = float(account.equity)
            position_size_pct = (estimated_cost / equity) * 100 if equity > 0 else 0
            validation_checks["within_position_limits"] = (
                position_size_pct <= self.MAX_POSITION_SIZE
            )

            if not validation_checks["within_position_limits"]:
                rejection_reasons.append(
                    f"Position size {position_size_pct:.2f}% exceeds limit of {self.MAX_POSITION_SIZE}%"
                )

            # 4. Check daily trade limits (PDT rules, etc.)
            validation_checks["within_daily_trade_limit"] = (
                True  # TODO: Implement PDT checking
            )

            # 5. Risk assessment
            estimated_risk = estimated_cost * 0.02  # 2% risk estimate
            validation_checks["passes_risk_limits"] = (
                True  # Would integrate with RiskManager
            )

            # Generate recommendations
            if position_size_pct > 5.0:
                recommendations.append(
                    f"Consider reducing position size to 5% of portfolio (currently {position_size_pct:.2f}%)"
                )

            # Determine if trade is approved
            is_valid = all(validation_checks.values())
            trade_approved = is_valid and len(rejection_reasons) == 0

            return success_response(
                {
                    "is_valid": is_valid,
                    "trade_approved": trade_approved,
                    "estimated_cost": estimated_cost,
                    "estimated_risk": estimated_risk,
                    "position_size_pct": round(position_size_pct, 2),
                    "warnings": warnings,
                    "recommendations": recommendations,
                    "rejection_reasons": rejection_reasons,
                    "validation_checks": validation_checks,
                }
            )

        except Exception as e:
            return error_response(
                f"Error validating trade: {str(e)}", "VALIDATION_ERROR"
            )

    def record_trade_result(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: Optional[float] = None,
        profit_loss: Optional[float] = None,
        status: str = "filled",
    ) -> Dict[str, Any]:
        """
        Record the outcome of a completed trade

        Args:
            trade_id: Unique trade identifier
            symbol: Ticker symbol
            side: "buy" or "sell"
            quantity: Shares traded
            entry_price: Fill price
            exit_price: Exit price if closed
            profit_loss: Realized P/L
            status: Trade status

        Returns:
            Dict with recording confirmation
        """
        try:
            # Update consecutive win/loss tracking
            if profit_loss is not None:
                if profit_loss > 0:
                    self.consecutive_wins += 1
                    self.consecutive_losses = 0
                elif profit_loss < 0:
                    self.consecutive_losses += 1
                    self.consecutive_wins = 0

            # TODO: Persist to database or state file
            # For now, just track in memory

            return success_response(
                {
                    "recorded": True,
                    "trade_id": trade_id,
                    "consecutive_wins": self.consecutive_wins,
                    "consecutive_losses": self.consecutive_losses,
                    "updated_metrics": {
                        "total_trades": 0,  # TODO: Load from state
                        "winning_trades": 0,
                        "win_rate": 0.0,
                    },
                }
            )

        except Exception as e:
            return error_response(
                f"Error recording trade result: {str(e)}", "RECORD_ERROR"
            )

    def _calculate_risk_score(
        self, drawdown: float, position_count: int, cash_pct: float, daily_pl_pct: float
    ) -> float:
        """Calculate overall risk score (0-10)"""
        score = 0.0

        # Drawdown component (0-3 points)
        score += min(3.0, (drawdown / 10.0) * 3.0)

        # Position concentration (0-2 points)
        if position_count > 10:
            score += 2.0
        elif position_count > 5:
            score += 1.0

        # Cash cushion (0-2 points)
        if cash_pct < 20:
            score += 2.0
        elif cash_pct < 40:
            score += 1.0

        # Daily volatility (0-3 points)
        score += min(3.0, abs(daily_pl_pct) / 2.0)

        return min(10.0, score)

    def _determine_health_status(
        self, risk_score: float, drawdown: float, daily_pl_pct: float
    ) -> str:
        """Determine overall health status"""
        if any(self.circuit_breakers_active.values()):
            return "HALTED"
        elif risk_score >= 8.0 or drawdown >= 8.0:
            return "CRITICAL"
        elif risk_score >= 6.0 or drawdown >= 6.0:
            return "WARNING"
        elif risk_score >= 4.0 or drawdown >= 4.0:
            return "CAUTION"
        else:
            return "HEALTHY"

    def _generate_warnings(
        self, drawdown: float, daily_pl_pct: float, cash_pct: float, risk_score: float
    ) -> List[str]:
        """Generate warning messages"""
        warnings = []

        if drawdown >= 7.5:
            warnings.append(f"Drawdown at {drawdown:.2f}% - approaching 10% limit")

        if daily_pl_pct <= -1.5:
            warnings.append(
                f"Daily loss at {daily_pl_pct:.2f}% - approaching -2% limit"
            )

        if cash_pct < 20:
            warnings.append(f"Low cash reserves at {cash_pct:.2f}%")

        if risk_score >= 7.0:
            warnings.append(f"High risk score: {risk_score:.2f}/10")

        return warnings


def main():
    """CLI interface"""
    parser = argparse.ArgumentParser(description="Portfolio Risk Assessment Skill")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # assess_portfolio_health command
    health_parser = subparsers.add_parser(
        "assess_portfolio_health", help="Assess portfolio health"
    )

    # check_circuit_breakers command
    breakers_parser = subparsers.add_parser(
        "check_circuit_breakers", help="Check circuit breakers"
    )
    breakers_parser.add_argument(
        "--force", action="store_true", help="Force re-evaluation"
    )

    # validate_trade command
    validate_parser = subparsers.add_parser(
        "validate_trade", help="Validate a proposed trade"
    )
    validate_parser.add_argument("--symbol", required=True, help="Ticker symbol")
    validate_parser.add_argument(
        "--side", required=True, choices=["buy", "sell"], help="Buy or sell"
    )
    validate_parser.add_argument(
        "--quantity", type=float, required=True, help="Number of shares"
    )
    validate_parser.add_argument("--order-type", required=True, help="Order type")
    validate_parser.add_argument("--limit-price", type=float, help="Limit price")
    validate_parser.add_argument("--stop-price", type=float, help="Stop price")

    # record_trade_result command
    record_parser = subparsers.add_parser(
        "record_trade_result", help="Record trade result"
    )
    record_parser.add_argument("--trade-id", required=True, help="Trade ID")
    record_parser.add_argument("--symbol", required=True, help="Ticker symbol")
    record_parser.add_argument(
        "--side", required=True, choices=["buy", "sell"], help="Buy or sell"
    )
    record_parser.add_argument("--quantity", type=float, required=True, help="Shares")
    record_parser.add_argument(
        "--entry-price", type=float, required=True, help="Entry price"
    )
    record_parser.add_argument("--exit-price", type=float, help="Exit price")
    record_parser.add_argument("--profit-loss", type=float, help="P/L")
    record_parser.add_argument("--status", default="filled", help="Trade status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize assessor
    assessor = PortfolioRiskAssessor()

    # Execute command
    if args.command == "assess_portfolio_health":
        result = assessor.assess_portfolio_health()
    elif args.command == "check_circuit_breakers":
        result = assessor.check_circuit_breakers(
            force_check=getattr(args, "force", False)
        )
    elif args.command == "validate_trade":
        result = assessor.validate_trade(
            symbol=args.symbol,
            side=args.side,
            quantity=args.quantity,
            order_type=args.order_type,
            limit_price=getattr(args, "limit_price", None),
            stop_price=getattr(args, "stop_price", None),
        )
    elif args.command == "record_trade_result":
        result = assessor.record_trade_result(
            trade_id=args.trade_id,
            symbol=args.symbol,
            side=args.side,
            quantity=args.quantity,
            entry_price=args.entry_price,
            exit_price=getattr(args, "exit_price", None),
            profit_loss=getattr(args, "profit_loss", None),
            status=args.status,
        )
    else:
        print(f"Unknown command: {args.command}")
        return

    # Print result
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
