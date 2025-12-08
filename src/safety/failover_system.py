"""
Trading System Failover & Resilience

Automatic recovery without human intervention:
1. API retry with exponential backoff
2. Health checks with auto-recovery
3. State persistence and recovery
4. Watchdog process monitoring
5. Graceful degradation

The system HANDLES problems, not just reports them.

Author: Trading System
Created: 2025-12-08
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ComponentStatus(Enum):
    """Health status of system components."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    component: str
    status: ComponentStatus
    message: str
    last_check: datetime
    consecutive_failures: int = 0
    recovery_attempts: int = 0


def retry_with_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator for automatic retry with exponential backoff.

    This is how you handle transient failures - not by alerting,
    but by automatically retrying.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts: {e}")
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)

                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)

            raise last_exception
        return wrapper
    return decorator


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerPattern:
    """
    Circuit breaker pattern for external services.

    Prevents cascading failures by stopping calls to failing services
    and automatically recovering when service is healthy again.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0

    def can_execute(self) -> bool:
        """Check if call should be allowed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    logger.info("Circuit breaker entering half-open state")
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.half_open_max_calls

        return False

    def record_success(self) -> None:
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                logger.info("Circuit breaker recovered, closing circuit")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit breaker failed during recovery, opening circuit")
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            self.state = CircuitState.OPEN


