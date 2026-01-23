# LL-298: Churning Prevention - Daily Trade Limits

**Date**: January 23, 2026
**Severity**: CRITICAL
**Status**: RESOLVED

## Incident

On Jan 23, 2026, the system executed **35 trades** instead of the expected **1 iron condor**, resulting in a **-$17.56 loss** from bid/ask spread erosion.

## Root Causes

1. **No daily limit in guaranteed_trader.py**
   - Script bought $100 of SPY every time it was called
   - No tracking of previous runs for the day

2. **Multiple workflow triggers**
   - 4+ "FORCE" commits triggered trading workflows repeatedly
   - Each trigger ran guaranteed_trader.py again

3. **Workflow coupling**
   - `claude-agent-utility.yml` calls guaranteed_trader without deduplication
   - No global daily execution tracking

## Impact

- **35 trades** instead of 1 iron condor
- **-$17.56** daily loss from bid/ask spreads
- Violated Phil Town Rule #1: Don't lose money

## Fix Applied

Added daily limit to `scripts/guaranteed_trader.py`:

```python
# LL-298 FIX: Daily trade limit to prevent churning
MAX_DAILY_RUNS = 1
state_file = Path("data/guaranteed_trader_daily.json")
today = datetime.now().strftime("%Y-%m-%d")

if state_file.exists():
    state = json.load(open(state_file))
    if state.get("date") == today and state.get("runs", 0) >= MAX_DAILY_RUNS:
        logger.warning("DAILY LIMIT REACHED - BLOCKING EXECUTION")
        return {"success": False, "reason": "daily_limit_reached"}
```

## Prevention Checklist

- [ ] All trading scripts MUST have daily execution limits
- [ ] Track runs in persistent state file (not memory)
- [ ] Use workflow concurrency groups to prevent parallel runs
- [ ] Review all "FORCE" or emergency trade triggers for accumulation risk
- [ ] Monitor daily trade count in system_state.json

## Related Lessons

- LL-281: Position Accumulation Crisis
- LL-268: 7 DTE Exit Rule
- LL-297: Iron Condor Daily Limit

## Phil Town Alignment

**Rule #1: Don't lose money.**
- Every trade has bid/ask spread cost (~$0.50-$1.00)
- 35 trades × $0.50 = $17.50 loss just from spreads
- 1 trade per day = minimal friction
