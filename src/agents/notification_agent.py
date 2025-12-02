"""
Notification Agent - Handles notifications across multiple channels

Integrates with MCP servers for:
- Slack notifications
- Email notifications
- SMS notifications (future)
- Dashboard updates
"""

import json
import logging
import os
from datetime import datetime
from enum import Enum
from typing import Any

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Notification channel types."""

    SLACK = "slack"
    EMAIL = "email"
    SMS = "sms"
    DASHBOARD = "dashboard"
    LOG = "log"


class NotificationPriority(Enum):
    """Notification priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationAgent(BaseAgent):
    """
    Notification agent for sending alerts and updates.

    Supports multiple channels:
    - Slack (via MCP)
    - Email (via MCP)
    - Dashboard updates
    - Log files
    """

    def __init__(self):
        super().__init__(name="NotificationAgent", role="Multi-Channel Notification Coordinator")
        self.enabled_channels = os.getenv(
            "NOTIFICATION_CHANNELS",
            "email,dashboard,log",  # Slack removed - use email instead
        ).split(",")

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Send a notification.

        Args:
            data: Notification data with message, channels, priority

        Returns:
            Notification result
        """
        message = data.get("message", "")
        channels = data.get("channels", self.enabled_channels)
        priority = data.get("priority", NotificationPriority.MEDIUM.value)
        notification_type = data.get("type", "info")
        context = data.get("context", {})

        if not message:
            return {"success": False, "error": "message required"}

        results = []

        for channel in channels:
            try:
                if channel == "slack":
                    result = self._send_slack_notification(message, priority, context)
                elif channel == "email":
                    result = self._send_email_notification(message, priority, context)
                elif channel == "dashboard":
                    result = self._update_dashboard(message, notification_type, context)
                elif channel == "log":
                    result = self._log_notification(message, priority, context)
                else:
                    result = {"success": False, "error": f"Unknown channel: {channel}"}

                results.append({"channel": channel, **result})
            except Exception as e:
                logger.error(f"Notification failed for {channel}: {e}")
                results.append({"channel": channel, "success": False, "error": str(e)})

        success_count = sum(1 for r in results if r.get("success"))

        return {
            "success": success_count > 0,
            "total_channels": len(channels),
            "successful_channels": success_count,
            "results": results,
        }

    def _send_slack_notification(
        self, message: str, priority: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Send Slack notification via MCP.

        Args:
            message: Notification message
            priority: Priority level
            context: Additional context

        Returns:
            Send result
        """
        logger.info(f"Slack notification ({priority}): {message[:100]}...")

        # TODO: Integrate with Slack MCP when available
        # For now, simulate

        {
            "channel": context.get("slack_channel", "#trading-alerts"),
            "message": message,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            **context,
        }

        # Would call: mcp.servers.slack.send_message(slack_payload)

        return {
            "success": True,
            "channel": "slack",
            "message_id": f"slack_{datetime.now().timestamp()}",
        }

    def _send_email_notification(
        self, message: str, priority: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Send email notification via MCP.

        Args:
            message: Notification message
            priority: Priority level
            context: Additional context

        Returns:
            Send result
        """
        logger.info(f"Email notification ({priority}): {message[:100]}...")

        # TODO: Integrate with Gmail MCP when available
        # For now, simulate

        {
            "to": context.get("recipients", [os.getenv("ALERT_EMAIL", "")]),
            "subject": f"[{priority.upper()}] Trading System Alert",
            "body": message,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
        }

        # Would call: mcp.servers.gmail.send_email(email_payload)

        return {
            "success": True,
            "channel": "email",
            "message_id": f"email_{datetime.now().timestamp()}",
        }

    def _update_dashboard(
        self, message: str, notification_type: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update dashboard with notification.

        Args:
            message: Notification message
            notification_type: Type of notification
            context: Additional context

        Returns:
            Update result
        """
        logger.info(f"Dashboard update ({notification_type}): {message[:100]}...")

        # Save notification to dashboard data
        {
            "message": message,
            "type": notification_type,
            "timestamp": datetime.now().isoformat(),
            **context,
        }

        # Would update dashboard state/store
        # For now, log it

        return {
            "success": True,
            "channel": "dashboard",
            "message_id": f"dashboard_{datetime.now().timestamp()}",
        }

    def _log_notification(
        self, message: str, priority: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Log notification to file.

        Args:
            message: Notification message
            priority: Priority level
            context: Additional context

        Returns:
            Log result
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "priority": priority,
            "message": message,
            **context,
        }

        logger.info(f"Notification logged: {json.dumps(log_entry)}")

        return {
            "success": True,
            "channel": "log",
            "message_id": f"log_{datetime.now().timestamp()}",
        }

    def send_trade_alert(self, trade_data: dict[str, Any]):
        """Send trade execution alert."""
        message = (
            f"Trade Executed: {trade_data.get('symbol')} "
            f"{trade_data.get('side', '').upper()} "
            f"{trade_data.get('quantity')} shares @ ${trade_data.get('price', 0):.2f}"
        )

        return self.analyze(
            {
                "message": message,
                "channels": ["email", "dashboard"],  # Removed Slack
                "priority": NotificationPriority.MEDIUM.value,
                "type": "trade",
                "context": trade_data,
            }
        )

    def send_risk_alert(self, risk_data: dict[str, Any]):
        """Send risk management alert."""
        message = (
            f"Risk Alert: {risk_data.get('alert_type')} - "
            f"{risk_data.get('message', 'Risk threshold exceeded')}"
        )

        return self.analyze(
            {
                "message": message,
                "channels": ["email"],  # Removed Slack
                "priority": NotificationPriority.HIGH.value,
                "type": "risk",
                "context": risk_data,
            }
        )

    def send_approval_request(self, approval_data: dict[str, Any]):
        """Send approval request notification."""
        message = (
            f"Approval Required: {approval_data.get('type')} - "
            f"{approval_data.get('description', 'Human approval needed')}"
        )

        return self.analyze(
            {
                "message": message,
                "channels": ["email"],  # Removed Slack
                "priority": NotificationPriority.CRITICAL.value,
                "type": "approval",
                "context": approval_data,
            }
        )
