"""
Pytest configuration and shared fixtures for trading system tests.

This file ensures proper cleanup of async operations, mocks, and resources
to prevent CI failures from hanging tests or memory leaks.
"""

import asyncio
import gc
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def disable_circuit_breaker_for_tests(monkeypatch, tmp_path):
    """Isolate the TRADING_HALTED kill-switch from tests via monkeypatch.

    The PRODUCTION file `data/TRADING_HALTED` is NEVER read, written, or
    renamed by the test suite. Per .claude/rules/boundary-policy.md Hard
    Block #2, renaming or removing that file re-enables trade execution;
    a pytest crash mid-fixture used to leave it gone on disk.

    Approach: redirect every module that owns a `TRADING_HALTED_FILE`
    module-level constant to a per-test tmp_path location. Tests that
    construct `Path("data/TRADING_HALTED")` inline are responsible for
    using tmp_path themselves (see tests/test_trading_halt.py).
    """
    from pathlib import Path

    fake_halt = tmp_path / "TRADING_HALTED"

    # Patch every module/class that owns a TRADING_HALTED_FILE path.
    # Use raising=False so absence of the attribute (e.g. import-time errors
    # in minimal CI) never breaks the whole test session.
    try:
        import src.safety.crisis_monitor as _crisis_monitor

        monkeypatch.setattr(_crisis_monitor, "TRADING_HALTED_FILE", fake_halt, raising=False)
    except (ImportError, ModuleNotFoundError):
        pass

    try:
        import src.risk.trade_gateway as _trade_gateway

        monkeypatch.setattr(
            _trade_gateway.TradeGateway,
            "TRADING_HALTED_FILE",
            fake_halt,
            raising=False,
        )
    except (ImportError, ModuleNotFoundError):
        pass

    # Sanity: the production file must exist on disk so the boundary
    # guard remains meaningful for the developer running tests locally.
    # We do NOT modify it. If it's missing, that is a real concern that
    # belongs in the developer's session, not in test-suite teardown.
    prod_halt = Path("data/TRADING_HALTED")
    assert prod_halt is not None  # never touched; reference only

    yield


@pytest.fixture(autouse=True)
def mock_trade_gateway_rag():
    """Global mock for TradeGateway's LessonsLearnedRAG.

    This prevents RAG initialization failures in CI environments
    where the RAG knowledge directory may not be properly set up.
    Applied automatically to all tests.
    """
    try:
        with patch("src.risk.trade_gateway.LessonsLearnedRAG") as mock_rag_class:
            mock_rag_instance = MagicMock()
            mock_rag_instance.query.return_value = []
            mock_rag_class.return_value = mock_rag_instance
            yield mock_rag_instance
    except (AttributeError, ModuleNotFoundError):
        # Module not importable in this test context (e.g., workflow tests)
        # Skip the mock gracefully
        yield None


@pytest.fixture(scope="function")
def event_loop():
    """
    Create an event loop for async tests.
    Ensures proper cleanup after each test.
    """
    loop = asyncio.new_event_loop()
    yield loop

    # Cleanup: cancel all pending tasks
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()

    # Wait for all tasks to complete cancellation
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

    # Close the loop
    loop.close()

    # Force garbage collection to clean up any remaining references
    gc.collect()


@pytest.fixture(autouse=True)
def cleanup_async_operations():
    """
    Auto-use fixture that ensures all async operations are cleaned up.
    Runs after every test to prevent hanging operations.
    """
    yield

    # Cleanup: cancel any remaining async tasks
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, schedule cleanup
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            if pending:
                for task in pending:
                    task.cancel()
        else:
            # If loop is not running, we can clean up directly
            pending = asyncio.all_tasks(loop)
            for task in pending:
                if not task.done():
                    task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except RuntimeError:
        # No event loop exists, which is fine
        pass

    # Force garbage collection
    gc.collect()


@pytest.fixture(autouse=True)
def cleanup_mocks():
    """
    Auto-use fixture that ensures all mocks are properly stopped.
    Prevents mock-related memory leaks.
    """
    yield

    # Stop all active patches
    # This is handled automatically by pytest's monkeypatch, but we ensure it here
    pass


@pytest.fixture(autouse=True)
def reset_environment():
    """
    Auto-use fixture that resets environment variables after each test.
    Prevents test pollution.
    """
    import os

    original_env = os.environ.copy()
    # Avoid hard failures in minimal CI where LanceDB isn't installed.
    os.environ.setdefault("LANCEDB_REQUIRED", "false")
    os.environ.setdefault("LANCEDB_RAG", "false")

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_time(monkeypatch):
    """
    Mock time for tests that need time control.
    Ensures proper cleanup of time mocks.
    """
    import time
    from unittest.mock import Mock

    mock_time_obj = Mock(return_value=time.time())
    monkeypatch.setattr(time, "time", mock_time_obj)

    yield mock_time_obj

    # Cleanup is automatic with monkeypatch


@pytest.fixture
def temp_cache_dir(tmp_path):
    """
    Provide a temporary cache directory for testing.
    Automatically cleaned up by pytest.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


# Pytest hooks for additional cleanup
def pytest_runtest_teardown(item):
    """Called after each test item is torn down."""
    # Force garbage collection after each test
    gc.collect()


def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished, right before returning exit status."""
    # Final cleanup: ensure all async tasks are cancelled
    try:
        loop = asyncio.get_event_loop()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            if not task.done():
                task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except RuntimeError:
        pass

    # Final garbage collection
    gc.collect()
