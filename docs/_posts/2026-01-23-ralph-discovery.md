---
layout: post
title: "Day 87: Two Bugs That Cost Us $93"
date: 2026-01-23 23:49:43
categories: [engineering, lessons-learned, debugging]
tags: [options, iron-condors, api-integration, bugs]
---

Thursday was a rough day. We found two bugs that were silently eating our profits.

## Bug #1: Invalid Option Strikes ($70 loss)

**The symptom:** Our iron condors only had PUT legs. No CALLs were executing.

**The cause:** SPY options only exist in $5 increments ($720, $725, $730...), but our code was calculating strikes like $724 and $729.

```python
# The bug
short_call = round(price * 1.05)  # round(690*1.05) = $724 - doesn't exist!

# The fix
def round_to_5(x): return round(x / 5) * 5
short_call = round_to_5(price * 1.05)  # = $725 - valid!
```

Alpaca silently rejected the invalid symbols. No error logs. No warning. Just... nothing.

**The lesson:** When your broker "fails silently," you need explicit validation. We now verify all 4 legs fill before considering a trade complete.

[View the full lesson: LL-298](https://github.com/IgorGanapolsky/trading/blob/main/rag_knowledge/lessons_learned/ll_298_invalid_strikes_call_legs_fail_jan23.md)

---

## Bug #2: Crisis Workflow Traded Shares ($22.61 loss)

**The symptom:** 49 SPY share trades appeared in our account. We don't trade shares—we trade iron condors.

**The cause:** A "crisis recovery" workflow kicked in when the main trading workflow hit credential issues. Instead of alerting us, it started buying and selling SPY shares repeatedly.

**Why this happened:**
1. GitHub secrets had wrong names (5K vs 30K accounts)
2. Iron condor workflow failed silently
3. Crisis workflow assumed "no positions = emergency" and started trading shares
4. No circuit breaker to stop runaway trades

**The fix:** Disabled all crisis workflows. Iron condors only. No automated share trading ever.

**The lesson:** Emergency fallback code is often the most dangerous code. It runs when things are already broken, making broken decisions.

---

## The Math

| Issue | Loss |
|-------|------|
| Invalid strikes (PUT-only positions) | ~$70 |
| Share churning (crisis workflow) | $22.61 |
| **Total** | **~$93** |

Small in absolute terms, but these are the bugs that compound into real losses at scale.

---

## What We Fixed

1. **Strike rounding** - All SPY strikes now round to $5 increments
2. **Leg validation** - Trade isn't "complete" until all 4 legs fill
3. **Disabled crisis workflows** - No more automated fallbacks
4. **Circuit breaker** - Halt if >5 share trades per day

---

## Code Changes

| Commit | Description |
|--------|-------------|
| [8b3e411](https://github.com/IgorGanapolsky/trading/commit/8b3e411) | Add round_to_5() for strike calculation |
| [fec427d](https://github.com/IgorGanapolsky/trading/commit/fec427d) | Disable crisis workflows |

---

*Day 87. Every bug we find in paper trading is a bug that won't cost us real money later.*
