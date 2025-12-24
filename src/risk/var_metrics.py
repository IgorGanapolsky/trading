"""
Value at Risk (VaR) and Conditional VaR (CVaR) Risk Metrics

Provides real-time risk monitoring and portfolio risk assessment using:
- Historical VaR: Based on historical return distribution
- Parametric VaR: GARCH-based volatility forecasting (with Gaussian fallback)
- Monte Carlo VaR: Simulation-based
- CVaR (Expected Shortfall): Average loss beyond VaR

Critical for:
- Real-time risk monitoring
- Position sizing decisions
- Circuit breaker triggers
- Regulatory compliance

GARCH Implementation (Dec 2025):
- Uses GARCH(1,1) for volatility clustering: σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}
- Captures "big moves follow big moves" phenomenon
- Falls back to constant volatility if arch library unavailable

Author: Trading System
Created: 2025-12-02
Updated: 2025-12-24 - Added GARCH volatility forecasting
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
from scipy import stats

# Optional GARCH support - graceful fallback to constant volatility
try:
    from arch import arch_model

    GARCH_AVAILABLE = True
except ImportError:
    GARCH_AVAILABLE = False

logger = logging.getLogger(__name__)


class VaRMethod(Enum):
    """Methods for VaR calculation."""

    HISTORICAL = "historical"
    PARAMETRIC = "parametric"
    MONTE_CARLO = "monte_carlo"


@dataclass
class VaRResult:
    """Result of VaR/CVaR calculation."""

    var_95: float  # 95% VaR (loss at 5th percentile)
    var_99: float  # 99% VaR (loss at 1st percentile)
    cvar_95: float  # 95% CVaR (expected shortfall)
    cvar_99: float  # 99% CVaR (expected shortfall)
    method: str
    horizon_days: int
    confidence_levels: dict[float, float] = field(default_factory=dict)
    portfolio_value: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "cvar_99": self.cvar_99,
            "method": self.method,
            "horizon_days": self.horizon_days,
            "portfolio_value": self.portfolio_value,
            "var_95_pct": self.var_95 / self.portfolio_value * 100
            if self.portfolio_value > 0
            else 0,
            "var_99_pct": self.var_99 / self.portfolio_value * 100
            if self.portfolio_value > 0
            else 0,
            "timestamp": self.timestamp,
        }


@dataclass
class RiskAlert:
    """Risk alert when thresholds are breached."""

    level: str  # "warning", "critical", "emergency"
    message: str
    metric: str
    current_value: float
    threshold: float
    timestamp: str
    action_required: str


class VaRCalculator:
    """
    Calculates VaR and CVaR for portfolio risk assessment.

    Supports multiple calculation methods and provides real-time
    risk monitoring with configurable thresholds.

    Args:
        method: VaR calculation method
        horizon_days: Time horizon for VaR (default: 1 day)
        num_simulations: Number of Monte Carlo simulations
    """

    def __init__(
        self,
        method: VaRMethod = VaRMethod.HISTORICAL,
        horizon_days: int = 1,
        num_simulations: int = 10000,
    ):
        self.method = method
        self.horizon_days = horizon_days
        self.num_simulations = num_simulations

        logger.info(
            f"VaRCalculator initialized: method={method.value}, "
            f"horizon={horizon_days}d, simulations={num_simulations}"
        )

    def calculate_var(
        self,
        returns: np.ndarray,
        portfolio_value: float,
        confidence_levels: list[float] = None,
    ) -> VaRResult:
        """
        Calculate VaR and CVaR for given returns.

        Args:
            returns: Array of historical returns (daily)
            portfolio_value: Current portfolio value
            confidence_levels: List of confidence levels (default: [0.95, 0.99])

        Returns:
            VaRResult with VaR and CVaR values
        """
        if confidence_levels is None:
            confidence_levels = [0.95, 0.99]

        if len(returns) < 20:
            logger.warning(f"Insufficient data for VaR: {len(returns)} returns (need >= 20)")
            return self._empty_result(portfolio_value)

        # Clean returns
        returns = np.array(returns)
        returns = returns[~np.isnan(returns)]
        returns = returns[~np.isinf(returns)]

        if len(returns) < 20:
            return self._empty_result(portfolio_value)

        # Scale to horizon
        if self.horizon_days > 1:
            # Square root of time rule for scaling
            returns = returns * np.sqrt(self.horizon_days)

        # Calculate based on method
        if self.method == VaRMethod.HISTORICAL:
            var_values, cvar_values = self._historical_var(returns, confidence_levels)
        elif self.method == VaRMethod.PARAMETRIC:
            var_values, cvar_values = self._parametric_var(returns, confidence_levels)
        else:  # MONTE_CARLO
            var_values, cvar_values = self._monte_carlo_var(returns, confidence_levels)

        # Convert to dollar values
        var_95_dollar = abs(var_values.get(0.95, 0)) * portfolio_value
        var_99_dollar = abs(var_values.get(0.99, 0)) * portfolio_value
        cvar_95_dollar = abs(cvar_values.get(0.95, 0)) * portfolio_value
        cvar_99_dollar = abs(cvar_values.get(0.99, 0)) * portfolio_value

        return VaRResult(
            var_95=var_95_dollar,
            var_99=var_99_dollar,
            cvar_95=cvar_95_dollar,
            cvar_99=cvar_99_dollar,
            method=self.method.value,
            horizon_days=self.horizon_days,
            confidence_levels={cl: abs(var_values.get(cl, 0)) for cl in confidence_levels},
            portfolio_value=portfolio_value,
            timestamp=datetime.now().isoformat(),
        )

    def _historical_var(
        self, returns: np.ndarray, confidence_levels: list[float]
    ) -> tuple[dict[float, float], dict[float, float]]:
        """Historical simulation VaR."""
        var_values = {}
        cvar_values = {}

        for cl in confidence_levels:
            # VaR is the (1-cl) percentile of returns
            percentile = (1 - cl) * 100
            var = np.percentile(returns, percentile)
            var_values[cl] = var

            # CVaR is the average of returns below VaR
            tail_returns = returns[returns <= var]
            cvar = np.mean(tail_returns) if len(tail_returns) > 0 else var
            cvar_values[cl] = cvar

        return var_values, cvar_values

    def _garch_volatility_forecast(self, returns: np.ndarray) -> float | None:
        """
        Forecast next-day volatility using GARCH(1,1).

        GARCH captures volatility clustering: σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}
        This models the empirical observation that "big moves follow big moves".

        Returns:
            Forecasted volatility (annualized), or None if GARCH unavailable/fails
        """
        if not GARCH_AVAILABLE:
            return None

        if len(returns) < 100:
            # GARCH needs sufficient data for reliable estimation
            logger.debug("Insufficient data for GARCH (need >= 100 returns)")
            return None

        try:
            # Scale returns to percentage for numerical stability
            returns_pct = returns * 100

            # Fit GARCH(1,1) - the workhorse model for financial volatility
            model = arch_model(returns_pct, vol="Garch", p=1, q=1, rescale=False)
            result = model.fit(disp="off", show_warning=False)

            # Forecast 1-step ahead variance
            forecast = result.forecast(horizon=1)
            next_variance = forecast.variance.values[-1, 0]

            # Convert back from percentage and return as std dev
            next_vol = np.sqrt(next_variance) / 100

            # Log persistence for monitoring (α+β close to 1 = highly persistent)
            alpha = result.params.get("alpha[1]", 0)
            beta = result.params.get("beta[1]", 0)
            persistence = alpha + beta

            logger.debug(
                f"GARCH forecast: vol={next_vol:.4f}, "
                f"persistence={persistence:.3f} (α={alpha:.3f}, β={beta:.3f})"
            )

            return next_vol

        except Exception as e:
            logger.warning(f"GARCH fitting failed, using constant vol: {e}")
            return None

    def _parametric_var(
        self, returns: np.ndarray, confidence_levels: list[float]
    ) -> tuple[dict[float, float], dict[float, float]]:
        """
        Parametric VaR with GARCH volatility forecasting.

        Uses GARCH(1,1) to forecast next-period volatility when available,
        falling back to historical standard deviation otherwise.
        """
        mu = np.mean(returns)

        # Try GARCH for dynamic volatility, fallback to constant
        garch_vol = self._garch_volatility_forecast(returns)
        if garch_vol is not None:
            sigma = garch_vol
            method_note = "GARCH"
        else:
            sigma = np.std(returns)
            method_note = "constant"

        logger.debug(f"Parametric VaR using {method_note} volatility: σ={sigma:.4f}")

        var_values = {}
        cvar_values = {}

        for cl in confidence_levels:
            # Z-score for confidence level
            z = stats.norm.ppf(1 - cl)
            var = mu + z * sigma
            var_values[cl] = var

            # CVaR for normal distribution
            # E[X | X < VaR] = μ - σ * φ(z) / (1-Φ(z))
            phi = stats.norm.pdf(z)
            cvar = mu - sigma * phi / (1 - cl)
            cvar_values[cl] = cvar

        return var_values, cvar_values

    def _monte_carlo_var(
        self, returns: np.ndarray, confidence_levels: list[float]
    ) -> tuple[dict[float, float], dict[float, float]]:
        """Monte Carlo simulation VaR."""
        mu = np.mean(returns)
        sigma = np.std(returns)

        # Simulate returns
        simulated = np.random.normal(mu, sigma, self.num_simulations)

        var_values = {}
        cvar_values = {}

        for cl in confidence_levels:
            percentile = (1 - cl) * 100
            var = np.percentile(simulated, percentile)
            var_values[cl] = var

            tail = simulated[simulated <= var]
            cvar = np.mean(tail) if len(tail) > 0 else var
            cvar_values[cl] = cvar

        return var_values, cvar_values

    def _empty_result(self, portfolio_value: float) -> VaRResult:
        """Return empty result when calculation fails."""
        return VaRResult(
            var_95=0.0,
            var_99=0.0,
            cvar_95=0.0,
            cvar_99=0.0,
            method=self.method.value,
            horizon_days=self.horizon_days,
            portfolio_value=portfolio_value,
            timestamp=datetime.now().isoformat(),
        )


class RiskMonitor:
    """
    Real-time risk monitoring with alerts and circuit breakers.

    Monitors:
    - VaR/CVaR against limits
    - Daily P&L drawdowns
    - Concentration risk
    - Correlation spikes

    Args:
        var_limit_pct: Maximum allowed VaR as % of portfolio (default: 5%)
        daily_loss_limit_pct: Max daily loss before pause (default: 2%)
        drawdown_limit_pct: Max drawdown before halt (default: 10%)
    """

    def __init__(
        self,
        var_limit_pct: float = 5.0,
        daily_loss_limit_pct: float = 2.0,
        drawdown_limit_pct: float = 10.0,
        position_limit_pct: float = 25.0,
    ):
        self.var_limit_pct = var_limit_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.drawdown_limit_pct = drawdown_limit_pct
        self.position_limit_pct = position_limit_pct

        self.var_calculator = VaRCalculator(method=VaRMethod.HISTORICAL)
        self.alerts: list[RiskAlert] = []

        # State tracking
        self.peak_value = 0.0
        self.daily_starting_value = 0.0
        self.is_paused = False
        self.is_halted = False

        logger.info(
            f"RiskMonitor initialized: VaR limit={var_limit_pct}%, "
            f"daily loss={daily_loss_limit_pct}%, drawdown={drawdown_limit_pct}%"
        )

    def check_risk(
        self,
        portfolio_value: float,
        returns: np.ndarray,
        positions: dict[str, float] | None = None,
    ) -> list[RiskAlert]:
        """
        Run comprehensive risk checks.

        Args:
            portfolio_value: Current portfolio value
            returns: Historical daily returns
            positions: Dict of {symbol: position_value}

        Returns:
            List of risk alerts (empty if all checks pass)
        """
        alerts = []

        # Update peak for drawdown tracking
        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value

        # 1. VaR Check
        var_result = self.var_calculator.calculate_var(returns, portfolio_value)
        var_pct = (var_result.var_95 / portfolio_value * 100) if portfolio_value > 0 else 0

        if var_pct > self.var_limit_pct:
            alert = RiskAlert(
                level="warning" if var_pct < self.var_limit_pct * 1.5 else "critical",
                message=f"VaR 95% ({var_pct:.2f}%) exceeds limit ({self.var_limit_pct}%)",
                metric="var_95",
                current_value=var_pct,
                threshold=self.var_limit_pct,
                timestamp=datetime.now().isoformat(),
                action_required="Reduce position sizes or hedge exposure",
            )
            alerts.append(alert)

        # 2. Daily Loss Check
        if self.daily_starting_value > 0:
            daily_pnl_pct = (
                (portfolio_value - self.daily_starting_value) / self.daily_starting_value * 100
            )
            if daily_pnl_pct < -self.daily_loss_limit_pct:
                alert = RiskAlert(
                    level="critical",
                    message=f"Daily loss ({daily_pnl_pct:.2f}%) exceeds limit ({-self.daily_loss_limit_pct}%)",
                    metric="daily_pnl",
                    current_value=daily_pnl_pct,
                    threshold=-self.daily_loss_limit_pct,
                    timestamp=datetime.now().isoformat(),
                    action_required="PAUSE trading for remainder of day",
                )
                alerts.append(alert)
                self.is_paused = True

        # 3. Drawdown Check
        if self.peak_value > 0:
            drawdown_pct = (self.peak_value - portfolio_value) / self.peak_value * 100
            if drawdown_pct > self.drawdown_limit_pct:
                alert = RiskAlert(
                    level="emergency",
                    message=f"Drawdown ({drawdown_pct:.2f}%) exceeds limit ({self.drawdown_limit_pct}%)",
                    metric="drawdown",
                    current_value=drawdown_pct,
                    threshold=self.drawdown_limit_pct,
                    timestamp=datetime.now().isoformat(),
                    action_required="HALT all trading. Manual review required.",
                )
                alerts.append(alert)
                self.is_halted = True

        # 4. Concentration Check
        if positions:
            total_value = sum(abs(v) for v in positions.values())
            for symbol, value in positions.items():
                concentration = abs(value) / total_value * 100 if total_value > 0 else 0
                if concentration > self.position_limit_pct:
                    alert = RiskAlert(
                        level="warning",
                        message=f"{symbol} concentration ({concentration:.1f}%) exceeds limit ({self.position_limit_pct}%)",
                        metric="concentration",
                        current_value=concentration,
                        threshold=self.position_limit_pct,
                        timestamp=datetime.now().isoformat(),
                        action_required=f"Reduce {symbol} position or diversify",
                    )
                    alerts.append(alert)

        self.alerts.extend(alerts)
        return alerts

    def start_new_day(self, portfolio_value: float) -> None:
        """Reset daily tracking at start of trading day."""
        self.daily_starting_value = portfolio_value
        self.is_paused = False
        logger.info(f"New trading day started. Portfolio: ${portfolio_value:,.2f}")

    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed based on risk state."""
        if self.is_halted:
            return False, "Trading HALTED due to drawdown limit breach"
        if self.is_paused:
            return False, "Trading PAUSED due to daily loss limit breach"
        return True, "Trading allowed"

    def get_risk_summary(self, portfolio_value: float, returns: np.ndarray) -> dict[str, Any]:
        """Get comprehensive risk summary."""
        var_result = self.var_calculator.calculate_var(returns, portfolio_value)

        drawdown = 0.0
        if self.peak_value > 0:
            drawdown = (self.peak_value - portfolio_value) / self.peak_value * 100

        daily_pnl = 0.0
        if self.daily_starting_value > 0:
            daily_pnl = (
                (portfolio_value - self.daily_starting_value) / self.daily_starting_value * 100
            )

        can_trade, reason = self.can_trade()

        return {
            "portfolio_value": portfolio_value,
            "var_95": var_result.var_95,
            "var_95_pct": var_result.var_95 / portfolio_value * 100 if portfolio_value > 0 else 0,
            "var_99": var_result.var_99,
            "cvar_95": var_result.cvar_95,
            "cvar_99": var_result.cvar_99,
            "current_drawdown_pct": drawdown,
            "max_drawdown_limit_pct": self.drawdown_limit_pct,
            "daily_pnl_pct": daily_pnl,
            "daily_loss_limit_pct": self.daily_loss_limit_pct,
            "peak_value": self.peak_value,
            "can_trade": can_trade,
            "trading_status": reason,
            "active_alerts": len(self.alerts),
            "timestamp": datetime.now().isoformat(),
        }

    def reset_alerts(self) -> int:
        """Clear alert history. Returns count of cleared alerts."""
        count = len(self.alerts)
        self.alerts = []
        return count


