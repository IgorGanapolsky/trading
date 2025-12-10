# verify_positions.py - Quick Reference

## Quick Start

```bash
# Basic usage (requires environment variables)
export ALPACA_API_KEY="your_key"
export ALPACA_SECRET_KEY="your_secret"
python3 scripts/verify_positions.py

# Or use .env file (will be auto-loaded)
python3 scripts/verify_positions.py
```

## What It Does

Compares your local trading state with Alpaca's API to find:
- ✅ Positions that match perfectly
- ❌ Phantom positions (local only, not in Alpaca)
- ❌ Missing positions (Alpaca only, not local)
- ❌ Quantity mismatches
- ❌ Value mismatches (>1% difference)

## Exit Codes

- **0** = Success (all positions match)
- **1** = Failure (discrepancies found)

## Example Output

### ✅ Success
```
======================================================================
🔍 POSITION VERIFICATION: Alpaca API vs Local State
======================================================================

📥 Loading positions...
   Local positions: 6
   Alpaca positions: 6

🔬 Comparing positions...

======================================================================
📊 COMPARISON RESULTS
======================================================================

✅ SUCCESS: All positions match!
   6 positions verified
```

### ❌ Failure
```
======================================================================
🔍 POSITION VERIFICATION: Alpaca API vs Local State
======================================================================

📥 Loading positions...
   Local positions: 5
   Alpaca positions: 6

🔬 Comparing positions...

======================================================================
📊 COMPARISON RESULTS
======================================================================

❌ FAILED: 2 discrepancies found

🚨 Discrepancies:

   1. GOOGL: Position in Alpaca but NOT in local state
      Local:  <missing>
      Alpaca:     2.500000

   2. SPY: Quantity mismatch
      Local:      5.000000
      Alpaca:     6.000000
      Diff:       1.000000

💡 Next Steps:
   1. Review discrepancies above
   2. Run: python scripts/reconcile_positions.py --fix
   3. Investigate why positions diverged
```

## When to Use

### Local Development
```bash
# After executing trades
python3 scripts/advanced_autonomous_trader.py
python3 scripts/verify_positions.py  # Verify trades executed correctly
```

### CI/CD Pipeline
```yaml
- name: Verify Positions
  env:
    ALPACA_API_KEY: ${{ secrets.ALPACA_API_KEY }}
    ALPACA_SECRET_KEY: ${{ secrets.ALPACA_SECRET_KEY }}
  run: python3 scripts/verify_positions.py
```

### Daily Audit
```bash
# Add to crontab for daily verification
0 17 * * 1-5 cd /path/to/trading && python3 scripts/verify_positions.py || \
  python3 scripts/reconcile_positions.py --fix
```

## Comparison Tolerances

- **Quantity**: Differences < 0.0001 shares are OK (floating-point precision)
- **Value**: Differences < 1% are OK (price fluctuations between API calls)

## GitHub Actions Integration

Automatically writes to `$GITHUB_OUTPUT`:
- `positions_match=true` or `false`
- `discrepancy_count=N`

Use in subsequent steps:
```yaml
- name: Check Results
  if: steps.verify.outputs.positions_match == 'false'
  run: |
    echo "Found ${{ steps.verify.outputs.discrepancy_count }} discrepancies"
    exit 1
```

## Troubleshooting

**Missing credentials?**
```bash
# Set environment variables
export ALPACA_API_KEY="your_key"
export ALPACA_SECRET_KEY="your_secret"

# Or create .env file
echo "ALPACA_API_KEY=your_key" >> .env
echo "ALPACA_SECRET_KEY=your_secret" >> .env
```

**Local state not found?**
```bash
# Initialize system state
python3 scripts/initialize_system_state.py
```

**Want to auto-fix discrepancies?**
```bash
# Use reconcile_positions.py instead
python3 scripts/reconcile_positions.py --fix
```

## Related Scripts

- `reconcile_positions.py` - Full reconciliation with auto-fix
- `check_positions.py` - Simple position display
- `realtime_pl_tracker.py` - Real-time P/L monitoring

## Full Documentation

See: [docs/position_verification.md](../docs/position_verification.md)
