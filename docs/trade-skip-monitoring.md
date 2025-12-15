# Trade Skip Monitoring System

## Overview

Automated monitoring system that detects when trades are skipped for consecutive days and creates alerts via GitHub Issues.

## Components

### 1. Monitor Script: `scripts/check_consecutive_skips.py`

Python script that:
- Checks the last 3 days of trade data (`data/trades_YYYY-MM-DD.json`)
- Identifies days where all trades had `action: "SKIP"`
- Extracts relevant data:
  - Skip reasons
  - MA distance (how far price is from 50-day MA)
  - RSI values (if available)
  - 7-day price changes
- Generates formatted GitHub issue body

**Usage:**
```bash
python3 scripts/check_consecutive_skips.py
```

**Exit Codes:**
- `0`: No consecutive skips (normal)
- `1`: Consecutive skips detected (alert needed)
- `2`: Error (e.g., data directory not found)

### 2. GitHub Actions Workflow: `.github/workflows/monitor-trade-skips.yml`

Automated workflow that:
- Runs daily at 11:00 AM ET (16:00 UTC)
- Executes the monitoring script
- Creates GitHub issue if consecutive skips are detected
- Labels issues: `trading-alert`, `needs-attention`, `automated`
- Uploads skip analysis as artifact for review

**Manual Trigger:**
```bash
gh workflow run monitor-trade-skips.yml
```

## Alert Format

When consecutive skips are detected, a GitHub issue is created with:

### Issue Title
🚨 Trading Alert: Consecutive Trade Skips Detected

### Issue Body
- **Skip Summary**: Date-by-date breakdown
- **Strategy Info**: Strategy name and version
- **Skip Reasons**: Why trades were skipped each day
- **Market Position**: Current price vs 50-day MA for each crypto (BTC, ETH, SOL)
- **RSI Values**: If available in trade data
- **Action Items**: Checklist for review

### Example Output
```
#### 2025-12-14
- **Strategy**: WorldClassCrypto v4.0
- **Reason**: All below 50-day MA - waiting for trend

**Market Position vs 50-day MA:**
- **BTC-USD**: $88800.00 (-7.98% below MA50 $96500.00)
- **ETH-USD**: $3080.00 (-6.67% below MA50 $3300.00)
- **SOL-USD**: $130.50 (-13.00% below MA50 $150.00)
```

## Configuration

### Adjust Days to Check
Edit `scripts/check_consecutive_skips.py`:
```python
days_to_check = 3  # Change to desired number
```

### Adjust Schedule
Edit `.github/workflows/monitor-trade-skips.yml`:
```yaml
schedule:
  - cron: '0 16 * * *'  # Change time (UTC)
```

### Add Labels
Edit workflow:
```yaml
--label "trading-alert" \
--label "needs-attention" \
--label "your-custom-label"
```

## Trade Data Format

The script expects trade files in format `data/trades_YYYY-MM-DD.json`:

```json
[
  {
    "date": "2025-12-15",
    "strategy": "WorldClassCrypto",
    "strategy_version": "4.0",
    "action": "SKIP",
    "skip_reason": "All below 50-day MA - waiting for trend",
    "trend_analysis": {
      "BTC-USD": {
        "price": 88500.0,
        "ma50": 96500.0,
        "above": false,
        "pct": -8.29,
        "chg7d": -2.5
      }
    }
  }
]
```

## Troubleshooting

### No Issues Created Despite Skips

1. Check workflow logs:
```bash
gh run list --workflow=monitor-trade-skips.yml
gh run view <run-id> --log
```

2. Run script manually:
```bash
python3 scripts/check_consecutive_skips.py
```

3. Verify trade files exist:
```bash
ls -la data/trades_*.json
```

### False Positives

- Script only triggers on SKIP actions (not missing data)
- Checks for `action: "SKIP"` specifically
- Missing trade files for a day = warning, not alert

### Test the System

Create test scenario:
```bash
# Manual trigger
gh workflow run monitor-trade-skips.yml

# Check run status
gh run list --workflow=monitor-trade-skips.yml
```

## Integration

This monitoring system integrates with:
- **Trading Strategies**: WorldClassCrypto v4.0+ (trend-aware)
- **Risk Management**: Alerts when no capital deployed for extended periods
- **Manual Review**: GitHub issues for CEO/CTO review
- **Daily Trading Workflow**: Complements `daily-trading.yml`

## History

- **Created**: December 15, 2025
- **Purpose**: Detect extended periods of no trading activity
- **Trigger**: Post crypto v4.0 trend filter implementation
- **Context**: Ensure system doesn't skip indefinitely during downtrends

## Related Files

- `.github/workflows/daily-trading.yml` - Main trading execution
- `src/strategies/world_class_crypto.py` - Strategy with MA filters
- `data/system_state.json` - Current system state
- `.claude/rules/MANDATORY_RULES.md` - Trading rules
