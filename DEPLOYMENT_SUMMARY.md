# Trading System - 24/7 Deployment Summary

## ✅ Deployment Files Created

All files have been created and configured for 24/7 operation:

### 1. Systemd Service (Production Linux Servers)

**Files:**
- `/home/user/trading/trading-system.service` (source)
- `/etc/systemd/system/trading-system.service` (installed)
- Symlink: `/etc/systemd/system/multi-user.target.wants/trading-system.service` (enabled)

**Status:** ✅ Service file installed and enabled for auto-start

**Usage:**
```bash
# Start the service
sudo systemctl start trading-system

# Stop the service
sudo systemctl stop trading-system

# Restart the service
sudo systemctl restart trading-system

# Check status
sudo systemctl status trading-system

# View live logs
sudo journalctl -u trading-system -f

# View last 100 log lines
sudo journalctl -u trading-system -n 100
```

**Features:**
- ✅ Auto-starts on system boot
- ✅ Auto-restarts on crashes (max 5 attempts per 5 minutes)
- ✅ Graceful shutdown with SIGTERM (30 second timeout)
- ✅ Loads environment from `/home/user/trading/.env`
- ✅ Logs to systemd journal + file logs
- ✅ Security hardening (read-only system, private tmp)
- ✅ Runs as non-root user (user:user)

---

### 2. Management Scripts (Universal)

**Files Created:**
- `/home/user/trading/start-trading-system.sh` - Start script
- `/home/user/trading/stop-trading-system.sh` - Stop script
- `/home/user/trading/status-trading-system.sh` - Status check

**Status:** ✅ All scripts executable

**Usage:**
```bash
# Start (paper trading mode - default)
./start-trading-system.sh

# Start in live mode
./start-trading-system.sh live

# Start with debug logging
./start-trading-system.sh paper DEBUG

# Stop
./stop-trading-system.sh

# Check status
./status-trading-system.sh

# View logs
tail -f logs/trading_system.log
```

**Features:**
- ✅ Works in any environment (systemd or not)
- ✅ PID file management
- ✅ Environment validation
- ✅ Graceful shutdown
- ✅ Color-coded output
- ✅ Detailed status reporting

---

### 3. Supervisor Configuration (Alternative to Systemd)

**File:** `/home/user/trading/supervisor-trading-system.conf`

**Usage:**
```bash
# Install
sudo cp supervisor-trading-system.conf /etc/supervisor/conf.d/
sudo supervisorctl reread
sudo supervisorctl update

# Manage
sudo supervisorctl start trading-system
sudo supervisorctl stop trading-system
sudo supervisorctl status trading-system
sudo supervisorctl tail -f trading-system
```

---

### 4. Environment Configuration

**File:** `/home/user/trading/.env`

**Status:** ✅ Created from template with secure permissions (600)

**⚠️ ACTION REQUIRED:** Configure your API keys before starting!

```bash
# Edit .env file
nano .env

# Required variables to configure:
# - ALPACA_API_KEY
# - ALPACA_SECRET_KEY
# - OPENROUTER_API_KEY (if using sentiment analysis)
```

---

### 5. Documentation

**Files:**
- `/home/user/trading/docs/DEPLOYMENT.md` - Comprehensive deployment guide
- `/home/user/trading/DEPLOYMENT_SUMMARY.md` - This file

---

## 🚀 Quick Start Guide

### Option A: Using Systemd (Recommended)

**Requirements:** Linux system with systemd (Ubuntu, Debian, CentOS, etc.)

```bash
# 1. Configure API keys
nano .env

# 2. Start service (will run on boot)
sudo systemctl start trading-system

# 3. Check status
sudo systemctl status trading-system

# 4. View logs
sudo journalctl -u trading-system -f
```

**Note:** In this sandboxed environment, systemd is not running. The service will work when deployed to a real server.

### Option B: Using Management Scripts

**Requirements:** Any Linux system, no systemd required

```bash
# 1. Configure API keys
nano .env

# 2. Start system
./start-trading-system.sh

# 3. Check status
./status-trading-system.sh

# 4. View logs
tail -f logs/trading_system.log
```

---

## 📊 Service Features

### 1. Auto-Start on Boot
- ✅ Systemd service enabled
- ✅ Service starts automatically when system boots
- ✅ No manual intervention required

### 2. Auto-Restart on Crashes
- ✅ Automatically restarts if process crashes
- ✅ Maximum 5 restart attempts per 5 minutes
- ✅ Prevents infinite restart loops

### 3. Graceful Shutdown
- ✅ Sends SIGTERM signal for clean shutdown
- ✅ Allows 30 seconds for cleanup
- ✅ Force kills if process doesn't stop
- ✅ Cancels pending orders on shutdown

### 4. Logging
- ✅ Application logs: `logs/trading_system.log`
- ✅ Error logs: `logs/trading_errors.log`
- ✅ Systemd journal: `journalctl -u trading-system`
- ✅ Log rotation: 10MB max, 5 backups

### 5. Security
- ✅ Runs as non-root user
- ✅ Read-only system directories
- ✅ Private tmp directory
- ✅ Environment file permissions: 600
- ✅ No new privileges

### 6. Monitoring
- ✅ Health checks every hour
- ✅ Status endpoint
- ✅ Performance metrics
- ✅ Circuit breaker monitoring

---

## 🧪 Testing Deployment

