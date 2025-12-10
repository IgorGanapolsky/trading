# Trading System Operations Runbook

> **Purpose**: This runbook defines operational procedures for the trading system across research, paper-trading, and live modes.

## Table of Contents

1. [Environment Modes](#environment-modes)
2. [Startup Procedures](#startup-procedures)
3. [Monitoring & Alerts](#monitoring--alerts)
4. [Risk Controls & Kill Switch](#risk-controls--kill-switch)
5. [Incident Response](#incident-response)
6. [Scheduled Operations](#scheduled-operations)
7. [Rollback Procedures](#rollback-procedures)

---

## Environment Modes

### Research Mode 🔬
**Purpose**: Exploration, backtesting, and idea testing.

| Aspect | Setting |
|--------|---------|
| Trading Enabled | ❌ No |
| Database | SQLite (local) |
| API Calls | Cached/Mocked |
| Risk Limits | None enforced |
| Deployable | No |

**Use for**:
- Notebooks and exploratory analysis
- Backtesting new strategies
- Parameter optimization
- Breaking things without consequences

**How to activate**:
```bash
export TRADING_MODE=research
python -m src.research.notebook_runner
```

### Paper Trading Mode 📝
**Purpose**: Always-deployable validation with simulated trades.

| Aspect | Setting |
|--------|---------|
| Trading Enabled | ✅ Yes (paper) |
| Database | PostgreSQL/SQLite |
| API Calls | Real market data, simulated orders |
| Risk Limits | Enforced |
| Deployable | Yes |

**Requirements**:
- All CI checks must pass
- Alpaca paper trading credentials configured
- Risk limits properly set

**How to activate**:
```bash
export TRADING_MODE=paper
export ALPACA_PAPER=true
python -m src.main --mode paper
```

### Live Mode 🔴
**Purpose**: Real money trading with maximum safeguards.

| Aspect | Setting |
|--------|---------|
| Trading Enabled | ✅ Yes (real) |
| Database | PostgreSQL |
| API Calls | Real market data, real orders |
| Risk Limits | Strictly enforced |
| Deployable | Manual approval required |

**Prerequisites**:
1. ✅ 30+ days of successful paper trading
2. ✅ Win rate > 50%
3. ✅ No critical bugs in last 7 days
4. ✅ Manual approval from CEO (Igor)
5. ✅ All environment variables validated
6. ✅ Kill switch tested

**How to activate**:
```bash
export TRADING_MODE=live
export ALPACA_PAPER=false
# Requires additional confirmation
python -m src.main --mode live --confirm-live
```

---

## Startup Procedures

### Daily Startup Checklist

```bash
# 1. Verify environment
./scripts/verify_environment.sh

# 2. Check broker connectivity
python -c "from src.core.broker_health import check_broker; check_broker()"

# 3. Verify risk limits are set
python -c "from src.risk.risk_manager import RiskManager; RiskManager().validate_limits()"

# 4. Check market status
python -c "from src.utils.market_data import is_market_open; print(is_market_open())"

# 5. Start trading system
./start-trading-system.sh
```

### Pre-Market Validation (9:00 AM ET)

1. **Check account balance**
   ```bash
   python scripts/check_account.py
   ```

2. **Review overnight news**
   ```bash
   python scripts/news_scan.py
   ```

3. **Validate no pending orders from previous day**
   ```bash
   python scripts/order_cleanup.py
   ```

---

## Monitoring & Alerts

### Key Metrics to Monitor

| Metric | Warning Threshold | Critical Threshold |
|--------|-------------------|-------------------|
| Daily P&L | -$50 | -$100 |
| Drawdown | -3% | -5% |
| Win Rate (rolling 5 days) | < 45% | < 35% |
| API Error Rate | > 1% | > 5% |
| Order Fill Rate | < 95% | < 90% |

### Alert Channels

1. **GitHub Actions** - Workflow failures
2. **Email** - Daily summary reports
3. **Log Files** - `/workspace/logs/trading.log`
4. **Dashboard** - Streamlit at `http://localhost:8501`

### When Workflows Get Disabled

If a GitHub Actions workflow is disabled:

1. **Check** why it was disabled (errors, manual action)
2. **Fix** the underlying issue
3. **Re-enable** via GitHub UI or CLI:
   ```bash
   gh workflow enable <workflow-name>
   ```
4. **Verify** by triggering a test run

---

## Risk Controls & Kill Switch

### Automated Circuit Breakers

The system has automatic circuit breakers that halt trading:

| Trigger | Action | Recovery |
|---------|--------|----------|
| Daily loss > 3% | Halt all new orders | Next trading day |
| 3 consecutive losses | 30-minute cooldown | Automatic |
| API errors > 10/hour | Switch to read-only | Manual review |
| Position limit exceeded | Reject new orders | Close positions |

### Manual Kill Switch

**EMERGENCY STOP ALL TRADING**:

```bash
# Option 1: Script
./stop-trading-system.sh

# Option 2: Direct
python scripts/kill_switch.py --confirm

# Option 3: Alpaca API direct
curl -X DELETE \
  -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
  -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" \
  https://paper-api.alpaca.markets/v2/orders
```

### Position Limits

| Asset Class | Max Position % | Max Positions |
|-------------|----------------|---------------|
| Equity/ETF | 20% | 10 |
| Options | 5% | 5 |
| Crypto | 10% | 3 |

---

## Incident Response

### Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| P1 | Trading halted / Money loss | Immediate |
| P2 | Degraded performance | < 1 hour |
| P3 | Non-critical bug | < 24 hours |
| P4 | Enhancement | Next sprint |

### P1 Response Procedure

1. **Stop** - Activate kill switch
2. **Assess** - Check positions, P&L, errors
3. **Communicate** - Log incident
4. **Fix** - Deploy hotfix
5. **Recover** - Restart in paper mode first
6. **Review** - Post-mortem within 24 hours

### Common Issues

#### "Orders not executing"
```bash
# Check order status
python scripts/check_orders.py

# Common causes:
# - Market closed
# - Insufficient buying power
# - Symbol not tradeable
# - API rate limit
```

#### "Wrong positions held"
```bash
# List all positions
python scripts/list_positions.py

# Close specific position
python scripts/close_position.py --symbol SPY

# Close all positions (DANGER)
python scripts/close_all_positions.py --confirm
```

---

## Scheduled Operations

### Daily Schedule (ET)

| Time | Operation | Mode |
|------|-----------|------|
| 9:00 AM | Pre-market validation | All |
| 9:35 AM | Execute equity trades | Paper/Live |
| 10:00 AM | Generate daily report | All |
| 4:00 PM | End-of-day reconciliation | All |
| 5:00 PM | Run backtests | Research |

### Weekly Schedule

| Day | Operation |
|-----|-----------|
| Monday | Strategy performance review |
| Wednesday | Risk parameter check |
| Friday | Weekly P&L report |
| Saturday | Crypto trades, RL model update |
| Sunday | System maintenance window |

### Monthly Schedule

| Task | Timing |
|------|--------|
| Full backtest of core strategy | 1st of month |
| Cost analysis | 5th of month |
| Strategy registry review | 15th of month |
| Roadmap update | Last day of month |

---

## Rollback Procedures

### Rolling Back Code Changes

```bash
# 1. Identify the bad commit
git log --oneline -10

# 2. Revert to previous version
git revert <commit-hash>

# 3. Deploy fix
git push origin main
```

### Rolling Back Strategy Changes

```bash
# 1. Check strategy registry
python -c "from src.strategies.registry import get_registry; print(get_registry().generate_report())"

# 2. Set strategy to deprecated
python -c "from src.strategies.registry import get_registry, StrategyStatus; get_registry().set_status('bad_strategy', StrategyStatus.DEPRECATED)"

# 3. Revert to core strategy
export ACTIVE_STRATEGY=core_momentum
```

### Database Rollback

```bash
# 1. List available backups
ls -la data/backups/

# 2. Restore from backup
cp data/backups/system_state_YYYYMMDD.json data/system_state.json

# 3. Verify integrity
python scripts/validate_state.py
```

---

## Appendix: Environment Variables

### Required Variables

```bash
# Alpaca Trading
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=true  # Set to false for live trading

# Trading Configuration
TRADING_MODE=paper  # research, paper, live
DAILY_INVESTMENT=10.0
MAX_DAILY_LOSS=50.0

# Risk Limits
MAX_POSITION_PCT=0.10
MAX_DAILY_DRAWDOWN_PCT=3.0

# Optional
OPENROUTER_API_KEY=your_key  # For LLM analysis
REDDIT_CLIENT_ID=your_id  # For sentiment
```

### Validation

```bash
python scripts/validate_env.py
```

---

**Last Updated**: 2025-12-03
**Maintainer**: Trading System (CTO: Claude)
