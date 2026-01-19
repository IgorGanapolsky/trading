# LL-247: Remaining Environment Variable Risks

**Date**: 2026-01-19
**Category**: Security, Adversarial Audit
**Severity**: MEDIUM

## Summary

Adversarial audit identified additional environment variables that could potentially be abused, though with lower risk than LL-245.

## Findings

### 1. ALPACA_SIMULATED (MEDIUM RISK)

```python
# src/execution/alpaca_executor.py:40
self.simulated = os.getenv("ALPACA_SIMULATED", "false").lower() in {"1", "true"}
```

**Risk**: Combined with `SIMULATED_EQUITY=1000000`, could bypass position limits by inflating apparent equity.

**Mitigation**: In simulated mode, orders aren't actually executed. Risk is limited to CI/testing scenarios.

### 2. ACCOUNT_EQUITY Fallback (LOW RISK)

```python
# src/risk/trade_gateway.py:1219
return float(os.getenv("ACCOUNT_EQUITY", "5000"))
```

**Risk**: Only used when executor unavailable. Could inflate equity.

**Mitigation**: Mandatory gate gets equity from Alpaca API directly, not this fallback.

### 3. STOP_LOSS_PCT / TAKE_PROFIT_PCT (LOW RISK)

```python
# src/orchestrator/main.py:281-282
take_profit_pct=float(os.getenv("TAKE_PROFIT_PCT", "0.15"))
stop_loss_pct=float(os.getenv("STOP_LOSS_PCT", "0.08"))
```

**Risk**: Could disable stop losses by setting to extreme values.

**Mitigation**: These affect orchestrator behavior, not mandatory gate. Defaults are reasonable.

## Recommendations

1. **Future Work**: Consider centralizing all risk-related config in constants module
2. **CI Security**: Audit GitHub Actions secrets for unexpected overrides
3. **Monitoring**: Log when env vars override defaults

## Not Fixed (Acceptable Risk)

These are lower priority because:
- Mandatory gate uses real Alpaca API equity
- Simulated mode doesn't execute real trades
- Would require system restart to exploit

## Related

- LL-245: Env var bypass for position limits (FIXED)
- LL-246: Position count not enforced (FIXED)
- LL-244: Adversarial audit findings

## Tags

`security`, `medium`, `env-var`, `audit`, `documentation`
