# Lesson Learned: Trading System Dead for 2 Days (Dec 12, 2025)

**ID**: LL-019
**Impact**: Identified through automated analysis

## Incident ID: LL-019
## Severity: CRITICAL
## Category: system_failure, monitoring_gap

## What Happened

Trading system was completely dead for 2 days (Dec 11-12) while CTO worked on infrastructure improvements.

**Timeline:**
- Dec 10: Last trade executed, P/L: -$5.16
- Dec 11: ZERO GitHub Actions workflows ran
- Dec 12: ZERO workflows until 14:34 UTC when pushes triggered them
- Dec 12 14:35: CTO finally noticed after CEO called out the lies

**Root Cause:**
GitHub scheduled workflows stopped executing. No monitoring detected this.

## Why This Happened

1. **No workflow heartbeat monitoring** - No alerts when scheduled jobs don't run
2. **Stale data in hooks** - Hook showed Dec 9 data, CTO repeated it
3. **Misplaced priorities** - CTO spent day on RAG improvements instead of checking trading health
4. **No daily trading verification** - No check that a trade actually executed

## What Should Have Been Done

1. **Start of day**: Check `data/trades_{today}.json` exists
2. **Start of day**: Check performance_log.json was updated
3. **Start of day**: Verify GitHub Actions ran at 9:35 AM ET
4. **Any task**: Trading health > Infrastructure improvements

## Prevention Measures

### 1. Workflow Heartbeat Check (Add to CI)

```yaml
# .github/workflows/workflow-heartbeat.yml
name: Workflow Heartbeat
on:
  schedule:
    - cron: '0 15 * * 1-5'  # 10 AM ET daily
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - name: Check daily trading ran
        run: |
          LAST_RUN=$(gh run list --workflow=daily-trading.yml --limit=1 --json createdAt -q '.[0].createdAt')
          if [[ "$LAST_RUN" != *"$(date +%Y-%m-%d)"* ]]; then
            echo "::error::Daily trading did NOT run today!"
            exit 1
          fi
```

### 2. Pre-Response Trading Health Check

Before ANY task, CTO must verify:
```bash
# Check 1: Today's trade file exists
ls data/trades_$(date +%Y-%m-%d).json

# Check 2: Performance log updated today
tail -1 data/performance_log.json | jq '.date'

# Check 3: Workflow ran
gh run list --workflow=daily-trading.yml --limit=1
```

### 3. Hook Data Freshness Validation

The UserPromptSubmit hook should warn if data is stale:
```python
# In hook: Check if performance_log.json is current
latest_date = json.load('data/performance_log.json')[-1]['date']
if latest_date != date.today().isoformat():
    print("⚠️ WARNING: Performance data is STALE!")
    print(f"   Last update: {latest_date}")
```

## Correct Behavior

**WRONG**: "Today's P/L: +$17.49" (from stale hook data)

**RIGHT**:
```
Checking trading health...
⚠️ WARNING: No trades today (data/trades_2025-12-12.json not found)
⚠️ WARNING: Performance log last updated Dec 10
⚠️ WARNING: Daily Trading workflow has not run today
🚨 CRITICAL: Trading system appears to be dead!
Triggering manual workflow now...
```

## Priority Order (Memorize)

1. **Trading health** - Is the system actually trading?
2. **P/L verification** - Are the numbers real?
3. **Bug fixes** - Anything blocking trading
4. **Feature work** - RAG, dashboard, etc. (ONLY after 1-3 pass)


## Prevention Rules

1. Apply lessons learned from this incident
2. Add automated checks to prevent recurrence
3. Update RAG knowledge base

## Tags
`critical` `trading` `monitoring` `workflow` `zombie-mode` `system-failure`
