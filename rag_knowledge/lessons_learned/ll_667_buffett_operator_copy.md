# LL-667 — Put-credit operator copy must follow the live Buffett profile

**Date:** 2026-09-19
**Severity:** 4
**Issue:** AGENT-667
**Evidence:** After AGENT-664/665, `mandatory_trade_gate._protocol_reasoning_for_strategy("spy_put_credit")` still said 30-45 DTE / TP 25% / exit 7 DTE. `freedom_builder_ops.behind_the_scenes_decisions` hold why still said `TP 25% / stop 200% credit / 7 DTE`. `tests/test_mandatory_trade_gate.py` required `"7 dte"` in that protocol text.

## Mistake

Updating scorecard `RISK_FRAMEWORK` and the manage-exits counterfactual note while leaving other operator-facing sentences hardcoded to the killed `spy-put-credit` lab. A unit test then locked the stale 7 DTE copy in.

Live default is `spy-put-credit-buffett`: 45-70 DTE (target 60), TP 50%, stop 200%, exit_dte=30.

## Fix

Derive protocol reasoning from `get_put_credit_profile()` and hold-why from `risk_framework()`. Tests must assert live TP/exit_dte and forbid `take profit 25%` / `7 DTE` in put-credit operator copy.

Public 21-DTE / TP-25% counterfactuals stay comparison-only (`attach_counterfactuals`); they are not the live manager.

## Verify

`pytest tests/test_mandatory_trade_gate.py tests/test_freedom_builder_ops.py tests/test_put_credit_milestones.py`
