"""
Error monitoring integration with Sentry.

Provides centralized error tracking for the trading system.
Integrates with GitHub Actions, workflow failures, and runtime errors.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_sentry_initialized = False


def init_sentry(dsn: str | None = None) -> bool:
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


def _get_account_context() -> dict | None:
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


def capture_workflow_failure(reason: str, context: dict | None = None):
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


def capture_api_failure(api_name: str, error: Exception, context: dict | None = None):
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


# ============================================
# Slack Direct Notifications (for critical alerts)
# ============================================

_slack_webhook_url = None


def init_slack_alerts(webhook_url: str | None = None) -> bool:
    """
    Initialize Slack webhook for direct alerts.

    Args:
        webhook_url: Slack webhook URL (optional, reads from SLACK_WEBHOOK_URL env var)

    Returns:
        True if initialized successfully, False otherwise
    """
    global _slack_webhook_url

    _slack_webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    if not _slack_webhook_url:
        logger.debug("Slack webhook URL not configured (SLACK_WEBHOOK_URL env var not set)")
        return False

    logger.info("Slack webhook alerts initialized")
    return True


def send_slack_alert(
    message: str,
    level: str = "error",
    context: dict | None = None,
    channel: str | None = None,
) -> bool:
    """
    Send alert directly to Slack via webhook.

    Args:
        message: Alert message
        level: Alert level (error, warning, info)
        context: Additional context to include
        channel: Override channel (if webhook supports it)

    Returns:
        True if sent successfully, False otherwise
    """
    global _slack_webhook_url

    # Try to initialize if not already done
    if not _slack_webhook_url:
        init_slack_alerts()

    if not _slack_webhook_url:
        logger.debug("Slack alerts not configured, skipping notification")
        return False

    try:
        from datetime import datetime

        import requests

        # Build Slack message with blocks
        emoji_map = {"error": ":rotating_light:", "warning": ":warning:", "info": ":information_source:"}
        color_map = {"error": "#dc3545", "warning": "#ffc107", "info": "#17a2b8"}

        emoji = emoji_map.get(level, ":bell:")
        color = color_map.get(level, "#6c757d")

        # Build attachment blocks
        attachment = {
            "color": color,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji} *Trading System Alert*\n{message}",
                    },
                },
            ],
        }

        # Add context if provided
        if context:
            fields = []
            for key, value in context.items():
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{key}:* {value}",
                })
            if fields:
                attachment["blocks"].append({
                    "type": "section",
                    "fields": fields[:10],  # Slack limit
                })

        # Add timestamp
        attachment["blocks"].append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Timestamp: {datetime.now().isoformat()}",
                }
            ],
        })

        payload = {"attachments": [attachment]}

        response = requests.post(
            _slack_webhook_url,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()

        logger.debug(f"Slack alert sent: {message[:50]}...")
        return True

    except Exception as e:
        logger.warning(f"Failed to send Slack alert: {e}")
        return False


def capture_critical_error(error: Exception | str, context: dict | None = None):
    """
    Capture a critical error in both Sentry and Slack.

    Use this for errors that need immediate attention.

    Args:
        error: The error/exception or error message
        context: Additional context
    """
    error_msg = str(error) if isinstance(error, Exception) else error

    # Send to Sentry
    if _sentry_initialized:
        try:
            import sentry_sdk

            with sentry_sdk.push_scope() as scope:
                scope.set_tag("severity", "critical")
                scope.set_level("fatal")

                if context:
                    for key, value in context.items():
                        scope.set_context(key, {"value": value})

                if isinstance(error, Exception):
                    sentry_sdk.capture_exception(error)
                else:
                    sentry_sdk.capture_message(error_msg, level="fatal")

        except Exception as e:
            logger.debug(f"Failed to capture critical error in Sentry: {e}")

    # Also send to Slack for immediate visibility
    send_slack_alert(
        message=f"CRITICAL: {error_msg}",
        level="error",
        context=context,
    )
