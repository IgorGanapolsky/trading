#!/usr/bin/env python3
"""
CEO NOTIFICATION SCRIPT

Multi-channel notification system for critical alerts.
Supports: Slack, Discord, Email (SendGrid), and GitHub Issue creation.

CRITICAL: This is the CEO's early warning system. When this fires,
something has gone wrong that requires immediate attention.

Usage:
    python scripts/notify_ceo.py --type critical --message "Health check failed"
    python scripts/notify_ceo.py --type warning --message "Stale data detected"
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

# Alert types and their severity
ALERT_TYPES = {
    "critical": {"emoji": "🚨", "color": "#FF0000", "priority": 1},
    "warning": {"emoji": "⚠️", "color": "#FFA500", "priority": 2},
    "info": {"emoji": "ℹ️", "color": "#0000FF", "priority": 3},
    "success": {"emoji": "✅", "color": "#00FF00", "priority": 4},
}


def send_slack_notification(message: str, alert_type: str = "critical") -> bool:
    """Send notification via Slack webhook."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print("  ⚠️  SLACK_WEBHOOK_URL not set - skipping Slack")
        return False

    alert_config = ALERT_TYPES.get(alert_type, ALERT_TYPES["critical"])

    payload = {
        "text": f"{alert_config['emoji']} *{alert_type.upper()}* - Igor Trading System",
        "attachments": [
            {
                "color": alert_config["color"],
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": message},
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Time:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                            }
                        ],
                    },
                ],
            }
        ],
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as response:
            if response.status == 200:
                print("  ✅ Slack notification sent")
                return True
            print(f"  ❌ Slack returned status {response.status}")
            return False
    except URLError as e:
        print(f"  ❌ Slack notification failed: {e}")
        return False


def send_discord_notification(message: str, alert_type: str = "critical") -> bool:
    """Send notification via Discord webhook."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("  ⚠️  DISCORD_WEBHOOK_URL not set - skipping Discord")
        return False

    alert_config = ALERT_TYPES.get(alert_type, ALERT_TYPES["critical"])

    # Convert hex color to int
    color_int = int(alert_config["color"].lstrip("#"), 16)

    payload = {
        "content": f"{alert_config['emoji']} **{alert_type.upper()}** - Igor Trading System",
        "embeds": [
            {
                "title": "Trading System Alert",
                "description": message,
                "color": color_int,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "footer": {"text": "Igor Trading System v2"},
            }
        ],
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as response:
            if response.status in (200, 204):
                print("  ✅ Discord notification sent")
                return True
            print(f"  ❌ Discord returned status {response.status}")
            return False
    except URLError as e:
        print(f"  ❌ Discord notification failed: {e}")
        return False


def send_email_notification(message: str, alert_type: str = "critical") -> bool:
    """Send notification via SendGrid email."""
    api_key = os.getenv("SENDGRID_API_KEY")
    to_email = os.getenv("CEO_EMAIL", "igor@example.com")
    from_email = os.getenv("SENDGRID_FROM_EMAIL", "alerts@trading-system.com")

    if not api_key:
        print("  ⚠️  SENDGRID_API_KEY not set - skipping Email")
        return False

    alert_config = ALERT_TYPES.get(alert_type, ALERT_TYPES["critical"])

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email, "name": "Trading System Alerts"},
        "subject": f"{alert_config['emoji']} [{alert_type.upper()}] Igor Trading System Alert",
        "content": [
            {
                "type": "text/html",
                "value": f"""
                <html>
                <body style="font-family: Arial, sans-serif;">
                    <h2 style="color: {alert_config["color"]};">
                        {alert_config["emoji"]} {alert_type.upper()} ALERT
                    </h2>
                    <p style="font-size: 16px;">{message.replace(chr(10), "<br>")}</p>
                    <hr>
                    <p style="color: #666; font-size: 12px;">
                        Time: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}<br>
                        System: Igor Trading System v2
                    </p>
                </body>
                </html>
                """,
            }
        ],
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urlopen(req, timeout=10) as response:
            if response.status in (200, 202):
                print("  ✅ Email notification sent")
                return True
            print(f"  ❌ SendGrid returned status {response.status}")
            return False
    except URLError as e:
        print(f"  ❌ Email notification failed: {e}")
        return False


def create_github_issue(message: str, alert_type: str = "critical") -> bool:
    """Create a GitHub issue for tracking the alert."""
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    repo = os.getenv("GITHUB_REPOSITORY", "IgorGanapolsky/trading")

    if not token:
        print("  ⚠️  GITHUB_TOKEN not set - skipping GitHub Issue")
        return False

    alert_config = ALERT_TYPES.get(alert_type, ALERT_TYPES["critical"])

    # Only create issues for critical alerts
    if alert_type != "critical":
        print(f"  ⚠️  GitHub issues only created for critical alerts (got: {alert_type})")
        return False

    labels = ["alert", "automated", alert_type]

    payload = {
        "title": f"{alert_config['emoji']} [{alert_type.upper()}] Trading System Alert - {datetime.utcnow().strftime('%Y-%m-%d')}",
        "body": f"""## Alert Details

