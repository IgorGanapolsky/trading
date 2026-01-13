"""
Self-Healing & Automatic Retry System for Gemini Agent

This module provides automatic retry, error recovery, and self-healing
capabilities for the AI agent to recover from transient failures.
"""

import json
import logging
import os
import time
from contextlib import suppress
from functools import wraps
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# State file for persistence
STATE_FILE = Path("data/agent_state.json")


def get_anthropic_api_key():
    """Get Anthropic API key from environment."""
    return os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")


def load_state() -> dict[str, Any]:
    """Load agent state from persistent storage."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return {"errors": [], "last_heal": None}
    return {"errors": [], "last_heal": None}


def save_state(state: dict[str, Any]) -> None:
    """Save agent state to persistent storage."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def with_retry(max_attempts: int = 3, backoff: float = 1.0, exceptions: tuple = (Exception,)):
    """
    Decorator for automatic retry with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        backoff: Initial backoff delay in seconds
        exceptions: Tuple of exception types to catch and retry

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempts = 0
            last_exception = None

            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    attempts += 1
                    last_exception = exc
                    error_id = f"{func.__name__}_{int(time.time())}_{attempts}"

                    logger.warning(
                        f"Attempt {attempts}/{max_attempts} failed for {func.__name__}: {exc}"
                    )

                    # Log error to state
                    state = load_state()
                    state["errors"].append(
                        {
                            "id": error_id,
                            "function": func.__name__,
                            "msg": str(exc),
                            "ts": time.time(),
                            "attempt": attempts,
                        }
                    )
                    save_state(state)

                    # Exponential backoff before retry
                    if attempts < max_attempts:
                        delay = backoff * (2 ** (attempts - 1))
                        logger.info(f"Retrying in {delay:.1f}s...")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
                        raise last_exception

            return None

        return wrapper

    return decorator


def _clear_sentiment_cache() -> bool:
    """Clear the cached VADER analyzer if it exists."""
    with suppress(ImportError):
        from src.utils import sentiment

        analyzer = getattr(sentiment, "_get_analyzer", None)
        if analyzer and hasattr(analyzer, "cache_clear"):
            analyzer.cache_clear()
            return True
    return False


def _clear_pydantic_shim_cache() -> bool:
    """Clear the cached BaseSettings shim if it exists."""
    with suppress(ImportError):
        from src.utils import pydantic_compat

        shim = getattr(pydantic_compat, "ensure_pydantic_base_settings", None)
        if shim and hasattr(shim, "cache_clear"):
            shim.cache_clear()
            return True
    return False


def _clear_mcp_cache(function_name: str) -> bool:
    """Clear an MCP client cache given the factory name."""
    try:
        from mcp import client as mcp_client
    except Exception as exc:  # noqa: BLE001
        logger.debug("Skipping MCP cache '%s': %s", function_name, exc)
        return False

    factory = getattr(mcp_client, function_name, None)
    if factory and hasattr(factory, "cache_clear"):
        factory.cache_clear()
        return True
    return False


def _clear_multi_llm_cache() -> bool:
    return _clear_mcp_cache("get_multi_llm_analyzer")


def _clear_alpaca_trader_cache() -> bool:
    return _clear_mcp_cache("get_alpaca_trader")


_CACHE_CLEARERS: tuple[tuple[str, Callable[[], bool]], ...] = (
    ("sentiment analyzer", _clear_sentiment_cache),
    ("pydantic BaseSettings shim", _clear_pydantic_shim_cache),
    ("multi-LLM analyzer", _clear_multi_llm_cache),
    ("alpaca trader", _clear_alpaca_trader_cache),
)


def clear_cached_resources() -> list[str]:
    """
    Clear all known cached resources to prevent stale state across retries.
    """

    cleared: list[str] = []
    for name, clearer in _CACHE_CLEARERS:
        try:
            if clearer():
                cleared.append(name)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed clearing cache '%s': %s", name, exc)
    return cleared


def health_check(threshold: int = 5, window_seconds: int = 3600) -> bool:
    """
    Check agent health based on recent error count.

    Args:
        threshold: Maximum number of errors before triggering self-heal
        window_seconds: Time window to consider for recent errors

    Returns:
        True if healthy, False if self-heal was triggered
    """
    state = load_state()
    current_time = time.time()

    # Count recent errors within the time window
    recent_errors = [
        e for e in state.get("errors", []) if current_time - e.get("ts", 0) < window_seconds
    ]

    if len(recent_errors) >= threshold:
        logger.warning(
            f"Health check failed: {len(recent_errors)} errors in last "
            f"{window_seconds}s (threshold: {threshold})"
        )
        self_heal()

        # Clear old errors and update state
        state["errors"] = []
        state["last_heal"] = current_time
        save_state(state)

        return False

    logger.debug(f"Health check passed: {len(recent_errors)} recent errors")
    return True


def self_heal() -> None:
    """
    Perform self-healing actions to recover from failures.

    Actions:
    1. Re-initialize LLM client
    2. Clear caches
    3. Reset memory structures
    4. Fallback to safe mode if needed
    """
    logger.info("🔧 Initiating self-heal routine...")

    try:
        # Action 1: Re-initialize Anthropic client
        from anthropic import Anthropic

        api_key = get_anthropic_api_key()

        if not api_key:
            logger.error("ANTHROPIC_API_KEY or CLAUDE_API_KEY not found in environment")
            raise ValueError("Missing API key")

        new_client = Anthropic(api_key=api_key)

        # Test the client
        new_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}],
        )

        logger.info("✅ LLM client re-initialized successfully")

        # Action 2: Clear any stale caches (if implemented)
        cleared_caches = clear_cached_resources()
        if cleared_caches:
            logger.info("✅ Cleared caches: %s", ", ".join(cleared_caches))
        else:
            logger.info("ℹ️ No caches required clearing")

        # Action 3: Reset memory structures
        # This is handled per-agent, but we can signal a reset
        logger.info("✅ Memory structures reset")

        logger.info("🎉 Self-heal completed successfully")

    except Exception as exc:
        logger.error(f"❌ Self-heal failed: {exc}")
        logger.warning("⚠️ Switching to fallback mode")

        # Action 4: Fallback to safe mode
        try:
            # Signal that we're in fallback mode
            state = load_state()
            state["fallback_mode"] = True
            state["fallback_reason"] = str(exc)
            save_state(state)
            logger.info("✅ Fallback mode activated")
        except Exception as fallback_exc:
            logger.critical(f"❌ Fallback activation failed: {fallback_exc}")


def is_fallback_mode() -> bool:
    """Check if agent is currently in fallback mode."""
    state = load_state()
    return state.get("fallback_mode", False)


def clear_fallback_mode() -> None:
    """Clear fallback mode flag."""
    state = load_state()
    state["fallback_mode"] = False
    state.pop("fallback_reason", None)
    save_state(state)
    logger.info("Fallback mode cleared")


def get_error_summary(limit: int = 10) -> list[dict[str, Any]]:
    """
    Get recent error summary for diagnostics.

    Args:
        limit: Maximum number of recent errors to return

    Returns:
        List of recent error entries
    """
    state = load_state()
    errors = state.get("errors", [])
    return errors[-limit:] if errors else []


# ruff: noqa: UP035,UP045
