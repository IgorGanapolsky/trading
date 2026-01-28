"""
Tests for resilience modules: circuit_breaker, retry, and self_healer.

These are HIGH RISK modules with ZERO test coverage.
Coverage priority: circuit breaker state transitions, retry backoff, self-healer checks.

Created: Jan 28, 2026
"""

import json
import os
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)
from src.resilience.retry import RetryableOperation, RetryConfig, retry_with_backoff
from src.resilience.self_healer import HealthCheck, HealthStatus, SelfHealer


# =============================================================================
# Circuit Breaker Tests
# =============================================================================


class TestCircuitBreakerStateTransitions:
    """Test circuit breaker state transitions."""

    def test_initial_state_is_closed(self):
        """Circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker(name="test")
        assert breaker.state == CircuitState.CLOSED

    def test_closed_to_open_on_failure_threshold(self):
        """Circuit opens after failure_threshold failures."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        @breaker
        def failing_func():
            raise ValueError("simulated failure")

        # Trigger failures up to threshold
        for _ in range(3):
            with pytest.raises(ValueError):
                failing_func()

        assert breaker.state == CircuitState.OPEN

    def test_open_blocks_requests(self):
        """OPEN circuit blocks requests with CircuitBreakerOpenError."""
        breaker = CircuitBreaker(name="test", failure_threshold=1)

        @breaker
        def failing_func():
            raise ValueError("fail")

        # Trip the breaker
        with pytest.raises(ValueError):
            failing_func()

        assert breaker.state == CircuitState.OPEN

        # Now should block
        with pytest.raises(CircuitBreakerOpenError):
            failing_func()

    def test_open_to_half_open_after_recovery_timeout(self):
        """Circuit transitions from OPEN to HALF_OPEN after recovery_timeout."""
        breaker = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)

        @breaker
        def failing_func():
            raise ValueError("fail")

        # Trip the breaker
        with pytest.raises(ValueError):
            failing_func()

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Accessing state should trigger transition
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_success_threshold(self):
        """Circuit closes from HALF_OPEN after success_threshold successes."""
        breaker = CircuitBreaker(
            name="test", failure_threshold=1, recovery_timeout=0.1, success_threshold=2
        )

        call_count = 0

        @breaker
        def sometimes_fails():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("first call fails")
            return "success"

        # Trip the breaker
        with pytest.raises(ValueError):
            sometimes_fails()

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        # Successful calls to meet threshold
        sometimes_fails()  # success 1
        assert breaker.state == CircuitState.HALF_OPEN

        sometimes_fails()  # success 2
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self):
        """Circuit reopens from HALF_OPEN on any failure."""
        breaker = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)

        call_count = 0

        @breaker
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"failure {call_count}")

        # Trip initially
        with pytest.raises(ValueError):
            always_fails()

        # Wait and enter half-open
        time.sleep(0.15)
        assert breaker.state == CircuitState.HALF_OPEN

        # Failure in half-open should reopen
        with pytest.raises(ValueError):
            always_fails()

        assert breaker.state == CircuitState.OPEN


