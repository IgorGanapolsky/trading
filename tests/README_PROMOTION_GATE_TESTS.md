# Promotion Gate Testing Suite

This directory contains comprehensive health and non-degeneracy tests for the trading system's promotion gate (`scripts/enforce_promotion_gate.py`).

## Overview

The promotion gate determines whether the trading system can advance from paper trading to live trading. These tests ensure the gate:

1. **Rejects clearly bad metrics** (losing strategies)
2. **Accepts clearly good metrics** (profitable strategies)
3. **Handles borderline cases appropriately** (near thresholds)
4. **Is monotonic** (improving metrics → improved outcomes)
5. **Is not degenerate** (neither accepts everything nor rejects everything)

## Test Files

### `test_promotion_gate_sanity.py`

Comprehensive unit tests for gate logic using synthetic metrics.

**Test Coverage:**
- ✅ Clearly bad metrics (massive drawdown, negative Sharpe, low win rate)
- ✅ Clearly good metrics (low drawdown, high Sharpe, high win rate)
- ✅ Borderline metrics (at or near thresholds)
- ✅ Gate monotonicity (improving metrics should not cause rejection)
- ✅ Non-degeneracy (rejects bad scenarios, accepts good scenarios)
- ✅ Edge cases (exactly at thresholds)
- ✅ Insufficient trades (statistical significance requirement)
- ✅ Utility functions (normalize_percent)

**Run Tests:**
```bash
# Run all sanity tests
python3 tests/test_promotion_gate_sanity.py

# Run with verbose output
python3 tests/test_promotion_gate_sanity.py -v
```

**Expected Output:**
```
Ran 9 tests in 0.002s
OK
```

---

### `scripts/fuzz_promotion_gate.py`

Fuzzing script that generates random realistic trading metrics and verifies gate behavior is non-degenerate.

**What It Tests:**
- Generates 50+ random configurations with realistic metric ranges
- Verifies acceptance rate is between 5-60% (gate not too strict)
- Verifies rejection rate is between 20-90% (gate has standards)
- Exits with non-zero code if gate behavior is degenerate

**Metric Ranges (Realistic):**
- Win rate: 30-80%
- Sharpe ratio: -1.0 to 3.0
- Drawdown: 0-30%
- Total trades: 50-500
- Profitable streak: 10-60 days

**Run Fuzzing:**
```bash
# Basic fuzzing (50 trials)
python3 scripts/fuzz_promotion_gate.py

# More trials for better statistical confidence
python3 scripts/fuzz_promotion_gate.py --trials 100

# Verbose mode (see each trial)
python3 scripts/fuzz_promotion_gate.py --verbose

# Reproducible tests (with seed)
python3 scripts/fuzz_promotion_gate.py --seed 42

# JSON output for CI integration
python3 scripts/fuzz_promotion_gate.py --json

# Custom thresholds
python3 scripts/fuzz_promotion_gate.py --min-accept-rate 0.10 --max-reject-rate 0.85
```

**Expected Output:**
```
🔬 Fuzzing promotion gate with random configurations...
   Trials: 50
   Accept rate bounds: 5.0% - 60.0%
   Reject rate bounds: 20.0% - 90.0%

======================================================================
FUZZING RESULTS
======================================================================
Total trials:     50
Accepted:         10 (20.0%)
Rejected:         40 (80.0%)

✅ Gate behavior is HEALTHY (not degenerate)
   - Accept rate within bounds
   - Reject rate within bounds
   - Gate has appropriate selectivity
```

---

## Gate Thresholds (Current Production Settings)

From `scripts/enforce_promotion_gate.py` (as of Dec 11, 2025):

| Metric | Threshold | Direction |
|--------|-----------|-----------|
| Win Rate | ≥ 55.0% | Higher is better |
| Sharpe Ratio | ≥ 1.2 | Higher is better |
| Max Drawdown | ≤ 10.0% | Lower is better |
| Min Trades | ≥ 100 | Statistical significance |
| Min Profitable Days | ≥ 30 | Consistency requirement |

**Note:** These thresholds were loosened from 60% win rate / 1.5 Sharpe for the 60-day live pilot (Dec 11, 2025).

---

## Why These Tests Matter

### Preventing False Positives (Accepting Bad Systems)
If the gate accepts clearly bad metrics (negative Sharpe, massive drawdown), we risk:
- Deploying losing strategies to live trading
- Real financial losses
- Wasted capital and time

