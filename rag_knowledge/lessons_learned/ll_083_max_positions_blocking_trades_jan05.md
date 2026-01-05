# Lesson Learned #083: max_positions=3 Blocked All Paper Trading for 13 Days

**Date**: 2026-01-05
**Severity**: CRITICAL
**Category**: configuration

## What Happened

The `simple_daily_trader.py` script had `max_positions=3` hardcoded. The paper account had 4 options positions. This caused `should_open_position()` to always return `False`, resulting in **ZERO trades for 13 consecutive days** (Dec 23, 2025 - Jan 5, 2026).

**Evidence:**
- `data/trades_2025-12-23.json` was the last trade file
- `data/trades_2026-01-05.json` never existed
- Workflow runs showed "SUCCESS" but no trades executed
- Dashboard showed "Trades Today: 0" for 13 days

## Root Cause

Line 51 in `scripts/simple_daily_trader.py`:
```python
"max_positions": 3,  # Max 3 open positions
```

With 4 open options positions:
- INTC260109P00035000
- SOFI260123P00024000
- AMD260116P00200000
- SPY260123P00660000

The check `len(options_positions) >= config["max_positions"]` (4 >= 3) always blocked new trades.

## The Fix

Changed `max_positions` from 3 to 10:
```python
"max_positions": 10,  # Max 10 open positions - FIXED: was blocking trades
```

**PR #1123**: Merged 2026-01-05

## Prevention

1. **Test Added**: `tests/test_simple_daily_trader.py` now asserts `max_positions >= 10`
2. **Alert**: Should alert if 3+ consecutive days without trades
3. **Config Review**: Review position limits before deploying

## Key Insight

The workflow showed "SUCCESS" because the script ran without errors - it just decided not to trade. Silent failures are the worst kind. We need:
- Alerting when max_positions is reached
- Dashboard warning when no trades for N days
- Smoke test that verifies trading CAN happen

## Tags
`trading`, `configuration`, `silent-failure`, `critical`, `max_positions`
