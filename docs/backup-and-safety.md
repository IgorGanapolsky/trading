# Backup & Safety Systems

This document describes the backup plans and safety mechanisms protecting the trading system.

## 🛡️ Safety Mechanisms Overview

| System | Trigger | Action |
|--------|---------|--------|
| **Circuit Breaker Tier 1** | 1% daily loss | Reduce position sizes 50% |
| **Circuit Breaker Tier 2** | 2% daily loss | Soft pause (no new trades) |
| **Circuit Breaker Tier 3** | 3% daily loss | Hard stop + liquidation review |
| **Circuit Breaker Tier 4** | 5% daily loss | Full halt, auto-liquidate |
| **VIX Spike Detector** | VIX > 30 or +20% intraday | Aggressive de-risking |
| **Emergency Liquidator** | 3% daily loss | Auto-close risky positions |
| **Kill Switch** | Manual activation | Block ALL trading immediately |

---

## 🚨 Emergency Alert System

**File**: `src/safety/emergency_alerts.py`

### Supported Channels

| Channel | Priority Levels | Setup Required |
|---------|-----------------|----------------|
| SMS (Twilio) | CRITICAL only | Twilio account |
| Email (SMTP) | CRITICAL, HIGH | SMTP credentials |
| Slack | CRITICAL, HIGH, MEDIUM | Webhook URL |
| Discord | CRITICAL, HIGH, MEDIUM | Webhook URL |

### Environment Variables

```bash
# Twilio SMS
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_FROM_NUMBER=+1234567890
TWILIO_TO_NUMBER=+1234567890

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASS=your_app_password
ALERT_EMAIL_TO=ceo@company.com

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx
```

### Usage

```python
from src.safety.emergency_alerts import send_critical_alert, send_high_alert

# Critical alert (SMS + Email + Slack + Discord)
send_critical_alert("System Down", "Trading system unresponsive")

# High priority alert (Email + Slack + Discord)
send_high_alert("Large Loss", "Portfolio down 2.5% today")
```

---

## 🛑 Kill Switch

**File**: `src/safety/kill_switch.py`

The kill switch provides multiple ways to immediately halt ALL trading.

### Activation Methods

1. **File-based**: Create `data/KILL_SWITCH` file
2. **Environment variable**: Set `TRADING_KILL_SWITCH=1`
3. **Programmatic**: Call `activate_kill_switch()`
4. **CLI**: `python src/safety/kill_switch.py activate "reason"`

### CLI Commands

```bash
# Check status
python src/safety/kill_switch.py status

# Activate
python src/safety/kill_switch.py activate "Emergency stop"

# Deactivate
python src/safety/kill_switch.py deactivate "Resume trading"
```

### Integration with Trading Code

```python
from src.safety.kill_switch import is_trading_blocked

# Check before any trade
blocked, reason = is_trading_blocked()
if blocked:
    raise TradingBlockedError(f"Trading blocked: {reason}")
```

---

## 💾 Data Backup System

**File**: `src/safety/data_backup.py`

### Backup Strategy

| Type | Frequency | Retention | Storage |
|------|-----------|-----------|---------|
| Daily | 11:30 PM ET | 30 days | Local + Git + Artifacts |
| Manual | On-demand | 30 backups | Local |
| Git | Daily | Unlimited | `data-backup` branch |

### What Gets Backed Up

- `data/system_state.json` - Complete system state
- `data/trades_*.json` - All trade logs
- `data/kill_switch_state.json` - Kill switch history
- `data/emergency_alerts.json` - Alert history
- `data/circuit_breaker_state.json` - Circuit breaker state

### CLI Commands

```bash
# Create manual backup
python src/safety/data_backup.py create manual

# List all backups
python src/safety/data_backup.py list

# Restore from latest backup
python src/safety/data_backup.py restore latest

# Restore from specific backup
python src/safety/data_backup.py restore backup_daily_20251208_233000.tar.gz

# Git backup (commits to data-backup branch)
python src/safety/data_backup.py git
```

### Automated Backup Workflow

The GitHub Actions workflow runs daily at 11:30 PM ET:
- Creates compressed backup archive
- Commits to `data-backup` branch
- Uploads as GitHub artifact (30-day retention)

---

## 🔄 Disaster Recovery

### Scenario: Complete Data Loss

1. **Restore from Git**:
   ```bash
   git checkout data-backup -- data/
   ```

2. **Restore from Backup Archive**:
   ```bash
   python src/safety/data_backup.py restore latest
   cp data/restored/* data/
   ```

3. **Restore from GitHub Artifacts**:
   - Go to Actions → Automated Data Backup → Download artifact

### Scenario: Broker (Alpaca) Down

1. Kill switch activates automatically if API errors persist
2. System logs all attempted trades
3. Manual intervention required to resume

### Scenario: Runaway Losses

1. Circuit breakers trigger at 1%, 2%, 3%, 5% thresholds
2. Emergency liquidator closes risky positions at 3%
3. Full liquidation at 5%
4. CEO notified via all alert channels

---

## 📋 Safety Checklist

Before deploying or resuming trading:

- [ ] Check kill switch status: `python src/safety/kill_switch.py status`
- [ ] Verify circuit breaker state
- [ ] Confirm alert channels are configured
- [ ] Test backup system: `python src/safety/data_backup.py create test`
- [ ] Review recent alerts in `data/emergency_alerts.json`

---

## 🔗 Related Files

- `src/safety/emergency_liquidator.py` - Auto-liquidation logic
- `src/safety/multi_tier_circuit_breaker.py` - Circuit breaker system
- `src/risk/vix_circuit_breaker.py` - VIX-based risk management
- `src/agents/fallback_strategy.py` - LLM fallback to pure technical analysis
- `.github/workflows/automated-backup.yml` - Daily backup workflow

---

*Last Updated: 2025-12-08*
