"""
Error monitoring integration with Sentry.

Provides centralized error tracking for the trading system.
Integrates with GitHub Actions, workflow failures, and runtime errors.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_sentry_initialized = False


def init_sentry(dsn: Optional[str] = None) -> bool:
    """
    Initialize Sentry error monitoring.

    Args:
        dsn: Sentry DSN (optional, reads from SENTRY_DSN env var)

    Returns:
        True if initialized successfully, False otherwise
    """
    global _sentry_initialized

    if _sentry_initialized:
        return True

    dsn = dsn or os.getenv("SENTRY_DSN")
    if not dsn:
        logger.debug("Sentry DSN not configured (SENTRY_DSN env var not set)")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.requests import RequestsIntegration

        # Initialize Sentry with integrations
        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
                RequestsIntegration(),
            ],
            # Set traces_sample_rate to 1.0 to capture 100% of transactions for performance monitoring
            traces_sample_rate=0.1,  # 10% of transactions (reduce in production)
            # Set profiles_sample_rate to 1.0 to profile 100% of sampled transactions
            profiles_sample_rate=0.1,  # 10% of transactions
            # Environment
            environment=os.getenv("ENVIRONMENT", "production"),
            # Release tracking
            release=os.getenv("GITHUB_SHA", "unknown"),
            # Additional context
            before_send=lambda event, hint: _add_trading_context(event, hint),
        )

        _sentry_initialized = True
        logger.info("✅ Sentry error monitoring initialized")
        return True

    except ImportError:
        logger.warning("sentry-sdk not installed. Install with: pip install sentry-sdk")
        return False
    except Exception as e:
        logger.warning(f"Failed to initialize Sentry: {e}")
        return False


def _add_trading_context(event, hint):
    """Add trading-specific context to Sentry events."""
    try:
        # Add trading context if available
        if "trading" in str(event.get("tags", {})).lower():
            event.setdefault("tags", {})["component"] = "trading_system"

        # Add GitHub Actions context if available
        if os.getenv("GITHUB_ACTIONS"):
            event.setdefault("tags", {})["workflow"] = os.getenv("GITHUB_WORKFLOW", "unknown")
            event.setdefault("tags", {})["run_id"] = os.getenv("GITHUB_RUN_ID", "unknown")
            event.setdefault("contexts", {})["github"] = {
                "workflow": os.getenv("GITHUB_WORKFLOW"),
                "run_id": os.getenv("GITHUB_RUN_ID"),
                "run_number": os.getenv("GITHUB_RUN_NUMBER"),
            }

        # Add account context if available
        account_info = _get_account_context()
        if account_info:
            event.setdefault("contexts", {})["account"] = account_info

    except Exception as e:
        logger.debug(f"Failed to add trading context to Sentry event: {e}")

    return event


def _get_account_context() -> Optional[dict]:
    """Get account context for Sentry events."""
    try:
        import json
        from pathlib import Path

        state_file = Path("data/system_state.json")
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)
                account = state.get("account", {})
                return {
                    "equity": account.get("current_equity"),
                    "pl": account.get("total_pl"),
                    "pl_pct": account.get("total_pl_pct"),
                }
    except Exception:
        pass
    return None


def capture_workflow_failure(reason: str, context: Optional[dict] = None):
    """Capture workflow failure in Sentry."""
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("failure_type", "workflow")
            scope.set_level("error")

            if context:
                for key, value in context.items():
                    scope.set_context(key, value)

            sentry_sdk.capture_message(f"Workflow failure: {reason}")

    except Exception as e:
        logger.debug(f"Failed to capture workflow failure in Sentry: {e}")


def capture_api_failure(api_name: str, error: Exception, context: Optional[dict] = None):
    """Capture API failure in Sentry."""
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("failure_type", "api")
            scope.set_tag("api", api_name)
            scope.set_level("error")

            if context:
                for key, value in context.items():
                    scope.set_context(key, value)

            sentry_sdk.capture_exception(error)

    except Exception as e:
        logger.debug(f"Failed to capture API failure in Sentry: {e}")


def capture_data_source_failure(source: str, symbol: str, error: str):
    """Capture data source failure in Sentry."""
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("failure_type", "data_source")
            scope.set_tag("source", source)
            scope.set_tag("symbol", symbol)
            scope.set_level("warning")

            sentry_sdk.capture_message(
                f"Data source failure: {source} failed for {symbol}: {error}"
            )

    except Exception as e:
        logger.debug(f"Failed to capture data source failure in Sentry: {e}")
