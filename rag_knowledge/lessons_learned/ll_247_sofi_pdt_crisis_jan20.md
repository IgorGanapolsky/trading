# LL-247: SOFI PDT Crisis - SPY ONLY Violation

**Date**: January 20, 2026
**Severity**: HIGH
**Resolution Date**: 2026-01-21
**Resolution**: Ticker validator deployed, close-non-spy workflow running
**Category**: Strategy Violation, Risk Management
**Status**: MITIGATED (fix deployed), PENDING (position close tomorrow)

## Incident Summary

A SOFI short put position (SOFI260213P00032000) was opened at 14:35 UTC, violating the "SPY ONLY" directive in CLAUDE.md. The position is now -$150 unrealized and cannot be closed until tomorrow due to PDT (Pattern Day Trading) protection.

## Root Cause Analysis

1. **Unknown trade source**: The SOFI trade was placed at 14:35 UTC, before the daily-trading workflow ran at 14:48 UTC
2. **Possible causes**:
   - Manual trade placed outside automated system
   - Another workflow/script without ticker validation
   - Scheduled job that bypassed SPY ONLY checks

3. **Missing safeguard**: No centralized ticker validation existed that ALL trading scripts were required to use

## Impact

- **Financial**: -$150 unrealized loss on SOFI260213P00032000
- **Strategic**: Violated "SPY ONLY" directive from CLAUDE.md
- **Operational**: Position locked until tomorrow (PDT rule)
- **Win rate**: 16.7% (1 win, 5 losses) - far below 80% target

## Fix Applied

1. Created `src/utils/ticker_validator.py`:
   - `ALLOWED_TICKERS = frozenset({"SPY"})` - whitelist
   - `validate_ticker()` - raises `TickerViolationError` for non-SPY
   - `is_allowed_ticker()` - boolean check without exception

2. Hardened `scripts/iron_condor_trader.py`:
   - Added `validate_ticker(strategy.config["underlying"], context="iron_condor_trader")` before any trading

3. Merged via PR #2298 (SHA: 915ba0a)

## Prevention

All trading scripts MUST now import and use the ticker validator:

```python
from src.utils.ticker_validator import validate_ticker
validate_ticker(symbol, context="script_name")  # Raises if not SPY
```

## Action Items

- [x] Create ticker_validator.py
- [x] Add validation to iron_condor_trader.py
- [x] Merge fix to main (PR #2298)
- [ ] Close SOFI position tomorrow (PDT blocked today)
- [ ] Add ticker validation to ALL trading scripts (audit needed)
- [ ] Investigate exact source of SOFI trade

## Lessons Learned

1. **Centralized validation is critical**: Without a single source of truth for allowed tickers, scripts can bypass restrictions
2. **PDT protection is a feature, not a bug**: The PDT block prevented same-day panic selling
3. **Win rate matters more than any single trade**: 16.7% win rate is the real crisis, not the -$150 position
4. **SPY ONLY is non-negotiable**: The $100K account succeeded with SPY; the $5K account failed with individual stocks

## Related Lessons

- LL-209: Ticker whitelist enforcement
- LL-242: Strategy mismatch (iron condors only)
- LL-244: Adversarial audit findings
