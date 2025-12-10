# P/L Sanity Check System

## Overview

The P/L Sanity Check system detects "zombie mode" - when the trading system appears to run but doesn't actually execute trades or update positions. This would have caught our 30-day silent failure within 3 days.

## Problem Statement

**The 30-Day Silent Failure (Nov 2025)**:
- System appeared operational (no errors in logs)
- GitHub Actions showed green checkmarks
- But NO trades were executing
- Equity remained stuck at $100,000.00 for 30+ days
- CEO assumed system was working, but it was silently failing

**Impact**: 30 days of lost trading opportunities, zero edge development, missed R&D goals.

## Solution

The `scripts/verify_pl_sanity.py` script performs comprehensive health checks:

### Alert Conditions

1. **STUCK_EQUITY (CRITICAL)**
   - Equity unchanged for 3+ trading days (within $0.01)
   - Indicates system is frozen or not executing

2. **NO_TRADES (CRITICAL)**
   - No trade executions in last 3+ days
   - Indicates automation failure

3. **ZERO_PL (WARNING)**
   - P/L exactly $0.00 for 3+ days
   - May indicate stale data or calculation errors

4. **ANOMALOUS_CHANGE (WARNING)**
   - Daily equity change >5%
   - Indicates unusual volatility or potential bug

5. **DRAWDOWN (WARNING)**
   - Equity dropped >10% from peak
   - Risk management alert

## Usage

### Command Line

```bash
# Basic check (uses system_state.json fallback)
python3 scripts/verify_pl_sanity.py

# Verbose mode (shows debug logging)
python3 scripts/verify_pl_sanity.py --verbose

# With Alpaca credentials (gets live equity)
ALPACA_API_KEY=xxx ALPACA_SECRET_KEY=yyy python3 scripts/verify_pl_sanity.py
```

### Exit Codes

- `0` - System healthy, no alerts
- `1` - Alert detected (critical or warning)
- `2` - Script error (missing deps, API failure, etc.)

### GitHub Actions Integration

The script writes to `GITHUB_OUTPUT` when run in CI:

```yaml
- name: Check P/L Sanity
  id: sanity
  run: python3 scripts/verify_pl_sanity.py

- name: Alert on Failure
  if: steps.sanity.outputs.pl_healthy == 'false'
  run: |
    echo "🚨 ALERT: ${{ steps.sanity.outputs.alert_reason }}"
    echo "Days since change: ${{ steps.sanity.outputs.days_since_change }}"
    echo "Days since trade: ${{ steps.sanity.outputs.days_since_trade }}"
```

## How It Works

### 1. Data Collection

The script maintains a `performance_log.json` file:

```json
[
  {
    "date": "2025-12-01",
    "timestamp": "2025-12-01T10:00:00",
    "equity": 100050.25,
    "pl": 50.25
  },
  {
    "date": "2025-12-02",
    "timestamp": "2025-12-02T10:00:00",
    "equity": 100075.50,
    "pl": 75.50
  }
]
```

### 2. Daily Updates

Each run:
1. Gets current equity from Alpaca API (or system_state.json fallback)
2. Appends entry to performance_log.json
3. Runs all health checks on historical data
4. Reports results

### 3. Trade Counting

Scans `data/trades_*.json` files to count recent executions.

### 4. Market Day Awareness

- Only counts trading days (weekdays)
- Ignores weekends for "stuck" detection
- Future: Could integrate with Alpaca market calendar for holidays

## Testing

Run the comprehensive test suite:

```bash
python3 scripts/test_verify_pl_sanity.py
```

This tests all 5 alert scenarios:
- ✅ Healthy system
- ✅ Stuck equity detection
- ✅ Zero P/L detection
- ✅ Anomalous change detection
- ✅ Drawdown detection

## Performance Log Structure

**Location**: `data/performance_log.json`

**Fields**:
- `date` - ISO date (YYYY-MM-DD)
- `timestamp` - Full ISO timestamp
- `equity` - Portfolio equity ($)
- `pl` - Total P/L vs starting balance ($)

**Retention**: Keep all historical data (file size minimal, ~1KB/month)

## Integration Points

### Daily Trading Workflow

```yaml
# .github/workflows/daily-trading.yml
jobs:
  trade:
    runs-on: ubuntu-latest
    steps:
      - name: Execute Trades
        run: python3 scripts/autonomous_trader.py

      - name: Sanity Check
        run: python3 scripts/verify_pl_sanity.py
```

### Monitoring Cron

```bash
# Run every 6 hours
0 */6 * * * cd /home/user/trading && python3 scripts/verify_pl_sanity.py
```

## Thresholds

Current thresholds (configurable in script):

```python
STALE_DAYS_THRESHOLD = 3        # Alert after 3 trading days stuck
ANOMALY_PCT_THRESHOLD = 5.0     # Alert on >5% daily change
DRAWDOWN_PCT_THRESHOLD = 10.0   # Alert on >10% drawdown
```

## Future Enhancements

1. **Market Calendar Integration**
   - Use Alpaca market calendar API
   - Properly handle holidays (don't alert on closed days)

2. **Slack/Email Alerts**
   - Send notifications on critical alerts
   - Daily digest of sanity check results

3. **Trend Analysis**
   - Detect declining win rate over time
   - Identify strategy degradation early

4. **Multi-Timeframe Checks**
   - Daily, weekly, monthly sanity checks
   - Different thresholds for different timeframes

5. **Predictive Alerts**
   - Warn BEFORE hitting critical thresholds
   - "Equity hasn't changed in 2 days" soft warning

## Related Files

- `scripts/verify_pl_sanity.py` - Main script
- `scripts/test_verify_pl_sanity.py` - Test suite
- `data/performance_log.json` - Historical equity data
- `data/system_state.json` - Current system state
- `data/trades_*.json` - Daily trade logs

## Lessons Learned

**From the 30-day silent failure:**

1. **Green checkmarks don't mean success** - CI can pass while business logic fails
2. **Monitor outcomes, not just outputs** - Track equity changes, not just script completion
3. **Early detection is critical** - 3 days vs 30 days = 90% reduction in lost time
4. **Automate verification** - Manual checks get skipped during busy periods
5. **Trust but verify** - Always have redundant monitoring

## CEO Directive

> "This would have caught our 30-day silent failure within 3 days. Make it mandatory."

**Status**: ✅ Implemented and tested
**Next**: Integrate into daily GitHub Actions workflow
**Mandate**: NEVER ship trading code without sanity checks
