# Trading System Deployment Guide

This guide covers multiple deployment options for running the trading system 24/7.

## Quick Start (Any Environment)

### 1. Configure Environment Variables

```bash
# Copy example and edit with your API keys
cp .env.example .env
chmod 600 .env

# Edit .env with your actual API keys
nano .env
```

**Required Variables:**
- `ALPACA_API_KEY` - Your Alpaca API key
- `ALPACA_SECRET_KEY` - Your Alpaca secret key
- `PAPER_TRADING=true` - Start with paper trading

### 2. Start the System

```bash
# Start in paper trading mode (default)
./start-trading-system.sh

# Start in live trading mode (use with caution!)
./start-trading-system.sh live

# Start with debug logging
./start-trading-system.sh paper DEBUG
```

### 3. Monitor the System

```bash
# Check status
./status-trading-system.sh

# View live logs
tail -f logs/trading_system.log

# View error logs only
tail -f logs/trading_errors.log
```

### 4. Stop the System

```bash
./stop-trading-system.sh
```

---

## Deployment Option 1: Systemd Service (Recommended for Production)

**Best for:** Ubuntu/Debian servers, VPS, cloud instances

### Installation

```bash
# 1. Copy service file
sudo cp trading-system.service /etc/systemd/system/

# 2. Reload systemd
sudo systemctl daemon-reload

# 3. Enable auto-start on boot
sudo systemctl enable trading-system

# 4. Start the service
sudo systemctl start trading-system
```

### Management Commands

```bash
# Start service
sudo systemctl start trading-system

# Stop service
sudo systemctl stop trading-system

# Restart service
sudo systemctl restart trading-system

# Check status
sudo systemctl status trading-system

# View logs (live)
sudo journalctl -u trading-system -f

# View logs (last 100 lines)
sudo journalctl -u trading-system -n 100

# View logs since boot
sudo journalctl -u trading-system -b
```

### Service Features

- ✅ Auto-starts on system boot
- ✅ Auto-restarts on crashes (max 5 retries in 5 minutes)
- ✅ Graceful shutdown with SIGTERM (30 second timeout)
- ✅ Logs to systemd journal + file logs
- ✅ Security hardening (read-only system, private tmp)
- ✅ Resource limits configured

### Troubleshooting

```bash
# Check service logs
sudo journalctl -u trading-system -n 50

# Check if service is enabled
sudo systemctl is-enabled trading-system

# Check if service is active
sudo systemctl is-active trading-system

# View service configuration
sudo systemctl cat trading-system

# Test configuration without starting
sudo systemd-analyze verify /etc/systemd/system/trading-system.service
```

---

## Deployment Option 2: Supervisor (Alternative to Systemd)

**Best for:** Systems without systemd, shared hosting, containers

### Installation

```bash
# Install supervisor
sudo apt-get update
sudo apt-get install -y supervisor

# Copy configuration
sudo cp supervisor-trading-system.conf /etc/supervisor/conf.d/

# Update supervisor
sudo supervisorctl reread
sudo supervisorctl update
```

### Management Commands

```bash
# Start
sudo supervisorctl start trading-system

# Stop
sudo supervisorctl stop trading-system

# Restart
sudo supervisorctl restart trading-system

# Status
sudo supervisorctl status trading-system

# View logs
sudo supervisorctl tail -f trading-system
```

---

## Deployment Option 3: Docker (Portable)

**Best for:** Cloud deployments, Kubernetes, multi-environment

### Dockerfile Example

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 trader && \
    chown -R trader:trader /app
USER trader

# Expose health check port (future)
EXPOSE 8080

# Start trading system
CMD ["python3", "src/main.py", "--mode", "paper", "--log-level", "INFO"]
```

### Docker Compose Example

```yaml
version: '3.8'

services:
  trading-system:
    build: .
    container_name: trading-system
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
      - ./reports:/app/reports
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Docker Commands

```bash
# Build image
docker build -t trading-system:latest .

# Run container
docker run -d \
  --name trading-system \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  trading-system:latest

# View logs
docker logs -f trading-system

# Stop container
docker stop trading-system

# Restart container
docker restart trading-system
```

---

## Deployment Option 4: Cron (Simple Scheduled Execution)

**Best for:** Running at specific times only (not 24/7)

### Crontab Configuration

```bash
# Edit crontab
crontab -e

# Add daily execution at 9:30 AM ET
30 9 * * 1-5 cd /home/user/trading && ./start-trading-system.sh paper INFO >> logs/cron.log 2>&1
```

