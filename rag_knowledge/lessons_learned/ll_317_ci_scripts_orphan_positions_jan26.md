# LL-317: CI Scripts Failing + Orphan Positions Blocking Trades

**ID**: LL-317
**Date**: 2026-01-26
**Severity**: CRITICAL
**Category**: trading-system, ci-infrastructure
**Tags**: `ci`, `positions`, `iron-condor`, `crisis`
**Status**: IN_PROGRESS

## Incident Summary

After fixing VIX threshold (LL-316), iron condor trades were STILL blocked because:
1. 3 orphan option positions from Jan 22 crisis were blocking new trades
2. The `manage_iron_condor_positions.py` script was failing in CI due to import error

## Root Causes

### 1. CI Import Error
`manage_iron_condor_positions.py` imported from `src.utils.alpaca_client`:
```python
from src.utils.alpaca_client import get_alpaca_credentials
```
But CI only installs `alpaca-py`, not the full `src` package.

### 2. Orphan Positions
Three positions left over from Jan 22 crisis:
- SPY260227C00730000: +1 (Long Call)
- SPY260227P00650000: +1 (Long Put)
- SPY260227P00655000: -1 (Short Put)

These are NOT a valid iron condor (missing short call). The position limit check blocks new trades.

### 3. close_position_direct.py Hardcoded Symbol
The script had a hardcoded target: `target_symbol = "SPY260220P00658000"` from a previous incident.

## Resolution

### Fix 1: CI-Compatible Credentials (manage_iron_condor_positions.py)
Added inline `get_alpaca_credentials()` that reads from env vars:
```python
def get_alpaca_credentials():
    """Get Alpaca credentials from environment variables (CI-compatible)."""
    api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_SECRET")
    return api_key, secret_key
```

### Fix 2: Close ALL Option Positions (close_position_direct.py)
Rewrote script to iterate through all option positions and close each:
```python
option_positions = [pos for pos in positions if is_option(pos.symbol)]
for pos in option_positions:
    client.close_position(pos.symbol)
```

## Prevention Measures

1. **CI-First Design**: Scripts should get credentials from env vars, not local modules
2. **Position Cleanup Automation**: Orphan positions should be detected and cleaned automatically
3. **Daily Position Audit**: Scheduled workflow to verify position structure is valid

## Next Steps Required

1. Merge branch `claude/review-rag-hooks-ixWGy` to main
2. Trigger "Close Position Direct" workflow to close orphan positions
3. Trigger "Force Iron Condor Execution" to open new trade

## Related Lessons

- LL-316: VIX threshold blocking trades
- LL-282: CTO Three-Day Crisis
- LL-291: Position accumulation issues
