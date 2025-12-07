"""
Margin Utilization Monitor - Track and Protect Margin Usage

Critical for options traders: Margin calls can force liquidation at worst prices!

Why Margin Monitoring Matters:
1. Margin Call Prevention: Get warned before broker liquidates positions
2. Risk Budgeting: Know how much buying power is available
3. Position Sizing: Size new trades based on available margin
4. Stress Testing: Understand margin impact of adverse moves

Key Thresholds:
- 50% Utilization: CAUTION - Reduce new position sizes
- 75% Utilization: WARNING - No new positions, consider closing
- 90% Utilization: CRITICAL - Actively close positions
- 100% Utilization: MARGIN CALL - Broker may liquidate

Options Margin (Simplified):
- Long options: Pay full premium (no margin)
- Short naked puts: Strike × 100 × quantity (minus premium received)
- Short naked calls: Complex calculation based on underlying
- Spreads: Max loss of spread (defined risk)
- Covered calls: No additional margin (collateralized by shares)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MarginStatus:
    """Current margin utilization status."""

    # Account values
    equity: float = 0.0
    cash: float = 0.0
    buying_power: float = 0.0
    margin_used: float = 0.0
    margin_available: float = 0.0

    # Utilization metrics
    utilization_pct: float = 0.0  # 0-100%
    maintenance_margin: float = 0.0
    initial_margin: float = 0.0

    # Risk level
    risk_level: str = "UNKNOWN"  # SAFE, CAUTION, WARNING, CRITICAL, MARGIN_CALL
    risk_score: int = 0  # 0-100

    # Options-specific
    options_buying_power: float = 0.0
    options_margin_used: float = 0.0

    # Recommendations
    can_open_new_positions: bool = True
    max_new_position_value: float = 0.0
    should_reduce_exposure: bool = False

    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "equity": self.equity,
            "cash": self.cash,
            "buying_power": self.buying_power,
            "margin_used": self.margin_used,
            "margin_available": self.margin_available,
            "utilization_pct": self.utilization_pct,
            "maintenance_margin": self.maintenance_margin,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "options_buying_power": self.options_buying_power,
            "can_open_new_positions": self.can_open_new_positions,
            "max_new_position_value": self.max_new_position_value,
            "should_reduce_exposure": self.should_reduce_exposure,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MarginImpact:
    """Projected margin impact of a potential trade."""

    symbol: str
    trade_type: str  # "buy_stock", "sell_put", "sell_call", "spread", etc.
    quantity: int

    # Margin requirements
    initial_margin_required: float = 0.0
    maintenance_margin_required: float = 0.0
    buying_power_effect: float = 0.0

    # After-trade projections
    projected_utilization: float = 0.0
    projected_risk_level: str = "UNKNOWN"

    # Approval
    is_approved: bool = False
    rejection_reason: str = ""


class MarginMonitor:
    """
    Margin Utilization Monitor.

    Tracks margin usage, provides risk assessments, and prevents
    margin calls through proactive position management.
    """

    # Utilization thresholds
    THRESHOLD_SAFE = 30  # 0-30%: Safe zone
    THRESHOLD_CAUTION = 50  # 30-50%: Caution
    THRESHOLD_WARNING = 75  # 50-75%: Warning
    THRESHOLD_CRITICAL = 90  # 75-90%: Critical
    # 90-100%: Margin call territory

    # Safety buffer
    MARGIN_BUFFER_PCT = 0.20  # Keep 20% buffer for volatility

    # History settings
    HISTORY_FILE = Path("data/margin_history.json")
    MAX_HISTORY_DAYS = 90

    def __init__(self, paper: bool = True):
        """
        Initialize Margin Monitor.

        Args:
            paper: Use paper trading account
        """
        self.paper = paper
        self._history: list[MarginStatus] = []

        # Initialize trading client
        try:
            from src.core.alpaca_trader import AlpacaTrader

            self.trader = AlpacaTrader(paper=paper)
        except ImportError:
            logger.warning("AlpacaTrader not available")
            self.trader = None

        self._load_history()
        logger.info(f"Margin Monitor initialized (paper={paper})")

    def _load_history(self) -> None:
        """Load margin history from disk."""
        try:
            if self.HISTORY_FILE.exists():
                with open(self.HISTORY_FILE) as f:
                    data = json.load(f)
                    # Only load recent history
                    cutoff = datetime.now().timestamp() - (self.MAX_HISTORY_DAYS * 86400)
                    for record in data.get("history", []):
                        ts = datetime.fromisoformat(record["timestamp"])
                        if ts.timestamp() > cutoff:
                            status = MarginStatus(
                                equity=record.get("equity", 0),
                                utilization_pct=record.get("utilization_pct", 0),
                                risk_level=record.get("risk_level", "UNKNOWN"),
                                timestamp=ts,
                            )
                            self._history.append(status)
        except Exception as e:
            logger.debug(f"Could not load margin history: {e}")

    def _save_history(self) -> None:
        """Save margin history to disk."""
        try:
            self.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "history": [
                    {
                        "equity": s.equity,
                        "utilization_pct": s.utilization_pct,
                        "risk_level": s.risk_level,
                        "timestamp": s.timestamp.isoformat(),
                    }
                    for s in self._history[-500:]  # Keep last 500 records
                ],
                "updated_at": datetime.now().isoformat(),
            }
            with open(self.HISTORY_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save margin history: {e}")

    def get_current_status(self) -> MarginStatus:
        """
        Get current margin utilization status from broker.

        Returns:
            MarginStatus with current values
        """
        if not self.trader:
            return MarginStatus(risk_level="UNAVAILABLE")

        try:
            # Get account info
            if hasattr(self.trader, "get_account_info"):
                account = self.trader.get_account_info()
            else:
                account = self.trader.get_account()

            # Extract margin values
            equity = float(account.get("equity", 0) or 0)
            cash = float(account.get("cash", 0) or 0)
            buying_power = float(account.get("buying_power", 0) or 0)

            # Alpaca-specific fields
            maintenance_margin = float(account.get("maintenance_margin", 0) or 0)
            initial_margin = float(account.get("initial_margin", 0) or 0)

            # Options-specific (if available)
            options_buying_power = float(
                account.get("options_buying_power", buying_power) or buying_power
            )

            # Calculate margin usage
            if equity > 0:
                # Margin used = Equity - Cash + Borrowed amount
                # For Alpaca: margin_used ≈ equity - buying_power (simplified)
                margin_used = max(0, equity - buying_power)
                margin_available = buying_power

                # Utilization percentage
                utilization_pct = (margin_used / equity) * 100 if equity > 0 else 0
            else:
                margin_used = 0
                margin_available = 0
                utilization_pct = 0

            # Determine risk level
            if utilization_pct >= 100:
                risk_level = "MARGIN_CALL"
                risk_score = 100
            elif utilization_pct >= self.THRESHOLD_CRITICAL:
                risk_level = "CRITICAL"
                risk_score = 90
            elif utilization_pct >= self.THRESHOLD_WARNING:
                risk_level = "WARNING"
                risk_score = 70
            elif utilization_pct >= self.THRESHOLD_CAUTION:
                risk_level = "CAUTION"
                risk_score = 45
            elif utilization_pct >= self.THRESHOLD_SAFE:
                risk_level = "SAFE"
                risk_score = 25
            else:
                risk_level = "SAFE"
                risk_score = 10

            # Recommendations
            can_open = risk_level in ["SAFE", "CAUTION"]
            should_reduce = risk_level in ["WARNING", "CRITICAL", "MARGIN_CALL"]

            # Max new position (with safety buffer)
            safe_available = margin_available * (1 - self.MARGIN_BUFFER_PCT)
            max_new_position = max(0, safe_available) if can_open else 0

            status = MarginStatus(
                equity=equity,
                cash=cash,
                buying_power=buying_power,
                margin_used=margin_used,
                margin_available=margin_available,
                utilization_pct=utilization_pct,
                maintenance_margin=maintenance_margin,
                initial_margin=initial_margin,
                risk_level=risk_level,
                risk_score=risk_score,
                options_buying_power=options_buying_power,
                can_open_new_positions=can_open,
                max_new_position_value=max_new_position,
                should_reduce_exposure=should_reduce,
            )

            # Add to history
            self._history.append(status)
            self._save_history()

            return status

        except Exception as e:
            logger.error(f"Failed to get margin status: {e}")
            return MarginStatus(risk_level="ERROR")

    def estimate_margin_impact(
        self,
        symbol: str,
        trade_type: str,
        quantity: int,
        strike: float | None = None,
        premium: float | None = None,
    ) -> MarginImpact:
        """
        Estimate margin impact of a potential trade.

        Args:
            symbol: Stock/option symbol
            trade_type: Type of trade ("buy_stock", "sell_put", "sell_call", "spread")
            quantity: Number of shares/contracts
            strike: Strike price (for options)
            premium: Premium per share (for options)

        Returns:
            MarginImpact assessment
        """
        current = self.get_current_status()

        # Calculate margin requirements based on trade type
        if trade_type == "buy_stock":
            # 50% margin for stock (Reg T)
            # Get current price
            try:
                import yfinance as yf

                ticker = yf.Ticker(symbol)
                price = ticker.info.get("currentPrice", 100)
            except Exception:
                price = 100

            initial_margin = price * quantity * 0.5
            maintenance_margin = price * quantity * 0.25
            buying_power_effect = -price * quantity * 0.5

        elif trade_type == "sell_put":
            # Cash-secured put: Full strike value
            if strike is None:
                strike = 100  # Default estimate
            initial_margin = strike * 100 * quantity
            maintenance_margin = initial_margin * 0.75
            # Premium received reduces buying power effect
            premium_received = (premium or 0) * 100 * quantity
            buying_power_effect = -(initial_margin - premium_received)

        elif trade_type == "sell_call":
            # Naked call: Complex calculation
            # Simplified: 20% of underlying + OTM amount
            try:
                import yfinance as yf

                ticker = yf.Ticker(symbol)
                price = ticker.info.get("currentPrice", 100)
            except Exception:
                price = 100

            otm_amount = max(0, (strike or price) - price)
            initial_margin = (price * 0.20 + otm_amount) * 100 * quantity
            maintenance_margin = initial_margin * 0.75
            premium_received = (premium or 0) * 100 * quantity
            buying_power_effect = -(initial_margin - premium_received)

        elif trade_type == "spread":
            # Spreads: Max loss of spread
            # Width assumed to be $5 if not specified
            width = 5  # Default spread width
            initial_margin = width * 100 * quantity
            maintenance_margin = initial_margin
            buying_power_effect = -initial_margin

        elif trade_type == "covered_call":
            # Covered call: No additional margin (shares collateralize)
            initial_margin = 0
            maintenance_margin = 0
            buying_power_effect = 0

        else:
            # Unknown trade type
            initial_margin = 0
            maintenance_margin = 0
            buying_power_effect = 0

        # Calculate projected utilization
        new_margin_used = current.margin_used - buying_power_effect
        projected_util = (new_margin_used / current.equity * 100) if current.equity > 0 else 0

        # Determine projected risk level
        if projected_util >= 100:
            projected_risk = "MARGIN_CALL"
        elif projected_util >= self.THRESHOLD_CRITICAL:
            projected_risk = "CRITICAL"
        elif projected_util >= self.THRESHOLD_WARNING:
            projected_risk = "WARNING"
        elif projected_util >= self.THRESHOLD_CAUTION:
            projected_risk = "CAUTION"
        else:
            projected_risk = "SAFE"

        # Approve if within limits
        is_approved = (
            projected_risk in ["SAFE", "CAUTION"]
            and initial_margin <= current.max_new_position_value
        )

        rejection_reason = ""
        if not is_approved:
            if projected_risk in ["CRITICAL", "MARGIN_CALL"]:
                rejection_reason = f"Trade would push margin to {projected_risk} level"
            elif initial_margin > current.max_new_position_value:
                rejection_reason = (
                    f"Margin required ${initial_margin:,.2f} exceeds "
                    f"safe limit ${current.max_new_position_value:,.2f}"
                )

        return MarginImpact(
            symbol=symbol,
            trade_type=trade_type,
            quantity=quantity,
            initial_margin_required=initial_margin,
            maintenance_margin_required=maintenance_margin,
            buying_power_effect=buying_power_effect,
            projected_utilization=projected_util,
            projected_risk_level=projected_risk,
            is_approved=is_approved,
            rejection_reason=rejection_reason,
        )

    def get_alerts(self) -> list[dict]:
        """
        Get any margin-related alerts.

        Returns:
            List of alert dicts
        """
        alerts = []
        current = self.get_current_status()

        if current.risk_level == "MARGIN_CALL":
            alerts.append(
                {
                    "severity": "CRITICAL",
                    "type": "MARGIN_CALL",
                    "message": f"MARGIN CALL! Utilization at {current.utilization_pct:.1f}%. "
                    "Close positions immediately to avoid forced liquidation.",
                    "action": "CLOSE_POSITIONS",
                }
            )

        elif current.risk_level == "CRITICAL":
            alerts.append(
                {
                    "severity": "HIGH",
                    "type": "CRITICAL_MARGIN",
                    "message": f"Margin utilization CRITICAL at {current.utilization_pct:.1f}%. "
                    "Reduce exposure to prevent margin call.",
                    "action": "REDUCE_EXPOSURE",
                }
            )

        elif current.risk_level == "WARNING":
            alerts.append(
                {
                    "severity": "MEDIUM",
                    "type": "HIGH_MARGIN",
                    "message": f"Margin utilization high at {current.utilization_pct:.1f}%. "
                    "No new positions recommended.",
                    "action": "NO_NEW_POSITIONS",
                }
            )

        elif current.risk_level == "CAUTION":
            alerts.append(
                {
                    "severity": "LOW",
                    "type": "ELEVATED_MARGIN",
                    "message": f"Margin utilization elevated at {current.utilization_pct:.1f}%. "
                    "Reduce new position sizes.",
                    "action": "REDUCE_SIZE",
                }
            )

        return alerts

    def get_recommendations(self) -> dict:
        """
        Get trading recommendations based on current margin.

        Returns:
            Dict with recommendations
        """
        current = self.get_current_status()

        if current.risk_level in ["MARGIN_CALL", "CRITICAL"]:
            return {
                "action": "CLOSE_POSITIONS",
                "max_position_value": 0,
                "size_multiplier": 0,
                "strategy_allowed": ["close_only"],
                "message": "Close positions to reduce margin utilization",
            }

        elif current.risk_level == "WARNING":
            return {
                "action": "NO_NEW_POSITIONS",
                "max_position_value": 0,
                "size_multiplier": 0,
                "strategy_allowed": ["spreads", "covered_calls"],  # Defined risk only
                "message": "Only defined-risk strategies allowed",
            }

        elif current.risk_level == "CAUTION":
            return {
                "action": "REDUCE_SIZE",
                "max_position_value": current.max_new_position_value * 0.5,
                "size_multiplier": 0.5,
                "strategy_allowed": ["all"],
                "message": "Reduce position sizes by 50%",
            }

        else:  # SAFE
            return {
                "action": "NORMAL_TRADING",
                "max_position_value": current.max_new_position_value,
                "size_multiplier": 1.0,
                "strategy_allowed": ["all"],
                "message": "Normal trading conditions",
            }

    def get_daily_report(self) -> dict:
        """
        Generate daily margin report.

        Returns:
            Dict with margin metrics and trends
        """
        current = self.get_current_status()

        # Get historical trend
        week_ago = datetime.now().timestamp() - (7 * 86400)
        recent_history = [s for s in self._history if s.timestamp.timestamp() > week_ago]

        avg_utilization = (
            sum(s.utilization_pct for s in recent_history) / len(recent_history)
            if recent_history
            else current.utilization_pct
        )

        max_utilization = (
            max(s.utilization_pct for s in recent_history)
            if recent_history
            else current.utilization_pct
        )

        return {
            "current": current.to_dict(),
            "alerts": self.get_alerts(),
            "recommendations": self.get_recommendations(),
            "trends": {
                "avg_utilization_7d": avg_utilization,
                "max_utilization_7d": max_utilization,
                "data_points": len(recent_history),
            },
            "generated_at": datetime.now().isoformat(),
        }


# Convenience functions
def get_margin_status(paper: bool = True) -> MarginStatus:
    """Quick check of current margin status."""
    monitor = MarginMonitor(paper=paper)
    return monitor.get_current_status()


def can_open_position(
    symbol: str,
    trade_type: str,
    quantity: int,
    paper: bool = True,
) -> tuple[bool, str]:
    """
    Check if a position can be opened within margin limits.

    Returns:
        Tuple of (approved, reason)
    """
    monitor = MarginMonitor(paper=paper)
    impact = monitor.estimate_margin_impact(symbol, trade_type, quantity)
    return impact.is_approved, impact.rejection_reason


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    monitor = MarginMonitor(paper=True)

    print("\n=== MARGIN STATUS ===\n")

    status = monitor.get_current_status()
    print(f"Equity: ${status.equity:,.2f}")
    print(f"Buying Power: ${status.buying_power:,.2f}")
    print(f"Margin Used: ${status.margin_used:,.2f}")
    print(f"Utilization: {status.utilization_pct:.1f}%")
    print(f"Risk Level: {status.risk_level}")
    print(f"Can Open New Positions: {status.can_open_new_positions}")
    print(f"Max New Position Value: ${status.max_new_position_value:,.2f}")

    # Test margin impact
    print("\n=== MARGIN IMPACT TEST ===\n")

    impact = monitor.estimate_margin_impact(
        symbol="SPY",
        trade_type="sell_put",
        quantity=1,
        strike=400,
        premium=2.50,
    )

    print("Trade: Sell 1 SPY $400 Put for $2.50")
    print(f"Initial Margin Required: ${impact.initial_margin_required:,.2f}")
    print(f"Buying Power Effect: ${impact.buying_power_effect:,.2f}")
    print(f"Projected Utilization: {impact.projected_utilization:.1f}%")
    print(f"Projected Risk Level: {impact.projected_risk_level}")
    print(f"Approved: {impact.is_approved}")
    if not impact.is_approved:
        print(f"Reason: {impact.rejection_reason}")

    # Get alerts
    print("\n=== ALERTS ===")
    alerts = monitor.get_alerts()
    for alert in alerts:
        print(f"[{alert['severity']}] {alert['message']}")

    if not alerts:
        print("No alerts - margin levels healthy")
