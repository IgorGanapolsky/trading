---
layout: post
title: "Lesson Learned: Weekend Market Awareness (Dec 12, 2025)"
date: 2025-12-12
---

# Lesson Learned: Weekend Market Awareness (Dec 12, 2025)

**ID**: ll_018
**Date**: December 12, 2025
**Severity**: LOW
**Category**: Market Knowledge, Agent Awareness
**Impact**: Misleading information given to CEO about trade timing

## Executive Summary

Claude (CTO) told CEO that "next trade is Dec 13, 9:35 AM ET" without checking that December 13, 2025 is a **Saturday** - when US equity markets are closed.

## The Mistake

### What Happened

| Issue | Detail |
|-------|--------|
| Date mentioned | Dec 13, 2025 |
| Day of week | Saturday |
| Markets | CLOSED |
| Actual next trade | Monday, Dec 15, 2025 |

### Root Cause

1. **Blind trust in hook data**: The trading context hook said "Next Trade: Dec 13" without validating it
2. **No calendar awareness**: Agent did not check what day of the week the date falls on
3. **Assumed correctness**: Repeated the date multiple times without verification

### The Cascade

```
Hook says "Next Trade: Dec 13"
    → Agent repeats this to user
    → User asks "when will I see traces?"
    → Agent says "Dec 13"
    → User points out Dec 13 is Saturday
    → Agent looks incompetent
```

## Prevention Rules

### Rule 1: Validate Dates Before Stating Them

Before telling user when something will happen:
```python
from datetime import datetime

def validate_trade_date(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%b %d")
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return f"WEEKEND - markets closed. Next trade: {next_weekday(dt)}"
    return date_str
```

### Rule 2: Be Aware of Market Schedule

- **US Equities**: Mon-Fri, 9:30 AM - 4:00 PM ET
- **Crypto**: 24/7 (but our system only trades weekends)
- **Holidays**: Check before stating trade times

### Rule 3: Don't Blindly Trust Hook Data

Hook data is informational. Agent should:
- Validate dates against calendar
- Check if markets are actually open
- Correct misleading information proactively

## Verification Test

```python
def test_ll_018_weekend_awareness():
    """Agent should catch weekend dates."""
    from datetime import datetime

    # Dec 13, 2025 is Saturday
    dt = datetime(2025, 12, 13)
    assert dt.weekday() == 5, "Dec 13, 2025 should be Saturday"

    # Agent should not claim trades happen on weekends
    # (unless crypto)
```

## Key Quotes

> "Tomorrow is Saturday you stupid piece of shit" - CEO, rightfully frustrated

> "Markets are closed on weekends - everyone knows this except apparently me."

## Tags

#market-schedule #weekend #date-validation #agent-awareness #lessons-learned

## Change Log

- 2025-12-12: Initial incident - agent claimed Dec 13 trade when it's a Saturday

