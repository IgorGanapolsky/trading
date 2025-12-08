"""
Emergency Alert System - SMS/Phone notifications for critical events.

Sends immediate alerts when:
- Circuit breaker triggers (Tier 2+)
- Emergency liquidation occurs
- System errors or downtime
- Daily P/L threshold breached

Supports:
- Twilio SMS
- Email (SMTP)
- Slack webhook
- Discord webhook

Author: Trading System
Created: 2025-12-08
"""

import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)


class EmergencyAlerts:
    """
    Multi-channel emergency alert system.

    Priority levels:
    - CRITICAL: SMS + Email + Slack (circuit breaker, liquidation)
    - HIGH: Email + Slack (large losses, system errors)
    - MEDIUM: Slack only (warnings, anomalies)
    - LOW: Log only (info, daily summaries)
    """

    PRIORITY_CRITICAL = "critical"
    PRIORITY_HIGH = "high"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_LOW = "low"

    def __init__(
        self,
        twilio_sid: Optional[str] = None,
        twilio_token: Optional[str] = None,
        twilio_from: Optional[str] = None,
        twilio_to: Optional[str] = None,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_pass: Optional[str] = None,
        email_to: Optional[str] = None,
        slack_webhook: Optional[str] = None,
        discord_webhook: Optional[str] = None,
        alert_log_file: str = "data/emergency_alerts.json",
    ):
        """
        Initialize emergency alert system.

        Credentials can be passed directly or loaded from environment variables:
        - TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_TO_NUMBER
        - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO
        - SLACK_WEBHOOK_URL
        - DISCORD_WEBHOOK_URL
        """
        # Twilio SMS
        self.twilio_sid = twilio_sid or os.environ.get("TWILIO_ACCOUNT_SID")
        self.twilio_token = twilio_token or os.environ.get("TWILIO_AUTH_TOKEN")
        self.twilio_from = twilio_from or os.environ.get("TWILIO_FROM_NUMBER")
        self.twilio_to = twilio_to or os.environ.get("TWILIO_TO_NUMBER")

        # Email SMTP
        self.smtp_host = smtp_host or os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.environ.get("SMTP_USER")
        self.smtp_pass = smtp_pass or os.environ.get("SMTP_PASS")
        self.email_to = email_to or os.environ.get("ALERT_EMAIL_TO")

        # Webhooks
        self.slack_webhook = slack_webhook or os.environ.get("SLACK_WEBHOOK_URL")
        self.discord_webhook = discord_webhook or os.environ.get("DISCORD_WEBHOOK_URL")

        # Alert log
        self.alert_log_file = Path(alert_log_file)
        self.alert_log_file.parent.mkdir(parents=True, exist_ok=True)

        # Track which channels are configured
        self._log_configured_channels()

    def _log_configured_channels(self) -> None:
        """Log which alert channels are configured."""
        channels = []
        if self.twilio_sid and self.twilio_token:
            channels.append("SMS (Twilio)")
        if self.smtp_user and self.smtp_pass:
            channels.append("Email (SMTP)")
        if self.slack_webhook:
            channels.append("Slack")
        if self.discord_webhook:
            channels.append("Discord")

        if channels:
            logger.info(f"Emergency alerts configured: {', '.join(channels)}")
        else:
            logger.warning("⚠️ No emergency alert channels configured!")

    def send_alert(
        self,
        title: str,
        message: str,
        priority: str = PRIORITY_HIGH,
        data: Optional[dict] = None,
    ) -> dict[str, bool]:
        """
        Send emergency alert through appropriate channels based on priority.

        Args:
            title: Alert title/subject
            message: Alert message body
            priority: Alert priority (critical, high, medium, low)
            data: Optional additional data to include

        Returns:
            Dict of channel -> success status
        """
        results = {}
        timestamp = datetime.now().isoformat()

        # Format full message
        full_message = f"🚨 {title}\n\n{message}"
        if data:
            full_message += f"\n\nDetails: {json.dumps(data, indent=2)}"
        full_message += f"\n\nTimestamp: {timestamp}"

        # Send based on priority
        if priority == self.PRIORITY_CRITICAL:
            # CRITICAL: All channels
            results["sms"] = self._send_sms(title, message)
            results["email"] = self._send_email(title, full_message)
            results["slack"] = self._send_slack(title, message, priority, data)
            results["discord"] = self._send_discord(title, message, priority, data)

        elif priority == self.PRIORITY_HIGH:
            # HIGH: Email + Slack/Discord
            results["email"] = self._send_email(title, full_message)
            results["slack"] = self._send_slack(title, message, priority, data)
            results["discord"] = self._send_discord(title, message, priority, data)

        elif priority == self.PRIORITY_MEDIUM:
            # MEDIUM: Slack/Discord only
            results["slack"] = self._send_slack(title, message, priority, data)
            results["discord"] = self._send_discord(title, message, priority, data)

        else:
            # LOW: Log only
            logger.info(f"[{priority.upper()}] {title}: {message}")

        # Log the alert
        self._log_alert(title, message, priority, data, results)

        return results

    def _send_sms(self, title: str, message: str) -> bool:
        """Send SMS via Twilio."""
        if not all([self.twilio_sid, self.twilio_token, self.twilio_from, self.twilio_to]):
            logger.debug("SMS not configured, skipping")
            return False

        try:
            # Use Twilio REST API directly (no SDK required)
            import base64

            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_sid}/Messages.json"

            # Truncate message for SMS (160 char limit)
            sms_body = f"🚨 {title[:50]}: {message[:100]}"

            data = f"To={self.twilio_to}&From={self.twilio_from}&Body={sms_body}".encode()

            auth = base64.b64encode(f"{self.twilio_sid}:{self.twilio_token}".encode()).decode()

            req = Request(url, data=data, method="POST")
            req.add_header("Authorization", f"Basic {auth}")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")

            with urlopen(req, timeout=10) as response:
                if response.status == 201:
                    logger.info(f"✅ SMS sent to {self.twilio_to}")
                    return True

        except Exception as e:
            logger.error(f"❌ SMS failed: {e}")

        return False

    def _send_email(self, subject: str, body: str) -> bool:
        """Send email via SMTP."""
        if not all([self.smtp_user, self.smtp_pass, self.email_to]):
            logger.debug("Email not configured, skipping")
            return False

        try:
            msg = MIMEText(body)
            msg["Subject"] = f"🚨 Trading Alert: {subject}"
            msg["From"] = self.smtp_user
            msg["To"] = self.email_to

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)

            logger.info(f"✅ Email sent to {self.email_to}")
            return True

        except Exception as e:
            logger.error(f"❌ Email failed: {e}")

        return False

    def _send_slack(
        self,
        title: str,
        message: str,
        priority: str,
        data: Optional[dict] = None,
    ) -> bool:
        """Send Slack webhook notification."""
        if not self.slack_webhook:
            logger.debug("Slack not configured, skipping")
            return False

        try:
            # Color based on priority
            colors = {
                self.PRIORITY_CRITICAL: "#FF0000",  # Red
                self.PRIORITY_HIGH: "#FF9900",      # Orange
                self.PRIORITY_MEDIUM: "#FFCC00",    # Yellow
                self.PRIORITY_LOW: "#00CC00",       # Green
            }

            payload = {
                "attachments": [{
                    "color": colors.get(priority, "#808080"),
                    "title": f"🚨 {title}",
                    "text": message,
                    "fields": [
                        {"title": "Priority", "value": priority.upper(), "short": True},
                        {"title": "Time", "value": datetime.now().strftime("%H:%M:%S"), "short": True},
                    ],
                    "footer": "Trading System Alert",
                }]
            }

            if data:
                payload["attachments"][0]["fields"].append({
                    "title": "Details",
                    "value": f"```{json.dumps(data, indent=2)[:500]}```",
                    "short": False,
                })

            req = Request(
                self.slack_webhook,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )

            with urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info("✅ Slack notification sent")
                    return True

        except Exception as e:
            logger.error(f"❌ Slack failed: {e}")

        return False

    def _send_discord(
        self,
        title: str,
        message: str,
        priority: str,
        data: Optional[dict] = None,
    ) -> bool:
        """Send Discord webhook notification."""
        if not self.discord_webhook:
            logger.debug("Discord not configured, skipping")
            return False

        try:
            # Color based on priority (Discord uses decimal)
            colors = {
                self.PRIORITY_CRITICAL: 16711680,  # Red
                self.PRIORITY_HIGH: 16744192,      # Orange
                self.PRIORITY_MEDIUM: 16776960,    # Yellow
                self.PRIORITY_LOW: 65280,          # Green
            }

            payload = {
                "embeds": [{
                    "title": f"🚨 {title}",
                    "description": message,
                    "color": colors.get(priority, 8421504),
                    "fields": [
                        {"name": "Priority", "value": priority.upper(), "inline": True},
                        {"name": "Time", "value": datetime.now().strftime("%H:%M:%S"), "inline": True},
                    ],
                    "footer": {"text": "Trading System Alert"},
                }]
            }

            if data:
                payload["embeds"][0]["fields"].append({
                    "name": "Details",
                    "value": f"```json\n{json.dumps(data, indent=2)[:500]}\n```",
                    "inline": False,
                })

            req = Request(
                self.discord_webhook,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )

            with urlopen(req, timeout=10) as response:
                if response.status == 204:
                    logger.info("✅ Discord notification sent")
                    return True

        except Exception as e:
            logger.error(f"❌ Discord failed: {e}")

        return False

    def _log_alert(
        self,
        title: str,
        message: str,
        priority: str,
        data: Optional[dict],
        results: dict[str, bool],
    ) -> None:
        """Log alert to file for audit trail."""
        try:
            # Load existing alerts
            alerts = []
            if self.alert_log_file.exists():
                with open(self.alert_log_file) as f:
                    alerts = json.load(f)

            # Add new alert
            alerts.append({
                "timestamp": datetime.now().isoformat(),
                "title": title,
                "message": message,
                "priority": priority,
                "data": data,
                "delivery_results": results,
            })

            # Keep last 1000 alerts
            alerts = alerts[-1000:]

            # Save
            with open(self.alert_log_file, "w") as f:
                json.dump(alerts, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to log alert: {e}")

    # Convenience methods for common alerts

    def circuit_breaker_alert(self, tier: str, trigger_reason: str, current_loss: float) -> None:
        """Alert for circuit breaker trigger."""
        self.send_alert(
            title=f"Circuit Breaker {tier} Triggered",
            message=f"Trading halted: {trigger_reason}",
            priority=self.PRIORITY_CRITICAL if tier in ["CRITICAL", "HALT"] else self.PRIORITY_HIGH,
            data={
                "tier": tier,
                "trigger_reason": trigger_reason,
                "current_loss_pct": f"{current_loss:.2%}",
            },
        )

    def liquidation_alert(self, positions_closed: list, total_value: float) -> None:
        """Alert for emergency liquidation."""
        self.send_alert(
            title="Emergency Liquidation Executed",
            message=f"Closed {len(positions_closed)} positions worth ${total_value:,.2f}",
            priority=self.PRIORITY_CRITICAL,
            data={
                "positions_closed": positions_closed[:10],  # Limit for message size
                "total_value": total_value,
            },
        )

    def daily_loss_alert(self, loss_pct: float, loss_amount: float) -> None:
        """Alert for significant daily loss."""
        priority = self.PRIORITY_CRITICAL if loss_pct >= 0.03 else self.PRIORITY_HIGH
        self.send_alert(
            title=f"Daily Loss Alert: {loss_pct:.2%}",
            message=f"Portfolio down ${abs(loss_amount):,.2f} today",
            priority=priority,
            data={
                "loss_pct": f"{loss_pct:.2%}",
                "loss_amount": f"${loss_amount:,.2f}",
            },
        )

    def system_error_alert(self, error_type: str, error_message: str) -> None:
        """Alert for system errors."""
        self.send_alert(
            title=f"System Error: {error_type}",
            message=error_message,
            priority=self.PRIORITY_HIGH,
            data={"error_type": error_type},
        )

    def kill_switch_alert(self, triggered_by: str, reason: str) -> None:
        """Alert when kill switch is activated."""
        self.send_alert(
            title="🛑 KILL SWITCH ACTIVATED",
            message=f"All trading halted by {triggered_by}: {reason}",
            priority=self.PRIORITY_CRITICAL,
            data={
                "triggered_by": triggered_by,
                "reason": reason,
            },
        )


# Singleton instance for easy access
_alerts_instance: Optional[EmergencyAlerts] = None


def get_alerts() -> EmergencyAlerts:
    """Get or create singleton alerts instance."""
    global _alerts_instance
    if _alerts_instance is None:
        _alerts_instance = EmergencyAlerts()
    return _alerts_instance


def send_critical_alert(title: str, message: str, data: Optional[dict] = None) -> None:
    """Quick function to send critical alert."""
    get_alerts().send_alert(title, message, EmergencyAlerts.PRIORITY_CRITICAL, data)


def send_high_alert(title: str, message: str, data: Optional[dict] = None) -> None:
    """Quick function to send high priority alert."""
    get_alerts().send_alert(title, message, EmergencyAlerts.PRIORITY_HIGH, data)
