# LL-261: Multiple Scripts Had Hardcoded Position Size Violations

**Date**: 2026-01-19
**Severity**: CRITICAL
**Category**: Risk Management Configuration Error

## Problems Found

During adversarial audit, discovered multiple trading scripts had hardcoded position limits that violated CLAUDE.md's 5% max per position mandate:

| Script | Setting | Value | CLAUDE.md Limit | Violation |
|--------|---------|-------|-----------------|-----------|
| iron_condor_trader.py | position_size_pct | 0.15 (15%) | 5% | **3x over limit** |
| rule_one_trader.py | max_position_pct | 0.10 (10%) | 5% | **2x over limit** |

Additionally, `iron_condor_trader.py` used SOFI as underlying, which is in blackout until Feb 1 per CLAUDE.md ticker hierarchy.

## Root Cause

Configuration drift: Scripts were written with their own position limits without referencing the central CLAUDE.md mandate. No automated enforcement existed at the script level.

## Fixes Applied

### iron_condor_trader.py
```python
# BEFORE
"position_size_pct": 0.15,  # 15% of portfolio per IC
"underlying": "SOFI",
"max_positions": 3,

# AFTER (Jan 19, 2026)
"position_size_pct": 0.05,  # 5% - CLAUDE.md MANDATE
"underlying": "IWM",  # Per CLAUDE.md: SPY/IWM only
"max_positions": 1,  # Per CLAUDE.md: "1 spread at a time"
```

### rule_one_trader.py
```python
# BEFORE
"max_position_pct": 0.10,  # 10% per position
"watchlist": ["F", "SOFI", "T", "INTC", "BAC", "VZ"]

# AFTER (Jan 19, 2026)
"max_position_pct": 0.05,  # 5% - CLAUDE.md MANDATE
"watchlist": ["SPY", "IWM"]  # Per CLAUDE.md: SPY/IWM only
```

## Prevention

1. All trading scripts should import position limits from a central constants file
2. Add pre-commit hook to scan for hardcoded percentages > 5%
3. Weekly adversarial audits to catch configuration drift

## Recommendation

Create `src/constants/trading_thresholds.py` and have ALL trading scripts import from there:

```python
# All scripts should use:
from src.constants.trading_thresholds import SIZING

# Instead of hardcoded values:
position_size_pct = SIZING.MAX_POSITION_PCT  # 0.05 (5%)
```

## Tags

position-sizing, configuration-drift, hardcoded-values, 5-percent-rule, audit-finding
