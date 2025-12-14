"""
Hallucination Alert System

Sends Slack/email notifications when hallucinations are detected.
Configurable alert thresholds and channels.

Created: Dec 11, 2025
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

ALERT_LOG_PATH = Path("data/alert_log.json")


@dataclass
class Alert:
    """Represents an alert to be sent."""

    alert_id: str
    timestamp: str
    severity: str  # "info", "warning", "critical"
    alert_type: str  # "hallucination", "circuit_breaker", "reconciliation", etc.
    title: str
    message: str
    context: dict[str, Any]
    sent_slack: bool = False
    sent_email: bool = False


class HallucinationAlertSystem:
    """
    Multi-channel alert system for hallucination detection.

    Supports:
    - Slack webhooks
    - Email notifications
    - Console logging
    - Alert history tracking
    """

    def __init__(
        self,
        slack_webhook_url: Optional[str] = None,
        email_config: Optional[dict] = None,
        min_severity_slack: str = "warning",  # Only send warning+ to Slack
        min_severity_email: str = "critical",  # Only send critical to email
    ):
        self.slack_webhook_url = slack_webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.email_config = email_config or self._get_email_config()
        self.min_severity_slack = min_severity_slack
        self.min_severity_email = min_severity_email

        self.alert_history: list[Alert] = []

        self._severity_levels = {"info": 0, "warning": 1, "critical": 2}

        logger.info("HallucinationAlertSystem initialized")

    def _get_email_config(self) -> dict:
        """Get email config from environment."""
        return {
            "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "sender_email": os.getenv("ALERT_SENDER_EMAIL"),
            "sender_password": os.getenv("ALERT_SENDER_PASSWORD"),
            "recipient_email": os.getenv("ALERT_RECIPIENT_EMAIL"),
        }

    def send_alert(
        self,
        severity: str,
        alert_type: str,
        title: str,
        message: str,
        context: Optional[dict] = None,
    ) -> Alert:
        """
        Send an alert through configured channels.

        Args:
            severity: "info", "warning", or "critical"
            alert_type: Type of alert (hallucination, circuit_breaker, etc.)
            title: Alert title
            message: Alert message
            context: Additional context

        Returns:
            Alert object with send status
        """
        import uuid

        alert = Alert(
            alert_id=f"alert_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            severity=severity,
            alert_type=alert_type,
            title=title,
            message=message,
            context=context or {},
        )

        # Always log
        log_level = {
            "info": logging.INFO,
            "warning": logging.WARNING,
            "critical": logging.CRITICAL,
        }.get(severity, logging.INFO)
        logger.log(log_level, f"[{alert_type.upper()}] {title}: {message}")

        # Send to Slack if severity meets threshold
        if self._should_send_slack(severity):
            alert.sent_slack = self._send_slack(alert)

        # Send email if severity meets threshold
        if self._should_send_email(severity):
            alert.sent_email = self._send_email(alert)

        self.alert_history.append(alert)
        self._save_alert_history()

        return alert

    def send_hallucination_alert(
        self,
        model: str,
        hallucination_type: str,
        claimed_value: Any,
        actual_value: Any,
        severity: str = "warning",
    ) -> Alert:
        """Send alert for detected hallucination."""
        return self.send_alert(
            severity=severity,
            alert_type="hallucination",
            title=f"LLM Hallucination Detected: {model}",
            message=(
                f"Model {model} hallucinated a {hallucination_type}.\n"
                f"Claimed: {claimed_value}\n"
                f"Actual: {actual_value}"
            ),
            context={
                "model": model,
                "hallucination_type": hallucination_type,
                "claimed": str(claimed_value),
                "actual": str(actual_value),
            },
        )

    def send_circuit_breaker_alert(
        self,
        model: str,
        reason: str,
        accuracy: float,
    ) -> Alert:
        """Send alert when circuit breaker trips."""
        return self.send_alert(
            severity="critical",
            alert_type="circuit_breaker",
            title=f"🔴 Circuit Breaker Tripped: {model}",
            message=(
                f"Model {model} has been DISABLED.\n"
                f"Reason: {reason}\n"
                f"Current accuracy: {accuracy:.1%}"
            ),
            context={
                "model": model,
                "reason": reason,
                "accuracy": accuracy,
            },
        )

    def send_reconciliation_alert(
        self,
        discrepancy_type: str,
        symbol: str,
        claimed_value: Any,
        actual_value: Any,
    ) -> Alert:
        """Send alert for position reconciliation failure."""
        severity = "critical" if discrepancy_type == "phantom_position" else "warning"
        return self.send_alert(
            severity=severity,
            alert_type="reconciliation",
            title=f"Position Reconciliation Failed: {symbol}",
            message=(
                f"Discrepancy type: {discrepancy_type}\n"
                f"Symbol: {symbol}\n"
                f"Claimed: {claimed_value}\n"
                f"Actual: {actual_value}"
            ),
            context={
                "discrepancy_type": discrepancy_type,
                "symbol": symbol,
                "claimed": str(claimed_value),
                "actual": str(actual_value),
            },
        )

    def send_backtest_failure_alert(
        self,
        symbol: str,
        signal_direction: str,
        model: str,
        reason: str,
    ) -> Alert:
        """Send alert when backtest fails."""
        return self.send_alert(
            severity="warning",
            alert_type="backtest_failure",
            title=f"Backtest Failed: {signal_direction} {symbol}",
            message=(f"Signal from {model} failed backtest validation.\nReason: {reason}"),
            context={
                "symbol": symbol,
                "signal_direction": signal_direction,
                "model": model,
                "reason": reason,
            },
        )

    def _should_send_slack(self, severity: str) -> bool:
        """Check if severity meets Slack threshold."""
        if not self.slack_webhook_url:
            return False
        return self._severity_levels.get(severity, 0) >= self._severity_levels.get(
            self.min_severity_slack, 1
        )

    def _should_send_email(self, severity: str) -> bool:
        """Check if severity meets email threshold."""
        if not self.email_config.get("sender_email"):
            return False
        return self._severity_levels.get(severity, 0) >= self._severity_levels.get(
            self.min_severity_email, 2
        )

    def _send_slack(self, alert: Alert) -> bool:
        """Send alert to Slack webhook."""
        try:
            import urllib.request

            # Format message with emoji based on severity
            emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(alert.severity, "📢")

            payload = {
                "text": f"{emoji} *{alert.title}*",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"{emoji} {alert.title}",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": alert.message,
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Severity:* {alert.severity} | *Type:* {alert.alert_type} | *Time:* {alert.timestamp}",
                            },
                        ],
                    },
                ],
            }

            req = urllib.request.Request(
                self.slack_webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            logger.info(f"Slack alert sent: {alert.alert_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    def _send_email(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            config = self.email_config
            if not all(
                [
                    config.get("sender_email"),
                    config.get("sender_password"),
                    config.get("recipient_email"),
                ]
            ):
                logger.warning("Email config incomplete - skipping email alert")
                return False

            msg = MIMEMultipart()
            msg["From"] = config["sender_email"]
            msg["To"] = config["recipient_email"]
            msg["Subject"] = f"[{alert.severity.upper()}] {alert.title}"

            body = f"""