### Test 1: Validate Configuration

```bash
# Run deployment test
./test-deployment.sh
```

### Test 2: Manual Test Run

```bash
# Test single execution (won't run scheduled)
python3 src/main.py --mode paper --run-once --strategy core
```

### Test 3: Service Test (Systemd)

```bash
# Start service
sudo systemctl start trading-system

# Wait 30 seconds
sleep 30

# Check status (should be running)
sudo systemctl status trading-system

# Check logs (should see "Trading Orchestrator initialized")
sudo journalctl -u trading-system -n 50

# Stop service
sudo systemctl stop trading-system
```

### Test 4: Management Script Test

```bash
# Start
./start-trading-system.sh

# Wait 30 seconds
sleep 30

# Check status
./status-trading-system.sh

# Stop
./stop-trading-system.sh
```

---

## 📁 File Structure

```
/home/user/trading/
├── .env                              # Environment variables (CONFIGURE THIS!)
├── .env.example                      # Example configuration
├── src/
│   └── main.py                       # Main application entry point
├── logs/                             # Log files (created on first run)
│   ├── trading_system.log           # Main logs
│   └── trading_errors.log           # Error logs
├── data/                             # Trade data and state
├── reports/                          # Daily reports
├── docs/
│   └── DEPLOYMENT.md                # Detailed deployment guide
├── trading-system.service           # Systemd service file
├── supervisor-trading-system.conf   # Supervisor configuration
├── start-trading-system.sh          # Start script
├── stop-trading-system.sh           # Stop script
├── status-trading-system.sh         # Status script
├── test-deployment.sh               # Deployment test
└── DEPLOYMENT_SUMMARY.md            # This file

/etc/systemd/system/
├── trading-system.service           # Installed service
└── multi-user.target.wants/
    └── trading-system.service       # Enabled symlink
```

---

## 🔧 Troubleshooting

### Issue: Service won't start

```bash
# Check logs
sudo journalctl -u trading-system -n 50

# Common causes:
# 1. API keys not configured - Edit .env
# 2. Python dependencies missing - pip install -r requirements.txt
# 3. Permission issues - chown -R user:user /home/user/trading
```

### Issue: Service keeps restarting

```bash
# Check error logs
sudo journalctl -u trading-system -p err

# Check application logs
tail -100 logs/trading_errors.log

# Common causes:
# 1. Invalid API keys
# 2. Network connectivity issues
# 3. Alpaca API rate limiting
```

### Issue: Logs not appearing

```bash
# Check if log directory exists and is writable
ls -la logs/

# Create if missing
mkdir -p logs
chown user:user logs
chmod 755 logs

# Check application is running
./status-trading-system.sh
```

### Issue: PID file exists but process not running

```bash
# Remove stale PID file
rm trading-system.pid

# Restart
./start-trading-system.sh
```

---

## 🎯 Next Steps

### 1. Configure API Keys (Required)

```bash
nano .env
# Update ALPACA_API_KEY, ALPACA_SECRET_KEY
```

### 2. Choose Deployment Method

**For production servers:**
```bash
sudo systemctl start trading-system
```

**For testing/development:**
```bash
./start-trading-system.sh
```

### 3. Monitor System

```bash
# Watch logs
tail -f logs/trading_system.log

# Check status every 30 minutes
watch -n 1800 ./status-trading-system.sh
```

### 4. Validate Operation

- ✅ Day 1-7: Monitor daily for issues
- ✅ Day 7: First weekly review
- ✅ Day 30: Full month review
- ✅ Day 90: Go/no-go decision for live trading

---

## 📞 Support

**Documentation:**
- Comprehensive guide: `docs/DEPLOYMENT.md`
- This summary: `DEPLOYMENT_SUMMARY.md`
- Project docs: `docs/`

**Logs:**
- Application logs: `logs/trading_system.log`
- Error logs: `logs/trading_errors.log`
- System journal: `journalctl -u trading-system`

**Status:**
- Check status: `./status-trading-system.sh`
- Service status: `systemctl status trading-system`

---

## ✅ Deployment Checklist

**Pre-Deployment:**
- [ ] `.env` file configured with real API keys
- [ ] `PAPER_TRADING=true` for initial testing
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] File permissions correct: `chmod 600 .env`

**Deployment:**
- [ ] Service installed: `systemctl enable trading-system`
- [ ] Service started: `systemctl start trading-system`
- [ ] Status verified: `systemctl status trading-system`
- [ ] Logs checked: `journalctl -u trading-system -n 50`

**Post-Deployment:**
- [ ] System running for 24 hours without issues
- [ ] Daily trades executing as scheduled
- [ ] Logs showing no errors
- [ ] Daily reports being generated

**Production (Day 90+):**
- [ ] Paper trading validated (>55% win rate, >1.0 Sharpe)
- [ ] Max drawdown <10%
- [ ] Circuit breakers tested
- [ ] Ready to switch `PAPER_TRADING=false`

---

## 🎉 Summary

**All deployment files created and configured!**

The trading system is ready for 24/7 operation with:
- ✅ Systemd service (auto-start, auto-restart, logging)
- ✅ Management scripts (start, stop, status)
- ✅ Supervisor config (alternative to systemd)
- ✅ Environment configuration (.env)
- ✅ Comprehensive documentation

**Next:** Configure API keys in `.env` and start the system!