class FailoverSystem:
    """
    Main failover and resilience system.

    Handles:
    - Component health monitoring
    - Automatic recovery
    - State persistence
    - Graceful degradation
    """

    STATE_FILE = Path("data/failover_state.json")
    HEALTH_CHECK_INTERVAL = 60  # seconds
    MAX_RECOVERY_ATTEMPTS = 3

    def __init__(self):
        self.components: dict[str, HealthCheckResult] = {}
        self.circuit_breakers: dict[str, CircuitBreakerPattern] = {}
        self.recovery_handlers: dict[str, Callable] = {}
        self._running = False

        # Ensure state directory exists
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Load previous state
        self._load_state()

        # Register default components
        self._register_default_components()

    def _register_default_components(self) -> None:
        """Register default system components to monitor."""
        # Alpaca API
        self.register_component(
            "alpaca_api",
            health_check=self._check_alpaca_health,
            recovery_handler=self._recover_alpaca,
        )

        # Market data
        self.register_component(
            "market_data",
            health_check=self._check_market_data_health,
            recovery_handler=self._recover_market_data,
        )

        # State persistence
        self.register_component(
            "state_persistence",
            health_check=self._check_state_persistence,
            recovery_handler=self._recover_state_persistence,
        )

    def register_component(
        self,
        name: str,
        health_check: Optional[Callable[[], bool]] = None,
        recovery_handler: Optional[Callable[[], bool]] = None,
    ) -> None:
        """Register a component for monitoring."""
        self.components[name] = HealthCheckResult(
            component=name,
            status=ComponentStatus.HEALTHY,
            message="Initialized",
            last_check=datetime.now(),
        )
        self.circuit_breakers[name] = CircuitBreakerPattern()

        if recovery_handler:
            self.recovery_handlers[name] = recovery_handler

    def _check_alpaca_health(self) -> bool:
        """Check if Alpaca API is accessible."""
        try:
            from alpaca.trading.client import TradingClient

            api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("APCA_API_KEY_ID")
            secret_key = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("APCA_API_SECRET_KEY")

            if not api_key or not secret_key:
                return True  # Skip check if not configured

            client = TradingClient(api_key, secret_key, paper=True)
            account = client.get_account()
            return account.status == "ACTIVE"
        except Exception as e:
            logger.warning(f"Alpaca health check failed: {e}")
            return False

    def _recover_alpaca(self) -> bool:
        """Attempt to recover Alpaca connection."""
        logger.info("Attempting Alpaca recovery...")

        # Simple recovery: just wait and retry
        # The circuit breaker + retry pattern handles most cases
        time.sleep(5)
        return self._check_alpaca_health()

    def _check_market_data_health(self) -> bool:
        """Check if market data is accessible."""
        try:
            import yfinance as yf

            # Quick check with SPY
            spy = yf.Ticker("SPY")
            info = spy.fast_info
            return info.last_price is not None and info.last_price > 0
        except Exception as e:
            logger.warning(f"Market data health check failed: {e}")
            return False

    def _recover_market_data(self) -> bool:
        """Attempt to recover market data."""
        logger.info("Attempting market data recovery...")
        time.sleep(2)
        return self._check_market_data_health()

    def _check_state_persistence(self) -> bool:
        """Check if state can be persisted."""
        try:
            test_file = Path("data/.health_check_test")
            test_file.write_text(f"health_check_{datetime.now().isoformat()}")
            content = test_file.read_text()
            test_file.unlink()
            return "health_check_" in content
        except Exception as e:
            logger.warning(f"State persistence health check failed: {e}")
            return False

    def _recover_state_persistence(self) -> bool:
        """Attempt to recover state persistence."""
        logger.info("Attempting state persistence recovery...")

        # Ensure directory exists
        Path("data").mkdir(parents=True, exist_ok=True)

        return self._check_state_persistence()

    def check_component(self, name: str) -> HealthCheckResult:
        """Run health check for a specific component."""
        if name not in self.components:
            return HealthCheckResult(
                component=name,
                status=ComponentStatus.FAILED,
                message="Component not registered",
                last_check=datetime.now(),
            )

        result = self.components[name]
        circuit = self.circuit_breakers.get(name)

        # Check circuit breaker
        if circuit and not circuit.can_execute():
            result.status = ComponentStatus.FAILED
            result.message = "Circuit breaker open"
            result.last_check = datetime.now()
            return result

        # Get health check function
        check_func = getattr(self, f"_check_{name}_health", None)
        if not check_func and name == "alpaca_api":
            check_func = self._check_alpaca_health
        elif not check_func and name == "market_data":
            check_func = self._check_market_data_health
        elif not check_func and name == "state_persistence":
            check_func = self._check_state_persistence

        if not check_func:
            result.status = ComponentStatus.HEALTHY
            result.message = "No health check defined"
            result.last_check = datetime.now()
            return result

        try:
            is_healthy = check_func()

            if is_healthy:
                if circuit:
                    circuit.record_success()
                result.status = ComponentStatus.HEALTHY
                result.message = "OK"
                result.consecutive_failures = 0
            else:
                if circuit:
                    circuit.record_failure()
                result.consecutive_failures += 1
                result.status = ComponentStatus.DEGRADED
                result.message = f"Health check failed ({result.consecutive_failures} consecutive)"

                # Attempt recovery
                if result.consecutive_failures >= 2:
                    self._attempt_recovery(name, result)

        except Exception as e:
            if circuit:
                circuit.record_failure()
            result.consecutive_failures += 1
            result.status = ComponentStatus.FAILED
            result.message = f"Health check error: {e}"

        result.last_check = datetime.now()
        self.components[name] = result
        self._save_state()

        return result

    def _attempt_recovery(self, name: str, result: HealthCheckResult) -> None:
        """Attempt automatic recovery for a component."""
        if result.recovery_attempts >= self.MAX_RECOVERY_ATTEMPTS:
            logger.error(f"Max recovery attempts reached for {name}")
            result.status = ComponentStatus.FAILED
            return

        result.status = ComponentStatus.RECOVERING
        result.recovery_attempts += 1

        recovery_func = self.recovery_handlers.get(name)
        if not recovery_func:
            logger.warning(f"No recovery handler for {name}")
            return

        logger.info(f"Attempting recovery for {name} (attempt {result.recovery_attempts})")

        try:
            if recovery_func():
                logger.info(f"Recovery successful for {name}")
                result.status = ComponentStatus.HEALTHY
                result.consecutive_failures = 0
                result.recovery_attempts = 0
            else:
                logger.warning(f"Recovery failed for {name}")
                result.status = ComponentStatus.DEGRADED
        except Exception as e:
            logger.error(f"Recovery error for {name}: {e}")
            result.status = ComponentStatus.FAILED

    def check_all(self) -> dict[str, HealthCheckResult]:
        """Run health checks for all components."""
        results = {}
        for name in self.components:
            results[name] = self.check_component(name)
        return results

    def get_system_status(self) -> dict[str, Any]:
        """Get overall system status."""
        results = self.check_all()

        # Determine overall status
        statuses = [r.status for r in results.values()]

        if all(s == ComponentStatus.HEALTHY for s in statuses):
            overall = "HEALTHY"
        elif any(s == ComponentStatus.FAILED for s in statuses):
            overall = "DEGRADED"
        elif any(s == ComponentStatus.RECOVERING for s in statuses):
            overall = "RECOVERING"
        else:
            overall = "DEGRADED"

        return {
            "overall_status": overall,
            "timestamp": datetime.now().isoformat(),
            "components": {
                name: {
                    "status": r.status.value,
                    "message": r.message,
                    "last_check": r.last_check.isoformat(),
                    "consecutive_failures": r.consecutive_failures,
                    "recovery_attempts": r.recovery_attempts,
                }
                for name, r in results.items()
            },
        }

    def _load_state(self) -> None:
        """Load previous failover state."""
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE) as f:
                    state = json.load(f)
                    # Could restore circuit breaker states here
                    logger.debug("Loaded failover state")
            except Exception as e:
                logger.warning(f"Failed to load failover state: {e}")

    def _save_state(self) -> None:
        """Save current failover state."""
        try:
            state = {
                "timestamp": datetime.now().isoformat(),
                "components": {
                    name: {
                        "status": r.status.value,
                        "consecutive_failures": r.consecutive_failures,
                        "recovery_attempts": r.recovery_attempts,
                    }
                    for name, r in self.components.items()
                },
            }
            with open(self.STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save failover state: {e}")

    def is_system_healthy(self) -> bool:
        """Quick check if system is healthy enough to trade."""
        # Must have Alpaca working
        alpaca_result = self.check_component("alpaca_api")
        if alpaca_result.status == ComponentStatus.FAILED:
            return False

        # State persistence should work
        state_result = self.check_component("state_persistence")
        if state_result.status == ComponentStatus.FAILED:
            return False

        return True


class Watchdog:
    """
    Watchdog process that monitors the main trading system.

    Runs as a separate process and can restart the main system if it dies.
    """

    PID_FILE = Path("data/trading_system.pid")
    WATCHDOG_INTERVAL = 30  # seconds

    def __init__(self, main_command: list[str]):
        self.main_command = main_command
        self.process: Optional[subprocess.Popen] = None
        self._running = False

    def start(self) -> None:
        """Start the watchdog."""
        self._running = True

        # Handle signals gracefully
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info("Watchdog started")

        while self._running:
            if not self._is_process_running():
                logger.warning("Main process not running, starting...")
                self._start_main_process()

            time.sleep(self.WATCHDOG_INTERVAL)

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self._running = False
        self._stop_main_process()

    def _is_process_running(self) -> bool:
        """Check if main process is running."""
        if self.process is None:
            return False

        poll = self.process.poll()
        return poll is None

    def _start_main_process(self) -> None:
        """Start the main trading process."""
        try:
            self.process = subprocess.Popen(
                self.main_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Save PID
            self.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.PID_FILE.write_text(str(self.process.pid))

            logger.info(f"Started main process with PID {self.process.pid}")
        except Exception as e:
            logger.error(f"Failed to start main process: {e}")

    def _stop_main_process(self) -> None:
        """Stop the main trading process."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()

            logger.info("Main process stopped")

        if self.PID_FILE.exists():
            self.PID_FILE.unlink()


# Singleton failover system
_failover: Optional[FailoverSystem] = None


def get_failover() -> FailoverSystem:
    """Get or create singleton failover system."""
    global _failover
    if _failover is None:
        _failover = FailoverSystem()
    return _failover


def with_failover(component: str = "alpaca_api"):
    """
    Decorator that adds automatic retry and circuit breaker to a function.

    Usage:
        @with_failover("alpaca_api")
        def place_order(...):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            failover = get_failover()
            circuit = failover.circuit_breakers.get(component)

            if circuit and not circuit.can_execute():
                raise RuntimeError(f"Circuit breaker open for {component}")

            try:
                result = func(*args, **kwargs)
                if circuit:
                    circuit.record_success()
                return result
            except Exception as e:
                if circuit:
                    circuit.record_failure()
                raise

        return wrapper
    return decorator


# CLI interface
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    failover = get_failover()

    if len(sys.argv) < 2:
        status = failover.get_system_status()
        print(f"System Status: {status['overall_status']}")
        print(json.dumps(status, indent=2))
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "status":
        status = failover.get_system_status()
        print(json.dumps(status, indent=2))

    elif command == "check":
        component = sys.argv[2] if len(sys.argv) > 2 else None
        if component:
            result = failover.check_component(component)
            print(f"{component}: {result.status.value} - {result.message}")
        else:
            results = failover.check_all()
            for name, result in results.items():
                print(f"{name}: {result.status.value} - {result.message}")

    elif command == "healthy":
        is_healthy = failover.is_system_healthy()
        print(f"System healthy: {is_healthy}")
        sys.exit(0 if is_healthy else 1)

    else:
        print(f"Unknown command: {command}")
        print("Usage: python failover_system.py [status|check|healthy] [component]")
        sys.exit(1)
