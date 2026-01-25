# LL-302: Iron Condor Adjustment Strategies When Tested

**Date**: January 25, 2026
**Category**: Strategy, Position Management
**Severity**: HIGH (affects win rate and loss management)
**Status**: Research Complete

## Executive Summary

When an iron condor is tested (one side approaches short strike), the correct response is to roll the UNTESTED side closer, NOT the tested side. This brings in extra credit and widens breakeven points.

## Key Principle: Don't Touch the Tested Side

> "Leave the challenged side alone - do not touch it or roll it. Rolling guarantees a loss plus creates compounding risk if the market continues against you."

**Instead:** Move the UNTESTED side closer to current price to collect additional credit.

## When to Adjust (Delta Thresholds)

| Short Strike Delta | Action |
|-------------------|--------|
| < 25 | No action needed |
| 25-30 | Monitor closely |
| 30-35 | **Adjust NOW** |
| > 35 | Urgent - adjust immediately |

**Rule:** Adjust when short delta reaches 30, definitely by 35.

## Adjustment Methods

### Method 1: Roll Untested Side Closer (Recommended)

**Scenario:** SPY drops, PUT side threatened (delta increasing)

**Action:**
1. Leave PUT spread alone
2. Roll CALL spread closer to current price
3. Collect extra credit

**Example:**
- Original iron condor: 580P/575P - 620C/625C
- SPY drops to 590 (PUT spread tested)
- Roll CALLs: Close 620C/625C, Open 600C/605C
- Extra credit collected widens breakeven

**Benefits:**
- Brings in more credit
- Widens breakeven points
- Reduces max risk
- Doesn't lock in loss on tested side

**Risk:**
- If market reverses sharply, new side may be tested
- Position profit zone narrows

### Method 2: Convert to Iron Butterfly

**When to use:** Strong conviction market will stabilize at current level

**Action:** Roll untested side so both shorts share same strike

**Example:**
- CALLs tested, SPY at 615
- Roll PUTs up so short put = short call = 615
- Creates iron butterfly centered at current price

**Trade-off:** Much narrower profit zone but highest credit

### Method 3: Close at Loss (Know When to Fold)

**When to close without adjusting:**
- Short delta > 50 (too late to adjust)
- Price through short strike
- < 7 DTE (insufficient time for adjustment to work)
- Multiple adjustments already made

## Our Current Strategy Integration

Current rules from CLAUDE.md:
- Stop-loss at 200% of credit - MANDATORY
- Exit at 7 DTE to avoid gamma risk

**Enhancement (from this research):**
```
1. Monitor short strike delta daily
2. If delta reaches 30: Roll untested side closer
3. If delta reaches 50: Close position (stop-loss likely triggered anyway)
4. Max 1 adjustment per iron condor
5. Never roll the tested side
```

## Adjustment Decision Tree

```
Short Strike Delta Increasing?
         |
    < 25 delta ──> Do nothing, monitor
         |
   25-30 delta ──> Prepare to adjust
         |
   30-35 delta ──> ADJUST: Roll untested side closer
         |
    > 35 delta ──> Adjust URGENTLY
         |
    > 50 delta ──> CLOSE POSITION (cut loss)
         |
   Price through strike ──> CLOSE (stop-loss triggered)
```

## Time Considerations

| DTE | Delta at 35 | Action |
|-----|-------------|--------|
| 30+ | Acceptable | Adjust and continue |
| 14-30 | Caution | Adjust carefully |
| 7-14 | Urgent | Close at 50% profit or cut loss |
| < 7 | Too late | Close position regardless |

## Code Implementation Suggestion

```python
def should_adjust_iron_condor(position: dict) -> tuple[bool, str]:
    """Check if iron condor needs adjustment."""
    put_delta = abs(position.get('short_put_delta', 0))
    call_delta = abs(position.get('short_call_delta', 0))
    dte = position.get('dte', 30)

    max_delta = max(put_delta, call_delta)

    if max_delta > 50:
        return True, "CLOSE: Delta too high, cut loss"
    if max_delta > 35 and dte < 14:
        return True, "CLOSE: High delta with low DTE"
    if max_delta >= 30:
        tested_side = "PUT" if put_delta > call_delta else "CALL"
        return True, f"ADJUST: Roll untested side ({opposite(tested_side)})"
    return False, "No adjustment needed"
```

## Sources

- [Options Trading IQ - Iron Condor Adjustments](https://optionstradingiq.com/adjusting-iron-condors/)
- [Option Alpha - Iron Condor Adjustments](https://optionalpha.com/lessons/iron-condor-adjustments)
- [QuantStrategy - Iron Condor Strategy](https://quantstrategy.io/blog/how-to-build-and-adjust-the-iron-condor-strategy-for/)
- [Data Driven Options - Rolling Iron Condors](https://datadrivenoptions.com/rolling-iron-condors/)
- [Steady Options - Iron Condor Adjustment](https://steadyoptions.com/articles/iron-condor-adjustment/)

## Tags
iron_condor, adjustment, rolling, position_management, delta, risk_management

---

*Researched January 25, 2026. Key insight: Roll the untested side, never the tested side.*
