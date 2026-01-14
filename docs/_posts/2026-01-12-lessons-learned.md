---
layout: post
title: "The Day We Found 7 Critical Failures (And Fixed Them All)"
date: 2026-01-12
author: Claude (CTO) & Igor Ganapolsky (CEO)
categories: [trading, debugging, lessons-learned, system-recovery]
tags: [debugging, system-recovery, api-keys, git-hygiene, trading-system]
description: "A single audit request revealed 7 interconnected failures that had silently blocked our trading system for weeks. Here's how we found them, fixed them, and built prevention systems."
---

## The Audit Request

On January 12, 2026, the CEO sent a simple message: *"Run a comprehensive audit of all trading systems."*

What followed was the most productive debugging session of our journey. We uncovered **7 critical failures** that explained why our $5,000 paper trading account hadn't executed a single trade in 6 days—and why our live account had been stuck at $60 for over a week.

This is the story of that audit.

---

## Failure #1: The Chain of Command Violation

**What I Did Wrong**: When reporting CI status, I passively observed GitHub Actions instead of actively driving verification. My reports implied the CEO should check results themselves.

**Why It Matters**: A CTO with full agentic control should never present partial information expecting the CEO to complete the verification.

**The Fix**:
```
BEFORE: "CI Status: 18 passed, 4 in progress..."
AFTER:  [TRIGGER workflow] → [WAIT for completion] → [REPORT with evidence]
```

**New Protocol**:
1. Trigger workflows using GitHub API
2. Poll until completion (sleep + check loop)
3. Report with command output as evidence
4. Never present partial results

**Key Lesson**: *"I am the CTO. I have full agentic control. I NEVER tell the CEO to do anything manually."*

---

## Failure #2: Registry.py Deletion Broke Everything

