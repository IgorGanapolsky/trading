# TRIGGER: Set Trailing Stops

**Date**: 2026-01-09
**Action**: SET TRAILING STOPS ON ALL OPEN POSITIONS

## Why This Is Critical

We have **$1,187.60** in unrealized gains with ZERO protection:

| Position | Unrealized P/L | Protection |
|----------|----------------|------------|
| SPY | +$74.60 | NONE |
| INTC put | +$151.00 | NONE |
| SOFI put | +$56.00 | NONE |
| AMD put | +$457.00 | NONE |
| SPY put | +$449.00 | NONE |

## Required Action

Run the `set-trailing-stops` task in GitHub Actions:

1. Go to: https://github.com/IgorGanapolsky/trading/actions/workflows/claude-agent-utility.yml
2. Click "Run workflow"
3. Select task: `set-trailing-stops`
4. Click "Run workflow"

Or trigger via API:
```bash
curl -X POST \
  -H "Authorization: token YOUR_PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/IgorGanapolsky/trading/actions/workflows/claude-agent-utility.yml/dispatches \
  -d '{"ref":"main","inputs":{"task":"set-trailing-stops"}}'
```

## Phil Town Rule #1

"Don't lose money" - these gains are at risk without trailing stops.

---
Triggered by: Claude CTO
Session: Jan 9, 2026 12:15 AM ET
