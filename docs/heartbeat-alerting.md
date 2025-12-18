# Heartbeat Alerting System

**Purpose**: Monitor the trading scheduler's health and alert when it becomes unresponsive.

**Created**: 2025-12-18
**Status**: Production Ready
**Priority**: P0 (Critical Infrastructure)

---

## Overview

The heartbeat alerting system monitors `data/scheduler_heartbeat.json` to ensure the trading scheduler is running correctly. It alerts when the heartbeat is missing or stale (>2 hours old during market hours).

### Components

1. **Script**: `/home/user/trading/scripts/heartbeat_alert.py`
   - Python script that checks heartbeat and sends alerts
   - Can be run manually, via cron, or GitHub Actions

2. **Workflow**: `/home/user/trading/.github/workflows/heartbeat-alert.yml`
   - Runs automatically every hour during market hours
   - Creates GitHub issues on failures
   - Auto-closes issues when resolved

3. **Heartbeat File**: `/home/user/trading/data/scheduler_heartbeat.json`
   - Updated every 30 minutes by scheduler-heartbeat workflow
   - Contains last_run timestamp and metadata

---

## How It Works

### Heartbeat Generation

The `scheduler-heartbeat.yml` workflow runs every 30 minutes during market hours (9:30 AM - 4:00 PM ET) and writes:

```json
{
  "last_run": "2025-12-18T14:30:00Z",
  "source": "github_actions",
  "workflow": "scheduler-heartbeat",
  "runner": "Linux",
  "run_id": "1234567890"
}
```

### Heartbeat Monitoring

The `heartbeat_alert.py` script:
1. Checks if market is open (uses `src/utils/market_hours.py`)
2. Reads `data/scheduler_heartbeat.json`
3. Calculates age of `last_run` timestamp
4. Alerts if age > threshold (default: 120 minutes)

### Alert Channels

Alerts are sent via `src/safety/emergency_alerts.py`:
- **CRITICAL Priority** (missing or very stale):
  - SMS (Twilio) - if configured
  - Email (SMTP) - if configured
  - Slack webhook - if configured
  - Discord webhook - if configured
  - GitHub Issue - always created

- **Logs**:
  - `data/heartbeat_alerts.json` - Alert history (last 500)
  - `data/emergency_alerts.json` - Emergency alert log

---

## Usage

### Manual Execution

```bash
# Check with default settings (2 hour threshold)
python3 scripts/heartbeat_alert.py

# Check with custom threshold (90 minutes)
python3 scripts/heartbeat_alert.py --threshold 90

# Dry run (check only, no alerts)
python3 scripts/heartbeat_alert.py --dry-run

# Force check even outside market hours
python3 scripts/heartbeat_alert.py --force

# Custom heartbeat file location
python3 scripts/heartbeat_alert.py --heartbeat-file data/custom_heartbeat.json
```

### Exit Codes

- `0` - Heartbeat is healthy or check was skipped (outside market hours)
- `1` - Heartbeat is stale or missing (CRITICAL)

### GitHub Actions Workflow

The workflow runs automatically:
- **Schedule**: Every hour during market hours (8 AM - 6 PM ET)
- **Manual**: Can be triggered via `workflow_dispatch`

**Manual Trigger**:
```bash
# Trigger via GitHub CLI
gh workflow run heartbeat-alert.yml

# With custom parameters
gh workflow run heartbeat-alert.yml \
  -f force_check=true \
  -f threshold_minutes=90

# Dry run
gh workflow run heartbeat-alert.yml \
  -f dry_run=true
```

**Via GitHub UI**:
1. Go to Actions → Scheduler Heartbeat Alert
2. Click "Run workflow"
3. Set optional parameters
4. Click "Run workflow"

---

## Alert Configuration

### Environment Variables

Configure alert channels via environment variables (in GitHub Secrets):

```bash
# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR/WEBHOOK/URL

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
ALERT_EMAIL_TO=alerts@yourdomain.com

# SMS (Twilio)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=+15551234567
TWILIO_TO_NUMBER=+15559876543
```

### Alert Priority Levels

| Status | Priority | Channels | Description |
|--------|----------|----------|-------------|
| CRITICAL | P0 | All | Heartbeat missing or >2 hours stale |
| ERROR | P1 | Email, Slack, Discord | Parse error or read failure |
| HEALTHY | - | None | Heartbeat current (<2 hours) |
| SKIPPED | - | None | Outside market hours |

---

## Cron Job Setup

To run as a cron job on a server:

```bash
# Edit crontab
crontab -e

# Add hourly check during market hours (9 AM - 5 PM ET)
# Adjust for your timezone
0 9-17 * * 1-5 cd /home/user/trading && python3 scripts/heartbeat_alert.py >> logs/heartbeat_cron.log 2>&1
```

---

## Troubleshooting

### Heartbeat File Not Found

**Symptoms**: Script reports "Heartbeat file not found"

**Causes**:
1. Scheduler workflow has never run
2. Workflow is disabled
3. File was deleted

**Solutions**:
```bash
# Check if workflow is enabled
gh workflow list | grep scheduler-heartbeat

# Enable workflow if needed
gh workflow enable scheduler-heartbeat.yml

# Manually trigger to create file
gh workflow run scheduler-heartbeat.yml

# Verify file was created
cat data/scheduler_heartbeat.json
```

### Stale Heartbeat

**Symptoms**: Script reports "Heartbeat is STALE"

**Causes**:
1. Scheduler workflow is stuck or failing
2. GitHub Actions outage
3. Workflow disabled or rate limited

