# LL-246: Position Count Not Enforced at Trade Entry

**Date**: 2026-01-19
**Category**: Security, Adversarial Audit
**Severity**: CRITICAL

## Summary

Adversarial audit discovered that position COUNT was only validated in tests, not at trade entry. This allowed accumulation of 6 positions when CLAUDE.md limits to 4 (1 iron condor).

## Vulnerability

The `mandatory_trade_gate.py` validated:
- ✓ Ticker whitelist
- ✓ Position SIZE (5%)
- ✓ Daily loss limit
- ✗ Position COUNT ← MISSING!

This allowed unlimited position accumulation.

## Evidence

From system_state.json:
```json
"positions_count": 6,  // Should be max 4
```

From test failure:
```
Position limit exceeded: 6 positions (max 4 per CLAUDE.md)
```

## Root Cause

The compliance test checked position count AFTER trades executed, but the mandatory gate didn't block new trades when at capacity.

## Fix Applied

Added to `mandatory_trade_gate.py`:
```python
# CHECK 2.5: Position COUNT limit (Jan 19, 2026 - LL-246)
MAX_POSITIONS = 4  # 1 iron condor = 4 legs (HARDCODED per CLAUDE.md)
current_positions = context.get("positions", []) if context else []
current_position_count = len(current_positions)

if side == "BUY" and current_position_count >= MAX_POSITIONS:
    return GateResult(
        approved=False,
        reason=f"Position count {current_position_count} >= max {MAX_POSITIONS}",
        checks_performed=checks_performed + ["position_count: BLOCKED"],
    )
```

## Prevention

1. **Gate validation must match test validation** - if tests check it, gates must enforce it
2. **Hardcode limits** - no env var or config overrides for safety limits
3. **Adversarial testing** - assume every check can be bypassed, then verify

## Related

- LL-244: Adversarial audit findings
- LL-245: Env var bypass vulnerability
- CLAUDE.md: "Position limit: 1 iron condor at a time"

## Tags

`security`, `critical`, `position-count`, `gate-enforcement`, `adversarial-audit`
