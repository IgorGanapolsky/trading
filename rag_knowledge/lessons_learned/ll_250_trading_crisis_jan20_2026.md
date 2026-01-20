# LL-250: Trading Crisis - System Stuck for 7 Days (Jan 20, 2026)

## Severity: CRITICAL

## Summary
Trading system was completely stuck for 7+ days (Jan 13-20, 2026) due to multiple compounding bugs. No new trades could execute despite market being open.

## Root Causes Found

### 1. Octal Interpretation Bug in Market Status Hook
- **File**: `.claude/hooks/inject_trading_context.sh`
- **Bug**: `date +%H` returns "09" with leading zero
- **Impact**: Bash interprets "09" as octal, but 9 is invalid (octal = 0-7)
- **Result**: `-lt`/`-eq` comparisons fail silently, PRE_MARKET falls through to POST_MARKET
- **Fix**: Use `%-H` (no leading zero) instead of `%H`
- **PR**: #2279

### 2. No Position Limit Check Before Trading
- **File**: `scripts/iron_condor_trader.py`
- **Bug**: Script placed new orders without checking existing positions
- **Impact**: System kept trying to trade despite max positions reached
- **Fix**: Added position check after RAG validation, returns SKIPPED_POSITION_LIMIT if limit reached
- **PR**: #2293

### 3. Incomplete Iron Condors (PUT Only)
- **Symptom**: 6 SPY PUT positions with no CALL legs
- **Cause**: Earlier pricing bug ($0.50 hardcoded) caused CALL legs to not fill
- **Impact**: Positions blocked new trades due to position limit
- **Fix**: Real option pricing from Alpaca API (PR #2270)

### 4. SOFI Trades Violating CLAUDE.md
- **Finding**: 27 SOFI trades in history despite "SPY ONLY" mandate
- **Impact**: Capital misallocated to non-approved ticker
- **Prevention**: Whitelist enforcement in iron_condor_trader.py

## Timeline
| Date | Event |
|------|-------|
| Jan 13 | Last successful trade (SOFI) |
| Jan 14-19 | System stuck - no trades due to position limit |
| Jan 20 | Crisis discovered and fixed |

## Verification Commands
```bash
# Check market status detection
CURRENT_HOUR=$(TZ=America/New_York date +%-H)
echo "Hour: $CURRENT_HOUR (should be 9, not 09)"

# Check positions
python3 -c "import json; d=json.load(open('data/system_state.json')); print(f'Positions: {d.get(\"paper_account\", {}).get(\"positions_count\", 0)}')"
```

## Prevention Checklist
- [ ] Always use `%-H` for hour comparisons in bash (no leading zero)
- [ ] Check position limits BEFORE placing any orders
- [ ] Verify ticker is in whitelist before trading
- [ ] Alert if no trades for >24 hours during market days

## Related PRs
- #2270: Fix real SPY/option pricing
- #2279: Fix market status octal bug
- #2293: Add position limit check

## Tags
crisis, bash, octal, position-limit, iron-condor, stuck, no-trades
