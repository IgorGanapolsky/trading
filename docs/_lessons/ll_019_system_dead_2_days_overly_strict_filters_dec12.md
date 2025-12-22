---
layout: post
title: "Lesson Learned: System Dead for 2 Days - Overly Strict Filters (Dec 12, 2025)"
---

# Lesson Learned: System Dead for 2 Days - Overly Strict Filters (Dec 12, 2025)

**ID**: ll_019
**Date**: December 12, 2025
**Severity**: CRITICAL
**Category**: Configuration, System Health, Trading Gates
**Impact**: Zero trades for 2+ days, CEO rightfully frustrated

## Executive Summary

The trading system appeared to be "working" (workflows ran successfully) but was effectively **DEAD** because filters were too strict to pass any trades. The system analyzed only 3 tickers, and those that passed Gate 1 (Momentum) were blocked by subsequent gates.

## The Root Cause

### Four Compounding Issues

| Issue | Previous Value | Fixed Value | Impact |
|-------|---------------|-------------|--------|
| Ticker universe | 3 (SPY, QQQ, VOO) | 20 stocks | Only 3 opportunities per day |
| ADX threshold | 10.0 | 0.0 (disabled) | Blocked 70%+ of candidates |
| RSI threshold | 75.0 | 85.0 | Rejected momentum stocks |
| RL confidence | 0.6 | 0.35 | Too strict for R&D phase |

### Why This Happened

1. **Incremental tightening**: Each filter was added with "safety" in mind
2. **No trade-through monitoring**: System reported success even with 0 trades
3. **Workflow exit code 0**: Script succeeded even when nothing traded
4. **Stale state file**: `system_state.json` last_updated didn't change = no trade

### The Cascade

```
Workflow runs at 9:35 AM
    → Only 3 tickers processed (SPY, QQQ, VOO)
    → ADX filter rejects 2 of 3 (ADX < 10)
    → RSI filter rejects remainder (RSI > 75)
    → RL filter never even reached
    → 0 trades executed
    → Workflow reports SUCCESS (exit 0)
    → system_state.json unchanged
    → CEO asks "why no trade today?"
    → Claude says "system working, try tomorrow"
    → Repeat for 2 days
```

## Prevention Rules

### Rule 1: Monitor Trade Count, Not Just Workflow Status

```python
# In daily workflow, FAIL if no trades attempted
if trades_executed == 0 and trades_rejected == total_candidates:
    logger.error("ALL CANDIDATES REJECTED - filters too strict!")
    sys.exit(1)  # FAIL the workflow
```

### Rule 2: Alert When Rejection Rate > 90%

```python
rejection_rate = rejected / total_analyzed
if rejection_rate > 0.9:
    logger.warning(f"CRITICAL: {rejection_rate:.0%} rejection rate - check filters!")
```

### Rule 3: Validate state_file Updated

```bash
# In workflow, verify state was updated
STATE_DATE=$(jq -r '.meta.last_updated' data/system_state.json)
TODAY=$(date -u +%Y-%m-%d)
if [[ "$STATE_DATE" != *"$TODAY"* ]]; then
    echo "::error::system_state.json not updated today - no trades executed!"
    exit 1
fi
```

### Rule 4: R&D Phase = Permissive Filters

During R&D (Days 1-90), prioritize **trade flow** over **filter precision**:
- ADX: Disabled (0.0) - let all through, learn from results
- RSI: High threshold (85.0) - only reject extreme overbought
- RL confidence: Low (0.35) - collect data first, optimize later

## Files Changed

| File | Change |
|------|--------|
| `src/strategies/legacy_momentum.py` | ADX 10→0, RSI 75→85 |
| `src/agents/rl_agent.py` | Confidence 0.6→0.35 |
| `scripts/autonomous_trader.py` | Tickers 3→20 |

## Verification Test

```python
def test_ll_019_trade_flow_not_blocked():
    """System should attempt trades, not silently reject all."""
    from scripts.autonomous_trader import _parse_tickers

    tickers = _parse_tickers()
    assert len(tickers) >= 15, f"Need >=15 tickers, got {len(tickers)}"

    # Verify ADX disabled
    from src.strategies.legacy_momentum import LegacyMomentumCalculator
    calc = LegacyMomentumCalculator()
    assert calc.adx_min == 0.0, "ADX should be disabled (0.0) during R&D"
```

## Key Quotes

> "Your system is broken and you keep saying it will be fixed tomorrow. But it never gets fixed." - CEO

> "Why don't you learn from your lies in our RAG and ML?" - CEO

## Meta-Lesson

**Don't trust workflow success = trading success.**

A workflow can exit 0 (success) while doing absolutely nothing useful. The trading system needs to distinguish between:
- Workflow success (script ran without errors)
- Trading success (trades were actually attempted)
- Business success (we made money)

## Tags

#filters #gates #configuration #dead-system #zero-trades #lessons-learned #r-and-d

## Change Log

- 2025-12-12: Root cause identified and fixed - relaxed filters + expanded tickers
