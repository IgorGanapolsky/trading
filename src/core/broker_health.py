"""
Broker Health Monitoring Module

Monitors broker connectivity, account status, and API health.
Provides automated health checks and failure alerts.

As CTO/CFO: Critical infrastructure monitoring for trading execution reliability.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BrokerStatus(Enum):
    """Broker health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    UNKNOWN = "unknown"


@dataclass
class BrokerHealthMetrics:
    """Broker health metrics tracking."""

    broker_name: str
    status: BrokerStatus
    last_successful_connection: datetime | None = None
    last_failed_connection: datetime | None = None
    consecutive_failures: int = 0
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    avg_response_time_ms: float = 0.0
    last_error: str | None = None
    account_status: str | None = None
    buying_power: float | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_checks == 0:
            return 0.0
        return (self.successful_checks / self.total_checks) * 100.0

    @property
    def is_healthy(self) -> bool:
        """Determine if broker is healthy."""
        if self.status == BrokerStatus.HEALTHY:
            return True
        return bool(self.status == BrokerStatus.DEGRADED and self.consecutive_failures < 3)


class BrokerHealthMonitor:
    """
    Monitors broker health and connectivity.

    Provides automated health checks, failure tracking, and alerting.
    """

    def __init__(self, broker_name: str = "alpaca"):
        self.broker_name = broker_name.lower()
        self.metrics = BrokerHealthMetrics(
            broker_name=self.broker_name, status=BrokerStatus.UNKNOWN
        )
        self._health_log_file = os.path.join(
            os.getenv("MARKET_DATA_CACHE_DIR", "data/cache"),
            f"{self.broker_name}_health.jsonl",
        )

    def check_health(
        self,
        retries: int = 3,
        backoff_seconds: float = 2.0,
    ) -> BrokerHealthMetrics:
        """
        Perform comprehensive health check.

        Returns:
            BrokerHealthMetrics with current status
        """
        import time

        start_time = time.time()
        errors: list[str] = []
        account_info = {}
        elapsed_ms = 0.0

        # Only count one health-check regardless of retries
        self.metrics.total_checks += 1

        for attempt in range(1, max(1, retries) + 1):
            try:
                from src.core.alpaca_trader import AlpacaTrader

                trader = AlpacaTrader(paper=True)
                account_info = trader.get_account_info()
                elapsed_ms = (time.time() - start_time) * 1000

                # Success: reset failure counters and break
                self.metrics.last_successful_connection = datetime.now()
                self.metrics.successful_checks += 1
                self.metrics.consecutive_failures = 0
                self.metrics.last_error = None
                break
            except Exception as e:  # noqa: PERF203
                errors.append(str(e))
                elapsed_ms = (time.time() - start_time) * 1000

                # If not last attempt, wait with exponential backoff then retry
                if attempt < retries:
                    sleep_for = backoff_seconds * attempt
                    time.sleep(sleep_for)
                    continue

                # Exhausted retries: record failure metrics
                self.metrics.last_failed_connection = datetime.now()
                self.metrics.failed_checks += 1
                self.metrics.consecutive_failures += 1
                self.metrics.last_error = "; ".join(errors) or str(e)
                self.metrics.status = BrokerStatus.FAILING

                self._log_health_check(
                    success=False, response_time_ms=elapsed_ms, error=self.metrics.last_error
                )
                logger.error(
                    f"❌ Broker health check failed after {attempt} attempt(s): {self.broker_name} "
                    f"(consecutive failures: {self.metrics.consecutive_failures}, "
                    f"errors: {self.metrics.last_error})"
                )
                return self.metrics

        # If we reached here, connection succeeded on some attempt
        self.metrics.account_status = account_info.get("status", "UNKNOWN")
        self.metrics.buying_power = account_info.get("buying_power", 0.0)

        # Update rolling average response time
        self.metrics.avg_response_time_ms = (
            self.metrics.avg_response_time_ms * (self.metrics.total_checks - 1) + elapsed_ms
        ) / self.metrics.total_checks

        # Determine status
        if account_info.get("status") == "ACTIVE" and not account_info.get(
            "trading_blocked", False
        ):
            self.metrics.status = BrokerStatus.HEALTHY
        elif account_info.get("trading_blocked", False):
            self.metrics.status = BrokerStatus.DEGRADED
            self.metrics.last_error = "Trading blocked"
        else:
            self.metrics.status = BrokerStatus.DEGRADED
            self.metrics.last_error = f"Account status: {account_info.get('status')}"

        # Log health check
        self._log_health_check(success=True, response_time_ms=elapsed_ms)

        logger.info(
            f"✅ Broker health check passed (attempts: {min(retries, len(errors) + 1)}): "
            f"{self.broker_name} (status: {self.metrics.status.value}, "
            f"response: {elapsed_ms:.2f}ms)"
        )

        return self.metrics

    def _log_health_check(self, success: bool, response_time_ms: float, error: str | None = None):
        """Log health check result to file."""
        import json
        from pathlib import Path

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "broker": self.broker_name,
            "success": success,
            "response_time_ms": round(response_time_ms, 2),
            "status": self.metrics.status.value,
            "consecutive_failures": self.metrics.consecutive_failures,
            "error": error,
            "account_status": self.metrics.account_status,
            "buying_power": self.metrics.buying_power,
        }

        log_file = Path(self._health_log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def get_health_summary(self) -> dict[str, Any]:
        """Get formatted health summary."""
        return {
            "broker": self.broker_name,
            "status": self.metrics.status.value,
            "is_healthy": self.metrics.is_healthy,
            "success_rate": round(self.metrics.success_rate, 2),
            "total_checks": self.metrics.total_checks,
            "successful_checks": self.metrics.successful_checks,
            "failed_checks": self.metrics.failed_checks,
            "consecutive_failures": self.metrics.consecutive_failures,
            "avg_response_time_ms": round(self.metrics.avg_response_time_ms, 2),
            "last_successful_connection": (
                self.metrics.last_successful_connection.isoformat()
                if self.metrics.last_successful_connection
                else None
            ),
            "last_failed_connection": (
                self.metrics.last_failed_connection.isoformat()
                if self.metrics.last_failed_connection
                else None
            ),
            "last_error": self.metrics.last_error,
            "account_status": self.metrics.account_status,
            "buying_power": self.metrics.buying_power,
        }

    def should_alert(self) -> bool:
        """Determine if alert should be sent."""
        # Alert if consecutive failures >= 3
        if self.metrics.consecutive_failures >= 3:
            return True

        # Alert if status is FAILING
        if self.metrics.status == BrokerStatus.FAILING:
            return True

        # Alert if success rate drops below 50% in recent checks
        return bool(self.metrics.total_checks >= 10 and self.metrics.success_rate < 50.0)

    def get_alert_message(self) -> str | None:
        """Generate alert message if needed."""
        if not self.should_alert():
            return None

        if self.metrics.consecutive_failures >= 3:
            return (
                f"🚨 CRITICAL: Broker {self.broker_name} has failed "
                f"{self.metrics.consecutive_failures} consecutive health checks.\n"
                f"Last error: {self.metrics.last_error}\n"
                f"Trading execution may be blocked."
            )

        if self.metrics.status == BrokerStatus.FAILING:
            return (
                f"⚠️ WARNING: Broker {self.broker_name} is in FAILING status.\n"
                f"Success rate: {self.metrics.success_rate:.1f}%\n"
                f"Last error: {self.metrics.last_error}"
            )

        return None
