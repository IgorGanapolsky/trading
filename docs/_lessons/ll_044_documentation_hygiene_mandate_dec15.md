---
layout: post
title: "Lesson Learned #044: Documentation Hygiene Mandate - Zero Tolerance for Stale Docs"
date: 2025-12-15
---

# Lesson Learned #044: Documentation Hygiene Mandate - Zero Tolerance for Stale Docs

**ID**: LL-044
**Impact**: Identified through automated analysis

**Date**: December 15, 2025
**Severity**: CRITICAL
**Category**: Process, Documentation, Code Hygiene
**Mandated By**: CEO

---

## Executive Summary

**Documentation rot is a silent killer.** When docs don't match reality, they become lies that waste time and destroy trust.

## The Failures We Found Today

| Document | What It Said | Reality | Impact |
|----------|--------------|---------|--------|
| `README.md` | Win rate: 62.2% | Options: 75%, Crypto: 0% | Misleading |
| `README.md` | Crypto: 5% allocation | Crypto: REMOVED | Wrong |
| `portfolio_allocation.yaml` | Options: 5% inactive | Options: 37% primary | Critical misconfig |
| `dashboard.md` | Last updated Dec 10 | Today is Dec 15 | 5 days stale |
| `claude-progress.txt` | Last entry Dec 9 | Today is Dec 15 | 6 days stale |
| RAG system | "Built and ready" | Dependencies not installed | Broken |

**Every single piece of documentation was lying.**

## The Damage

1. **Missed $109 in opportunity cost** - Options insight was in RAG since Dec 12, not acted upon
2. **Crypto kept running** despite 0% win rate - docs said "active"
3. **User confusion** - Asked "how much money did we make?" because dashboard was stale
4. **RAG useless** - Built but never queried because we assumed it worked

## The Mandate (Effective Immediately)

### Rule 1: Update Docs With Every Change

```
Code Change → Documentation Update → SAME COMMIT

No exceptions. No "I'll do it later." No separate PR.
```

### Rule 2: Daily Staleness Check

Every file must have a "Last Updated" timestamp. If >3 days old:
- Dashboard: AUTO-FAIL
- README: WARNING
- Progress files: AUTO-FAIL

### Rule 3: Single Source of Truth

| Data | Authoritative Source | All Others Must Sync |
|------|---------------------|---------------------|
| Allocation | `config/portfolio_allocation.yaml` | README, dashboard |
| Performance | `data/system_state.json` | README, dashboard |
| Strategy status | `data/system_state.json` | All docs |
| Lessons | `rag_knowledge/lessons_learned/` | Queried before changes |

### Rule 4: Pre-Commit Documentation Check

```bash
# Add to .git/hooks/pre-commit
python3 scripts/check_doc_freshness.py
# Fails if critical docs >3 days old
```

### Rule 5: RAG Must Be Queried

Before ANY strategic change:
```bash
python3 scripts/mandatory_rag_check.py "<what you're changing>"
```

If RAG returns relevant lessons → READ THEM FIRST.

## Files That Must Stay Current

| File | Max Staleness | Auto-Update |
|------|---------------|-------------|
| `README.md` | 7 days | No (manual) |
| `dashboard.md` | 1 day | Yes (GitHub Actions) |
| `claude-progress.txt` | 1 day | No (per session) |
| `data/system_state.json` | 1 day | Yes (trading system) |
| `config/portfolio_allocation.yaml` | On change | No (manual) |

## Implementation Checklist

### Immediate (Today)
- [x] Update README.md with current strategy
- [x] Update portfolio_allocation.yaml (options 37%, crypto removed)
- [x] Update system_state.json
- [ ] Update dashboard.md
- [ ] Update claude-progress.txt
- [ ] Install RAG dependencies (sentence-transformers, chromadb)

### This Week
- [ ] Create `scripts/check_doc_freshness.py`
- [ ] Add pre-commit hook for doc freshness
- [ ] Add GitHub Action for daily dashboard update
- [ ] Clean up duplicate/conflicting RAG implementations (ChromaDB vs LanceDB)

### Ongoing
- [ ] Query RAG at start of every session
- [ ] Update docs in same commit as code changes
- [ ] Run doc freshness check before every PR

## The Philosophy

> "If it's not documented, it doesn't exist. If the documentation is wrong, it's worse than not existing - it's a lie."

**Documentation is not a chore. It's part of the work.**

A feature without updated docs is an incomplete feature.
A bug fix without a lesson learned is a bug waiting to recur.
A strategy change without config/doc updates is a ticking time bomb.

## Consequences of Violation

1. **First violation**: Document the lesson learned
2. **Second violation**: Review why process wasn't followed
3. **Third violation**: System is considered unreliable until fixed

## Key Metrics to Track

| Metric | Target | Current |
|--------|--------|---------|
| Doc freshness (critical files) | 100% <3 days | ~40% |
| README accuracy | 100% | ~60% |
| RAG query rate (per session) | 100% | 0% |
| Config/Doc sync | 100% | ~50% |


## Prevention Rules

1. Apply lessons learned from this incident
2. Add automated checks to prevent recurrence
3. Update RAG knowledge base

## Related Lessons

- LL_035: Failed to Use RAG Despite Building It
- LL_020: Options Primary Strategy (was in RAG, not acted upon)
- LL_017: RAG Vectorization Gap

## Tags

`documentation`, `hygiene`, `process`, `rag`, `freshness`, `mandate`, `critical`

## The Bottom Line

**Clean docs = Clean system. Dirty docs = Dirty system.**

If we can't trust our documentation, we can't trust our system.
If we can't trust our system, we can't trust our trades.
If we can't trust our trades, we lose money.

**Documentation hygiene is not optional. It's survival.**

