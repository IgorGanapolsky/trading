# LL-275: Missing --symbol Argument Blocked Trading for 8+ Days

**Date:** January 21, 2026
**Severity:** CRITICAL
**Category:** Silent Failure, Argparse, Trading Blocked

## Issue
The iron condor trading system appeared to work (workflow showed SUCCESS) but no trades were actually executing for 8+ days.

## Root Cause
The `iron_condor_trader.py` script did NOT define a `--symbol` argument in its argparse parser, but the `daily-trading.yml` workflow called it with `--symbol SPY`.

```python
# BEFORE (broken):
parser = argparse.ArgumentParser(description="Iron Condor Trader")
parser.add_argument("--live", action="store_true", help="Execute LIVE trades on Alpaca")
parser.add_argument("--dry-run", action="store_true", help="Dry run (simulate only)")
args = parser.parse_args()  # <-- ERRORS with "unrecognized arguments: --symbol SPY"
```

```yaml
# Workflow call in daily-trading.yml line 1152:
python3 scripts/iron_condor_trader.py --symbol "${TICKER}" || {
    echo "   ⚠️  ${TICKER} iron condor returned non-zero"
}
```

The `|| { echo... }` silently caught the argparse error and continued, making the workflow appear successful.

## Impact
- **8+ days without iron condor trades**
- **$0 income during this period**
- **Crisis mode for 2 consecutive days**
- **Misattributed cause** - initially thought position limits were blocking trades, but it was argparse

## Fix
Added `--symbol` argument to argparse and use it to override the strategy config:

```python
# AFTER (fixed):
parser.add_argument("--symbol", type=str, default="SPY", help="Underlying symbol (default: SPY)")
# ... later ...
if args.symbol:
    strategy.config["underlying"] = args.symbol.upper()
```

## Prevention
1. **Test argparse acceptance** - Always test that scripts accept the exact arguments workflows pass
2. **Remove silent error catching** - Consider using `set -e` or removing `|| { echo... }` for critical trading scripts
3. **Verify execution** - Check that trading scripts actually place orders, not just "complete without error"
4. **CI gate** - Add test that verifies argparse accepts all workflow arguments

## Lesson
Silent failures are the worst failures. A script erroring out looks like success when the error handler doesn't fail the workflow. Always validate that argparse definitions match actual usage.

## Related
- LL-268: Iron condor execution failure (4-leg validation)
- LL-270: System blocked, no auto cleanup
- LL-242: Strategy mismatch crisis
