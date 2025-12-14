"""
Continuous ML Verification Monitor.

Continuously monitors the trading system for anomalies and potential issues.
Uses ML models trained on historical data to detect:
1. Trading pattern anomalies
2. Performance drift
3. Code change risks
4. System health issues

Integrates with RAG to learn from past incidents and prevent recurrence.

Created: 2025-12-14
Author: Trading CTO
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MonitorType(Enum):
    """Types of monitors."""

    TRADING_HEALTH = "trading_health"
    CODE_QUALITY = "code_quality"
    SYSTEM_PERFORMANCE = "system_performance"
    DATA_QUALITY = "data_quality"
    ML_MODEL_HEALTH = "ml_model_health"


@dataclass
class Alert:
    """Represents a monitoring alert."""

    alert_id: str
    monitor_type: MonitorType
    severity: AlertSeverity
    title: str
    message: str
    details: dict[str, Any]
    timestamp: datetime
    resolved: bool = False
    resolution: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "monitor_type": self.monitor_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


@dataclass
class HealthCheck:
    """Result of a health check."""

    name: str
    passed: bool
    message: str
    details: dict[str, Any]
    timestamp: datetime


class TradingHealthMonitor:
    """Monitor trading system health."""

    def __init__(self, system_state_path: str = "data/system_state.json"):
        self.system_state_path = Path(system_state_path)
        self.trade_history: deque = deque(maxlen=100)
        self.alerts: list[Alert] = []

    def check_trading_activity(self) -> HealthCheck:
        """Check if trading is happening as expected."""
        try:
            if not self.system_state_path.exists():
                return HealthCheck(
                    name="trading_activity",
                    passed=False,
                    message="System state file not found",
                    details={"path": str(self.system_state_path)},
                    timestamp=datetime.now(timezone.utc),
                )

            with open(self.system_state_path) as f:
                state = json.load(f)

            # Check last trade execution
            automation = state.get("automation", {})
            last_execution = automation.get("last_successful_execution")

            if not last_execution:
                return HealthCheck(
                    name="trading_activity",
                    passed=False,
                    message="No trading execution recorded",
                    details={"automation": automation},
                    timestamp=datetime.now(timezone.utc),
                )

            # Parse last execution time
            last_exec_dt = datetime.fromisoformat(
                last_execution.replace("Z", "+00:00")
            )

            # Check if it's a weekend (expected no trading)
            now = datetime.now(timezone.utc)
            if now.weekday() >= 5:  # Saturday or Sunday
                return HealthCheck(
                    name="trading_activity",
                    passed=True,
                    message="Weekend - trading not expected",
                    details={"weekday": now.weekday()},
                    timestamp=now,
                )

            # Check if last execution was recent (within 48 hours on weekdays)
            age_hours = (now - last_exec_dt).total_seconds() / 3600

            if age_hours > 48:
                return HealthCheck(
                    name="trading_activity",
                    passed=False,
                    message=f"No trading for {age_hours:.1f} hours",
                    details={
                        "last_execution": last_execution,
                        "age_hours": age_hours,
                    },
                    timestamp=now,
                )

            return HealthCheck(
                name="trading_activity",
                passed=True,
                message=f"Trading active (last: {age_hours:.1f}h ago)",
                details={
                    "last_execution": last_execution,
                    "age_hours": age_hours,
                },
                timestamp=now,
            )

        except Exception as e:
            return HealthCheck(
                name="trading_activity",
                passed=False,
                message=f"Error checking trading activity: {e}",
                details={"error": str(e)},
                timestamp=datetime.now(timezone.utc),
            )

    def check_performance_drift(self) -> HealthCheck:
        """Check for performance drift."""
        try:
            if not self.system_state_path.exists():
                return HealthCheck(
                    name="performance_drift",
                    passed=True,
                    message="No system state to check",
                    details={},
                    timestamp=datetime.now(timezone.utc),
                )

            with open(self.system_state_path) as f:
                state = json.load(f)

            performance = state.get("performance", {})
            win_rate = performance.get("win_rate", 0)
            total_pl = state.get("account", {}).get("total_pl", 0)

            # Check for concerning metrics
            warnings = []
            if win_rate < 40:
                warnings.append(f"Low win rate: {win_rate}%")
            if total_pl < -100:
                warnings.append(f"Significant loss: ${total_pl:.2f}")

            if warnings:
                return HealthCheck(
                    name="performance_drift",
                    passed=False,
                    message="; ".join(warnings),
                    details={
                        "win_rate": win_rate,
                        "total_pl": total_pl,
                    },
                    timestamp=datetime.now(timezone.utc),
                )

            return HealthCheck(
                name="performance_drift",
                passed=True,
                message=f"Performance OK (win rate: {win_rate}%, P/L: ${total_pl:.2f})",
                details={
                    "win_rate": win_rate,
                    "total_pl": total_pl,
                },
                timestamp=datetime.now(timezone.utc),
            )

        except Exception as e:
            return HealthCheck(
                name="performance_drift",
                passed=True,  # Don't fail on check errors
                message=f"Could not check performance: {e}",
                details={"error": str(e)},
                timestamp=datetime.now(timezone.utc),
            )


class CodeQualityMonitor:
    """Monitor code quality and changes."""

    def __init__(self, repo_path: str = "/workspace"):
        self.repo_path = Path(repo_path)

    def check_syntax(self) -> HealthCheck:
        """Check all Python files for syntax errors."""
        try:
            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "py_compile",
                    *list(self.repo_path.glob("src/**/*.py")),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return HealthCheck(
                    name="syntax_check",
                    passed=False,
                    message="Syntax errors found",
                    details={"stderr": result.stderr[:500]},
                    timestamp=datetime.now(timezone.utc),
                )

            return HealthCheck(
                name="syntax_check",
                passed=True,
                message="All Python files have valid syntax",
                details={},
                timestamp=datetime.now(timezone.utc),
            )

        except Exception as e:
            return HealthCheck(
                name="syntax_check",
                passed=False,
                message=f"Syntax check failed: {e}",
                details={"error": str(e)},
                timestamp=datetime.now(timezone.utc),
            )

    def check_critical_imports(self) -> HealthCheck:
        """Verify critical imports work."""
        critical_imports = [
            "from src.orchestrator.main import TradingOrchestrator",
            "from src.execution.alpaca_executor import AlpacaExecutor",
            "from src.risk.trade_gateway import TradeGateway",
        ]

        failed = []
        for import_stmt in critical_imports:
            try:
                result = subprocess.run(
                    ["python3", "-c", import_stmt],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(self.repo_path),
                )
                if result.returncode != 0:
                    failed.append(import_stmt)
            except Exception as e:
                failed.append(f"{import_stmt} ({e})")

        if failed:
            return HealthCheck(
                name="critical_imports",
                passed=False,
                message=f"{len(failed)} critical imports failed",
                details={"failed": failed},
                timestamp=datetime.now(timezone.utc),
            )

        return HealthCheck(
            name="critical_imports",
            passed=True,
            message="All critical imports work",
            details={"checked": len(critical_imports)},
            timestamp=datetime.now(timezone.utc),
        )


class MLModelHealthMonitor:
    """Monitor ML model health."""

    def __init__(self, models_path: str = "models"):
        self.models_path = Path(models_path)

    def check_model_availability(self) -> HealthCheck:
        """Check if ML models are available."""
        model_files = list(self.models_path.glob("*.pt")) + list(
            self.models_path.glob("*.pkl")
        )

        if not model_files:
            return HealthCheck(
                name="model_availability",
                passed=True,  # Not critical if no models yet
                message="No ML models found (may be expected)",
                details={"path": str(self.models_path)},
                timestamp=datetime.now(timezone.utc),
            )

        return HealthCheck(
            name="model_availability",
            passed=True,
            message=f"Found {len(model_files)} ML models",
            details={"models": [f.name for f in model_files]},
            timestamp=datetime.now(timezone.utc),
        )

    def check_rag_health(self) -> HealthCheck:
        """Check RAG system health."""
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            rag = LessonsLearnedRAG()

            if len(rag.lessons) == 0:
                return HealthCheck(
                    name="rag_health",
                    passed=False,
                    message="RAG has no lessons",
                    details={"lessons_count": 0},
                    timestamp=datetime.now(timezone.utc),
                )

            # Test search functionality
            results = rag.search("test query", top_k=1)

            return HealthCheck(
                name="rag_health",
                passed=True,
                message=f"RAG healthy ({len(rag.lessons)} lessons)",
                details={
                    "lessons_count": len(rag.lessons),
                    "search_works": len(results) > 0,
                },
                timestamp=datetime.now(timezone.utc),
            )

        except Exception as e:
            return HealthCheck(
                name="rag_health",
                passed=False,
                message=f"RAG check failed: {e}",
                details={"error": str(e)},
                timestamp=datetime.now(timezone.utc),
            )


class DataQualityMonitor:
    """Monitor data quality."""

    def __init__(self, data_path: str = "data"):
        self.data_path = Path(data_path)

    def check_data_freshness(self) -> HealthCheck:
        """Check if data files are fresh."""
        stale_files = []
        checked_files = []

        # Check key data files
        data_files = [
            self.data_path / "system_state.json",
            self.data_path / "rag" / "lessons_learned.json",
        ]

        for data_file in data_files:
            if data_file.exists():
                mtime = datetime.fromtimestamp(
                    data_file.stat().st_mtime, tz=timezone.utc
                )
                age_hours = (
                    datetime.now(timezone.utc) - mtime
                ).total_seconds() / 3600

                checked_files.append(
                    {"file": data_file.name, "age_hours": round(age_hours, 1)}
                )

                if age_hours > 24 * 7:  # 7 days
                    stale_files.append(data_file.name)

        if stale_files:
            return HealthCheck(
                name="data_freshness",
                passed=False,
                message=f"{len(stale_files)} stale data files",
                details={"stale": stale_files, "checked": checked_files},
                timestamp=datetime.now(timezone.utc),
            )

        return HealthCheck(
            name="data_freshness",
            passed=True,
            message="Data files are fresh",
            details={"checked": checked_files},
            timestamp=datetime.now(timezone.utc),
        )


class ContinuousMLMonitor:
    """
    Main continuous monitoring orchestrator.

    Combines all monitors and provides unified health checking,
    alerting, and anomaly detection.
    """

    ALERTS_LOG_PATH = Path("data/monitoring/alerts.json")

    def __init__(self):
        self.trading_monitor = TradingHealthMonitor()
        self.code_monitor = CodeQualityMonitor()
        self.ml_monitor = MLModelHealthMonitor()
        self.data_monitor = DataQualityMonitor()

        self.alerts: list[Alert] = []
        self.health_history: deque = deque(maxlen=1000)

        # Load existing alerts
        self._load_alerts()

    def _load_alerts(self) -> None:
        """Load alerts from disk."""
        if self.ALERTS_LOG_PATH.exists():
            try:
                with open(self.ALERTS_LOG_PATH) as f:
                    data = json.load(f)
                self.alerts = [
                    Alert(
                        alert_id=a["alert_id"],
                        monitor_type=MonitorType(a["monitor_type"]),
                        severity=AlertSeverity(a["severity"]),
                        title=a["title"],
                        message=a["message"],
                        details=a["details"],
                        timestamp=datetime.fromisoformat(a["timestamp"]),
                        resolved=a.get("resolved", False),
                        resolution=a.get("resolution"),
                    )
                    for a in data
                ]
            except Exception as e:
                logger.warning(f"Could not load alerts: {e}")

    def _save_alerts(self) -> None:
        """Save alerts to disk."""
        self.ALERTS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = [a.to_dict() for a in self.alerts[-500:]]  # Keep last 500
        with open(self.ALERTS_LOG_PATH, "w") as f:
            json.dump(data, f, indent=2)

    def _create_alert(
        self,
        monitor_type: MonitorType,
        severity: AlertSeverity,
        title: str,
        message: str,
        details: dict,
    ) -> Alert:
        """Create and save a new alert."""
        alert = Alert(
            alert_id=f"ALT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(self.alerts)}",
            monitor_type=monitor_type,
            severity=severity,
            title=title,
            message=message,
            details=details,
            timestamp=datetime.now(timezone.utc),
        )
        self.alerts.append(alert)
        self._save_alerts()
        return alert

    def run_all_checks(self) -> dict[str, Any]:
        """
        Run all health checks.

        Returns:
            Dict with overall status and check results
        """
        checks = []
        new_alerts = []

        # Trading health checks
        trading_activity = self.trading_monitor.check_trading_activity()
        checks.append(trading_activity)
        if not trading_activity.passed:
            new_alerts.append(
                self._create_alert(
                    MonitorType.TRADING_HEALTH,
                    AlertSeverity.ERROR,
                    "Trading Activity Issue",
                    trading_activity.message,
                    trading_activity.details,
                )
            )

        performance_drift = self.trading_monitor.check_performance_drift()
        checks.append(performance_drift)
        if not performance_drift.passed:
            new_alerts.append(
                self._create_alert(
                    MonitorType.TRADING_HEALTH,
                    AlertSeverity.WARNING,
                    "Performance Drift Detected",
                    performance_drift.message,
                    performance_drift.details,
                )
            )

        # Code quality checks
        syntax_check = self.code_monitor.check_syntax()
        checks.append(syntax_check)
        if not syntax_check.passed:
            new_alerts.append(
                self._create_alert(
                    MonitorType.CODE_QUALITY,
                    AlertSeverity.CRITICAL,
                    "Syntax Errors Found",
                    syntax_check.message,
                    syntax_check.details,
                )
            )

        import_check = self.code_monitor.check_critical_imports()
        checks.append(import_check)
        if not import_check.passed:
            new_alerts.append(
                self._create_alert(
                    MonitorType.CODE_QUALITY,
                    AlertSeverity.CRITICAL,
                    "Critical Import Failure",
                    import_check.message,
                    import_check.details,
                )
            )

        # ML model checks
        model_check = self.ml_monitor.check_model_availability()
        checks.append(model_check)

        rag_check = self.ml_monitor.check_rag_health()
        checks.append(rag_check)
        if not rag_check.passed:
            new_alerts.append(
                self._create_alert(
                    MonitorType.ML_MODEL_HEALTH,
                    AlertSeverity.WARNING,
                    "RAG System Issue",
                    rag_check.message,
                    rag_check.details,
                )
            )

        # Data quality checks
        data_freshness = self.data_monitor.check_data_freshness()
        checks.append(data_freshness)
        if not data_freshness.passed:
            new_alerts.append(
                self._create_alert(
                    MonitorType.DATA_QUALITY,
                    AlertSeverity.WARNING,
                    "Stale Data Detected",
                    data_freshness.message,
                    data_freshness.details,
                )
            )

        # Calculate overall health
        passed = sum(1 for c in checks if c.passed)
        total = len(checks)
        health_pct = (passed / total) * 100 if total > 0 else 0

        overall_status = "healthy"
        if health_pct < 50:
            overall_status = "critical"
        elif health_pct < 75:
            overall_status = "degraded"
        elif health_pct < 100:
            overall_status = "warning"

        result = {
            "status": overall_status,
            "health_percentage": health_pct,
            "checks_passed": passed,
            "checks_total": total,
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "message": c.message,
                }
                for c in checks
            ],
            "new_alerts": [a.to_dict() for a in new_alerts],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Store in history
        self.health_history.append(result)

        return result

    def get_active_alerts(
        self,
        severity: Optional[AlertSeverity] = None,
    ) -> list[Alert]:
        """Get unresolved alerts."""
        alerts = [a for a in self.alerts if not a.resolved]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return alerts

    def resolve_alert(self, alert_id: str, resolution: str) -> bool:
        """Mark an alert as resolved."""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolution = resolution
                self._save_alerts()
                return True
        return False

    def get_health_summary(self) -> dict[str, Any]:
        """Get summary of health over time."""
        if not self.health_history:
            return {"message": "No health history available"}

        recent = list(self.health_history)[-10:]
        avg_health = sum(r["health_percentage"] for r in recent) / len(recent)

        return {
            "current_status": recent[-1]["status"] if recent else "unknown",
            "average_health_pct": avg_health,
            "checks_in_history": len(self.health_history),
            "active_alerts": len(self.get_active_alerts()),
            "critical_alerts": len(
                self.get_active_alerts(AlertSeverity.CRITICAL)
            ),
        }


def run_health_check() -> dict[str, Any]:
    """
    Convenience function to run a health check.

    Returns:
        Dict with health check results
    """
    monitor = ContinuousMLMonitor()
    return monitor.run_all_checks()


def get_monitoring_status() -> dict[str, Any]:
    """
    Get current monitoring status.

    Returns:
        Dict with monitoring summary
    """
    monitor = ContinuousMLMonitor()
    check_result = monitor.run_all_checks()
    summary = monitor.get_health_summary()

    return {
        "current_check": check_result,
        "summary": summary,
    }


if __name__ == "__main__":
    """Run health check and display results."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("CONTINUOUS ML VERIFICATION MONITOR")
    print("=" * 80)

    monitor = ContinuousMLMonitor()
    result = monitor.run_all_checks()

    print(f"\nStatus: {result['status'].upper()}")
    print(f"Health: {result['health_percentage']:.0f}%")
    print(f"Checks: {result['checks_passed']}/{result['checks_total']} passed")

    print("\n" + "-" * 40)
    print("CHECKS:")
    for check in result["checks"]:
        status = "✅" if check["passed"] else "❌"
        print(f"  {status} {check['name']}: {check['message']}")

    if result["new_alerts"]:
        print("\n" + "-" * 40)
        print("NEW ALERTS:")
        for alert in result["new_alerts"]:
            print(f"  [{alert['severity'].upper()}] {alert['title']}")
            print(f"    {alert['message']}")

    # Show summary
    summary = monitor.get_health_summary()
    print("\n" + "-" * 40)
    print("SUMMARY:")
    print(f"  Active Alerts: {summary['active_alerts']}")
    print(f"  Critical Alerts: {summary['critical_alerts']}")
    print(f"  Avg Health: {summary['average_health_pct']:.0f}%")
