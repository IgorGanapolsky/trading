# LL-306: RAG Learning Synthesis - Iron Condor Adjustments

**Date**: January 25, 2026
**Category**: Strategy / RAG Learning
**Severity**: HIGH

## Context

During Ralph Mode iteration 21, queried RAG and synthesized key learnings from recent lessons.

## Key Learnings from RAG

### From LL-299: Iron Condor Adjustment Strategies

**Critical insight**: When tested, roll the UNTESTED side closer (not the tested side).

| Trigger | Action |
|---------|--------|
| Short strike at 25-30 delta | Consider adjustment |
| Untested side < 15 delta | Must roll closer |
| < 7 DTE | NO adjustments - just close |
| Both sides threatened | Close position immediately |

**Example adjustment**:
- SPY rallies → call side tested
- Roll put spread UP (closer to current price)
- Collect additional credit to lower cost basis

### From LL-305: CI Lint Best Practices

**Key insight**: Run `ruff check .` on entire repo, not just `src/`.

Avoid ambiguous variable names:
- ❌ `l` (looks like `1` or `|`)
- ❌ `O` (looks like `0`)
- ❌ `I` (looks like `l` or `1`)
- ✅ `line`, `output`, `index`

## Applied Learnings

1. **Verified lint on entire repo** - per LL-305 guidance
2. **Updated LL-302** - ML model now α=11.0, posterior=0.917
3. **Understood adjustment rules** - will apply when first iron condor is tested

## ML Model Update

After this session:
- Posterior: 0.917 (exceeds 0.90 target)
- test pattern: +0.90 (strongest signal)
- rag pattern: +0.10 (new feature)

## Tags

`rag`, `learning`, `synthesis`, `iron-condor`, `adjustment`, `lint`
