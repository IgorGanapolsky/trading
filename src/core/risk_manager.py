"""
Risk Management System for Trading Operations

This module provides comprehensive risk management capabilities including:
- Circuit breakers for daily loss limits and maximum drawdown
- Position sizing based on account value and risk parameters
- Trade validation before execution
- Consecutive loss tracking
- Alert system for risk limit breaches
- Behavioral finance integration (Jason Zweig principles)
- Kelly Criterion position sizing for optimal capital allocation

Author: Trading System
Date: 2025-10-28
Updated: 2025-11-24 - Added behavioral finance integration
Updated: 2025-12-09 - Added Kelly Criterion position sizing
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


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
    last_reset_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))


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
        use_behavioral_finance: bool = True,
        data_dir: str = "data",
    ):
        """
        Initialize the Risk Manager with configurable parameters.

        Args:
            max_daily_loss_pct: Maximum daily loss percentage (default: 2.0%)
            max_position_size_pct: Maximum position size percentage (default: 10.0%)
            max_drawdown_pct: Maximum drawdown percentage (default: 10.0%)
            max_consecutive_losses: Maximum consecutive losses before warning (default: 3)
            use_behavioral_finance: Enable behavioral finance checks (default: True)
            data_dir: Directory for behavioral finance data storage
        """
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.use_behavioral_finance = use_behavioral_finance

        self.metrics = RiskMetrics()
        self.peak_account_value: float = 0.0
        self.alerts: list = []

        # Initialize behavioral finance manager if enabled
        self.behavioral_manager = None
        if use_behavioral_finance:
            try:
                from src.core.behavioral_finance import BehavioralFinanceManager

                self.behavioral_manager = BehavioralFinanceManager(data_dir=data_dir)
                logger.info("Behavioral finance manager initialized")
            except ImportError as e:
                logger.warning(f"Failed to import behavioral finance module: {e}")
                self.behavioral_manager = None
                self.use_behavioral_finance = False

        logger.info("[RISK MANAGER] Initialized")
        logger.info("  - Max Daily Loss: %s%%", max_daily_loss_pct)
        logger.info("  - Max Position Size: %s%%", max_position_size_pct)
        logger.info("  - Max Drawdown: %s%%", max_drawdown_pct)
        logger.info("  - Max Consecutive Losses: %s", max_consecutive_losses)
        logger.info(
            "  - Behavioral Finance: %s",
            "Enabled" if self.use_behavioral_finance else "Disabled",
        )

    def can_trade(
        self,
        account_value: float,
        daily_pl: float,
        account_info: dict[str, any] | None = None,
    ) -> bool:
        """
        Determine if trading is allowed based on current risk parameters.

        Checks circuit breakers including daily loss limits, drawdown limits,
        and Pattern Day Trader (PDT) restrictions to determine if new trades can be executed.

        Args:
            account_value: Current account value
            daily_pl: Today's profit/loss
            account_info: Optional account info dict with 'pattern_day_trader' and 'equity' keys

        Returns:
            bool: True if trading is allowed, False otherwise
        """
        # Check Pattern Day Trader restrictions
        if account_info:
            is_pdt = account_info.get("pattern_day_trader", False)
            equity = account_info.get("equity", account_value)
            daytrade_count = account_info.get("daytrade_count", 0)

            # Critical PDT protection: Block trading if daytrade_count >= 3 and equity < $25k
            if daytrade_count >= 3 and equity < 25000.0:
                self._send_alert(
                    severity="CRITICAL",
                    message=f"🚨 PDT PROTECTION: Daytrade count ({daytrade_count}) >= 3 and equity ${equity:,.2f} < $25,000. Trading blocked to prevent account lock.",
                    details={
                        "equity": equity,
                        "daytrade_count": daytrade_count,
                        "pattern_day_trader": is_pdt,
                        "minimum_required": 25000.0,
                    },
                )
                self.metrics.circuit_breaker_triggered = True
                return False

            # Standard PDT check (if flagged as PDT and equity insufficient)
            if is_pdt and equity < 25000.0:
                self._send_alert(
                    severity="CRITICAL",
                    message=f"Pattern Day Trader restriction: Account equity ${equity:,.2f} below $25,000 minimum. Day trading restricted.",
                    details={
                        "equity": equity,
                        "pattern_day_trader": is_pdt,
                        "minimum_required": 25000.0,
                    },
                )
                self.metrics.circuit_breaker_triggered = True
                return False
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
        price_per_share: float | None = None,
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

    def calculate_kelly_fraction(
        self,
        win_rate: float | None = None,
        win_loss_ratio: float | None = None,
        historical_trades: list[dict] | None = None,
        use_half_kelly: bool = True,
        max_kelly_cap: float = 0.25,
    ) -> float:
        """
        Calculate the Kelly Criterion fraction for position sizing.

        The Kelly Criterion formula: Kelly % = W - [(1-W)/R]
        Where:
        - W = Win probability (historical win rate)
        - R = Win/Loss ratio (average win / average loss)

        Args:
            win_rate: Win probability (0.0 to 1.0). If None, calculated from historical_trades.
            win_loss_ratio: Win/Loss ratio. If None, calculated from historical_trades.
            historical_trades: List of trade dicts with 'profit_loss' keys for calculating stats.
            use_half_kelly: If True, uses half-Kelly for conservative sizing (default: True).
            max_kelly_cap: Maximum Kelly fraction cap (default: 0.25 or 25%).

        Returns:
            float: Kelly fraction (0.0 to max_kelly_cap), representing the optimal position size
                   as a fraction of portfolio.

        Note:
            - Returns 0.0 if insufficient data or invalid parameters
            - Half-Kelly (50% of full Kelly) is recommended for real trading to reduce volatility
            - Full Kelly can lead to excessive drawdowns; half-Kelly provides better risk-adjusted returns
        """
        # Calculate from historical trades if provided
        if historical_trades and len(historical_trades) > 0:
            wins = [t["profit_loss"] for t in historical_trades if t.get("profit_loss", 0) > 0]
            losses = [abs(t["profit_loss"]) for t in historical_trades if t.get("profit_loss", 0) < 0]

            total_trades = len(historical_trades)
            if total_trades == 0:
                logger.warning("No historical trades provided for Kelly calculation")
                return 0.0

            # Calculate win rate
            win_rate = len(wins) / total_trades if total_trades > 0 else 0.0

            # Calculate win/loss ratio
            if len(wins) > 0 and len(losses) > 0:
                avg_win = sum(wins) / len(wins)
                avg_loss = sum(losses) / len(losses)
                win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0
            else:
                # Not enough data for meaningful calculation
                logger.warning(
                    f"Insufficient win/loss data: {len(wins)} wins, {len(losses)} losses"
                )
                return 0.0

        # Validate inputs
        if win_rate is None or win_loss_ratio is None:
            logger.warning("Kelly Criterion requires win_rate and win_loss_ratio")
            return 0.0

        if not 0.0 <= win_rate <= 1.0:
            logger.warning(f"Invalid win_rate: {win_rate} (must be 0.0-1.0)")
            return 0.0

        if win_loss_ratio <= 0:
            logger.warning(f"Invalid win_loss_ratio: {win_loss_ratio} (must be > 0)")
            return 0.0

        # Calculate Kelly fraction: W - [(1-W)/R]
        loss_rate = 1.0 - win_rate
        kelly_fraction = win_rate - (loss_rate / win_loss_ratio)

        # Kelly can be negative if strategy has negative expectancy - return 0 in this case
        if kelly_fraction <= 0:
            logger.info(
                f"Kelly fraction is negative ({kelly_fraction:.4f}) - strategy has negative expectancy. "
                f"Win rate: {win_rate:.2%}, W/L ratio: {win_loss_ratio:.2f}"
            )
            return 0.0

        # Apply half-Kelly if requested (conservative approach)
        if use_half_kelly:
            kelly_fraction = kelly_fraction / 2.0
            logger.debug(f"Using half-Kelly: {kelly_fraction:.4f} (full Kelly: {kelly_fraction * 2:.4f})")

        # Apply maximum cap
        kelly_fraction = min(kelly_fraction, max_kelly_cap)

        logger.info(
            f"Kelly Criterion: {kelly_fraction:.2%} "
            f"(win_rate={win_rate:.2%}, W/L ratio={win_loss_ratio:.2f}, "
            f"half_kelly={use_half_kelly}, cap={max_kelly_cap:.2%})"
        )

        return kelly_fraction

    def kelly_adjusted_size(
        self,
        base_position_size: float,
        win_rate: float | None = None,
        win_loss_ratio: float | None = None,
        historical_trades: list[dict] | None = None,
        use_half_kelly: bool = True,
        max_kelly_cap: float = 0.25,
    ) -> float:
        """
        Adjust position size using Kelly Criterion.

        Takes a base position size and applies Kelly Criterion to optimize allocation.
        This method integrates Kelly sizing with existing position sizing logic.

        Args:
            base_position_size: Initial position size in dollars
            win_rate: Win probability (0.0 to 1.0)
            win_loss_ratio: Win/Loss ratio (average win / average loss)
            historical_trades: List of trade dicts for calculating stats
            use_half_kelly: If True, uses half-Kelly for conservative sizing (default: True)
            max_kelly_cap: Maximum Kelly fraction cap (default: 0.25 or 25%)

        Returns:
            float: Kelly-adjusted position size in dollars

        Example:
            >>> # Adjust a $1000 position with 60% win rate and 2:1 win/loss ratio
            >>> adjusted_size = risk_mgr.kelly_adjusted_size(
            ...     base_position_size=1000.0,
            ...     win_rate=0.60,
            ...     win_loss_ratio=2.0
            ... )
        """
        if base_position_size <= 0:
            return 0.0

        kelly_fraction = self.calculate_kelly_fraction(
            win_rate=win_rate,
            win_loss_ratio=win_loss_ratio,
            historical_trades=historical_trades,
            use_half_kelly=use_half_kelly,
            max_kelly_cap=max_kelly_cap,
        )

        if kelly_fraction <= 0:
            logger.warning("Kelly fraction is 0 - returning minimum position size")
            return 0.0

        # Apply Kelly multiplier to base position size
        adjusted_size = base_position_size * kelly_fraction

        logger.info(
            f"Kelly position sizing: ${base_position_size:.2f} → ${adjusted_size:.2f} "
            f"(Kelly fraction: {kelly_fraction:.2%})"
        )

        return adjusted_size

    def validate_trade(
        self,
        symbol: str,
        amount: float,
        sentiment_score: float,
        account_value: float,
        trade_type: str = "BUY",
        account_info: dict[str, any] | None = None,
        expected_return_pct: float | None = None,
        confidence: float | None = None,
        pattern_type: str | None = None,
    ) -> dict[str, any]:
        """
        Validate a trade before execution.

        Performs comprehensive validation checks including position sizing,
        sentiment score thresholds, risk limits, Pattern Day Trader restrictions,
        and behavioral finance checks (Jason Zweig principles).

        Args:
            symbol: Trading symbol
            amount: Trade amount in dollars
            sentiment_score: Sentiment analysis score (-1 to 1)
            account_value: Current account value
            trade_type: Type of trade (BUY/SELL)
            account_info: Optional account info dict with PDT and equity info
            expected_return_pct: Expected return percentage (for behavioral tracking)
            confidence: Confidence level (0-1) for behavioral checks
            pattern_type: Type of pattern detected (for pattern bias checks)

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
            validation_result["reason"] = "Circuit breaker triggered - trading suspended"
            return validation_result

        # Check Pattern Day Trader restrictions
        if account_info:
            is_pdt = account_info.get("pattern_day_trader", False)
            equity = account_info.get("equity", account_value)
            daytrade_count = account_info.get("daytrade_count", 0)

            # Critical PDT protection: Block trade if daytrade_count >= 3 and equity < $25k
            if daytrade_count >= 3 and equity < 25000.0:
                validation_result["valid"] = False
                validation_result["reason"] = (
                    f"🚨 PDT PROTECTION: Daytrade count ({daytrade_count}) >= 3 and "
                    f"equity ${equity:,.2f} < $25,000. Trading blocked to prevent account lock."
                )
                validation_result["warnings"].append(
                    "PDT restriction: Account must maintain $25,000 equity for unlimited day trading"
                )
                return validation_result

            # Warn if approaching PDT limit
            if daytrade_count >= 2 and equity < 25000.0:
                validation_result["warnings"].append(
                    f"⚠️  Warning: Daytrade count ({daytrade_count}/3). "
                    f"Next trade will trigger PDT restriction if equity < $25,000"
                )

            # Standard PDT check (if flagged as PDT and equity insufficient)
            if is_pdt and equity < 25000.0:
                validation_result["valid"] = False
                validation_result["reason"] = (
                    f"Pattern Day Trader restriction: Account equity ${equity:,.2f} "
                    f"below $25,000 minimum required for day trading"
                )
                validation_result["warnings"].append(
                    "PDT restriction: Account must maintain $25,000 equity for unlimited day trading"
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

        # Behavioral Finance Checks (Jason Zweig principles)
        if self.use_behavioral_finance and self.behavioral_manager:
            # Get recent losses for loss aversion check
            recent_losses = []
            if self.metrics.losing_trades > 0:
                # Estimate recent losses from metrics
                recent_losses = [-self.max_daily_loss_pct / 100]  # Placeholder

            # Check if trade should proceed based on behavioral finance
            should_proceed, behavioral_reason = self.behavioral_manager.should_proceed_with_trade(
                symbol=symbol,
                expected_return=expected_return_pct or 0.0,
                confidence=confidence or 0.5,
                pattern_type=pattern_type,
                recent_losses=recent_losses if recent_losses else None,
            )

            if not should_proceed:
                validation_result["valid"] = False
                validation_result["reason"] = (
                    f"Behavioral finance check failed: {behavioral_reason}"
                )
                validation_result["warnings"].append(behavioral_reason)
                return validation_result
            elif behavioral_reason and "warning" in behavioral_reason.lower():
                validation_result["warnings"].append(f"Behavioral: {behavioral_reason}")

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
                self._send_alert(severity="INFO", message=warning, details={"symbol": symbol})

        return validation_result

    def record_trade_expectation(
        self,
        symbol: str,
        expected_return_pct: float,
        expected_confidence: float,
        entry_price: float,
    ):
        """
        Record trade expectation for behavioral finance tracking.

        Args:
            symbol: Trading symbol
            expected_return_pct: Expected return percentage
            expected_confidence: Confidence level (0-1)
            entry_price: Entry price

        Returns:
            TradeExpectation object if behavioral finance is enabled, None otherwise
        """
        if self.use_behavioral_finance and self.behavioral_manager:
            return self.behavioral_manager.record_trade_expectation(
                symbol=symbol,
                expected_return_pct=expected_return_pct,
                expected_confidence=expected_confidence,
                entry_price=entry_price,
            )
        return None

    def update_trade_outcome(
        self,
        expectation,
        exit_price: float,
        actual_return_pct: float,
    ):
        """
        Update trade outcome for behavioral finance tracking.

        Args:
            expectation: TradeExpectation object from record_trade_expectation
            exit_price: Exit price
            actual_return_pct: Actual return percentage
        """
        if self.use_behavioral_finance and self.behavioral_manager and expectation:
            self.behavioral_manager.update_trade_outcome(
                expectation=expectation,
                exit_price=exit_price,
                actual_return_pct=actual_return_pct,
            )

    def get_behavioral_summary(self) -> dict[str, any]:
        """
        Get behavioral finance summary.

        Returns:
            Dictionary with behavioral finance metrics
        """
        if self.use_behavioral_finance and self.behavioral_manager:
            return self.behavioral_manager.get_behavioral_summary()
        return {}

    def check_circuit_breakers(self, account_info: dict[str, float]) -> dict[str, any]:
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
                "breached": self.metrics.consecutive_losses >= self.max_consecutive_losses,
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
            print("[RISK MANAGER] Trade result: BREAKEVEN")

        # Log current metrics
        win_rate = (
            (self.metrics.winning_trades / self.metrics.total_trades * 100)
            if self.metrics.total_trades > 0
            else 0
        )
        print(f"[RISK MANAGER] Daily P&L: ${self.metrics.daily_pl:.2f} | Win Rate: {win_rate:.1f}%")

    def reset_daily_counters(self) -> None:
        """
        Reset daily counters and metrics.

        Should be called at the start of each trading day to reset
        daily P&L and trade counts.
        """
        current_date = datetime.now().strftime("%Y-%m-%d")

        print("[RISK MANAGER] Resetting daily counters")
        print(f"  - Previous Daily P&L: ${self.metrics.daily_pl:.2f}")
        print(f"  - Previous Daily Trades: {self.metrics.daily_trades}")

        self.metrics.daily_pl = 0.0
        self.metrics.daily_trades = 0
        self.metrics.circuit_breaker_triggered = False
        self.metrics.last_reset_date = current_date
        self.alerts.clear()

        print(f"[RISK MANAGER] Daily counters reset for {current_date}")

    def get_historical_trades_for_kelly(self, data_dir: str = "data") -> list[dict]:
        """
        Retrieve historical trades for Kelly Criterion calculation.

        Loads trade data from JSON files in the data directory and formats them
        for Kelly Criterion calculations.

        Args:
            data_dir: Directory containing trade JSON files (default: "data")

        Returns:
            list: List of trade dicts with 'profit_loss' keys

        Note:
            This method will look for files matching pattern: trades_YYYY-MM-DD.json
            If no files found or loading fails, returns empty list.
        """
        import json
        import os
        from pathlib import Path

        historical_trades = []

        try:
            data_path = Path(data_dir)
            if not data_path.exists():
                logger.warning(f"Data directory not found: {data_dir}")
                return historical_trades

            # Find all trade files
            trade_files = sorted(data_path.glob("trades_*.json"))

            for trade_file in trade_files:
                try:
                    with open(trade_file, "r") as f:
                        trades = json.load(f)
                        # Extract profit_loss if available
                        for trade in trades:
                            if "profit_loss" in trade:
                                historical_trades.append({"profit_loss": trade["profit_loss"]})
                except Exception as e:
                    logger.debug(f"Could not load trade file {trade_file}: {e}")
                    continue

            logger.info(f"Loaded {len(historical_trades)} historical trades for Kelly calculation")

        except Exception as e:
            logger.warning(f"Error loading historical trades: {e}")

        return historical_trades

    def get_risk_metrics(self) -> dict[str, any]:
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

    def _send_alert(self, severity: str, message: str, details: dict | None = None) -> None:
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
    position_size = risk_mgr.calculate_position_size(account_value, risk_per_trade_pct=1.0)
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

    print("\n--- Scenario 7: Kelly Criterion Position Sizing ---")
    # Example with explicit win rate and win/loss ratio
    kelly_frac = risk_mgr.calculate_kelly_fraction(
        win_rate=0.60,  # 60% win rate
        win_loss_ratio=2.0,  # Average win is 2x average loss
        use_half_kelly=True,  # Conservative half-Kelly
        max_kelly_cap=0.25,  # Cap at 25% of portfolio
    )
    print(f"Kelly fraction (60% win rate, 2:1 W/L): {kelly_frac:.2%}")

    # Example with Kelly-adjusted position sizing
    base_position = 10000.0  # $10,000 base position
    kelly_adjusted = risk_mgr.kelly_adjusted_size(
        base_position_size=base_position,
        win_rate=0.60,
        win_loss_ratio=2.0,
        use_half_kelly=True,
    )
    print(f"Kelly-adjusted position: ${base_position:.2f} → ${kelly_adjusted:.2f}")

    print("\n--- Scenario 8: Kelly with Historical Trades ---")
    # Simulate historical trades
    simulated_trades = [
        {"profit_loss": 100},  # Win
        {"profit_loss": -50},  # Loss
        {"profit_loss": 150},  # Win
        {"profit_loss": -40},  # Loss
        {"profit_loss": 120},  # Win
    ]
    kelly_frac_historical = risk_mgr.calculate_kelly_fraction(
        historical_trades=simulated_trades, use_half_kelly=True
    )
    print(f"Kelly fraction from historical trades: {kelly_frac_historical:.2%}")
    print(f"Historical: 3 wins (avg $123.33), 2 losses (avg $45.00)")
    print(f"Win rate: 60%, W/L ratio: 2.74")

    print("\n--- Scenario 9: Daily Reset ---")
    risk_mgr.reset_daily_counters()

    print("\n" + "=" * 70)
    print("Example completed successfully!")
    print("=" * 70)
