# LL-210: Missing OptionsPosition Class Broke CI Tests

**ID**: ll_210
**Date**: January 14, 2026
**Severity**: HIGH
**Category**: Import Error / CI Failure

## Problem

CI workflow "Run All Tests" failed with:
```
ImportError: cannot import name 'OptionsPosition' from 'src.risk.options_risk_monitor'
```

The `options_executor.py` file tried to import `OptionsPosition` from `options_risk_monitor.py`, but the class did not exist in that module.

## Root Cause

1. `src/trading/options_executor.py` line 27 imports `OptionsPosition`
2. `src/risk/options_risk_monitor.py` only had `OptionsRiskMonitor` class
3. The `OptionsPosition` dataclass was never created despite being referenced

## Solution

Added the missing `OptionsPosition` dataclass to `options_risk_monitor.py`:

```python
@dataclass
class OptionsPosition:
    """Represents an options position for risk monitoring."""
    symbol: str
    underlying: str
    position_type: str
    side: Literal["long", "short"]
    quantity: int
    entry_price: float
    current_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    expiration_date: date
    strike: float
    opened_at: datetime
```

Also updated `add_position()` method for backwards compatibility.

## Prevention

1. Always verify imports work locally before pushing
2. Run `python -c "from module import Class"` to verify imports
3. CI should catch import errors in test phase (which it did)

## PR Reference

PR #1832: fix: Add OptionsPosition dataclass to fix CI import error