Trading System Alert
====================

Severity: {alert.severity.upper()}
Type: {alert.alert_type}
Time: {alert.timestamp}

{alert.message}

Context:
{json.dumps(alert.context, indent=2)}

---
This is an automated alert from the Trading System.
            """

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
                server.starttls()
                server.login(config["sender_email"], config["sender_password"])
                server.send_message(msg)

            logger.info(f"Email alert sent: {alert.alert_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    def get_alert_summary(self, hours: int = 24) -> dict[str, Any]:
        """Get summary of recent alerts."""
        cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        recent = [a for a in self.alert_history if a.timestamp >= cutoff_str]

        by_type = {}
        by_severity = {}
        for alert in recent:
            by_type[alert.alert_type] = by_type.get(alert.alert_type, 0) + 1
            by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1

        return {
            "period_hours": hours,
            "total_alerts": len(recent),
            "by_type": by_type,
            "by_severity": by_severity,
            "latest_alerts": [
                {
                    "title": a.title,
                    "severity": a.severity,
                    "timestamp": a.timestamp,
                }
                for a in recent[-5:]
            ],
        }

    def _save_alert_history(self) -> None:
        """Save alert history to disk."""
        ALERT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Keep last 500 alerts
        recent = self.alert_history[-500:]

        data = {
            "alerts": [
                {
                    "alert_id": a.alert_id,
                    "timestamp": a.timestamp,
                    "severity": a.severity,
                    "alert_type": a.alert_type,
                    "title": a.title,
                    "message": a.message,
                    "sent_slack": a.sent_slack,
                    "sent_email": a.sent_email,
                }
                for a in recent
            ],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with open(ALERT_LOG_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save alert history: {e}")
