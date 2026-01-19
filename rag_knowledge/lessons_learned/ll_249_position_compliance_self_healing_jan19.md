# LL-249: Position Compliance Self-Healing Mechanism

**Date**: 2026-01-19
**Category**: Resilience, Self-Healing
**Severity**: HIGH (Improvement)

## Summary

Created automated self-healing mechanism to detect and queue remediation for position limit violations. System now automatically identifies compliance issues and creates action plans for market open.

## Problem

Position violations could accumulate without automated detection or remediation:
- 6 positions (max 4)
- $570 position (max $249)
- Required manual intervention to identify and fix

## Solution

Created `scripts/position_compliance_heal.py` that:

1. **Detects violations**:
   - Position count > MAX_POSITIONS (4)
   - Position value > 5% of equity

2. **Creates remediation plan**:
   - REDUCE: Close 1 contract to bring under size limit
   - CLOSE: Close smallest positions to bring under count limit
   - REVIEW: Flag critical issues that need manual review

3. **Queues actions**:
   - Saves to `system_state.json -> remediation_queue`
   - Workflow executes on market open

## Remediation Queue Example

```json
{
  "created_at": "2026-01-19T20:15:37",
  "reason": "Position compliance self-healing",
  "actions": [
    {"action": "REDUCE", "symbol": "SPY260220P00653000", "priority": "HIGH"},
    {"action": "CLOSE", "symbol": "SPY260220P00565000", "priority": "MEDIUM"}
  ],
  "status": "PENDING"
}
```

## Integration

The script should be called:
1. Pre-market health check (daily-trading workflow)
2. After any trade execution
3. Manual invocation when needed

## Benefits

- **Automated detection**: No manual monitoring required
- **Proactive remediation**: Issues fixed before they compound
- **Audit trail**: All actions logged to system_state.json
- **Phil Town Rule #1**: Automatically protects capital

## Related

- LL-246: Position count not enforced at entry (prevention)
- LL-245: Env var bypass vulnerability (prevention)
- CLAUDE.md: 5% position limit, 4 position max

## Tags

`resilience`, `self-healing`, `position-limits`, `automation`
