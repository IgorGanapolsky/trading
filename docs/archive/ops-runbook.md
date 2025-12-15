# Operations Runbook

This document describes how to operate the trading system across different environments.

## Environment Split

### Research Mode
- **Purpose**: Free experimentation, notebook testing, idea validation
- **Location**: `notebooks/`, `research_templates/`
- **Data**: Can break things, no production impact
- **Access**: Developers, researchers
- **State**: Ephemeral, no persistence required

### Paper Trading Mode
- **Purpose**: Always deployable, runs on schedule, logs all trades
- **Location**: `src/orchestrator/`, `scripts/autonomous_trader.py`
- **Data**: Durable storage in `data/`, `reports/`
- **Access**: Automated via GitHub Actions
- **State**: Persistent, tracks performance
- **Schedule**: Weekdays 9:35 AM ET (equity), Weekends 10:00 AM ET (crypto)

### Live Trading Mode
- **Purpose**: Real money execution, gated by manual approval
- **Location**: Same as paper, but with `PAPER_TRADING=false`
- **Data**: Same durable storage, clearly marked as LIVE
- **Access**: Manual approval required, strict risk checks
- **State**: Persistent, critical monitoring
- **Risk Limits**: Enforced via `src/risk/risk_manager.py`

## Environment Configuration

### Research Mode
```bash
# No special config needed
# Use notebooks freely
jupyter notebook notebooks/
```

### Paper Trading Mode
```bash
# Set environment variables
export PAPER_TRADING=true
export ALPACA_API_KEY=<paper_key>
export ALPACA_SECRET_KEY=<paper_secret>
export DAILY_INVESTMENT=10.0

# Run orchestrator
PYTHONPATH=src python -m orchestrator.main --mode paper
```

### Live Trading Mode
```bash
# Set environment variables (REQUIRES MANUAL APPROVAL)
export PAPER_TRADING=false  # CRITICAL: Must be false
export ALPACA_API_KEY=<live_key>
export ALPACA_SECRET_KEY=<live_secret>
export DAILY_INVESTMENT=10.0

# Run with explicit confirmation
PYTHONPATH=src python -m orchestrator.main --mode live --confirm
```

## Operational Procedures

### Starting the System

1. **Check Environment**:
   ```bash
   python scripts/check_environment.py
   ```

2. **Verify Risk Limits**:
   ```bash
   python scripts/check_risk_limits.py
   ```

3. **Start Paper Trading**:
   ```bash
   # Automated via GitHub Actions (recommended)
   # Or manually:
   PYTHONPATH=src python -m orchestrator.main --mode paper
   ```

### Stopping the System

1. **Graceful Shutdown**:
   ```bash
   # Send SIGTERM to process
   pkill -TERM -f "orchestrator.main"
   ```

2. **Emergency Stop**:
   ```bash
   # Kill switch script
   ./stop-trading-system.sh
   ```

3. **Close All Positions** (if needed):
   ```bash
   python scripts/close_all_positions.py --confirm
   ```

### Monitoring

1. **Check System Status**:
   ```bash
   python scripts/check_system_status.py
   ```

2. **View Recent Trades**:
   ```bash
   python scripts/view_recent_trades.py --days 7
   ```

3. **Check Performance**:
   ```bash
   python scripts/generate_daily_report.py
   ```

### Restarting After Failure

1. **Check Logs**:
   ```bash
   tail -n 100 logs/trading.log
   ```

2. **Verify State**:
   ```bash
   python scripts/verify_system_state.py
   ```

3. **Restart**:
   ```bash
   PYTHONPATH=src python -m orchestrator.main --mode paper
   ```

### Scaling

1. **Increase Daily Investment**:
   ```bash
   export DAILY_INVESTMENT=20.0
   # Restart orchestrator
   ```

2. **Add More Strategies**:
   - Register in `src/strategies/strategy_registry.py`
   - Update orchestrator config
   - Test in paper mode first

## Risk Management

### Daily Loss Limits
- **Paper**: 2% of portfolio value
- **Live**: 1% of portfolio value (stricter)

### Drawdown Limits
- **Max Drawdown**: 10% of portfolio value
- **Worst 5-Day**: $2,000 (paper) / $1,000 (live)
- **Worst 20-Day**: $10,000 (paper) / $5,000 (live)

### Circuit Breakers
- Automatic stop if daily loss exceeds limit
- Automatic stop if drawdown exceeds limit
- Manual kill switch always available

## Alerts and Monitoring

### GitHub Actions Workflow Status
- Monitor `.github/workflows/daily-trading.yml`
- Alerts if workflow fails or is disabled
- Check `workflow-health-check.yml` for status

### Telegram Alerts (if configured)
- Daily P&L summary
- Risk limit breaches
- System failures

### Dashboard
- Streamlit dashboard: `streamlit run dashboard/trading_dashboard.py`
- View at: `http://localhost:8501`

## Troubleshooting

### Workflow Disabled
```bash
# Check workflow status
gh workflow view daily-trading.yml

# Re-enable if needed
gh workflow enable daily-trading.yml
```

### API Connection Issues
```bash
# Test Alpaca connection
python scripts/test_alpaca_connection.py

# Check credentials
python scripts/verify_credentials.py
```

### State File Corruption
```bash
# Backup current state
cp data/system_state.json data/system_state.json.backup

# Reset to last known good state
python scripts/reset_system_state.py --backup data/system_state.json.backup
```

## Emergency Procedures

### Kill Switch
```bash
# Immediate stop
./stop-trading-system.sh

# Close all positions
python scripts/close_all_positions.py --emergency --confirm
```

### Risk Limit Breach
1. System automatically stops trading
2. Alert sent to monitoring channel
3. Review `data/system_state.json` for details
4. Fix issue before restarting

### Data Loss
1. Check backups in `data/backups/`
2. Restore from last known good state
3. Verify integrity before restarting

## Best Practices

1. **Always test in paper mode first**
2. **Monitor daily reports**
3. **Keep risk limits conservative**
4. **Document all manual interventions**
5. **Review performance weekly**
6. **Never disable risk checks in live mode**