{message}

---

**Time:** {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}
**Type:** {alert_type}
**Source:** Automated monitoring

---
*This issue was created automatically by the trading system's self-healing monitor.*
""",
        "labels": labels,
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            f"https://api.github.com/repos/{repo}/issues",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urlopen(req, timeout=10) as response:
            if response.status == 201:
                result = json.loads(response.read().decode("utf-8"))
                print(f"  ✅ GitHub issue created: {result.get('html_url', 'unknown')}")
                return True
            print(f"  ❌ GitHub returned status {response.status}")
            return False
    except URLError as e:
        print(f"  ❌ GitHub issue creation failed: {e}")
        return False


def log_alert(message: str, alert_type: str, channels_sent: list) -> None:
    """Log the alert to local file for audit trail."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "ceo_alerts.jsonl"

    alert_record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "type": alert_type,
        "message": message,
        "channels_sent": channels_sent,
        "channels_configured": {
            "slack": bool(os.getenv("SLACK_WEBHOOK_URL")),
            "discord": bool(os.getenv("DISCORD_WEBHOOK_URL")),
            "email": bool(os.getenv("SENDGRID_API_KEY")),
            "github": bool(os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")),
        },
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(alert_record) + "\n")


def notify_ceo(message: str, alert_type: str = "critical") -> bool:
    """
    Send notification to CEO via all configured channels.

    Returns True if at least one notification was sent successfully.
    """
    print(f"\n{'=' * 60}")
    print(f"{ALERT_TYPES[alert_type]['emoji']} CEO NOTIFICATION - {alert_type.upper()}")
    print(f"{'=' * 60}")
    print(f"\nMessage: {message[:100]}{'...' if len(message) > 100 else ''}")
    print("\nSending via configured channels...")

    channels_sent = []

    # Try all channels - we want redundancy
    if send_slack_notification(message, alert_type):
        channels_sent.append("slack")

    if send_discord_notification(message, alert_type):
        channels_sent.append("discord")

    if send_email_notification(message, alert_type):
        channels_sent.append("email")

    if alert_type == "critical":
        if create_github_issue(message, alert_type):
            channels_sent.append("github")

    # Log for audit trail
    log_alert(message, alert_type, channels_sent)

    print(f"\n{'=' * 60}")
    if channels_sent:
        print(f"✅ Notification sent via: {', '.join(channels_sent)}")
    else:
        print("❌ WARNING: No notifications were sent!")
        print("   Configure at least one channel:")
        print("   - SLACK_WEBHOOK_URL")
        print("   - DISCORD_WEBHOOK_URL")
        print("   - SENDGRID_API_KEY")
        print("   - GITHUB_TOKEN (for issue creation)")
    print(f"{'=' * 60}\n")

    return len(channels_sent) > 0


def main():
    parser = argparse.ArgumentParser(description="Send CEO notifications")
    parser.add_argument(
        "--type",
        choices=["critical", "warning", "info", "success"],
        default="critical",
        help="Alert type/severity",
    )
    parser.add_argument(
        "--message",
        required=True,
        help="Alert message to send",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be sent without actually sending",
    )

    args = parser.parse_args()

    if args.dry_run:
        print(f"DRY RUN - Would send {args.type} alert:")
        print(f"  Message: {args.message}")
        print("  Channels configured:")
        print(f"    - Slack: {bool(os.getenv('SLACK_WEBHOOK_URL'))}")
        print(f"    - Discord: {bool(os.getenv('DISCORD_WEBHOOK_URL'))}")
        print(f"    - Email: {bool(os.getenv('SENDGRID_API_KEY'))}")
        print(f"    - GitHub: {bool(os.getenv('GITHUB_TOKEN') or os.getenv('GH_TOKEN'))}")
        return 0

    success = notify_ceo(args.message, args.type)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
