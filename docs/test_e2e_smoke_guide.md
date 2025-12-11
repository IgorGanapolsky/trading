# End-to-End Smoke Tests - Implementation Guide

## Overview

After the **Dec 11, 2025 incident** where a syntax error was merged to main and caused **0 trades to execute** for an entire trading day, I created comprehensive end-to-end smoke tests to prevent this from happening again.

**Location**: `/home/user/trading/tests/test_e2e_smoke.py`

## Purpose

These tests verify that the trading funnel actually produces trade requests when given valid buy signals. They ensure that gates don't accidentally block all trades.

## Test Coverage

### 1. `test_funnel_produces_trade_with_buy_signal`
**CRITICAL TEST**: Verifies the trading funnel produces at least one trade when:
- Momentum agent returns a BUY signal
- Gates are disabled (simplification mode)
- Paper trading is enabled

**Assertions**:
- `TradeGateway.execute()` is called at least once
- `TradeGateway.evaluate()` is called (trade reaches gateway)
- No exceptions occur during execution

**Failure Modes**:
- If this test fails, it means gates are silently blocking all trades
- This would prevent the system from executing any trades in production

### 2. `test_funnel_respects_sell_signal`
Verifies Gate 1 (Momentum) correctly rejects SELL signals:
- Momentum agent returns a SELL signal
- `TradeGateway.execute()` should NOT be called
- Confirms momentum filter is working properly

### 3. `test_gates_disabled_allows_passthrough`
Verifies that with ALL gates disabled (simplification mode), BUY signals flow through:
- `RL_FILTER_ENABLED=false`
- `LLM_SENTIMENT_ENABLED=false`
- This is the MINIMUM requirement - system must execute trades with gates off

### 4. `test_no_silent_rejection`
Verifies that rejected trades are logged (not silent):
- Gateway rejects a trade (e.g., minimum batch not met)
- Logs must contain rejection keywords: "reject", "blocked", "skip", "warning"
- Silent rejections make debugging impossible

### 5. `test_orchestrator_runs_without_exceptions`
Basic smoke test - verifies orchestrator.run() completes without crashing

### 6. `test_real_alpaca_integration_smoke` (integration test)
**Requires**: `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` environment variables
- Tests full system with real Alpaca API (paper trading)
- Skipped if credentials not available
- Verifies end-to-end flow with real APIs

## How the Tests Work

### Mocking Strategy

The tests mock key components to create a deterministic environment:

```python
# Mock Alpaca Executor
mock_executor.account_equity = 100000.0
mock_executor.get_positions.return_value = []
mock_executor.place_order.return_value = {"id": "mock-order-123", "status": "filled"}

# Mock Momentum Agent (deterministic BUY signal)
MomentumSignal(
    is_buy=True,
    strength=0.75,
    indicators={"rsi": 55.0, "macd": 0.5, "volume_ratio": 1.2, ...}
)

# Mock Macro Agent (bullish context)
{"state": "DOVISH", "reason": "Fed signaling rate cuts", "confidence": 0.8}

# Mock TradeGateway (track calls)
mock_gateway.evaluate.return_value = MagicMock(approved=True)
mock_gateway.execute.return_value = {"id": "test-order-1", "status": "filled"}
```

### Verification Points

Each test verifies critical points in the trading funnel:

1. **Momentum Gate (Gate 1)**: BUY vs SELL signal filtering
2. **RL Filter (Gate 2)**: Disabled in simplification mode
3. **LLM Sentiment (Gate 3)**: Disabled in simplification mode
4. **Risk Gateway (Gate 4)**: `TradeGateway.evaluate()` called
5. **Execution**: `TradeGateway.execute()` called with approved trades

## Running the Tests

### Prerequisites

Install required dependencies:
```bash
pip install -r requirements-minimal.txt
pip install pytest pytest-mock pandas
```

### Run All Smoke Tests

```bash
# All tests
python3 -m pytest tests/test_e2e_smoke.py -v

# Single test
python3 -m pytest tests/test_e2e_smoke.py::test_funnel_produces_trade_with_buy_signal -v

# With detailed output
python3 -m pytest tests/test_e2e_smoke.py -v -s

# With coverage
python3 -m pytest tests/test_e2e_smoke.py --cov=src.orchestrator --cov-report=html
```

### Environment Variables