# Convenience functions
def calculate_portfolio_var(
    returns: np.ndarray,
    portfolio_value: float,
    method: VaRMethod = VaRMethod.HISTORICAL,
) -> VaRResult:
    """Quick VaR calculation."""
    calculator = VaRCalculator(method=method)
    return calculator.calculate_var(returns, portfolio_value)


def get_risk_monitor() -> RiskMonitor:
    """Get default risk monitor instance."""
    return RiskMonitor(
        var_limit_pct=5.0,
        daily_loss_limit_pct=2.0,
        drawdown_limit_pct=10.0,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("VaR/CVaR RISK METRICS DEMO")
    print("=" * 80)

    # Show GARCH status
    print(
        f"\nGARCH Volatility Forecasting: {'ENABLED' if GARCH_AVAILABLE else 'DISABLED (install arch)'}"
    )

    # Generate sample returns (200 days)
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.015, 200)  # ~0.05% mean, 1.5% daily vol

    portfolio_value = 100000.0

    print("\n1. VaR Calculation by Method:")
    print("-" * 40)

    for method in VaRMethod:
        calc = VaRCalculator(method=method)
        result = calc.calculate_var(returns, portfolio_value)

        method_label = method.value.upper()
        if method == VaRMethod.PARAMETRIC:
            method_label += " (GARCH)" if GARCH_AVAILABLE else " (constant σ)"

        print(f"\n{method_label}:")
        print(f"  VaR 95%: ${result.var_95:,.2f} ({result.var_95 / portfolio_value * 100:.2f}%)")
        print(f"  VaR 99%: ${result.var_99:,.2f} ({result.var_99 / portfolio_value * 100:.2f}%)")
        print(f"  CVaR 95%: ${result.cvar_95:,.2f}")
        print(f"  CVaR 99%: ${result.cvar_99:,.2f}")

    print("\n\n2. Risk Monitor Demo:")
    print("-" * 40)

    monitor = RiskMonitor(
        var_limit_pct=3.0,  # Lower limit for demo
        daily_loss_limit_pct=1.0,
        drawdown_limit_pct=5.0,
    )

    # Start day
    monitor.start_new_day(portfolio_value)

    # Simulate some loss
    current_value = 98500  # 1.5% loss
    alerts = monitor.check_risk(current_value, returns)

    print(f"\nPortfolio: ${current_value:,.2f}")
    print(f"Alerts: {len(alerts)}")
    for alert in alerts:
        print(f"  [{alert.level.upper()}] {alert.message}")
        print(f"    Action: {alert.action_required}")

    can_trade, reason = monitor.can_trade()
    print(f"\nCan Trade: {can_trade}")
    print(f"Reason: {reason}")

    print("\n\n3. Risk Summary:")
    print("-" * 40)
    summary = monitor.get_risk_summary(current_value, returns)
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:,.2f}")
        else:
            print(f"  {key}: {value}")