class TestCircuitBreakerDecorator:
    """Test circuit breaker as decorator."""

    def test_successful_calls_pass_through(self):
        """Successful calls pass through and return results."""
        breaker = CircuitBreaker(name="test")

        @breaker
        def successful_func():
            return "success"

        assert successful_func() == "success"
        assert breaker.state == CircuitState.CLOSED

    def test_exception_propagation(self):
        """Exceptions are propagated after being recorded."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)

        @breaker
        def failing_func():
            raise RuntimeError("test error")

        with pytest.raises(RuntimeError, match="test error"):
            failing_func()

        # Failure recorded but not at threshold
        assert breaker._failure_count == 1
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerContextManager:
    """Test circuit breaker as context manager."""

    def test_context_manager_success(self):
        """Context manager records success on normal exit."""
        breaker = CircuitBreaker(name="test")

        with breaker:
            pass  # Successful operation

        assert breaker._failure_count == 0

    def test_context_manager_failure(self):
        """Context manager records failure on exception."""
        breaker = CircuitBreaker(name="test", failure_threshold=1)

        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("test")

        assert breaker.state == CircuitState.OPEN

    def test_context_manager_blocks_when_open(self):
        """Context manager blocks entry when circuit is open."""
        breaker = CircuitBreaker(name="test", failure_threshold=1)

        # Trip the breaker
        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("trip")

        # Now should block entry
        with pytest.raises(CircuitBreakerOpenError):
            with breaker:
                pass


class TestCircuitBreakerMethods:
    """Test circuit breaker utility methods."""

    def test_reset(self):
        """Manual reset returns circuit to CLOSED state."""
        breaker = CircuitBreaker(name="test", failure_threshold=1)

        @breaker
        def failing():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            failing()

        assert breaker.state == CircuitState.OPEN

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0
        assert breaker._success_count == 0

    def test_get_status(self):
        """get_status returns monitoring information."""
        breaker = CircuitBreaker(name="test_breaker", failure_threshold=5, recovery_timeout=30.0)

        status = breaker.get_status()

        assert status["name"] == "test_breaker"
        assert status["state"] == "closed"
        assert status["failure_threshold"] == 5
        assert status["recovery_timeout"] == 30.0

    def test_allow_request(self):
        """allow_request returns True when CLOSED or HALF_OPEN."""
        breaker = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)

        assert breaker.allow_request() is True

        # Trip
        with pytest.raises(ValueError):
            with breaker:
                raise ValueError("trip")

        assert breaker.allow_request() is False

        # Wait for half-open
        time.sleep(0.15)
        assert breaker.allow_request() is True


class TestCircuitBreakerThreadSafety:
    """Test thread safety of circuit breaker."""

    def test_concurrent_failures(self):
        """Circuit breaker handles concurrent failures correctly."""
        breaker = CircuitBreaker(name="test", failure_threshold=10)
        errors = []

        def trigger_failure():
            try:
                with breaker:
                    raise ValueError("concurrent fail")
            except (ValueError, CircuitBreakerOpenError) as e:
                errors.append(e)

        threads = [threading.Thread(target=trigger_failure) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All errors should be recorded
        assert len(errors) == 20
        # Circuit should be open (10+ failures)
        assert breaker.state == CircuitState.OPEN


# =============================================================================
# Retry Tests
# =============================================================================


class TestRetryWithBackoff:
    """Test retry_with_backoff decorator."""

    def test_successful_on_first_attempt(self):
        """Function succeeds on first attempt, no retry needed."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        def successful():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful()

        assert result == "success"
        assert call_count == 1

    def test_retry_after_transient_failure(self):
        """Function retries and succeeds after transient failure."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient failure")
            return "success"

        result = fails_twice()

        assert result == "success"
        assert call_count == 3

    def test_max_attempts_exhaustion(self):
        """Exception raised after max_attempts exhausted."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent failure")

        with pytest.raises(ValueError, match="permanent failure"):
            always_fails()

        assert call_count == 3

    def test_retryable_exceptions_filter(self):
        """Only retryable_exceptions trigger retry."""
        call_count = 0

        @retry_with_backoff(max_attempts=3, base_delay=0.01, retryable_exceptions=(ValueError,))
        def raises_runtime_error():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("not retryable")

        with pytest.raises(RuntimeError, match="not retryable"):
            raises_runtime_error()

        # Should fail immediately, no retry
        assert call_count == 1

    def test_exponential_backoff_timing(self):
        """Verify exponential backoff increases delay."""
        call_times = []

        @retry_with_backoff(max_attempts=4, base_delay=0.05)
        def track_timing():
            call_times.append(time.time())
            raise ValueError("fail")

        with pytest.raises(ValueError):
            track_timing()

        # Calculate delays between calls
        assert len(call_times) == 4

        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        delay3 = call_times[3] - call_times[2]

        # Each delay should roughly double (with jitter)
        # base_delay=0.05, so: 0.05, 0.1, 0.2 (with jitter ±25%)
        assert delay1 < delay2  # Later delays are longer
        assert delay2 < delay3

    def test_retry_config_object(self):
        """RetryConfig object configures retry behavior."""
        config = RetryConfig(max_attempts=2, base_delay=0.01, jitter=False)

        call_count = 0

        @retry_with_backoff(config=config)
        def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("fail")
            return "ok"

        result = fails_once()

        assert result == "ok"
        assert call_count == 2


