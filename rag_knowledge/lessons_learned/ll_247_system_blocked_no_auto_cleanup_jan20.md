# LL-247: System Blocked But No Auto-Cleanup Mechanism

**Date**: 2026-01-20
**Severity**: CRITICAL
**Category**: Risk Management, System Architecture

## Summary

The trading system correctly blocked new trades due to 30% risk exposure (3 spreads when max is 1), but there was NO automated mechanism to close excess positions. Result: **0 trades on Jan 20, 2026** despite market being open.

## The Crisis

```
Portfolio: $4,986.39
Open Positions: 6 (3 spreads)
  - SPY 565/570 put spread
  - SPY 595/600 put spread
  - SPY 653/658 put spread (only compliant one)

Total Risk: $1,500 = 30.1% of portfolio
CLAUDE.md Limits:
  - Max 1 iron condor at a time
  - Max 15% total portfolio risk

Today's P/L: $-2.00 (unrealized)
Trades Executed: 0 (system blocked)
```

## Root Cause

1. **Detection worked**: Trade gateway correctly blocked new trades (LL-246 fix)
2. **Resolution missing**: No automated workflow to CLOSE excess positions
3. **Manual intervention assumed**: System expected human to notice and close positions

This violates Core Directive: "Never tell CEO to do manual work"

## Evidence

From trade_gateway.py logs:
```
CHECK 0.7: MAX_POSITIONS_EXCEEDED - Blocked
CHECK 0.8: TOTAL_PORTFOLIO_RISK_EXCEEDED - Blocked
```

System was in "blocked state" all day - correct behavior, but no recovery path.

## Fix Applied

Created automated position compliance system:

### 1. Emergency Cleanup Script
`scripts/emergency_position_cleanup.py`
- Identifies all spreads in portfolio
- Calculates excess (current - max allowed)
- Closes worst-performing spreads first
- Can be run manually or via workflow

### 2. Manual Trigger Workflow
`.github/workflows/emergency-position-cleanup.yml`
- Dispatch trigger for immediate cleanup
- Includes dry_run option

### 3. Automated Scheduled Workflow (KEY FIX)
`.github/workflows/auto-position-compliance.yml`
- Runs every 30 minutes during market hours
- Automatically detects limit violations
- Closes excess spreads without human intervention
- Triggers state sync after closing

## Architecture Change

```
BEFORE (LL-246):
[Trade Request] → [Gateway Blocks] → [System Stuck] → [Manual Fix Needed]

AFTER (LL-247):
[Trade Request] → [Gateway Blocks] → [Auto-Compliance Detects] → [Auto-Close Excess] → [System Resumes]
```

## Key Lesson

**Detection without resolution creates deadlock.**

If a system can detect a violation, it must also have an automated path to RESOLVE that violation. Otherwise the system becomes stuck in a non-functional state.

## Prevention Rules

1. Every blocking check needs a corresponding unblocking mechanism
2. Automated systems must self-heal, not wait for humans
3. Scheduled compliance checks prevent drift accumulation
4. Close worst-performing positions first (minimize realized losses)

## Related

- LL-246: 30% risk violation discovered (detection)
- LL-247: This lesson (resolution)
- CLAUDE.md: "1 iron condor at a time", "15% max risk"

## Tags

`crisis`, `self-healing`, `automation`, `risk-management`, `phil-town-rule-one`, `critical`
