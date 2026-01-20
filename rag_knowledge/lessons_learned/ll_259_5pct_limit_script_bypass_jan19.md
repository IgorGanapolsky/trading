# LL-259: 5% Position Limit Check Missing from execute_credit_spread.py

**Date**: 2026-01-19
**Severity**: CRITICAL
**Category**: Risk Management Gap

## Problem Found

The `execute-credit-spread.yml` workflow has a compliance check for the 5% per-position limit. However, `daily-trading.yml` calls `execute_credit_spread.py` DIRECTLY (line 1088), completely bypassing the workflow's compliance check!

**Attack vector**:
- `daily-trading.yml` runs theta harvest step
- Step calls `python3 scripts/execute_credit_spread.py --symbol SPY --width 2`
- Script NEVER checks if $200 collateral exceeds 5% of account
- With a $3,000 account, 5% = $150, but script would allow $200 trade!

## Root Cause

Defense-in-depth failure: The 5% check existed in the workflow YAML but NOT in the Python script itself. Any direct script execution (CI, manual, other workflows) bypassed the protection.

## Fix Applied

Added `check_position_limit()` function to `execute_credit_spread.py`:

```python
def check_position_limit(trading_client, collateral_required: float) -> tuple[bool, str]:
    """Check if proposed trade violates 5% per-position limit (CLAUDE.md mandate)."""
    account = trading_client.get_account()
    equity = float(account.equity)
    max_per_position = equity * 0.05  # 5% per CLAUDE.md

    if collateral_required > max_per_position:
        return (True, f"POSITION SIZE VIOLATION: ${collateral_required:.2f} exceeds 5% limit")
    return False, "OK"
```

This check runs AFTER finding the spread (so we know collateral) but BEFORE executing the trade.

## Defense-in-Depth Principle

**ALWAYS enforce critical limits at the lowest level (Python script), not just at workflow level.**

The script can be called from:
1. `execute-credit-spread.yml` workflow (had check)
2. `daily-trading.yml` workflow (NO check until now)
3. Manual execution via CLI
4. Future workflows

Only enforcing in the Python script guarantees ALL callers are protected.

## Verification

With $5K account:
- Max per position: $250 (5%)
- $3 spread = $300 collateral
- Script NOW blocks: "POSITION SIZE VIOLATION: $300.00 exceeds 5% limit ($250.00)"

## Tags

risk-management, position-sizing, 5-percent-rule, defense-in-depth, script-bypass, bug-fix
