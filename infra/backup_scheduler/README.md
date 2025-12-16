# Backup Scheduler Configuration

**Purpose**: Provide scheduler redundancy when GitHub Actions is unavailable.

GitHub Actions is a single point of failure. This backup scheduler ensures trading
continues even if GitHub Actions:
- Has an outage
- Rate limits your repository
- Fails due to runner issues
- Gets disabled by mistake

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│   GitHub Actions    │     │   Cloud Scheduler   │
│   (Primary)         │     │   (Backup)          │
└─────────┬───────────┘     └─────────┬───────────┘
          │                           │
          │ writes heartbeat          │ checks heartbeat
          ▼                           ▼
     ┌────────────────────────────────────────┐
     │        data/scheduler_heartbeat.json   │
     └────────────────────────────────────────┘
          │
          │ if stale (>45 mins)
          ▼
     ┌────────────────────────────────────────┐
     │        Run Trading Script              │
     └────────────────────────────────────────┘
```

## Options

### Option 1: Local Cron (Free, Simplest)

Add to your crontab:

```bash
# Edit crontab
crontab -e

# Add these lines:
# Weekday trading backup (every 30 mins, 9:30 AM - 4 PM ET)
*/30 9-16 * * 1-5 cd /path/to/trading && /path/to/venv/bin/python infra/backup_scheduler/backup_scheduler.py >> logs/backup_scheduler.log 2>&1
```

**Cost**: Free
**Reliability**: Depends on your machine being online

### Option 2: systemd Timer (Linux servers)

Create `/etc/systemd/system/trading-backup.timer`:

```ini
[Unit]
Description=Trading Backup Scheduler

[Timer]
OnCalendar=*:0/30
Persistent=true

[Install]
WantedBy=timers.target
```

Create `/etc/systemd/system/trading-backup.service`:

```ini
[Unit]
Description=Trading Backup Run

[Service]
Type=oneshot
User=trading
WorkingDirectory=/path/to/trading
ExecStart=/path/to/venv/bin/python infra/backup_scheduler/backup_scheduler.py
```

Enable:
```bash
sudo systemctl enable trading-backup.timer
sudo systemctl start trading-backup.timer
```

**Cost**: Free
**Reliability**: High (if server is managed)

### Option 3: Google Cloud Scheduler (Recommended for Production)

1. **Prerequisites**:
   - GCP project with billing enabled
   - `gcloud` CLI installed
   - Cloud Run service deployed

2. **Deploy**:
   ```bash
   cd infra/backup_scheduler

   # Initialize Terraform
   terraform init

   # Preview changes
   terraform plan -var="project_id=YOUR_PROJECT_ID"

   # Apply
   terraform apply -var="project_id=YOUR_PROJECT_ID"
   ```

3. **Cost**: ~$0.10/month (well within $100 budget)
   - Cloud Scheduler: $0.10/job/month (3 jobs = $0.30)
   - Cloud Run: Free tier covers light usage

**Cost**: ~$0.10-1.00/month
**Reliability**: Very high (GCP SLA)

## Heartbeat Protocol

GitHub Actions workflows should write heartbeats:

```yaml
# In your trading workflow
- name: Write heartbeat
  run: |
    mkdir -p data
    echo '{"last_run": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'", "source": "github_actions"}' > data/scheduler_heartbeat.json
    git add data/scheduler_heartbeat.json
    git commit -m "chore: Update scheduler heartbeat" || true
    git push || true
```

The backup scheduler checks this heartbeat and only runs if it's stale (>45 mins).

## Testing

```bash
# Check GitHub Actions status
python backup_scheduler.py --check-only

# Dry run (no actual trades)
python backup_scheduler.py --dry-run

# Force run (ignore heartbeat)
python backup_scheduler.py --force

# Force dry run
python backup_scheduler.py --force --dry-run
```

## Monitoring

The backup scheduler logs to telemetry:
- `scheduler_heartbeat.json` - Last run timestamp and source
- Telemetry events for backup runs

Alert if backup scheduler runs more than 3x in a day (indicates GitHub Actions issues).

## Cost Summary

| Option | Monthly Cost | Reliability |
|--------|--------------|-------------|
| Local Cron | $0 | Medium |
| systemd Timer | $0 | High |
| GCP Cloud Scheduler | ~$0.10-1.00 | Very High |

All options fit within the $100/month R&D budget.
