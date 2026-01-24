---
layout: post
title: "Day 88: Weekend Maintenance and Strategy Validation"
date: 2026-01-24 12:00:00
categories: [engineering, lessons-learned, ai-trading]
tags: [iron-condors, strategy, research, risk-management]
---

Markets are closed today (Saturday), so Ralph is running maintenance tasks and reviewing recent discoveries. Here's what we're working with.

## The 86% Win Rate Research (LL-277)

This week we deep-dived into iron condor optimization research from [Options Trading IQ](https://optionstradingiq.com/iron-condor-success-rate/) and [Project Finance](https://www.projectfinance.com/iron-condor-management/) (based on 71,417 real trades).

**The key insight:** Delta selection is everything.

| Short Strike Delta | Win Rate |
|-------------------|----------|
| 10-15 delta | **86%** |
| 30 delta | 34% |

We're using 15-20 delta short strikes. The research validates our approach, but also suggests a change: close at **7 DTE** instead of 21 DTE for better win rates.

[View the full lesson: LL-277](https://github.com/IgorGanapolsky/trading/blob/main/rag_knowledge/lessons_learned/ll_277_iron_condor_optimization_research_jan21.md)

---

## Position Stacking Bug Fixed (LL-290)

Earlier this week, we discovered our safety gate had a critical flaw: it counted unique *symbols* instead of *contracts*. This allowed 8 contracts of the same option to accumulate.

**The bug:**
```python
# Only counted unique positions (wrong)
current_position_count = len(current_positions)
```

**The fix ([PR #2702](https://github.com/IgorGanapolsky/trading/pull/2702)):**
```python
# Now blocks buying more of an existing symbol
if symbol in existing_symbols:
    return GateResult(approved=False, reason="POSITION STACKING BLOCKED")
```

This bug cost $1,472 in paper trading. Better to learn this lesson with fake money.

[Read the full post-mortem](/trading/2026/01/22/position-stacking-disaster-fix.html)

---

## Dead Code Cleanup

Ralph's proactive scanner identified unused imports and deprecated functions across the codebase. Nothing dramatic—just routine maintenance to keep the system lean.

---

## This Week's Commits

| Commit | Description |
|--------|-------------|
| [daaed27](https://github.com/IgorGanapolsky/trading/commit/daaed27) | Auto-publish discovery blog post |
| [a88b49d](https://github.com/IgorGanapolsky/trading/commit/a88b49d) | CI iteration |
| [f7f1dd8](https://github.com/IgorGanapolsky/trading/commit/f7f1dd8) | Auto-publish discovery blog post |

---

## What's Next

Monday the markets reopen. We're ready to:
1. Paper trade iron condors with validated 15-delta setup
2. Test the new 7-DTE exit strategy (vs. our previous 21-DTE)
3. Let the system run autonomously while monitoring for issues

The goal is simple: prove 80%+ win rate over 90 days of paper trading before scaling.

---

*Day 88 of building an AI trading system in public. [View the full source code](https://github.com/IgorGanapolsky/trading).*
