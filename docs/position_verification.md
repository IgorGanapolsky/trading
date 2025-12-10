# Position Verification System

## Overview

The position verification system ensures that our local trading state (`data/system_state.json`) stays synchronized with the ground truth from Alpaca's API. This is critical for:

- **Data Integrity**: Detect discrepancies between local and broker state
- **Trade Verification**: Ensure all trades executed successfully
- **Audit Trail**: Maintain accurate position tracking
- **CI/CD Quality Gates**: Prevent deployments when positions are out of sync

## Scripts

### 1. `verify_positions.py` - Quick Verification

**Purpose**: Fast verification script designed for CI/CD pipelines

**Features**:
- ✅ Compares Alpaca API positions vs local state
- ✅ Reports all discrepancies clearly
- ✅ Fail-fast (exit code 1 on ANY discrepancy)
- ✅ GitHub Actions integration (GITHUB_OUTPUT)
- ✅ Works both locally and in CI

**Usage**:

```bash
# Local development
python scripts/verify_positions.py

# In CI/CD (auto-detects GITHUB_OUTPUT)
python scripts/verify_positions.py
# Sets: positions_match=true/false, discrepancy_count=N
```

**Exit Codes**:
- `0` - All positions match (success)
- `1` - Discrepancies found or errors occurred (failure)

**Example Output** (Success):
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

📈 Verified Positions:
   BIL      | Qty:   131.103245 | Value: $11,998.57
   BTCUSD   | Qty:     0.000220 | Value:     $19.68
   IEF      | Qty:     1.243668 | Value:    $119.98
   SHY      | Qty:     5.554236 | Value:    $459.72
   SPY      | Qty:     6.000000 | Value:  $4,114.14
   TLT      | Qty:     0.226623 | Value:     $19.98

======================================================================
```

**Example Output** (Failure):
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

======================================================================
```

### 2. `reconcile_positions.py` - Full Reconciliation

**Purpose**: Comprehensive reconciliation with auto-fix capabilities

**Features**:
- 🔍 Detailed position comparison
- 🔧 Auto-fix mode (syncs local to Alpaca)
- 📊 Full reconciliation reports
- 📁 Historical audit trail

**Usage**:

```bash
# Report only (no changes)
python scripts/reconcile_positions.py --report-only

# Auto-fix discrepancies
python scripts/reconcile_positions.py --fix
```

**When to Use Each Script**:

| Script | Purpose | Use Case |
|--------|---------|----------|
| `verify_positions.py` | Quick verification | CI/CD gates, pre-deployment checks |
| `reconcile_positions.py` | Full reconciliation | Daily audits, fixing discrepancies |

## Comparison Tolerances

The verification uses the following tolerances to account for floating-point precision:

```python
QTY_TOLERANCE = 0.0001          # Quantity differences < 0.0001 are OK
VALUE_TOLERANCE_PCT = 0.01      # Value differences < 1% are OK
```

**Rationale**:
- Floating-point arithmetic can cause tiny differences
- Market price updates between API calls may cause small value shifts
- Tolerances prevent false positives from rounding errors

## Discrepancy Types

### 1. Phantom Position
**Issue**: Position exists locally but NOT in Alpaca
**Cause**: Local state out of sync (position closed but not updated locally)
**Fix**: Remove from local state or investigate if trade failed

### 2. Missing Position
**Issue**: Position exists in Alpaca but NOT locally
**Cause**: Trade executed but local state not updated
**Fix**: Add to local state via reconciliation

### 3. Quantity Mismatch
**Issue**: Different share counts between local and Alpaca
**Cause**: Partial fills, order modifications, or state update failures
**Fix**: Sync to Alpaca's quantity (source of truth)

### 4. Value Mismatch (>1%)
**Issue**: Market value differs by more than 1%
**Cause**: Stale prices, incorrect quantity, or calculation errors
**Fix**: Update local state with Alpaca's current data

## GitHub Actions Integration

### Example Workflow Step

```yaml
- name: Verify Positions Match Alpaca
  id: verify_positions
  env:
    ALPACA_API_KEY: ${{ secrets.ALPACA_API_KEY }}
    ALPACA_SECRET_KEY: ${{ secrets.ALPACA_SECRET_KEY }}
  run: |
    python3 scripts/verify_positions.py

- name: Handle Discrepancies
  if: steps.verify_positions.outputs.positions_match == 'false'
  run: |
    echo "❌ Positions out of sync!"
    echo "Discrepancy count: ${{ steps.verify_positions.outputs.discrepancy_count }}"
    # Auto-fix or alert based on your policy
    # python3 scripts/reconcile_positions.py --fix
    exit 1
```

### Output Variables

The script sets these GitHub Actions outputs:

- `positions_match`: `true` if all positions match, `false` otherwise
- `discrepancy_count`: Number of discrepancies found (or `-1` for errors)

## Best Practices

### 1. Run Verification After Trades
```bash
# Execute trades
python3 scripts/advanced_autonomous_trader.py

# Verify positions synced
python3 scripts/verify_positions.py || {
    echo "❌ Positions out of sync - running reconciliation"
    python3 scripts/reconcile_positions.py --fix
}
```

### 2. Daily Reconciliation Cron
```bash
# Add to crontab
0 17 * * 1-5 cd /path/to/trading && python3 scripts/reconcile_positions.py --fix >> logs/reconciliation.log 2>&1
```

### 3. Pre-Deployment Gate
```yaml
# In CI/CD pipeline
test:
  script:
    - python3 scripts/verify_positions.py
  allow_failure: false  # Block deployment on mismatch
```

## Troubleshooting

### Error: Missing Credentials
```
❌ ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables required
```

**Solution**: Set environment variables or create `.env` file:
```bash
export ALPACA_API_KEY="your_key"
export ALPACA_SECRET_KEY="your_secret"
```

### Error: Local State Not Found
```
❌ ERROR: Local state file not found: /path/to/data/system_state.json
```

**Solution**: Initialize system state:
```bash
python3 scripts/initialize_system_state.py
```

### All Positions Show as Discrepancies
**Cause**: Stale local state or clock skew
**Solution**:
1. Check `data/system_state.json` timestamp
2. Run reconciliation with `--fix` flag
3. Verify system clock is accurate

### Positions Match But Values Differ Slightly
**Cause**: Normal price fluctuations between API calls
**Solution**: This is expected - tolerance is set to 1% to handle this

## Related Documentation

- [Verification Protocols](verification-protocols.md) - Overall verification strategy
- [State Management](state-management.md) - How system state is maintained
- [Trading Execution](trading-execution.md) - Trade execution workflow

## Change Log

| Date | Change |
|------|--------|
| 2025-12-08 | Created `verify_positions.py` for CI/CD integration |
| 2025-12-08 | Enhanced with GitHub Actions output support |
| 2025-12-08 | Added comprehensive test suite |