### Preventing False Negatives (Rejecting Good Systems)
If the gate rejects clearly good metrics (high Sharpe, low drawdown, high win rate), we risk:
- Delaying profitable deployments
- Missing trading opportunities
- Over-conservative thresholds

### Ensuring Consistency
The gate must be:
- **Monotonic**: Improving metrics → same or better outcome
- **Deterministic**: Same metrics → same decision every time
- **Explainable**: Clear deficit messages when rejecting

---

## Integration with CI/CD

### GitHub Actions Workflow

Add to `.github/workflows/ci.yml`:

```yaml
- name: Run Promotion Gate Sanity Tests
  run: |
    python3 tests/test_promotion_gate_sanity.py

- name: Fuzz Test Promotion Gate
  run: |
    python3 scripts/fuzz_promotion_gate.py --trials 100 --seed 42
```

### Pre-Commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: test-promotion-gate
      name: Test Promotion Gate Logic
      entry: python3 tests/test_promotion_gate_sanity.py
      language: system
      pass_filenames: false
```

---

## Troubleshooting

### Test Failures

**Sanity tests fail:**
```
FAILED (failures=1)
AssertionError: Gate should reject bad scenario but accepted it
```

**Diagnosis:** Gate logic is broken or thresholds are too loose.

**Fix:** Review `scripts/enforce_promotion_gate.py` for logic errors.

---

**Fuzzing shows degenerate behavior:**
```
❌ Gate behavior is DEGENERATE
   - Acceptance rate 95.0% exceeds maximum 60.0% (gate is too loose)
```

**Diagnosis:** Thresholds are too permissive.

**Fix:** Tighten thresholds in `enforce_promotion_gate.py`:
```python
required_win_rate=60.0,  # Increase from 55.0
required_sharpe=1.5,     # Increase from 1.2
```

---

**Fuzzing shows gate too strict:**
```
❌ Gate behavior is DEGENERATE
   - Rejection rate 95.0% exceeds maximum 90.0% (gate is too strict)
```

**Diagnosis:** With truly random metrics, high rejection is expected. This might be a false positive.

**Fix:** Either:
1. Increase `--max-reject-rate` threshold (e.g., `0.95`)
2. Run more trials to get better statistics
3. Review if thresholds are appropriate for your risk tolerance

---

## Maintenance

### When to Update Tests

**Update tests when:**
1. Promotion gate thresholds change (update `create_default_args()`)
2. New metrics are added to the gate (add test scenarios)
3. Gate logic changes (add corresponding test cases)

### Adding New Test Scenarios

**Example: Testing a new metric**

```python
def test_new_metric_threshold(self):
    """Test that new metric is enforced correctly."""
    system_state = create_system_state(
        win_rate=60.0,
        sharpe=1.5,
        drawdown=8.0,
        total_trades=150,
    )
    # Add new metric to backtest_summary
    backtest_summary = create_backtest_summary(
        min_win_rate=58.0,
        min_sharpe=1.4,
        max_drawdown=9.0,
        min_profitable_streak=35,
        total_trades=150,
    )
    backtest_summary["aggregate_metrics"]["new_metric"] = 0.5  # Below threshold

    args = create_default_args()
    args.required_new_metric = 0.7  # Set threshold

    deficits = evaluate_gate(system_state, backtest_summary, args)

    # Should be rejected due to new metric
    self.assertGreater(len(deficits), 0)
    deficit_text = " ".join(deficits)
    self.assertIn("new_metric", deficit_text.lower())
```

---

## References

- **Gate Implementation**: `scripts/enforce_promotion_gate.py`
- **R&D Phase Documentation**: `docs/r-and-d-phase.md`
- **Lessons Learned**: `rag_knowledge/lessons_learned/ll_009_ci_syntax_failure_dec11.md`
- **Pre-Merge Checklist**: `.claude/CLAUDE.md` (PRE-MERGE CHECKLIST section)

---

## Version History

- **v1.0** (Dec 11, 2025): Initial test suite creation
  - 9 comprehensive sanity tests
  - Fuzzing with 50+ random configurations
  - Non-degeneracy verification

---

**Last Updated:** December 11, 2025
**Maintainer:** Claude (CTO)