---

## Production Deployment Checklist

### Security

- [ ] `.env` file has 600 permissions (read/write owner only)
- [ ] API keys are NOT in git history
- [ ] Service runs as non-root user
- [ ] Firewall configured (if needed)
- [ ] SSH key-based authentication enabled
- [ ] System updates applied

### Monitoring

- [ ] Log rotation configured
- [ ] Disk space monitoring set up
- [ ] Alerting configured (email/webhook)
- [ ] Health check endpoint working
- [ ] Backup strategy for trade data

### Testing

- [ ] Paper trading validated for 30+ days
- [ ] Win rate >55%, Sharpe ratio >1.0
- [ ] Max drawdown <10%
- [ ] Circuit breakers tested
- [ ] Graceful shutdown tested
- [ ] Auto-restart tested

### Configuration

- [ ] `PAPER_TRADING=true` for initial deployment
- [ ] `DAILY_INVESTMENT` set appropriately
- [ ] Risk limits configured
- [ ] Stop-loss percentages validated
- [ ] Tier allocations sum to ≤100%

---

## Monitoring & Logs

### Log Files

```
logs/
├── trading_system.log      # Main application logs (INFO+)
├── trading_errors.log      # Error logs only (ERROR+)
├── supervisor_stdout.log   # Supervisor stdout (if using)
└── supervisor_stderr.log   # Supervisor stderr (if using)
```

### Log Rotation

The application uses `RotatingFileHandler`:
- Max file size: 10MB
- Backup files: 5
- Total max storage: 50MB per log type

### Systemd Journal

```bash
# Real-time logs
journalctl -u trading-system -f

# Logs since boot
journalctl -u trading-system -b

# Logs from last hour
journalctl -u trading-system --since "1 hour ago"

# Logs with priority ERROR or higher
journalctl -u trading-system -p err

# Export logs to file
journalctl -u trading-system > trading-system-logs.txt
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status trading-system

# Check recent logs
sudo journalctl -u trading-system -n 50

# Test manual start
cd /home/user/trading
python3 src/main.py --mode paper --log-level DEBUG
```

### Common Issues

**Issue:** `EnvironmentFile not found`
```bash
# Solution: Create .env file
cp .env.example .env
chmod 600 .env
# Edit with your API keys
nano .env
```

**Issue:** `Permission denied`
```bash
# Solution: Fix permissions
sudo chown -R user:user /home/user/trading
chmod +x start-trading-system.sh
```

**Issue:** `API authentication failed`
```bash
# Solution: Verify API keys
cat .env | grep API_KEY
# Test keys manually with Alpaca
```

**Issue:** `Process already running`
```bash
# Solution: Stop existing process
./stop-trading-system.sh
# Or manually
kill $(cat trading-system.pid)
```

---

## Upgrade Process

### Rolling Update (Zero Downtime)

```bash
# 1. Pull latest code
git pull origin main

# 2. Install dependencies
pip install -r requirements.txt

# 3. Test in separate terminal
python3 src/main.py --mode paper --run-once --strategy core

# 4. Restart service
sudo systemctl restart trading-system

# 5. Verify
sudo systemctl status trading-system
```

### Emergency Rollback

```bash
# 1. Stop service
sudo systemctl stop trading-system

# 2. Rollback code
git checkout <previous-commit>

# 3. Restart service
sudo systemctl start trading-system
```

---

## Performance Tuning

### Resource Monitoring

```bash
# CPU and memory usage
ps aux | grep python3

# Detailed process info
top -p $(cat trading-system.pid)

# Disk usage
du -sh logs/ data/ reports/
```

### Optimization Tips

1. **Log Level**: Use INFO in production (DEBUG only for troubleshooting)
2. **Log Rotation**: Adjust max file size if disk space is limited
3. **API Rate Limits**: Monitor Alpaca API usage
4. **Memory**: System typically uses 50-100MB RAM
5. **CPU**: Very low usage (<5%) except during trade execution

---

## Contact & Support

- **GitHub Issues**: [Report bugs/issues]
- **Documentation**: `/home/user/trading/docs/`
- **Logs**: `/home/user/trading/logs/`
- **Configuration**: `/home/user/trading/.env`

---

## Next Steps

1. **Day 1-30**: Paper trading with monitoring
2. **Day 30**: Review performance metrics
3. **Day 60**: Validate win rate and Sharpe ratio
4. **Day 90**: Consider going live if criteria met
5. **Month 4+**: Scale with Fibonacci strategy