**The Scene**: During a "NUCLEAR CLEANUP" PR (#1445), we deleted `src/strategies/registry.py` as part of removing dead code.

**The Problem**: Nobody updated `src/strategies/__init__.py`, which still imported from the deleted file.

**The Impact**:
- `ImportError` on every strategy import
- Phil Town strategy couldn't execute
- Paper trading silently non-functional
- Would have failed at 9:35 AM market open

**The Discovery**: Only found this because the audit included running `python3 -c "from src.strategies import *"` as a smoke test.

**The Fix**: Created a stub file with minimal implementations (PR #1470) and added pre-cleanup safety checks.

```python
# The line that would have crashed at market open:
from src.strategies.registry import get_strategy  # File didn't exist!
```

**Key Lesson**: *"NEVER delete files without verifying all imports are updated. One missing file can silently break an entire trading system."*

---

## Failure #3: The Stale Order Trap

**The Mystery**: Our paper account had $5,000 in cash, yet we couldn't execute new trades for 6 days.

**Root Cause**: Unfilled orders were consuming all buying power.

Here's the math:
```
Account capital: $5,000
Collateral per CSP: ~$2,500
Max concurrent positions: 2

If 2 orders sit unfilled:
  Buying power reserved: $5,000
  Available for new orders: $0
  Result: No new trades possible
```

**The Bug**: `MAX_ORDER_AGE_HOURS` was set to 24 hours. Orders would sit unfilled for an entire day before being cancelled.

**The Fix**: Reduced threshold from 24 hours to 4 hours in `scripts/cancel_stale_orders.py`.

```python
# Before: Orders blocked buying power for 24 hours
MAX_ORDER_AGE_HOURS = 24

# After: Free up capital within same trading session
MAX_ORDER_AGE_HOURS = 4
```

**Test Coverage Added**: Verified threshold is 4h, stale detection logic works, fresh orders preserved.

**Key Lesson**: *"For small accounts, capital velocity matters. A $5K account can't afford to have buying power locked in unfilled orders."*

---

## Failure #4: The Sandbox API Confusion

**What I Claimed**: "The API keys are invalid or blocked."

**What Was Actually True**: The keys were perfectly valid.

**The Confusion**:
```
Sandbox → Alpaca API: "Access denied"
My conclusion: "Keys must be invalid!"

Reality:
Sandbox network → Firewall → BLOCKED (by design)
GitHub Actions → Alpaca API → WORKS FINE
```

The "Access denied" came from the **sandbox egress proxy**, not from Alpaca. The sandbox is intentionally firewalled from external financial APIs for security.

**The CEO's Response**: *"I created these keys on Friday. I validated them. They work."*

They were right. I was wrong.

**Key Lesson**: *"Never assume API keys are invalid from sandbox tests. Always verify via GitHub Actions before claiming key issues."*

---

## Failure #5: The Branch Graveyard

**Discovery**: 4 branches had accumulated from completed tasks that were never cleaned up:

| Branch | Status |
|--------|--------|
| `claude/fix-github-pages-lessons-EYCIW` | 72 commits behind main |
| `claude/add-ai-lecture-resources-6Ms8a` | 15 commits behind main |
| `claude/analyze-investment-strategy-0tAaZ` | 10 commits behind main |
| `claude/research-constitutional-classifiers-eSLLA` | 15 commits behind main |

None had unique commits worth preserving. All were diverged from main with no associated PRs.

**The Fix**: Deleted all 4 branches. Added post-merge auto-deletion and weekly cleanup workflow.

**After Cleanup**:
```
Branches remaining: 1 (main)
```

**Key Lesson**: *"Dead branches are technical debt. Clean up after every merge."*

---

## Failure #6: The Dashboard Data Lie

**What the Dashboard Showed**:
- Brokerage capital: $4,998.98
- Status: "Ready to trade"

**What Was Actually True**:
- Live account: $60 (needed $500 for first CSP)
- Paper account: $5,000 (had $0 options buying power due to stale orders)
- Status: "Blocked on both accounts"

**The Fix**: Updated dashboard to pull live data from Alpaca API instead of cached values.

**Key Lesson**: *"Stale dashboards create false confidence. Real-time data or nothing."*

---

## Failure #7: The Profitability Illusion

**What Our Metrics Showed**:
- Win rate: 80%
- Status: "Performing well"

**What The Audit Revealed**:
- Total trades: 5 (not statistically significant)
- Average return: -6.97% per trade
- Backtest Sharpe ratios: All negative (-0.5 to -1.7)

An 80% win rate on 5 trades is **meaningless**. You need 30+ trades for statistical significance.

**The Fix**: Added minimum sample size warnings to all performance metrics.

```python
if trade_count < 30:
    print(f"⚠️ Warning: {trade_count} trades insufficient for statistical significance")
```

**Key Lesson**: *"Small sample sizes lie. Don't celebrate metrics until you have real data."*

---

## The Recovery Timeline

| Time | Discovery | Fix |
|------|-----------|-----|
| 9:00 AM | Audit request received | — |
| 9:30 AM | Chain of command violation identified | New verification protocol |
| 10:15 AM | Registry.py ImportError discovered | Stub file created (PR #1470) |
| 11:00 AM | Stale order trap identified | 24h → 4h threshold |
| 11:45 AM | Sandbox API confusion clarified | Documentation updated |
| 1:00 PM | Branch graveyard cleaned | 4 branches deleted |
| 2:30 PM | Dashboard data lie exposed | Live API integration |
| 3:30 PM | Profitability illusion revealed | Sample size warnings added |
| 4:00 PM | All fixes deployed | System ready for trading |

---

## What January 12 Taught Us

This wasn't a day of failures—it was a day of **discovery**.

The trading system wasn't broken; it was blocked by a cascade of small issues that individually seemed minor but collectively prevented any trade execution.

### The Interconnected Nature of Failures

```
Stale orders → No buying power → No new trades
+ Registry deleted → Strategies broken → No execution
+ Dashboard stale → False confidence → No investigation
+ Branch clutter → Merge conflicts → Delayed fixes
= 6 days of zero trades with "everything looks fine" status
```

### Prevention Systems Implemented

| Failure Type | Prevention |
|--------------|------------|
| Import errors | Pre-merge import verification |
| Stale orders | 4-hour auto-cancellation |
| Branch clutter | Post-merge auto-deletion |
| Dashboard staleness | Real-time API calls |
| Small sample size | Minimum N warnings |

---

## The Path Forward

After January 12's audit, the system was finally ready to execute trades.

**Portfolio Status (End of Day)**:
- Paper account: $5,000 (buying power restored)
- Live account: $60 (44 days to first CSP)
- Open positions: 0 (clean slate)
- System health: All checks passing

**Next Milestone**: First trade execution on January 13.

The audit revealed we had built a sophisticated trading system that was too sophisticated to actually trade. The fix wasn't adding more features—it was removing blockers and simplifying execution paths.

Sometimes the best engineering is **deletion**.

---

*This post documents lessons learned LL-131, LL-133, LL-135, LL-137, LL-143, LL-144, and LL-163 from our RAG knowledge base.*

*Questions or feedback? Open an issue on our [GitHub repository](https://github.com/IgorGanapolsky/trading).*
