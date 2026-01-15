# Lesson Learned LL-217: OptionsRiskMonitor Paper Arg Crisis

## Date
2026-01-15

## Severity
**P0 - CRITICAL** - Blocked ALL trading for entire day

## What Happened
The Daily Trading workflow failed at 14:44 UTC with exit code 2. Zero trades executed.

## Root Cause
```python
# In src/orchestrator/main.py line 196
self.options_risk_monitor = OptionsRiskMonitor(paper=paper)  # WRONG!
```

The `OptionsRiskMonitor.__init__()` method only accepts `max_loss_percent`, not `paper`. This caused a `TypeError` that crashed the entire trading orchestrator.

## Error Message
```
TypeError: OptionsRiskMonitor.__init__() got an unexpected keyword argument 'paper'
```

## Impact
- Daily Trading workflow: FAILED
- Trades executed: ZERO
- Revenue lost: ~$50-70 (one day's potential credit spread premium)
- Time to detect: ~1 hour (CEO discovered at 15:40 UTC)
- Time to fix: 5 minutes once identified

## Fix Applied
```python
# Fixed version
self.options_risk_monitor = OptionsRiskMonitor()  # No paper arg needed
```

PR #1887 merged at 15:45 UTC.

## How This Was Introduced
Unknown - likely a refactoring that added `paper=paper` without checking the OptionsRiskMonitor signature.

## Prevention Measures
1. **Type checking**: Add mypy/pyright to catch signature mismatches
2. **Integration tests**: Add test that instantiates TradingOrchestrator
3. **Pre-commit hooks**: Run quick smoke test before push
4. **CI gate**: Add orchestrator instantiation test to CI

## Detection Method
- Analyzed GitHub Actions logs for run #21035255376
- Found `TypeError` in execute-trading job step 18
- Traced to `src/orchestrator/main.py:196`

## Lessons
1. **Always check method signatures** when passing arguments
2. **Read workflow logs immediately** when trading fails
3. **Test orchestrator instantiation** as part of CI
4. **Monitor workflow status proactively** - don't wait for CEO to discover

## Tags
- P0
- trading-blocked
- TypeError
- orchestrator
- options-risk-monitor
- ci-failure
