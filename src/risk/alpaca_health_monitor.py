"""
Alpaca Health Monitor - API Failover and Alert System

Provides redundancy against Alpaca failures:
1. Real-time API health checks with retry logic
2. Exponential backoff on failures (2s, 4s, 8s, 16s)
3. Alert system (logs, webhook, email-ready)
4. Circuit breaker pattern - stop trading if API unstable
5. Order queue for failed orders (retry later)

Critical gap addressed:
- "If Alpaca decides to fuck us" - CEO concern Dec 8, 2025
- No alerts if API fails
- No retry logic
- No order queue for failed trades

Author: Trading System CTO
Created: 2025-12-08
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """API health status levels."""

    HEALTHY = "healthy"  # All systems go
    DEGRADED = "degraded"  # Slow but working
    UNHEALTHY = "unhealthy"  # Failing, retrying
    CRITICAL = "critical"  # Multiple failures, stop trading
    UNKNOWN = "unknown"  # Not yet checked


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    status: HealthStatus
    latency_ms: float
    error: str | None
    timestamp: datetime
    consecutive_failures: int
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "consecutive_failures": self.consecutive_failures,
            "details": self.details,
        }


@dataclass
class QueuedOrder:
    """Order queued for retry after API failure."""

    symbol: str
    amount_usd: float
    side: str
    tier: str
    created_at: datetime
    retry_count: int = 0
    max_retries: int = 3
    last_error: str | None = None


class AlpacaHealthMonitor:
    """
    Monitor Alpaca API health and provide failover capabilities.

    Features:
    - Periodic health checks
    - Retry with exponential backoff
    - Circuit breaker (stop trading after N failures)
    - Order queue for failed trades
    - Alert system integration
    """

    # Thresholds
    LATENCY_WARNING_MS = 2000  # Warn if API > 2 seconds
    LATENCY_CRITICAL_MS = 5000  # Critical if API > 5 seconds
    MAX_CONSECUTIVE_FAILURES = 3  # Trip circuit breaker after 3 failures
    CIRCUIT_BREAKER_RESET_MINUTES = 5  # Reset circuit breaker after 5 min

    # Retry settings
    MAX_RETRIES = 4
    BASE_RETRY_DELAY_SECONDS = 2  # 2s, 4s, 8s, 16s

    def __init__(
        self,
        alpaca_client=None,
        alert_webhook_url: str | None = None,
        order_queue_path: Path = Path("data/failed_orders_queue.json"),
    ):
        """
        Initialize the health monitor.

        Args:
            alpaca_client: Alpaca TradingClient instance
            alert_webhook_url: Webhook URL for alerts (Slack, Discord, etc.)
            order_queue_path: Path to persist failed orders
        """
        self.client = alpaca_client
        self.alert_webhook_url = alert_webhook_url or os.getenv("ALERT_WEBHOOK_URL")
        self.order_queue_path = order_queue_path

        # State
        self.consecutive_failures = 0
        self.last_successful_check: datetime | None = None
        self.circuit_breaker_tripped = False
        self.circuit_breaker_tripped_at: datetime | None = None
        self.order_queue: list[QueuedOrder] = []

        # Load persisted order queue
        self._load_order_queue()

        logger.info("AlpacaHealthMonitor initialized")

    def check_health(self) -> HealthCheckResult:
        """
        Perform a health check on Alpaca API.

        Returns:
            HealthCheckResult with status, latency, and any errors
        """
        start_time = time.time()
        error = None
        status = HealthStatus.UNKNOWN
        details = {}

        try:
            if not self.client:
                # Try to create client if not provided
                from alpaca.trading.client import TradingClient

                api_key = os.getenv("ALPACA_API_KEY")
                api_secret = os.getenv("ALPACA_SECRET_KEY")

                if not api_key or not api_secret:
                    raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY not set")

                self.client = TradingClient(api_key, api_secret, paper=True)

            # Check account (lightweight API call)
            account = self.client.get_account()

            latency_ms = (time.time() - start_time) * 1000

            # Determine status based on latency
            if latency_ms < self.LATENCY_WARNING_MS:
                status = HealthStatus.HEALTHY
                self.consecutive_failures = 0
                self.last_successful_check = datetime.now()
            elif latency_ms < self.LATENCY_CRITICAL_MS:
                status = HealthStatus.DEGRADED
                logger.warning(f"Alpaca API degraded: {latency_ms:.0f}ms latency")
            else:
                status = HealthStatus.DEGRADED
                logger.warning(f"Alpaca API slow: {latency_ms:.0f}ms latency")

            # Collect account details
            details = {
                "equity": float(account.equity),
                "buying_power": float(account.buying_power),
                "trading_blocked": account.trading_blocked,
                "account_blocked": account.account_blocked,
            }

            # Check if trading is blocked
            if account.trading_blocked or account.account_blocked:
                status = HealthStatus.CRITICAL
                error = "Trading or account is blocked by Alpaca"
                self._send_alert(f"CRITICAL: {error}", details)

            # Reset circuit breaker if healthy
            if status == HealthStatus.HEALTHY:
                self._reset_circuit_breaker()

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error = str(e)
            self.consecutive_failures += 1

            if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                status = HealthStatus.CRITICAL
                self._trip_circuit_breaker(error)
            else:
                status = HealthStatus.UNHEALTHY

            logger.error(f"Alpaca health check failed ({self.consecutive_failures}x): {error}")

        return HealthCheckResult(
            status=status,
            latency_ms=latency_ms,
            error=error,
            timestamp=datetime.now(),
            consecutive_failures=self.consecutive_failures,
            details=details,
        )

    def execute_with_retry(
        self,
        operation: Callable[[], Any],
        operation_name: str = "API call",
    ) -> tuple[bool, Any, str | None]:
        """
        Execute an operation with retry logic and exponential backoff.

        Args:
            operation: Callable to execute
            operation_name: Name for logging

        Returns:
            Tuple of (success, result, error_message)
        """
        if self.circuit_breaker_tripped:
            if not self._should_reset_circuit_breaker():
                logger.warning(f"Circuit breaker tripped - skipping {operation_name}")
                return False, None, "Circuit breaker tripped - API unstable"

        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                result = operation()

                # Success - reset failure count
                self.consecutive_failures = 0
                self.last_successful_check = datetime.now()

                if attempt > 0:
                    logger.info(f"{operation_name} succeeded on attempt {attempt + 1}")

                return True, result, None

            except Exception as e:
                last_error = str(e)
                self.consecutive_failures += 1

                if attempt < self.MAX_RETRIES - 1:
                    delay = self.BASE_RETRY_DELAY_SECONDS * (2**attempt)
                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"{operation_name} failed after {self.MAX_RETRIES} attempts: {e}")

        # All retries failed
        if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            self._trip_circuit_breaker(last_error)

        return False, None, last_error

    def queue_failed_order(
        self,
        symbol: str,
        amount_usd: float,
        side: str,
        tier: str,
        error: str,
    ) -> None:
        """
        Queue a failed order for later retry.

        Args:
            symbol: Trading symbol
            amount_usd: Order amount
            side: 'buy' or 'sell'
            tier: Trading tier
            error: Error that caused the failure
        """
        order = QueuedOrder(
            symbol=symbol,
            amount_usd=amount_usd,
            side=side,
            tier=tier,
            created_at=datetime.now(),
            last_error=error,
        )

        self.order_queue.append(order)
        self._save_order_queue()

        logger.info(f"Order queued for retry: {side} {symbol} ${amount_usd:.2f}")
        self._send_alert(
            f"Order queued due to API failure: {side} {symbol} ${amount_usd:.2f}",
            {"error": error, "queue_size": len(self.order_queue)},
        )

    def process_order_queue(self, executor: Callable[[QueuedOrder], bool]) -> int:
        """
        Process queued orders using provided executor.

        Args:
            executor: Function that takes QueuedOrder and returns success bool

        Returns:
            Number of orders successfully processed
        """
        if not self.order_queue:
            return 0

        # Check if API is healthy first
        health = self.check_health()
        if health.status in (HealthStatus.CRITICAL, HealthStatus.UNHEALTHY):
            logger.warning("API unhealthy - skipping order queue processing")
            return 0

        processed = 0
        remaining = []

        for order in self.order_queue:
            order.retry_count += 1

            if order.retry_count > order.max_retries:
                logger.error(f"Order exceeded max retries, discarding: {order.side} {order.symbol}")
                self._send_alert(
                    f"FAILED ORDER DISCARDED: {order.side} {order.symbol} ${order.amount_usd:.2f}",
                    {"retries": order.retry_count, "last_error": order.last_error},
                )
                continue

            try:
                success = executor(order)
                if success:
                    processed += 1
                    logger.info(f"Queued order processed: {order.side} {order.symbol}")
                else:
                    remaining.append(order)
            except Exception as e:
                order.last_error = str(e)
                remaining.append(order)
                logger.warning(f"Order retry failed: {order.side} {order.symbol} - {e}")

        self.order_queue = remaining
        self._save_order_queue()

        if processed > 0:
            logger.info(f"Processed {processed} queued orders, {len(remaining)} remaining")

        return processed

    def is_trading_allowed(self) -> tuple[bool, str]:
        """
        Check if trading should be allowed based on API health.

        Returns:
            Tuple of (allowed, reason)
        """
        if self.circuit_breaker_tripped:
            if self._should_reset_circuit_breaker():
                return True, "Circuit breaker reset - trading allowed"
            return False, "Circuit breaker tripped - API unstable"

        if self.consecutive_failures >= 2:
            return True, f"Warning: {self.consecutive_failures} consecutive failures"

        return True, "API healthy"

    def get_status_summary(self) -> dict:
        """Get current health monitor status."""
        return {
            "consecutive_failures": self.consecutive_failures,
            "circuit_breaker_tripped": self.circuit_breaker_tripped,
            "circuit_breaker_tripped_at": (
                self.circuit_breaker_tripped_at.isoformat()
                if self.circuit_breaker_tripped_at
                else None
            ),
            "last_successful_check": (
                self.last_successful_check.isoformat() if self.last_successful_check else None
            ),
            "queued_orders": len(self.order_queue),
            "trading_allowed": self.is_trading_allowed()[0],
        }

    # ==================== Private Methods ====================

    def _trip_circuit_breaker(self, error: str) -> None:
        """Trip the circuit breaker to stop trading."""
        if not self.circuit_breaker_tripped:
            self.circuit_breaker_tripped = True
            self.circuit_breaker_tripped_at = datetime.now()

            logger.critical(f"CIRCUIT BREAKER TRIPPED: {error}")
            self._send_alert(
                f"CRITICAL: Circuit breaker tripped after {self.consecutive_failures} failures",
                {"error": error, "will_reset_in": f"{self.CIRCUIT_BREAKER_RESET_MINUTES} minutes"},
            )

    def _reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker."""
        if self.circuit_breaker_tripped:
            self.circuit_breaker_tripped = False
            self.circuit_breaker_tripped_at = None
            logger.info("Circuit breaker reset - trading resumed")
            self._send_alert("Circuit breaker reset - API recovered", {})

    def _should_reset_circuit_breaker(self) -> bool:
        """Check if circuit breaker should auto-reset."""
        if not self.circuit_breaker_tripped or not self.circuit_breaker_tripped_at:
            return True

        elapsed = datetime.now() - self.circuit_breaker_tripped_at
        if elapsed > timedelta(minutes=self.CIRCUIT_BREAKER_RESET_MINUTES):
            # Try a health check before resetting
            health = self.check_health()
            if health.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED):
                self._reset_circuit_breaker()
                return True

        return False

    def _send_alert(self, message: str, details: dict) -> None:
        """Send alert via configured channels."""
        alert_data = {
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "source": "AlpacaHealthMonitor",
        }

        # Log alert
        logger.warning(f"ALERT: {message}")

        # Send to webhook if configured
        if self.alert_webhook_url:
            try:
                import requests

                requests.post(
                    self.alert_webhook_url,
                    json=alert_data,
                    timeout=5,
                )
            except Exception as e:
                logger.error(f"Failed to send webhook alert: {e}")

        # Save to alert log
        alert_log_path = Path("data/alerts/health_alerts.json")
        alert_log_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            alerts = []
            if alert_log_path.exists():
                with open(alert_log_path) as f:
                    alerts = json.load(f)

            alerts.append(alert_data)

            # Keep last 100 alerts
            alerts = alerts[-100:]

            with open(alert_log_path, "w") as f:
                json.dump(alerts, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save alert log: {e}")

    def _load_order_queue(self) -> None:
        """Load persisted order queue from disk."""
        if self.order_queue_path.exists():
            try:
                with open(self.order_queue_path) as f:
                    data = json.load(f)

                self.order_queue = [
                    QueuedOrder(
                        symbol=o["symbol"],
                        amount_usd=o["amount_usd"],
                        side=o["side"],
                        tier=o["tier"],
                        created_at=datetime.fromisoformat(o["created_at"]),
                        retry_count=o.get("retry_count", 0),
                        last_error=o.get("last_error"),
                    )
                    for o in data
                ]

                if self.order_queue:
                    logger.info(f"Loaded {len(self.order_queue)} orders from queue")
            except Exception as e:
                logger.error(f"Failed to load order queue: {e}")
                self.order_queue = []

    def _save_order_queue(self) -> None:
        """Persist order queue to disk."""
        self.order_queue_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = [
                {
                    "symbol": o.symbol,
                    "amount_usd": o.amount_usd,
                    "side": o.side,
                    "tier": o.tier,
                    "created_at": o.created_at.isoformat(),
                    "retry_count": o.retry_count,
                    "last_error": o.last_error,
                }
                for o in self.order_queue
            ]

            with open(self.order_queue_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save order queue: {e}")


# Convenience function for quick health check
def check_alpaca_health() -> HealthCheckResult:
    """Quick health check without creating monitor instance."""
    monitor = AlpacaHealthMonitor()
    return monitor.check_health()
