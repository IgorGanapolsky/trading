# LL-315: CI Halt State Test Isolation

**ID**: LL-315
**Date**: 2026-06-17
**Severity**: HIGH
**Category**: ci, testing, risk-gates, ml-feedback
**Status**: RESOLVED
**Related PR**: #4134
**Merge Commit**: 75cb586d328a05a9981dc86e3f360a4b10639b5c

## Incident Summary

`main` CI failed after an automated reconciliation commit because checked-in production halt state leaked into unit tests. `TradeGateway.evaluate()` read `data/TRADING_HALTED` directly, so tests that expected downstream rejection reasons were short-circuited by the global circuit breaker.

Affected tests included:

- `tests/test_trade_gateway.py`
- `tests/test_rule_one_validator.py`
- `tests/test_ml_feedback_loop.py`

## Root Cause

Production safety state was hard-coded inside `TradeGateway.evaluate()` as `Path("data/TRADING_HALTED")`. Tests had no clean way to isolate that state, so the repo-level halt file changed behavior for otherwise deterministic unit tests.

The ML feedback-loop fixtures also missed `total_realized_pnl`, while the production expectancy path uses broker-truth realized P/L. That made synthetic good-performance fixtures fail the profitability gate.

## Fix

PR #4134 made halt state injectable and patched it in tests:

1. Added `TradeGateway.TRADING_HALTED_FILE`.
2. Patched that class attribute in `tests/conftest.py` to a per-test `tmp_path`.
3. Added `total_realized_pnl` to the synthetic good-performance ML fixtures.

## Verification

Local targeted suite after rebase:

```text
pytest tests/test_trade_gateway.py tests/test_rule_one_validator.py tests/test_ml_feedback_loop.py -q
66 passed in 0.78s
```

Pre-push validation:

```text
200 unit tests passed
Smoke tests passed
Workflow contracts passed
ALL PRE-PUSH CHECKS PASSED
```

GitHub PR CI on head `93ddf74b7e6739bcdf7073af88539d9ba6b57713`:

```text
Detect Changed Paths: pass
Validate Workflows: pass
Run All Tests: pass in 18m48s
```

Post-merge `main` CI on `75cb586d328a05a9981dc86e3f360a4b10639b5c`:

```text
CI: success
CodeQL: success
SonarCloud: success
OpenSSF Scorecard: success
no-direct-submit-order: success
```

## Prevention Rules

1. Production safety files must be injectable or fixture-patched before unit tests exercise risk gates.
2. Unit tests must not read live repo state such as `data/TRADING_HALTED` unless the test explicitly validates that state.
3. Broker-truth ML fixtures must include the same fields production metrics consume, especially `total_realized_pnl`.
4. When `main` moves during PR repair, rebase onto the latest green `origin/main` before trusting PR CI.
5. Do not mark PR hygiene complete until post-merge `main` CI passes on the merge commit.

