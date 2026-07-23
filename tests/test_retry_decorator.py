"""
Tests for src/utils/retry_decorator.py

Covers missing lines 69-117:
- wrapper function execution with and without timeout
- per-attempt timeout (ThreadPoolExecutor path)
- total timeout guard
- TimeoutException propagation on final attempt
- exception retry logic with backoff
- exception propagation on final attempt
- fallthrough return after exhausting retries
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.utils.retry_decorator import TimeoutException, retry_with_backoff


# ---------------------------------------------------------------------------
# Happy-path
# ---------------------------------------------------------------------------


class TestRetryWithBackoffSuccess:
    def test_success_on_first_attempt_no_timeout(self):
        """Function that succeeds immediately, timeout disabled."""

        @retry_with_backoff(max_retries=3, timeout=None, total_timeout=None)
        def always_succeeds():
            return 42

        assert always_succeeds() == 42

    def test_success_on_first_attempt_with_timeout(self):
        """Function succeeds within timeout window (ThreadPoolExecutor path)."""

        @retry_with_backoff(max_retries=3, timeout=5.0, total_timeout=30.0)
        def fast_func():
            return "ok"

        assert fast_func() == "ok"

    def test_passes_args_and_kwargs(self):
        """Wrapper forwards positional and keyword arguments correctly."""

        @retry_with_backoff(max_retries=2, timeout=None, total_timeout=None)
        def add(a, b, multiplier=1):
            return (a + b) * multiplier

        assert add(3, 4, multiplier=2) == 14

    def test_wraps_preserves_function_name(self):
        """@wraps keeps the original function name."""

        @retry_with_backoff(max_retries=1, timeout=None, total_timeout=None)
        def my_function():
            pass

        assert my_function.__name__ == "my_function"


# ---------------------------------------------------------------------------
# Retry on exception (lines 104-115)
# ---------------------------------------------------------------------------


class TestRetryOnException:
    def test_retries_then_succeeds(self):
        """Retries on ValueError, succeeds on the second attempt."""
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            initial_delay=0,
            exceptions=(ValueError,),
            timeout=None,
            total_timeout=None,
        )
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("transient")
            return "success"

        with patch("time.sleep"):
            result = flaky()

        assert result == "success"
        assert call_count == 2

    def test_raises_after_max_retries(self):
        """Raises the caught exception after exhausting all retries."""

        @retry_with_backoff(
            max_retries=3,
            initial_delay=0,
            exceptions=(RuntimeError,),
            timeout=None,
            total_timeout=None,
        )
        def always_fails():
            raise RuntimeError("permanent")

        with patch("time.sleep"), pytest.raises(RuntimeError, match="permanent"):
            always_fails()

    def test_backoff_delay_applied(self):
        """time.sleep is called with exponentially growing delays."""
        sleep_calls = []

        @retry_with_backoff(
            max_retries=3,
            initial_delay=1.0,
            backoff_factor=2.0,
            exceptions=(ValueError,),
            timeout=None,
            total_timeout=None,
        )
        def always_fails():
            raise ValueError("boom")

        with patch("time.sleep", side_effect=lambda d: sleep_calls.append(d)):
            with pytest.raises(ValueError):
                always_fails()

        # Two sleeps expected: after attempt 0 and attempt 1 (attempt 2 is last)
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == pytest.approx(1.0)
        assert sleep_calls[1] == pytest.approx(2.0)

    def test_only_catches_specified_exceptions(self):
        """Exceptions not in the tuple propagate immediately."""

        @retry_with_backoff(
            max_retries=3,
            exceptions=(ValueError,),
            timeout=None,
            total_timeout=None,
        )
        def raises_type_error():
            raise TypeError("unexpected")

        with pytest.raises(TypeError):
            raises_type_error()

    def test_fallthrough_return_via_zero_retries(self):
        """When max_retries=0 the for loop is skipped entirely and line 117 is hit."""

        @retry_with_backoff(
            max_retries=0,
            initial_delay=0,
            exceptions=(ValueError,),
            timeout=None,
            total_timeout=None,
        )
        def simple():
            return "fallthrough"

        result = simple()
        assert result == "fallthrough"


# ---------------------------------------------------------------------------
# Per-attempt timeout (lines 82-89)
# ---------------------------------------------------------------------------


class TestPerAttemptTimeout:
    def test_timeout_raises_timeout_exception(self):
        """Slow function triggers TimeoutException via ThreadPoolExecutor (mock path)."""
        from concurrent.futures import TimeoutError as ConcurrentTimeoutError

        future_mock = MagicMock()
        future_mock.result.side_effect = ConcurrentTimeoutError()

        executor_instance = MagicMock()
        executor_instance.__enter__ = MagicMock(return_value=executor_instance)
        executor_instance.__exit__ = MagicMock(return_value=False)
        executor_instance.submit.return_value = future_mock

        @retry_with_backoff(
            max_retries=1,
            initial_delay=0,
            timeout=0.05,
            total_timeout=None,
        )
        def slow_func():
            return "never"

        with patch("src.utils.retry_decorator.ThreadPoolExecutor", return_value=executor_instance):
            with pytest.raises(TimeoutException):
                slow_func()

    def test_timeout_exception_reraised_on_last_attempt(self):
        """TimeoutException is re-raised after the last retry attempt (mock path)."""
        from concurrent.futures import TimeoutError as ConcurrentTimeoutError

        future_mock = MagicMock()
        future_mock.result.side_effect = ConcurrentTimeoutError()

        executor_instance = MagicMock()
        executor_instance.__enter__ = MagicMock(return_value=executor_instance)
        executor_instance.__exit__ = MagicMock(return_value=False)
        executor_instance.submit.return_value = future_mock

        @retry_with_backoff(
            max_retries=2,
            initial_delay=0,
            timeout=0.05,
            total_timeout=None,
        )
        def slow_func():
            pass

        with (
            patch("src.utils.retry_decorator.ThreadPoolExecutor", return_value=executor_instance),
            patch("src.utils.retry_decorator.time.sleep"),
        ):
            with pytest.raises(TimeoutException):
                slow_func()

    def test_timeout_retried_with_backoff(self):
        """TimeoutException causes backoff sleep between attempts."""
        # Use the mock executor approach so no real threads block the test.
        from concurrent.futures import TimeoutError as ConcurrentTimeoutError

        sleep_calls = []

        future_mock = MagicMock()
        future_mock.result.side_effect = ConcurrentTimeoutError()

        executor_instance = MagicMock()
        executor_instance.__enter__ = MagicMock(return_value=executor_instance)
        executor_instance.__exit__ = MagicMock(return_value=False)
        executor_instance.submit.return_value = future_mock

        executor_cls = MagicMock(return_value=executor_instance)

        @retry_with_backoff(
            max_retries=2,
            initial_delay=0.5,
            backoff_factor=2.0,
            timeout=0.05,
            total_timeout=None,
        )
        def slow_func():
            pass  # body never reached — executor is mocked

        with (
            patch("src.utils.retry_decorator.ThreadPoolExecutor", executor_cls),
            patch(
                "src.utils.retry_decorator.time.sleep", side_effect=lambda d: sleep_calls.append(d)
            ),
        ):
            with pytest.raises(TimeoutException):
                slow_func()

        # At least one backoff sleep should have been recorded (after first timeout)
        assert len(sleep_calls) >= 1


# ---------------------------------------------------------------------------
# Total timeout (lines 74-77)
# ---------------------------------------------------------------------------


class TestTotalTimeout:
    def test_total_timeout_exceeded_raises(self):
        """Total timeout triggers TimeoutException before next attempt starts."""
        call_count = 0

        @retry_with_backoff(
            max_retries=5,
            initial_delay=0,
            total_timeout=0.01,  # expires almost immediately
            timeout=None,
            exceptions=(ValueError,),
        )
        def always_fails():
            nonlocal call_count
            call_count += 1
            time.sleep(0.02)  # each call exceeds the total timeout
            raise ValueError("boom")

        with pytest.raises((TimeoutException, ValueError)):
            always_fails()

        # Should not have attempted all 5 retries
        assert call_count < 5

    def test_total_timeout_none_does_not_guard(self):
        """When total_timeout=None the guard is skipped and retries proceed normally."""
        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            initial_delay=0,
            total_timeout=None,
            timeout=None,
            exceptions=(ValueError,),
        )
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "done"

        with patch("time.sleep"):
            result = fails_twice()

        assert result == "done"
        assert call_count == 3


# ---------------------------------------------------------------------------
# TimeoutException class
# ---------------------------------------------------------------------------


class TestTimeoutExceptionClass:
    def test_is_exception_subclass(self):
        assert issubclass(TimeoutException, Exception)

    def test_message_preserved(self):
        exc = TimeoutException("timed out after 10s")
        assert "10s" in str(exc)