Tests automatically set:
```bash
PAPER_TRADING=true
RL_FILTER_ENABLED=false
LLM_SENTIMENT_ENABLED=false
DAILY_INVESTMENT=10
ENABLE_MENTAL_COACHING=false
ENABLE_BULL_BEAR_DEBATE=false
ENABLE_RAG_CONTEXT=false
ENABLE_INTROSPECTION=false
```

## Integration with Pre-Merge Gate

These tests should be run by the pre-merge gate:

**File**: `scripts/pre_merge_gate.py`

```python
def run_smoke_tests():
    """Run end-to-end smoke tests before allowing merge."""
    result = subprocess.run(
        ["python3", "-m", "pytest", "tests/test_e2e_smoke.py", "-v"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("❌ SMOKE TESTS FAILED - BLOCKING MERGE")
        print(result.stdout)
        print(result.stderr)
        return False

    print("✅ Smoke tests passed")
    return True
```

## What the Tests Prevent

### Dec 11, 2025 Incident Prevention

The tests specifically prevent:
1. **Syntax errors in critical paths** (would cause import failures)
2. **Silent gate rejections** (trades blocked without logging)
3. **Broken trading funnel** (BUY signals not reaching execution)
4. **Gateway misconfiguration** (trades never hitting execute())
5. **Exception-throwing code** (system crashes during run)

### Real-World Scenarios

**Scenario 1**: Developer adds new gate that accidentally rejects everything
- `test_funnel_produces_trade_with_buy_signal` fails
- Pre-merge gate blocks the PR
- CEO never sees 0 trades executed

**Scenario 2**: Developer changes risk calculation, breaks gateway
- `test_gates_disabled_allows_passthrough` fails
- Tests show gateway never approves trades
- Issue caught before merge

**Scenario 3**: Developer adds silent return statement in critical path
- `test_no_silent_rejection` fails
- Tests detect lack of logging
- Debugging remains possible

## Test Maintenance

### When to Update Tests

1. **New gate added**: Add test case for the gate
2. **Gate logic changed**: Update mock to reflect new behavior
3. **New rejection reason**: Add test case for rejection logging
4. **Orchestrator refactored**: Update mocks to match new structure

### Common Issues

**Import Errors**:
- Mock additional dependencies in `sys.modules` at top of file
- Example: `sys.modules['new_dependency'] = MagicMock()`

**Flaky Tests**:
- Tests should be fully deterministic (all mocks, no real APIs)
- If flaky, add more explicit assertions
- Check for async code that needs proper mocking

**Test Too Slow**:
- All tests should complete in <1 second
- If slow, check for real API calls sneaking through mocks
- Disable optional features in test environment

## Success Metrics

When tests are working correctly:
- ✅ All 6 tests pass in <5 seconds
- ✅ No real API calls made (all mocked)
- ✅ Coverage of critical trading funnel paths
- ✅ Clear failure messages when something breaks
- ✅ Pre-merge gate blocks broken code

## Lessons Learned from Dec 11, 2025

**What Went Wrong**:
- Syntax error merged to main
- CI passed (didn't catch runtime import error)
- 0 trades executed for entire day
- No smoke tests to verify basic functionality

**What These Tests Fix**:
- Import errors caught during test collection
- Trading funnel verified to produce trades
- Gate configuration validated
- Execution path verified end-to-end

**Prevention Strategy**:
1. Run smoke tests in pre-merge gate
2. Verify critical import succeeds: `python3 -c "from src.orchestrator.main import TradingOrchestrator"`
3. Check for silent rejections in logs
4. Validate at least one mock trade executes

## Related Documentation

- **Pre-Merge Checklist**: `/home/user/trading/.claude/CLAUDE.md` (search for "PRE-MERGE CHECKLIST")
- **CI Workflow**: `.github/workflows/ci.yml`
- **Lessons Learned**: `rag_knowledge/lessons_learned/ll_009_ci_syntax_failure_dec11.md`

## Future Enhancements

Potential improvements:
1. **Property-based tests**: Use Hypothesis to generate random signals
2. **Snapshot tests**: Capture and compare full trading sessions
3. **Performance benchmarks**: Verify orchestrator.run() completes in <30s
4. **Integration tests**: Test with real paper trading API (nightly runs)
5. **Chaos engineering**: Inject random failures to verify error handling

---

**Last Updated**: December 11, 2025
**Author**: Claude (AI CTO)
**Status**: Active, critical for preventing production incidents
