"""
SRE-Style Telemetry and Monitoring

Production-grade Site Reliability Engineering (SRE) monitoring for the trading system.
Provides real-time visibility into system health, gate performance, and early warning
detection for fragility before it costs real money.

Key Features:
1. Per-gate pass rates (momentum, RL, LLM, risk)
2. Regime classification tracking
3. Live vs backtest divergence monitoring
4. Circuit breaker event tracking
5. Latency and error rate metrics
6. SLI/SLO compliance reporting

Author: Trading System
Created: 2025-12-02
"""

import json
import logging
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GateMetrics:
    """Metrics for a single gate in the funnel."""

    gate_name: str
    total_evaluations: int = 0
    passes: int = 0
    rejections: int = 0
    errors: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as percentage."""
        if self.total_evaluations == 0:
            return 0.0
        return (self.passes / self.total_evaluations) * 100

    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage."""
        if self.total_evaluations == 0:
            return 0.0
        return (self.errors / self.total_evaluations) * 100


@dataclass
class RegimeMetrics:
    """Metrics for market regime performance."""

    regime: str
    observations: int = 0
    avg_signal_strength: float = 0.0
    trades_executed: int = 0
    win_rate: float = 0.0
    avg_pnl: float = 0.0


@dataclass
class SLIMetrics:
    """Service Level Indicator metrics."""

    name: str
    target: float  # SLO target (e.g., 99.5%)
    current_value: float
    window_hours: int = 24
    compliant: bool = True
    budget_remaining: float = 100.0  # Error budget remaining %


@dataclass
class SystemHealthReport:
    """Comprehensive system health report."""

    timestamp: str
    overall_health: str  # "healthy", "degraded", "unhealthy"
    health_score: float  # 0-100
    gate_metrics: dict[str, GateMetrics]
    regime_metrics: dict[str, RegimeMetrics]
    sli_metrics: list[SLIMetrics]
    alerts: list[dict[str, Any]]
    circuit_breaker_status: dict[str, Any]
    live_backtest_divergence: dict[str, Any]


