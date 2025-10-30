"""
Risk Management System for Trading Operations

This module provides comprehensive risk management capabilities including:
- Circuit breakers for daily loss limits and maximum drawdown
- Position sizing based on account value and risk parameters
- Trade validation before execution
- Consecutive loss tracking
- Alert system for risk limit breaches

Author: Trading System
Date: 2025-10-28
"""

from typing import Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class RiskMetrics:
    """Container for risk-related metrics and statistics."""

    daily_pl: float = 0.0
    daily_trades: int = 0
    consecutive_losses: int = 0
    max_consecutive_losses: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    max_drawdown_reached: float = 0.0
    circuit_breaker_triggered: bool = False
    last_reset_date: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d")
    )


class RiskManager:
    """
    Comprehensive risk management system for trading operations.

    This class implements various risk controls including circuit breakers,
    position sizing, trade validation, and loss tracking to protect trading capital.

    Attributes:
        max_daily_loss_pct (float): Maximum daily loss as percentage of account value
        max_position_size_pct (float): Maximum position size as percentage of account value
        max_drawdown_pct (float): Maximum drawdown from peak as percentage
        max_consecutive_losses (int): Maximum consecutive losses before alert
        metrics (RiskMetrics): Current risk metrics and statistics
        peak_account_value (float): Peak account value for drawdown calculation
        alerts (list): List of risk alerts triggered
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 2.0,
        max_position_size_pct: float = 10.0,
        max_drawdown_pct: float = 10.0,
        max_consecutive_losses: int = 3,
    ):
        """
        Initialize the Risk Manager with configurable parameters.

        Args:
            max_daily_loss_pct: Maximum daily loss percentage (default: 2.0%)
            max_position_size_pct: Maximum position size percentage (default: 10.0%)
            max_drawdown_pct: Maximum drawdown percentage (default: 10.0%)
            max_consecutive_losses: Maximum consecutive losses before warning (default: 3)
        """
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losses = max_consecutive_losses

        self.metrics = RiskMetrics()
        self.peak_account_value: float = 0.0
        self.alerts: list = []

        print(f"[RISK MANAGER] Initialized with parameters:")
        print(f"  - Max Daily Loss: {max_daily_loss_pct}%")
        print(f"  - Max Position Size: {max_position_size_pct}%")
        print(f"  - Max Drawdown: {max_drawdown_pct}%")
        print(f"  - Max Consecutive Losses: {max_consecutive_losses}")

    def can_trade(self, account_value: float, daily_pl: float) -> bool:
        """
        Determine if trading is allowed based on current risk parameters.

        Checks circuit breakers including daily loss limits and drawdown limits
        to determine if new trades can be executed.

        Args:
            account_value: Current account value
            daily_pl: Today's profit/loss

        Returns:
            bool: True if trading is allowed, False otherwise
        """
        # Update peak account value
        if account_value > self.peak_account_value:
            self.peak_account_value = account_value

        # Check daily loss limit
        daily_loss_pct = (daily_pl / account_value * 100) if account_value > 0 else 0
        if daily_loss_pct < -self.max_daily_loss_pct:
            self._send_alert(
                severity="CRITICAL",
                message=f"Daily loss limit breached: {daily_loss_pct:.2f}% (limit: {-self.max_daily_loss_pct}%)",
                details={"daily_pl": daily_pl, "account_value": account_value},
            )
            self.metrics.circuit_breaker_triggered = True
            return False

        # Check drawdown limit
        if self.peak_account_value > 0:
            current_drawdown_pct = (
                (self.peak_account_value - account_value) / self.peak_account_value
            ) * 100
            if current_drawdown_pct > self.max_drawdown_pct:
                self._send_alert(
                    severity="CRITICAL",
                    message=f"Maximum drawdown breached: {current_drawdown_pct:.2f}% (limit: {self.max_drawdown_pct}%)",
                    details={
                        "peak_value": self.peak_account_value,
                        "current_value": account_value,
                    },
                )
                self.metrics.circuit_breaker_triggered = True
                self.metrics.max_drawdown_reached = max(
                    self.metrics.max_drawdown_reached, current_drawdown_pct
                )
                return False

        # Check consecutive losses
        if self.metrics.consecutive_losses >= self.max_consecutive_losses:
            self._send_alert(
                severity="WARNING",
                message=f"Maximum consecutive losses reached: {self.metrics.consecutive_losses}",
                details={"consecutive_losses": self.metrics.consecutive_losses},
            )
            # Don't stop trading, just warn

        return True

    def calculate_position_size(
        self,
        account_value: float,
        risk_per_trade_pct: float = 1.0,
        price_per_share: Optional[float] = None,
    ) -> float:
        """
        Calculate appropriate position size based on risk parameters.

        Uses the risk percentage method to determine position size while
        respecting maximum position size limits.

        Args:
            account_value: Current account value
            risk_per_trade_pct: Risk per trade as percentage of account (default: 1.0%)
            price_per_share: Price per share for share calculation (optional)

        Returns:
            float: Position size in dollars (or shares if price_per_share provided)
        """
        if account_value <= 0:
            return 0.0

        # Calculate position size based on risk percentage
        risk_amount = account_value * (risk_per_trade_pct / 100)

        # Apply maximum position size limit
        max_position_value = account_value * (self.max_position_size_pct / 100)
        position_value = min(risk_amount, max_position_value)

        # Convert to shares if price provided
        if price_per_share and price_per_share > 0:
            position_size = position_value / price_per_share
            return int(position_size)  # Return whole shares

        return position_value

    def validate_trade(
        self,
        symbol: str,
        amount: float,
        sentiment_score: float,
        account_value: float,
        trade_type: str = "BUY",
    ) -> Dict[str, any]:
        """
        Validate a trade before execution.

        Performs comprehensive validation checks including position sizing,
        sentiment score thresholds, and risk limits.

        Args:
            symbol: Trading symbol
            amount: Trade amount in dollars
            sentiment_score: Sentiment analysis score (-1 to 1)
            account_value: Current account value
            trade_type: Type of trade (BUY/SELL)

        Returns:
            dict: Validation result with 'valid' flag and 'reason' for rejection
        """
        validation_result = {
            "valid": True,
            "symbol": symbol,
            "amount": amount,
            "trade_type": trade_type,
            "warnings": [],
            "reason": None,
        }

        # Check if trading is allowed (circuit breakers)
        if self.metrics.circuit_breaker_triggered:
            validation_result["valid"] = False
            validation_result["reason"] = (
                "Circuit breaker triggered - trading suspended"
            )
            return validation_result

        # Validate amount is positive
        if amount <= 0:
            validation_result["valid"] = False
            validation_result["reason"] = "Trade amount must be positive"
            return validation_result

        # Check position size limits
        position_size_pct = (amount / account_value * 100) if account_value > 0 else 0
        if position_size_pct > self.max_position_size_pct:
            validation_result["valid"] = False
            validation_result["reason"] = (
                f"Position size {position_size_pct:.2f}% exceeds limit of {self.max_position_size_pct}%"
            )
            return validation_result

        # Validate sentiment score
        if not -1.0 <= sentiment_score <= 1.0:
            validation_result["valid"] = False
            validation_result["reason"] = (
                f"Invalid sentiment score: {sentiment_score} (must be between -1 and 1)"
            )
            return validation_result

        # Check sentiment strength (weak sentiment warning)
        if abs(sentiment_score) < 0.3:
            validation_result["warnings"].append(
                f"Weak sentiment signal: {sentiment_score:.2f} (consider stronger signals)"
            )

        # Check if sentiment matches trade type
        if trade_type.upper() == "BUY" and sentiment_score < 0:
            validation_result["warnings"].append(
                f"Buy trade with negative sentiment: {sentiment_score:.2f}"
            )
        elif trade_type.upper() == "SELL" and sentiment_score > 0:
            validation_result["warnings"].append(
                f"Sell trade with positive sentiment: {sentiment_score:.2f}"
            )

        # Check consecutive losses
        if self.metrics.consecutive_losses >= self.max_consecutive_losses:
            validation_result["warnings"].append(
                f"Trading after {self.metrics.consecutive_losses} consecutive losses - exercise caution"
            )

        # Log warnings if any
        if validation_result["warnings"]:
            for warning in validation_result["warnings"]:
                self._send_alert(
                    severity="INFO", message=warning, details={"symbol": symbol}
                )

        return validation_result

    def check_circuit_breakers(self, account_info: Dict[str, float]) -> Dict[str, any]:
        """
        Check all circuit breaker conditions.

        Evaluates current account state against all configured risk limits
        and returns detailed status information.

        Args:
            account_info: Dictionary with 'account_value' and 'daily_pl' keys

        Returns:
            dict: Circuit breaker status with all risk metrics
        """
        account_value = account_info.get("account_value", 0.0)
        daily_pl = account_info.get("daily_pl", 0.0)

        # Update peak value
        if account_value > self.peak_account_value:
            self.peak_account_value = account_value

        # Calculate current metrics
        daily_loss_pct = (daily_pl / account_value * 100) if account_value > 0 else 0
        current_drawdown_pct = 0.0
        if self.peak_account_value > 0:
            current_drawdown_pct = (
                (self.peak_account_value - account_value) / self.peak_account_value
            ) * 100

        status = {
            "trading_allowed": True,
            "daily_loss": {
                "current_pct": daily_loss_pct,
                "limit_pct": -self.max_daily_loss_pct,
                "breached": daily_loss_pct < -self.max_daily_loss_pct,
            },
            "drawdown": {
                "current_pct": current_drawdown_pct,
                "limit_pct": self.max_drawdown_pct,
                "breached": current_drawdown_pct > self.max_drawdown_pct,
            },
            "consecutive_losses": {
                "current": self.metrics.consecutive_losses,
                "limit": self.max_consecutive_losses,
                "breached": self.metrics.consecutive_losses
                >= self.max_consecutive_losses,
            },
            "account_value": account_value,
            "peak_account_value": self.peak_account_value,
            "daily_pl": daily_pl,
        }

        # Determine if trading should be stopped
        if status["daily_loss"]["breached"] or status["drawdown"]["breached"]:
            status["trading_allowed"] = False
            self.metrics.circuit_breaker_triggered = True

        return status

    def record_trade_result(self, profit_loss: float) -> None:
        """
        Record the result of a completed trade.

        Updates internal metrics including consecutive losses, win/loss counts,
        and daily P&L tracking.

        Args:
            profit_loss: Profit or loss from the trade (positive for profit, negative for loss)
        """
        self.metrics.total_trades += 1
        self.metrics.daily_trades += 1
        self.metrics.daily_pl += profit_loss

        if profit_loss > 0:
            self.metrics.winning_trades += 1
            self.metrics.consecutive_losses = 0
            print(f"[RISK MANAGER] Trade result: PROFIT ${profit_loss:.2f}")
        elif profit_loss < 0:
            self.metrics.losing_trades += 1
            self.metrics.consecutive_losses += 1
            self.metrics.max_consecutive_losses = max(
                self.metrics.max_consecutive_losses, self.metrics.consecutive_losses
            )
            print(f"[RISK MANAGER] Trade result: LOSS ${profit_loss:.2f}")

            # Alert on consecutive losses
            if self.metrics.consecutive_losses >= self.max_consecutive_losses:
                self._send_alert(
                    severity="WARNING",
                    message=f"Consecutive losses: {self.metrics.consecutive_losses}",
                    details={"total_loss": profit_loss},
                )
        else:
            print(f"[RISK MANAGER] Trade result: BREAKEVEN")

        # Log current metrics
        win_rate = (
            (self.metrics.winning_trades / self.metrics.total_trades * 100)
            if self.metrics.total_trades > 0
            else 0
        )
        print(
            f"[RISK MANAGER] Daily P&L: ${self.metrics.daily_pl:.2f} | Win Rate: {win_rate:.1f}%"
        )

    def reset_daily_counters(self) -> None:
        """
        Reset daily counters and metrics.

        Should be called at the start of each trading day to reset
        daily P&L and trade counts.
        """
        current_date = datetime.now().strftime("%Y-%m-%d")

        print(f"[RISK MANAGER] Resetting daily counters")
        print(f"  - Previous Daily P&L: ${self.metrics.daily_pl:.2f}")
        print(f"  - Previous Daily Trades: {self.metrics.daily_trades}")

        self.metrics.daily_pl = 0.0
        self.metrics.daily_trades = 0
        self.metrics.circuit_breaker_triggered = False
        self.metrics.last_reset_date = current_date
        self.alerts.clear()

        print(f"[RISK MANAGER] Daily counters reset for {current_date}")

    def get_risk_metrics(self) -> Dict[str, any]:
        """
        Get current risk metrics and statistics.

        Returns:
            dict: Comprehensive risk metrics including trades, P&L, and limits
        """
        win_rate = 0.0
        if self.metrics.total_trades > 0:
            win_rate = (self.metrics.winning_trades / self.metrics.total_trades) * 100

        return {
            "daily_metrics": {
                "daily_pl": self.metrics.daily_pl,
                "daily_trades": self.metrics.daily_trades,
                "last_reset": self.metrics.last_reset_date,
            },
            "trade_statistics": {
                "total_trades": self.metrics.total_trades,
                "winning_trades": self.metrics.winning_trades,
                "losing_trades": self.metrics.losing_trades,
                "win_rate_pct": round(win_rate, 2),
                "consecutive_losses": self.metrics.consecutive_losses,
                "max_consecutive_losses": self.metrics.max_consecutive_losses,
            },
            "risk_limits": {
                "max_daily_loss_pct": self.max_daily_loss_pct,
                "max_position_size_pct": self.max_position_size_pct,
                "max_drawdown_pct": self.max_drawdown_pct,
                "max_consecutive_losses_limit": self.max_consecutive_losses,
            },
            "account_metrics": {
                "peak_account_value": self.peak_account_value,
                "max_drawdown_reached": self.metrics.max_drawdown_reached,
                "circuit_breaker_triggered": self.metrics.circuit_breaker_triggered,
            },
            "alerts": self.alerts[-10:],  # Last 10 alerts
        }

    def _send_alert(
        self, severity: str, message: str, details: Optional[Dict] = None
    ) -> None:
        """
        Send a risk management alert.

        Internal method to generate and store alerts. Currently prints to console
        but can be extended to send emails, SMS, or push notifications.

        Args:
            severity: Alert severity level (INFO, WARNING, CRITICAL)
            message: Alert message
            details: Additional details dictionary (optional)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        alert = {
            "timestamp": timestamp,
            "severity": severity,
            "message": message,
            "details": details or {},
        }

        self.alerts.append(alert)

        # Console output with color-coded severity
        severity_symbols = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨"}

        symbol = severity_symbols.get(severity, "•")
        print(f"\n{symbol} [RISK ALERT - {severity}] {timestamp}")
        print(f"  Message: {message}")
        if details:
            print(f"  Details: {details}")
        print()