**Solutions**:
```bash
# Check recent workflow runs
gh run list --workflow=scheduler-heartbeat.yml --limit 10

# Check for failures
gh run list --workflow=scheduler-heartbeat.yml --status=failure

# View latest run logs
gh run view --log

# Check GitHub Actions status
curl https://www.githubstatus.com/api/v2/status.json

# Manually trigger to recover
gh workflow run scheduler-heartbeat.yml
```

### False Positives

**Symptoms**: Alerts during weekends or market closures

**Causes**:
1. Script run with `--force` flag
2. Cron job not configured for market hours only

**Solutions**:
```bash
# Remove --force flag unless intentional
# The script automatically skips checks outside market hours

# For cron jobs, use market hours only:
0 9-17 * * 1-5  # Weekdays 9 AM - 5 PM only
```

### No Alerts Being Sent

**Symptoms**: Script detects failure but no alerts received

**Causes**:
1. Alert channels not configured
2. Invalid credentials
3. Dry run mode enabled

**Solutions**:
```bash
# Check environment variables
env | grep -E 'SLACK|DISCORD|SMTP|TWILIO'

# Test alert system manually
python3 -c "
from src.safety.emergency_alerts import get_alerts
get_alerts().send_alert('Test', 'Testing alerts', 'high')
"

# Ensure not in dry-run mode
python3 scripts/heartbeat_alert.py  # No --dry-run flag
```

---

## Integration with Other Systems

### Pre-commit Hook

Add to `.pre-commit-config.yaml` to check heartbeat before commits:

```yaml
- repo: local
  hooks:
    - id: check-heartbeat
      name: Check scheduler heartbeat
      entry: python3 scripts/heartbeat_alert.py --dry-run
      language: system
      pass_filenames: false
```

### Dashboard Integration

Display heartbeat status in your dashboard:

```python
import json
from datetime import datetime
from pathlib import Path

def get_heartbeat_status():
    heartbeat_file = Path("data/scheduler_heartbeat.json")

    if not heartbeat_file.exists():
        return {"status": "CRITICAL", "message": "Heartbeat file missing"}

    with open(heartbeat_file) as f:
        data = json.load(f)

    last_run = datetime.fromisoformat(data["last_run"].replace("Z", "+00:00"))
    age_minutes = (datetime.utcnow() - last_run.replace(tzinfo=None)).total_seconds() / 60

    if age_minutes > 120:
        return {"status": "CRITICAL", "age_minutes": age_minutes}
    elif age_minutes > 60:
        return {"status": "WARNING", "age_minutes": age_minutes}
    else:
        return {"status": "HEALTHY", "age_minutes": age_minutes}
```

### Monitoring Integration

For external monitoring (Datadog, New Relic, etc.):

```bash
# Export metrics
python3 scripts/heartbeat_alert.py --dry-run > /tmp/heartbeat_status.txt

# Parse and send to monitoring system
# (implement based on your monitoring platform)
```

---

## Best Practices

1. **Regular Testing**
   - Run dry-run checks periodically to ensure system works
   - Test alert channels monthly to verify delivery

2. **Threshold Tuning**
   - Default 120 minutes is conservative
   - Consider 90 minutes for more aggressive monitoring
   - Don't go below 60 minutes to avoid false positives

3. **Alert Fatigue Prevention**
   - Script only alerts during market hours by default
   - GitHub issue auto-closes when resolved
   - Alerts consolidate to existing issues (no spam)

4. **Backup Monitoring**
   - Set up cron job as backup to GitHub Actions
   - Use multiple alert channels for redundancy
   - Monitor the monitor (check alert log file growth)

5. **Documentation**
   - Keep runbooks updated with recovery procedures
   - Document all alert channel configurations
   - Track false positive incidents for tuning

---

## Maintenance

### Regular Checks

```bash
# Weekly: Review alert log
cat data/heartbeat_alerts.json | jq '.[-10:]'

# Monthly: Test alert channels
python3 -c "
from src.safety.emergency_alerts import EmergencyAlerts
alerts = EmergencyAlerts()
alerts.send_alert('Monthly Test', 'Testing heartbeat alerts', 'medium')
"

# Quarterly: Review and tune threshold
python3 scripts/heartbeat_alert.py --threshold 90 --dry-run
```

### Log Rotation

Alert logs are automatically limited to last 500 entries in `data/heartbeat_alerts.json`.

For external log archival:

```bash
# Archive old alerts (run monthly)
cp data/heartbeat_alerts.json \
   archive/heartbeat_alerts_$(date +%Y-%m).json
```

---

## Metrics and SLOs

### Service Level Objectives

| Metric | Target | Current |
|--------|--------|---------|
| Heartbeat uptime during market hours | >99.5% | TBD |
| Alert delivery time | <5 minutes | TBD |
| False positive rate | <5% | TBD |
| Mean time to detect (MTTD) | <1 hour | TBD |
| Mean time to recover (MTTR) | <30 minutes | TBD |

### Monitoring

Track these metrics over time:
- Number of heartbeat failures per month
- Average age of heartbeat when detected
- Alert delivery success rate per channel
- Time to resolution for heartbeat issues

---

## Related Documentation

- **Scheduler Heartbeat Workflow**: `.github/workflows/scheduler-heartbeat.yml`
- **Emergency Alerts**: `src/safety/emergency_alerts.py`
- **Market Hours Utility**: `src/utils/market_hours.py`
- **Health Monitoring**: `scripts/health_monitor.py`
- **Mandatory Rules**: `.claude/rules/MANDATORY_RULES.md`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-18 | Initial release |

---

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review alert logs: `data/heartbeat_alerts.json`
3. Check GitHub issues with label `heartbeat-alert`
4. Review recent workflow runs in GitHub Actions

**Emergency Contact**: If scheduler is down and impacting trading, manually halt trading via kill switch and investigate immediately.