class SREMonitor:
    """
    SRE-style monitoring system for trading infrastructure.

    Provides production-grade observability including:
    - Gate pass/reject rates
    - Latency tracking
    - Error budgets
    - Regime performance
    - Divergence detection
    """

    # SLO targets (Service Level Objectives)
    SLO_GATE_AVAILABILITY = float(os.getenv("SLO_GATE_AVAILABILITY", "99.5"))  # %
    SLO_GATE_LATENCY_P95_MS = float(os.getenv("SLO_GATE_LATENCY_P95", "500"))  # ms
    SLO_ERROR_RATE = float(os.getenv("SLO_ERROR_RATE", "1.0"))  # %
    SLO_MOMENTUM_PASS_RATE_MIN = float(os.getenv("SLO_MOMENTUM_PASS_MIN", "10"))  # %
    SLO_MOMENTUM_PASS_RATE_MAX = float(os.getenv("SLO_MOMENTUM_PASS_MAX", "50"))  # %

    # Alert thresholds
    ALERT_ERROR_RATE_THRESHOLD = float(os.getenv("ALERT_ERROR_RATE", "5.0"))  # %
    ALERT_LATENCY_THRESHOLD_MS = float(os.getenv("ALERT_LATENCY_MS", "2000"))  # ms
    ALERT_PASS_RATE_LOW = float(os.getenv("ALERT_PASS_RATE_LOW", "5.0"))  # %
    ALERT_DIVERGENCE_THRESHOLD = float(os.getenv("ALERT_DIVERGENCE", "0.3"))  # 30%

    def __init__(
        self,
        metrics_file: str = "data/sre_metrics.json",
        events_file: str = "data/audit_trail/hybrid_funnel_runs.jsonl",
        window_hours: int = 24,
    ):
        self.metrics_file = Path(metrics_file)
        self.events_file = Path(events_file)
        self.window_hours = window_hours

        # In-memory metrics
        self.gate_metrics: dict[str, GateMetrics] = {}
        self.regime_metrics: dict[str, RegimeMetrics] = {}
        self.latency_samples: dict[str, list[float]] = defaultdict(list)
        self.alerts: list[dict[str, Any]] = []

        # Load historical metrics
        self._load_metrics()

        logger.info(f"SREMonitor initialized: window={window_hours}h")

    def record_gate_event(
        self,
        gate: str,
        status: str,
        latency_ms: float = 0.0,
        ticker: str = "",
        payload: dict | None = None,
    ) -> None:
        """
        Record a gate evaluation event.

        Args:
            gate: Gate name (momentum, rl_filter, llm, risk)
            status: Event status (pass, reject, error, skipped)
            latency_ms: Processing latency in milliseconds
            ticker: Ticker symbol being evaluated
            payload: Additional event data
        """
        if gate not in self.gate_metrics:
            self.gate_metrics[gate] = GateMetrics(gate_name=gate)

        metrics = self.gate_metrics[gate]
        metrics.total_evaluations += 1

        if status == "pass":
            metrics.passes += 1
        elif status == "reject":
            metrics.rejections += 1
        elif status == "error":
            metrics.errors += 1

        # Track latency
        if latency_ms > 0:
            self.latency_samples[gate].append(latency_ms)
            # Keep last 1000 samples
            if len(self.latency_samples[gate]) > 1000:
                self.latency_samples[gate] = self.latency_samples[gate][-1000:]

        # Check for alerts
        self._check_gate_alerts(gate, metrics, latency_ms)

        # Persist periodically
        if metrics.total_evaluations % 100 == 0:
            self._save_metrics()

    def record_regime_observation(
        self,
        regime: str,
        signal_strength: float,
        trade_executed: bool = False,
        pnl: float | None = None,
    ) -> None:
        """
        Record a regime observation.

        Args:
            regime: Detected market regime
            signal_strength: Signal strength at observation
            trade_executed: Whether a trade was executed
            pnl: P/L if trade was executed
        """
        if regime not in self.regime_metrics:
            self.regime_metrics[regime] = RegimeMetrics(regime=regime)

        metrics = self.regime_metrics[regime]
        metrics.observations += 1

        # Update rolling average signal strength
        metrics.avg_signal_strength = (
            metrics.avg_signal_strength * (metrics.observations - 1) + signal_strength
        ) / metrics.observations

        if trade_executed:
            metrics.trades_executed += 1
            if pnl is not None:
                # Update win rate
                if pnl > 0:
                    wins = metrics.win_rate * (metrics.trades_executed - 1) + 1
                else:
                    wins = metrics.win_rate * (metrics.trades_executed - 1)
                metrics.win_rate = wins / metrics.trades_executed

                # Update average P/L
                metrics.avg_pnl = (
                    metrics.avg_pnl * (metrics.trades_executed - 1) + pnl
                ) / metrics.trades_executed

    def record_circuit_breaker_event(
        self,
        tier: str,
        action: str,
        trigger_reason: str,
        trigger_value: float,
    ) -> None:
        """Record circuit breaker event."""
        alert = {
            "type": "circuit_breaker",
            "timestamp": datetime.now().isoformat(),
            "tier": tier,
            "action": action,
            "trigger_reason": trigger_reason,
            "trigger_value": trigger_value,
            "severity": self._cb_tier_to_severity(tier),
        }
        self.alerts.append(alert)
        logger.warning(f"Circuit breaker alert: {tier} - {action} ({trigger_reason})")

    def record_divergence(
        self,
        strategy: str,
        metric: str,
        expected: float,
        actual: float,
    ) -> None:
        """Record live vs backtest divergence."""
        divergence_pct = abs(expected - actual) / abs(expected) if expected != 0 else 0

        if divergence_pct > self.ALERT_DIVERGENCE_THRESHOLD:
            alert = {
                "type": "divergence",
                "timestamp": datetime.now().isoformat(),
                "strategy": strategy,
                "metric": metric,
                "expected": expected,
                "actual": actual,
                "divergence_pct": divergence_pct,
                "severity": "warning" if divergence_pct < 0.5 else "critical",
            }
            self.alerts.append(alert)
            logger.warning(
                f"Divergence alert: {strategy}.{metric} "
                f"expected={expected:.2f}, actual={actual:.2f} ({divergence_pct:.1%})"
            )

    def get_gate_metrics(self, gate: str | None = None) -> dict[str, GateMetrics]:
        """Get gate metrics, optionally filtered by gate name."""
        self._calculate_latency_percentiles()

        if gate:
            return {gate: self.gate_metrics.get(gate, GateMetrics(gate_name=gate))}
        return self.gate_metrics

    def get_regime_metrics(self, regime: str | None = None) -> dict[str, RegimeMetrics]:
        """Get regime metrics, optionally filtered by regime."""
        if regime:
            return {regime: self.regime_metrics.get(regime, RegimeMetrics(regime=regime))}
        return self.regime_metrics

    def get_sli_report(self) -> list[SLIMetrics]:
        """Generate SLI/SLO compliance report."""
        self._calculate_latency_percentiles()
        slis = []

        # Gate availability SLI
        for gate, metrics in self.gate_metrics.items():
            if metrics.total_evaluations > 0:
                availability = (
                    (metrics.total_evaluations - metrics.errors) / metrics.total_evaluations
                ) * 100
                slis.append(
                    SLIMetrics(
                        name=f"{gate}_availability",
                        target=self.SLO_GATE_AVAILABILITY,
                        current_value=availability,
                        window_hours=self.window_hours,
                        compliant=availability >= self.SLO_GATE_AVAILABILITY,
                        budget_remaining=max(0, availability - self.SLO_GATE_AVAILABILITY)
                        / (100 - self.SLO_GATE_AVAILABILITY)
                        * 100,
                    )
                )

                # Latency SLI
                if metrics.p95_latency_ms > 0:
                    latency_compliant = metrics.p95_latency_ms <= self.SLO_GATE_LATENCY_P95_MS
                    slis.append(
                        SLIMetrics(
                            name=f"{gate}_latency_p95",
                            target=self.SLO_GATE_LATENCY_P95_MS,
                            current_value=metrics.p95_latency_ms,
                            window_hours=self.window_hours,
                            compliant=latency_compliant,
                        )
                    )

        # Overall error rate SLI
        total_evals = sum(m.total_evaluations for m in self.gate_metrics.values())
        total_errors = sum(m.errors for m in self.gate_metrics.values())
        if total_evals > 0:
            error_rate = (total_errors / total_evals) * 100
            slis.append(
                SLIMetrics(
                    name="overall_error_rate",
                    target=self.SLO_ERROR_RATE,
                    current_value=error_rate,
                    window_hours=self.window_hours,
                    compliant=error_rate <= self.SLO_ERROR_RATE,
                )
            )

        # Momentum pass rate SLI (should be in healthy range)
        if "momentum" in self.gate_metrics:
            pass_rate = self.gate_metrics["momentum"].pass_rate
            compliant = (
                self.SLO_MOMENTUM_PASS_RATE_MIN <= pass_rate <= self.SLO_MOMENTUM_PASS_RATE_MAX
            )
            slis.append(
                SLIMetrics(
                    name="momentum_pass_rate_range",
                    target=self.SLO_MOMENTUM_PASS_RATE_MAX,
                    current_value=pass_rate,
                    window_hours=self.window_hours,
                    compliant=compliant,
                )
            )

        return slis

    def get_health_report(self) -> SystemHealthReport:
        """Generate comprehensive system health report."""
        self._calculate_latency_percentiles()
        slis = self.get_sli_report()

        # Calculate health score
        sli_compliance = sum(1 for s in slis if s.compliant) / len(slis) if slis else 1.0
        error_rate = self._calculate_overall_error_rate()
        recent_critical_alerts = sum(
            1 for a in self.alerts[-50:] if a.get("severity") == "critical"
        )

        health_score = (
            sli_compliance * 40  # 40% SLI compliance
            + (1 - min(1, error_rate / 10)) * 30  # 30% error rate
            + (1 - min(1, recent_critical_alerts / 5)) * 30  # 30% no critical alerts
        )

        if health_score >= 90:
            overall_health = "healthy"
        elif health_score >= 70:
            overall_health = "degraded"
        else:
            overall_health = "unhealthy"

        # Get circuit breaker status
        cb_status = self._get_circuit_breaker_status()

        # Get divergence data
        divergence_data = self._get_divergence_summary()

        return SystemHealthReport(
            timestamp=datetime.now().isoformat(),
            overall_health=overall_health,
            health_score=health_score,
            gate_metrics={k: v for k, v in self.gate_metrics.items()},
            regime_metrics={k: v for k, v in self.regime_metrics.items()},
            sli_metrics=slis,
            alerts=self.alerts[-20:],  # Last 20 alerts
            circuit_breaker_status=cb_status,
            live_backtest_divergence=divergence_data,
        )

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get data formatted for dashboard display."""
        report = self.get_health_report()

        return {
            "health": {
                "status": report.overall_health,
                "score": round(report.health_score, 1),
                "timestamp": report.timestamp,
            },
            "gates": {
                gate: {
                    "pass_rate": round(m.pass_rate, 1),
                    "error_rate": round(m.error_rate, 1),
                    "total_evals": m.total_evaluations,
                    "p95_latency_ms": round(m.p95_latency_ms, 1),
                }
                for gate, m in report.gate_metrics.items()
            },
            "regimes": {
                regime: {
                    "observations": m.observations,
                    "avg_strength": round(m.avg_signal_strength, 3),
                    "trades": m.trades_executed,
                    "win_rate": round(m.win_rate * 100, 1),
                }
                for regime, m in report.regime_metrics.items()
            },
            "slis": [
                {
                    "name": s.name,
                    "target": s.target,
                    "current": round(s.current_value, 2),
                    "compliant": s.compliant,
                }
                for s in report.sli_metrics
            ],
            "alerts": [
                {
                    "type": a.get("type"),
                    "severity": a.get("severity"),
                    "message": self._format_alert_message(a),
                    "timestamp": a.get("timestamp"),
                }
                for a in report.alerts[-10:]
            ],
            "circuit_breaker": report.circuit_breaker_status,
        }

    def ingest_telemetry_events(self) -> int:
        """
        Ingest events from the telemetry JSONL file.

        Returns:
            Number of events ingested
        """
        if not self.events_file.exists():
            return 0

        ingested = 0
        try:
            with open(self.events_file) as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        self._process_telemetry_event(event)
                        ingested += 1
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error ingesting telemetry events: {e}")

        return ingested

    def _process_telemetry_event(self, event: dict) -> None:
        """Process a single telemetry event."""
        event_type = event.get("event", "")
        status = event.get("status", "")
        ticker = event.get("ticker", "")
        payload = event.get("payload", {})

        if event_type.startswith("gate."):
            gate = event_type.split(".")[-1]
            self.record_gate_event(
                gate=gate,
                status=status,
                ticker=ticker,
                payload=payload,
            )
        elif event_type == "microstructure":
            # Extract regime from microstructure events
            regime = payload.get("label", "unknown")
            self.record_regime_observation(
                regime=regime,
                signal_strength=payload.get("confidence", 0.0),
            )

    def _check_gate_alerts(self, gate: str, metrics: GateMetrics, latency_ms: float) -> None:
        """Check for alert conditions on a gate."""
        # Error rate alert
        if metrics.total_evaluations >= 10:  # Need minimum samples
            if metrics.error_rate > self.ALERT_ERROR_RATE_THRESHOLD:
                self._add_alert(
                    alert_type="high_error_rate",
                    gate=gate,
                    value=metrics.error_rate,
                    threshold=self.ALERT_ERROR_RATE_THRESHOLD,
                    severity="warning",
                )

        # Latency alert
        if latency_ms > self.ALERT_LATENCY_THRESHOLD_MS:
            self._add_alert(
                alert_type="high_latency",
                gate=gate,
                value=latency_ms,
                threshold=self.ALERT_LATENCY_THRESHOLD_MS,
                severity="warning",
            )

        # Pass rate too low alert (might indicate data issues)
        if metrics.total_evaluations >= 50:
            if metrics.pass_rate < self.ALERT_PASS_RATE_LOW:
                self._add_alert(
                    alert_type="low_pass_rate",
                    gate=gate,
                    value=metrics.pass_rate,
                    threshold=self.ALERT_PASS_RATE_LOW,
                    severity="warning",
                )

    def _add_alert(
        self,
        alert_type: str,
        gate: str,
        value: float,
        threshold: float,
        severity: str,
    ) -> None:
        """Add an alert, avoiding duplicates in short timeframe."""
        now = datetime.now()

        # Check for recent duplicate
        for alert in self.alerts[-10:]:
            if (
                alert.get("type") == alert_type
                and alert.get("gate") == gate
                and datetime.fromisoformat(alert["timestamp"]) > now - timedelta(minutes=5)
            ):
                return  # Skip duplicate

        self.alerts.append(
            {
                "type": alert_type,
                "gate": gate,
                "timestamp": now.isoformat(),
                "value": value,
                "threshold": threshold,
                "severity": severity,
            }
        )

        # Keep last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]

    def _calculate_latency_percentiles(self) -> None:
        """Calculate latency percentiles for all gates."""
        for gate, samples in self.latency_samples.items():
            if gate in self.gate_metrics and samples:
                sorted_samples = sorted(samples)
                n = len(sorted_samples)
                self.gate_metrics[gate].avg_latency_ms = statistics.mean(samples)
                self.gate_metrics[gate].p95_latency_ms = sorted_samples[int(n * 0.95)]
                self.gate_metrics[gate].p99_latency_ms = sorted_samples[int(n * 0.99)]

    def _calculate_overall_error_rate(self) -> float:
        """Calculate overall error rate across all gates."""
        total_evals = sum(m.total_evaluations for m in self.gate_metrics.values())
        total_errors = sum(m.errors for m in self.gate_metrics.values())
        return (total_errors / total_evals * 100) if total_evals > 0 else 0.0

    def _get_circuit_breaker_status(self) -> dict[str, Any]:
        """Get circuit breaker status from file if available."""
        try:
            cb_file = Path("data/multi_tier_circuit_breaker_state.json")
            if cb_file.exists():
                with open(cb_file) as f:
                    return json.load(f)
        except Exception:
            pass
        return {"status": "unknown"}

    def _get_divergence_summary(self) -> dict[str, Any]:
        """Get live vs backtest divergence summary."""
        try:
            div_file = Path("data/live_vs_backtest_state.json")
            if div_file.exists():
                with open(div_file) as f:
                    data = json.load(f)
                    # Summarize divergence data
                    summary = {}
                    for strategy, info in data.items():
                        live_perf = info.get("live_performance", [])
                        if live_perf:
                            recent = live_perf[-5:]
                            summary[strategy] = {
                                "periods": len(live_perf),
                                "recent_alerts": sum(
                                    1
                                    for p in recent
                                    if p.get("alert_level") in ["WARNING", "CRITICAL"]
                                ),
                            }
                    return summary
        except Exception:
            pass
        return {}

    def _format_alert_message(self, alert: dict) -> str:
        """Format alert for display."""
        alert_type = alert.get("type", "unknown")
        if alert_type == "high_error_rate":
            return f"{alert.get('gate')} error rate {alert.get('value', 0):.1f}%"
        elif alert_type == "high_latency":
            return f"{alert.get('gate')} latency {alert.get('value', 0):.0f}ms"
        elif alert_type == "low_pass_rate":
            return f"{alert.get('gate')} pass rate {alert.get('value', 0):.1f}%"
        elif alert_type == "circuit_breaker":
            return f"CB {alert.get('tier')}: {alert.get('action')}"
        elif alert_type == "divergence":
            return f"{alert.get('strategy')}.{alert.get('metric')} diverged {alert.get('divergence_pct', 0):.0%}"
        return str(alert)

    def _cb_tier_to_severity(self, tier: str) -> str:
        """Convert circuit breaker tier to alert severity."""
        if tier in ["HALT", "CRITICAL"]:
            return "critical"
        elif tier == "WARNING":
            return "warning"
        return "info"

    def _load_metrics(self) -> None:
        """Load metrics from disk."""
        if not self.metrics_file.exists():
            return

        try:
            with open(self.metrics_file) as f:
                data = json.load(f)

            # Restore gate metrics
            for gate, gdata in data.get("gate_metrics", {}).items():
                self.gate_metrics[gate] = GateMetrics(
                    gate_name=gate,
                    total_evaluations=gdata.get("total_evaluations", 0),
                    passes=gdata.get("passes", 0),
                    rejections=gdata.get("rejections", 0),
                    errors=gdata.get("errors", 0),
                    avg_latency_ms=gdata.get("avg_latency_ms", 0),
                    p95_latency_ms=gdata.get("p95_latency_ms", 0),
                    p99_latency_ms=gdata.get("p99_latency_ms", 0),
                )

            # Restore regime metrics
            for regime, rdata in data.get("regime_metrics", {}).items():
                self.regime_metrics[regime] = RegimeMetrics(
                    regime=regime,
                    observations=rdata.get("observations", 0),
                    avg_signal_strength=rdata.get("avg_signal_strength", 0),
                    trades_executed=rdata.get("trades_executed", 0),
                    win_rate=rdata.get("win_rate", 0),
                    avg_pnl=rdata.get("avg_pnl", 0),
                )

            self.alerts = data.get("alerts", [])

            logger.info(f"Loaded SRE metrics from {self.metrics_file}")

        except Exception as e:
            logger.error(f"Error loading SRE metrics: {e}")

    def _save_metrics(self) -> None:
        """Save metrics to disk."""
        try:
            self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "timestamp": datetime.now().isoformat(),
                "gate_metrics": {
                    gate: {
                        "total_evaluations": m.total_evaluations,
                        "passes": m.passes,
                        "rejections": m.rejections,
                        "errors": m.errors,
                        "avg_latency_ms": m.avg_latency_ms,
                        "p95_latency_ms": m.p95_latency_ms,
                        "p99_latency_ms": m.p99_latency_ms,
                    }
                    for gate, m in self.gate_metrics.items()
                },
                "regime_metrics": {
                    regime: {
                        "observations": m.observations,
                        "avg_signal_strength": m.avg_signal_strength,
                        "trades_executed": m.trades_executed,
                        "win_rate": m.win_rate,
                        "avg_pnl": m.avg_pnl,
                    }
                    for regime, m in self.regime_metrics.items()
                },
                "alerts": self.alerts[-50:],
            }

            with open(self.metrics_file, "w") as f:
                json.dump(data, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Error saving SRE metrics: {e}")


# Global instance
_GLOBAL_SRE_MONITOR: SREMonitor | None = None


def get_sre_monitor() -> SREMonitor:
    """Get or create global SRE monitor."""
    global _GLOBAL_SRE_MONITOR
    if _GLOBAL_SRE_MONITOR is None:
        _GLOBAL_SRE_MONITOR = SREMonitor()
    return _GLOBAL_SRE_MONITOR


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=" * 80)
    print("SRE MONITOR DEMO")
    print("=" * 80)

    monitor = SREMonitor()

    # Simulate some events
    for i in range(100):
        monitor.record_gate_event("momentum", "pass" if i % 3 != 0 else "reject", latency_ms=50 + i)
        monitor.record_gate_event(
            "rl_filter", "pass" if i % 4 != 0 else "reject", latency_ms=30 + i
        )
        monitor.record_gate_event("llm", "pass" if i % 5 != 0 else "reject", latency_ms=200 + i * 2)
        monitor.record_gate_event("risk", "pass" if i % 10 != 0 else "reject", latency_ms=10 + i)

    # Simulate regime observations
    for regime in ["bull_low_vol", "sideways", "bear_high_vol"]:
        for _ in range(20):
            monitor.record_regime_observation(
                regime=regime,
                signal_strength=0.5 + 0.3 * (1 if regime.startswith("bull") else -0.5),
                trade_executed=True,
                pnl=10 if regime.startswith("bull") else -5,
            )

    # Get dashboard data
    dashboard = monitor.get_dashboard_data()

    print("\nSystem Health:")
    print(f"  Status: {dashboard['health']['status']}")
    print(f"  Score: {dashboard['health']['score']}")

    print("\nGate Metrics:")
    for gate, metrics in dashboard["gates"].items():
        print(
            f"  {gate}: pass_rate={metrics['pass_rate']:.1f}%, p95_latency={metrics['p95_latency_ms']:.0f}ms"
        )

    print("\nRegime Metrics:")
    for regime, metrics in dashboard["regimes"].items():
        print(f"  {regime}: win_rate={metrics['win_rate']:.1f}%, trades={metrics['trades']}")

    print("\nSLI Compliance:")
    for sli in dashboard["slis"]:
        status = "✅" if sli["compliant"] else "❌"
        print(f"  {status} {sli['name']}: {sli['current']:.2f} (target: {sli['target']})")

    print("\n" + "=" * 80)