# Example usage and testing
if __name__ == "__main__":
    print("=" * 70)
    print("RISK MANAGER - Example Usage")
    print("=" * 70)

    # Initialize risk manager
    risk_mgr = RiskManager(
        max_daily_loss_pct=2.0,
        max_position_size_pct=10.0,
        max_drawdown_pct=10.0,
        max_consecutive_losses=3,
    )

    # Simulate trading scenarios
    account_value = 100000.0
    daily_pl = 0.0

    print("\n--- Scenario 1: Normal Trading ---")
    can_trade = risk_mgr.can_trade(account_value, daily_pl)
    print(f"Can trade: {can_trade}")

    print("\n--- Scenario 2: Calculate Position Size ---")
    position_size = risk_mgr.calculate_position_size(
        account_value, risk_per_trade_pct=1.0
    )
    print(f"Position size (1% risk): ${position_size:.2f}")

    print("\n--- Scenario 3: Validate Trade ---")
    validation = risk_mgr.validate_trade(
        symbol="AAPL",
        amount=5000.0,
        sentiment_score=0.75,
        account_value=account_value,
        trade_type="BUY",
    )
    print(f"Trade valid: {validation['valid']}")
    if validation["warnings"]:
        print(f"Warnings: {validation['warnings']}")

    print("\n--- Scenario 4: Record Trade Results ---")
    risk_mgr.record_trade_result(-500.0)  # Loss
    risk_mgr.record_trade_result(-300.0)  # Loss
    risk_mgr.record_trade_result(-200.0)  # Loss

    print("\n--- Scenario 5: Check Circuit Breakers ---")
    daily_pl = -1500.0  # Total losses
    account_info = {"account_value": account_value, "daily_pl": daily_pl}
    breaker_status = risk_mgr.check_circuit_breakers(account_info)
    print(f"Trading allowed: {breaker_status['trading_allowed']}")
    print(f"Daily loss: {breaker_status['daily_loss']['current_pct']:.2f}%")

    print("\n--- Scenario 6: Get Risk Metrics ---")
    metrics = risk_mgr.get_risk_metrics()
    print(f"Total trades: {metrics['trade_statistics']['total_trades']}")
    print(f"Consecutive losses: {metrics['trade_statistics']['consecutive_losses']}")
    print(f"Win rate: {metrics['trade_statistics']['win_rate_pct']:.2f}%")

    print("\n--- Scenario 7: Daily Reset ---")
    risk_mgr.reset_daily_counters()

    print("\n" + "=" * 70)
    print("Example completed successfully!")
    print("=" * 70)
