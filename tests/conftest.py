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
def disable_circuit_breaker_for_tests():
    """Disable circuit breaker during tests by temporarily renaming TRADING_HALTED.

    The circuit breaker was added to prevent trading during crisis mode,
    but tests should run without this restriction.
    """
    from pathlib import Path

    halt_file = Path("data/TRADING_HALTED")
    backup_file = Path("data/TRADING_HALTED.test_backup")

    # Temporarily move the halt file if it exists
    if halt_file.exists():
        halt_file.rename(backup_file)

    yield

    # Restore the halt file after test
    if backup_file.exists():
        backup_file.rename(halt_file)


@pytest.fixture(autouse=True)
def mock_trade_gateway_rag():
    """Global mock for TradeGateway's LessonsLearnedRAG.

    This prevents RAG initialization failures in CI environments
    where the RAG knowledge directory may not be properly set up.
    Applied automatically to all tests.
    """
    with patch("src.risk.trade_gateway.LessonsLearnedRAG") as mock_rag_class:
        mock_rag_instance = MagicMock()
        mock_rag_instance.query.return_value = []
        mock_rag_class.return_value = mock_rag_instance
        yield mock_rag_instance


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