class TestRetryableOperation:
    """Test RetryableOperation context manager."""

    def test_successful_operation(self):
        """Successful operation on first attempt."""
        with RetryableOperation(max_attempts=3) as retry:
            for attempt in retry:
                result = "success"
                break

        assert result == "success"
        assert retry.attempt == 1

    def test_retry_on_failure(self):
        """Operation retries on failure and succeeds."""
        results = []

        with RetryableOperation(max_attempts=3, base_delay=0.01) as retry:
            for attempt in retry:
                if attempt < 3:
                    try:
                        raise ValueError("fail")
                    except ValueError as e:
                        retry.record_failure(e)
                else:
                    results.append("success")
                    break

        assert results == ["success"]
        assert retry.attempt == 3

    def test_exhaustion_raises(self):
        """record_failure raises after max attempts exhausted."""
        with pytest.raises(ValueError, match="fail"):
            with RetryableOperation(max_attempts=2, base_delay=0.01) as retry:
                for _attempt in retry:
                    try:
                        raise ValueError("fail")
                    except ValueError as e:
                        retry.record_failure(e)

    def test_last_error_property(self):
        """last_error property tracks most recent error."""
        retry = RetryableOperation(max_attempts=3, base_delay=0.01)

        assert retry.last_error is None

        # Simulate failures
        retry._attempt = 1
        error = ValueError("test error")
        try:
            retry.record_failure(error)
        except ValueError:
            pass

        assert retry.last_error is error


# =============================================================================
# Self-Healer Tests
# =============================================================================


class TestSelfHealerChecks:
    """Test individual SelfHealer health checks."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create directory structure
            (project / "data").mkdir()
            (project / "data" / "backups").mkdir()
            (project / ".claude").mkdir()

            yield project

    def test_check_system_state_healthy(self, temp_project):
        """Healthy system_state.json passes check."""
        state_file = temp_project / "data" / "system_state.json"
        state_data = {
            "portfolio": {"equity": 30000},
            "positions": [],
            "trade_history": [],
        }
        state_file.write_text(json.dumps(state_data))

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_system_state()

        assert check.status == HealthStatus.HEALTHY
        assert check.details["equity"] == 30000

    def test_check_system_state_missing(self, temp_project):
        """Missing system_state.json is UNHEALTHY."""
        healer = SelfHealer(project_root=temp_project)
        check = healer._check_system_state()

        assert check.status == HealthStatus.UNHEALTHY
        assert "not found" in check.message

    def test_check_system_state_missing_fields(self, temp_project):
        """Missing required fields is DEGRADED."""
        state_file = temp_project / "data" / "system_state.json"
        state_file.write_text(json.dumps({"portfolio": {}}))

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_system_state()

        assert check.status == HealthStatus.DEGRADED
        assert "Missing required fields" in check.message

    def test_check_system_state_corrupt_json(self, temp_project):
        """Corrupt JSON is UNHEALTHY with can_heal=True."""
        state_file = temp_project / "data" / "system_state.json"
        state_file.write_text("{invalid json")

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_system_state()

        assert check.status == HealthStatus.UNHEALTHY
        assert "Corrupt JSON" in check.message
        assert check.details.get("can_heal") is True

    def test_check_json_files_all_valid(self, temp_project):
        """All valid JSON files pass check."""
        (temp_project / "data" / "file1.json").write_text('{"key": "value"}')
        (temp_project / "data" / "file2.json").write_text("[]")

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_json_files()

        assert check.status == HealthStatus.HEALTHY
        assert check.details["valid_count"] == 2

    def test_check_json_files_corrupt(self, temp_project):
        """Corrupt JSON files detected."""
        (temp_project / "data" / "valid.json").write_text('{"ok": true}')
        (temp_project / "data" / "corrupt.json").write_text("{broken")

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_json_files()

        assert check.status == HealthStatus.UNHEALTHY
        assert "corrupt.json" in check.details["corrupt"]

    def test_check_env_vars_healthy(self, temp_project):
        """Environment variables present passes check."""
        with patch.dict(
            os.environ,
            {
                "ALPACA_PAPER_TRADING_5K_API_KEY": "test_key",
                "ALPACA_PAPER_TRADING_5K_API_SECRET": "test_secret",
            },
        ):
            healer = SelfHealer(project_root=temp_project)
            check = healer._check_env_vars()

            assert check.status == HealthStatus.HEALTHY

    def test_check_env_vars_missing(self, temp_project):
        """Missing environment variables is DEGRADED."""
        with patch.dict(os.environ, {}, clear=True):
            healer = SelfHealer(project_root=temp_project)
            check = healer._check_env_vars()

            assert check.status == HealthStatus.DEGRADED
            assert "Missing env vars" in check.message

    def test_check_claude_md_healthy(self, temp_project):
        """Valid CLAUDE.md passes check."""
        claude_md = temp_project / ".claude" / "CLAUDE.md"
        claude_md.write_text(
            """
