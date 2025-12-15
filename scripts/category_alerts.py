#!/usr/bin/env python3
"""
Category Performance Alerts

Monitor category P/L and send alerts when thresholds are hit.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class Alert:
    """Performance alert."""
    timestamp: str
    category: str
    alert_type: str  # 'profit_target', 'loss_threshold', 'win_streak', 'loss_streak'
    value: float
    threshold: float
    message: str
    severity: str  # 'info', 'warning', 'critical'


class CategoryAlerts:
    """Monitor and alert on category performance."""

    # Alert thresholds
    PROFIT_TARGET = 100.0  # Alert when category hits +$100
    LOSS_THRESHOLD = 50.0  # Alert when category loses -$50
    WIN_STREAK = 5  # Alert on 5 consecutive wins
    LOSS_STREAK = 3  # Alert on 3 consecutive losses

    def __init__(self):
        self.data_dir = Path('data')
        self.performance_file = self.data_dir / 'enhanced_performance_log.json'
        self.alerts_file = self.data_dir / 'category_alerts.json'

    def check_alerts(self) -> list[Alert]:
        """Check for alert conditions."""

        if not self.performance_file.exists():
            return []

        with open(self.performance_file) as f:
            log = json.load(f)

        if not log:
            return []

        latest = log[-1]
        alerts = []

        # Check each category
        for cat_name in ['crypto', 'equities', 'options', 'bonds']:
            cat_data = latest.get(cat_name, {})
            total_pl = cat_data.get('total_pl', 0)

            # Profit target hit
            if total_pl >= self.PROFIT_TARGET:
                alerts.append(Alert(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    category=cat_name,
                    alert_type='profit_target',
                    value=total_pl,
                    threshold=self.PROFIT_TARGET,
                    message=f"🎉 {cat_name.upper()} hit profit target! P/L: ${total_pl:+.2f}",
                    severity='info'
                ))

            # Loss threshold breached
            if total_pl <= -self.LOSS_THRESHOLD:
                alerts.append(Alert(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    category=cat_name,
                    alert_type='loss_threshold',
                    value=total_pl,
                    threshold=-self.LOSS_THRESHOLD,
                    message=f"⚠️ {cat_name.upper()} hit loss threshold! P/L: ${total_pl:+.2f}",
                    severity='warning'
                ))

        # Check win/loss streaks (requires historical data)
        if len(log) >= 5:
            for cat_name in ['crypto', 'equities', 'options', 'bonds']:
                streak_alerts = self._check_streaks(log[-5:], cat_name)
                alerts.extend(streak_alerts)

        return alerts

    def _check_streaks(self, recent_log: list[dict], category: str) -> list[Alert]:
        """Check for win/loss streaks in a category."""

        alerts = []

        # Extract P/L for category over time
        pls = []
        for entry in recent_log:
            cat_data = entry.get(category, {})
            pls.append(cat_data.get('total_pl', 0))

        # Check for consecutive wins
        win_streak = 0
        for pl in pls:
            if pl > 0:
                win_streak += 1
            else:
                win_streak = 0

        if win_streak >= self.WIN_STREAK:
            alerts.append(Alert(
                timestamp=datetime.now(timezone.utc).isoformat(),
                category=category,
                alert_type='win_streak',
                value=win_streak,
                threshold=self.WIN_STREAK,
                message=f"🔥 {category.upper()} on {win_streak}-day win streak!",
                severity='info'
            ))

        # Check for consecutive losses
        loss_streak = 0
        for pl in pls:
            if pl < 0:
                loss_streak += 1
            else:
                loss_streak = 0

        if loss_streak >= self.LOSS_STREAK:
            alerts.append(Alert(
                timestamp=datetime.now(timezone.utc).isoformat(),
                category=category,
                alert_type='loss_streak',
                value=loss_streak,
                threshold=self.LOSS_STREAK,
                message=f"🚨 {category.upper()} on {loss_streak}-day loss streak!",
                severity='critical'
            ))

        return alerts

    def save_alerts(self, alerts: list[Alert]):
        """Save alerts to file."""

        if not alerts:
            return

        # Load existing alerts
        if self.alerts_file.exists():
            with open(self.alerts_file) as f:
                all_alerts = json.load(f)
        else:
            all_alerts = []

        # Add new alerts
        for alert in alerts:
            all_alerts.append({
                'timestamp': alert.timestamp,
                'category': alert.category,
                'alert_type': alert.alert_type,
                'value': alert.value,
                'threshold': alert.threshold,
                'message': alert.message,
                'severity': alert.severity
            })

        # Save
        self.data_dir.mkdir(exist_ok=True)
        with open(self.alerts_file, 'w') as f:
            json.dump(all_alerts, f, indent=2)

        print(f"✅ Saved {len(alerts)} alert(s)")

    def get_recent_alerts(self, hours: int = 24) -> list[dict]:
        """Get alerts from the last N hours."""

        if not self.alerts_file.exists():
            return []

        with open(self.alerts_file) as f:
            all_alerts = json.load(f)

        # Filter by time
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        recent = []
        for alert in all_alerts:
            alert_time = datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00'))
            if alert_time >= cutoff:
                recent.append(alert)

        return recent

    def print_alerts(self, alerts: list[Alert]):
        """Print alerts to console."""

        if not alerts:
            print("✅ No alerts")
            return

        print(f"\n🚨 {len(alerts)} ALERT(S) DETECTED:\n")
        for alert in alerts:
            icon = "🎉" if alert.severity == 'info' else "⚠️" if alert.severity == 'warning' else "🚨"
            print(f"{icon} {alert.message}")
            print(f"   Category: {alert.category.upper()}")
            print(f"   Value: ${alert.value:+.2f} | Threshold: ${alert.threshold:+.2f}")
            print()


if __name__ == '__main__':
    monitor = CategoryAlerts()
    alerts = monitor.check_alerts()
    monitor.print_alerts(alerts)
    monitor.save_alerts(alerts)

    # Show recent alerts
    recent = monitor.get_recent_alerts(hours=24)
    if recent:
        print(f"\n📋 Recent Alerts (Last 24 Hours): {len(recent)}")
        for alert in recent:
            print(f"  - [{alert['severity'].upper()}] {alert['message']}")
