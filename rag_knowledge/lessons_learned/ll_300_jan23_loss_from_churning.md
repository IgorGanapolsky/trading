# LL-300: $22.61 Loss from Stock Churning (Jan 23, 2026)

## Summary
On January 23, 2026, the trading system lost $22.61 due to uncontrolled stock churning from `guaranteed_trader.py` running 22+ times.

## What Happened
1. `guaranteed_trader.py` was triggered by `claude-agent-utility.yml` on every push to `claude/*` branches
2. Each run bought $100 of SPY STOCK (not iron condors)
3. No effective daily limit was in place
4. 22+ trades executed, each losing money to bid/ask spreads
5. Iron condor attempts failed due to invalid Sunday expiry date (Feb 22 instead of Friday)

## Root Causes
1. **Workflow misconfiguration**: `guaranteed_trader.py` ran on every branch push
2. **Strategy violation**: Script bought SPY stock, not iron condors per CLAUDE.md
3. **Missing guardrails**: No daily run limit file existed
4. **Expiry bug**: Iron condor used Feb 22 (Sunday) - options don't expire on Sundays

## Fixes Applied
1. Disabled `guaranteed_trader.py` execution in `claude-agent-utility.yml`
2. Added pre-validation to prevent partial option fills (PR #2882)
3. Fixed credential usage to 30K account

## Financial Impact
- Starting balance: $30,000.00
- Ending equity: $29,977.39
- Daily loss: **-$22.61**
- Phil Town Rule #1 VIOLATED

## Lesson
Stock churning destroys capital through bid/ask spread losses. The system MUST:
1. Execute iron condors ONLY (per CLAUDE.md)
2. Have strict daily execution limits
3. Validate option expiry dates are valid trading days (Fridays for standard options)
4. Never run guaranteed_trader.py - it contradicts the iron condor strategy

## Prevention
- `guaranteed_trader.py` is now DISABLED
- Added `data/guaranteed_trader_daily.json` block file
- Pre-validation prevents partial fills
- Expiry calculation verified to output Fridays

## Tags
- trading-loss
- churning
- bid-ask-spread
- guaranteed-trader
- phil-town-rule-1