# AI Trading System
## Strategy
Iron condor strategy on SPY
        """
        )

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_claude_md()

        assert check.status == HealthStatus.HEALTHY

    def test_check_claude_md_missing(self, temp_project):
        """Missing CLAUDE.md is UNHEALTHY."""
        healer = SelfHealer(project_root=temp_project)
        check = healer._check_claude_md()

        assert check.status == HealthStatus.UNHEALTHY
        assert "not found" in check.message

    def test_check_claude_md_missing_sections(self, temp_project):
        """CLAUDE.md missing required sections is DEGRADED."""
        claude_md = temp_project / ".claude" / "CLAUDE.md"
        claude_md.write_text("# Just a header")

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_claude_md()

        assert check.status == HealthStatus.DEGRADED

    def test_check_data_freshness_healthy(self, temp_project):
        """Fresh data passes check."""
        state_file = temp_project / "data" / "system_state.json"
        now = datetime.now(timezone.utc)
        state_data = {"last_updated": now.isoformat()}
        state_file.write_text(json.dumps(state_data))

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_data_freshness()

        assert check.status == HealthStatus.HEALTHY

    def test_check_data_freshness_stale(self, temp_project):
        """Stale data (>24h) is UNHEALTHY."""
        state_file = temp_project / "data" / "system_state.json"
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        state_data = {"last_updated": old_time.isoformat()}
        state_file.write_text(json.dumps(state_data))

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_data_freshness()

        assert check.status == HealthStatus.UNHEALTHY
        assert check.details.get("can_heal") is True

    def test_check_data_freshness_degraded(self, temp_project):
        """Moderately stale data (4-24h) is DEGRADED."""
        state_file = temp_project / "data" / "system_state.json"
        old_time = datetime.now(timezone.utc) - timedelta(hours=5)
        state_data = {"last_updated": old_time.isoformat()}
        state_file.write_text(json.dumps(state_data))

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_data_freshness()

        assert check.status == HealthStatus.DEGRADED

    def test_check_position_compliance_healthy(self, temp_project):
        """Compliant positions pass check."""
        state_file = temp_project / "data" / "system_state.json"
        state_data = {
            "portfolio": {"equity": 30000},
            "positions": [{"symbol": "SPY250117C00500000", "value": 500}],
        }
        state_file.write_text(json.dumps(state_data))

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_position_compliance()

        assert check.status == HealthStatus.HEALTHY

    def test_check_position_compliance_violations(self, temp_project):
        """Position violations detected."""
        state_file = temp_project / "data" / "system_state.json"
        state_data = {
            "portfolio": {"equity": 30000},
            "positions": [
                {"symbol": "AAPL", "value": 500},  # Non-SPY
                {"symbol": "SPY", "value": 5000},  # Over 5% limit
            ],
        }
        state_file.write_text(json.dumps(state_data))

        healer = SelfHealer(project_root=temp_project)
        check = healer._check_position_compliance()

        assert check.status == HealthStatus.UNHEALTHY
        assert len(check.details["violations"]) >= 2


class TestSelfHealerRunAll:
    """Test SelfHealer.run_all_checks()."""

    def test_run_all_checks(self):
        """run_all_checks executes all checks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "data").mkdir()
            (project / "data" / "backups").mkdir()
            (project / ".claude").mkdir()

            # Create minimal valid state
            state_file = project / "data" / "system_state.json"
            state_file.write_text(
                json.dumps(
                    {
                        "portfolio": {"equity": 30000},
                        "positions": [],
                        "trade_history": [],
                        "last_updated": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )

            (project / ".claude" / "CLAUDE.md").write_text("## Strategy\nIron condor on SPY")

            healer = SelfHealer(project_root=project)
            checks = healer.run_all_checks()

            # Should have run 6 checks
            assert len(checks) == 6
            check_names = [c.name for c in checks]
            assert "system_state" in check_names
            assert "json_files" in check_names
            assert "env_vars" in check_names
            assert "claude_md" in check_names
            assert "data_freshness" in check_names
            assert "position_compliance" in check_names


class TestSelfHealerSummary:
    """Test SelfHealer summary and reporting."""

    def test_get_summary(self):
        """get_summary returns structured summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "data").mkdir()
            (project / ".claude").mkdir()

            healer = SelfHealer(project_root=project)
            healer.checks = [
                HealthCheck(name="test1", status=HealthStatus.HEALTHY, message="ok"),
                HealthCheck(name="test2", status=HealthStatus.DEGRADED, message="warn"),
            ]

            summary = healer.get_summary()

            assert summary["total_checks"] == 2
            assert summary["overall_status"] == "degraded"
            assert summary["by_status"]["healthy"] == 1
            assert summary["by_status"]["degraded"] == 1

    def test_get_summary_unhealthy_overrides(self):
        """UNHEALTHY status takes priority over DEGRADED."""
        healer = SelfHealer()
        healer.checks = [
            HealthCheck(name="t1", status=HealthStatus.HEALTHY, message="ok"),
            HealthCheck(name="t2", status=HealthStatus.DEGRADED, message="warn"),
            HealthCheck(name="t3", status=HealthStatus.UNHEALTHY, message="bad"),
        ]

        summary = healer.get_summary()

        assert summary["overall_status"] == "unhealthy"

    def test_get_report(self):
        """get_report returns human-readable string."""
        healer = SelfHealer()
        healer.checks = [
            HealthCheck(name="test", status=HealthStatus.HEALTHY, message="All good"),
        ]

        report = healer.get_report()

        assert "SELF-HEALING HEALTH CHECK REPORT" in report
        assert "test" in report
        assert "All good" in report


class TestSelfHealerHealing:
    """Test auto-healing functionality."""

    def test_heal_corrupt_json_from_backup(self):
        """Corrupt JSON healed from backup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "data").mkdir()
            (project / "data" / "backups").mkdir()

            # Create corrupt state file
            state_file = project / "data" / "system_state.json"
            state_file.write_text("{corrupt")

            # Create valid backup
            backup_file = project / "data" / "backups" / "system_state_20260128.json"
            backup_data = {
                "portfolio": {"equity": 30000},
                "positions": [],
                "trade_history": [],
            }
            backup_file.write_text(json.dumps(backup_data))

            healer = SelfHealer(project_root=project)

            # Run check to register healer
            check = healer._check_system_state()
            assert check.status == HealthStatus.UNHEALTHY
            assert "system_state" in healer._healers

            # Heal
            result = healer._heal_corrupt_json()

            assert result is True

            # Verify restoration
            restored = json.loads(state_file.read_text())
            assert restored["portfolio"]["equity"] == 30000

    def test_heal_no_backup_fails(self):
        """Healing fails gracefully when no backup exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "data").mkdir()
            (project / "data" / "backups").mkdir()

            healer = SelfHealer(project_root=project)
            result = healer._heal_corrupt_json()

            assert result is False

    def test_heal_method_processes_healers(self):
        """heal() method processes registered healers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            (project / "data").mkdir()
            (project / "data" / "backups").mkdir()

            # Setup corrupt file and backup
            state_file = project / "data" / "system_state.json"
            state_file.write_text("{bad")

            backup = project / "data" / "backups" / "system_state_backup.json"
            backup.write_text('{"portfolio": {}, "positions": [], "trade_history": []}')

            healer = SelfHealer(project_root=project)
            healer._check_system_state()  # Register healer

            # Add check to checks list
            healer.checks = [
                HealthCheck(
                    name="system_state",
                    status=HealthStatus.UNHEALTHY,
                    message="Corrupt",
                )
            ]

            healed = healer.heal()

            assert len(healed) == 1
            assert healed[0].status == HealthStatus.HEALED
            assert healed[0].auto_fixed is True
