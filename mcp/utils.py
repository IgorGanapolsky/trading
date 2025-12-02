"""
Utility helpers for MCP-aware code execution.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def run_sync(coro: Awaitable[T]) -> T:
    """
    Execute an async coroutine from synchronous code.

    Args:
        coro: Coroutine to execute.

    Returns:
        Result of the coroutine.

    Raises:
        RuntimeError: If called when an event loop is already running.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError(
            "run_sync() cannot be used when an event loop is already running. "
            "Use the async variant of the MCP tool instead."
        )

    return asyncio.run(coro)


def ensure_env_var(getter: Callable[[], Any], description: str) -> Any:
    """
    Retrieve a resource while providing a helpful error if it is missing.

    Args:
        getter: Callable that returns the resource or raises.
        description: Human-readable description of the resource.

    Returns:
        Resource value.

    Raises:
        RuntimeError: If the getter raises an exception.
    """
    try:
        return getter()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"{description} is unavailable. Original error: {exc}") from exc
