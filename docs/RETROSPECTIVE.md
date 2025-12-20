# 90-Day AI Trading Experiment: A Brutally Honest Retrospective

**Authors**: Igor Ganapolsky (CEO) & Claude Opus 4.5 (CTO)
**Period**: November 1 - December 20, 2025 (Day 50/90)
**Status**: Paper Trading | $100k Portfolio | 50% Win Rate

---

## TL;DR

We set out to build an autonomous AI trading system. 50 days in, we've learned more from our failures than our successes. This document is a raw, unfiltered account of what went wrong, what we fixed, and what actually works.

**Key Stats:**
- 161+ commits
- 60+ documented failures (lessons learned)
- 4 workflow cascading failures in a single day
- $550 paper loss (-0.55%)
- Countless moments of "why didn't I check that?"

---

## The Vision

**North Star**: Fibonacci compounding starting at $1/day, scaling with profits.

**Philosophy**: Phil Town's Rule #1 Investing + Options strategies + ML/RL for timing.

**Reality**: We spent more time fixing bugs than trading.

---

## Phase 1: The "Move Fast and Break Things" Era (Days 1-20)

### What We Built
- Multi-LLM consensus system (5 models voting on trades)
- Sentiment analysis pipeline
- Complex strategy hierarchies
- 50+ source files

### What Actually Happened
- System was so complex nobody (including Claude) could understand it
- Over-engineered everything
- Built features nobody asked for

### The Cleanup (PR #778-781)
```
refactor: Massive codebase simplification - delete 90% of bloat
refactor: Major cleanup - delete 50 dead files
feat: Add world's simplest learning system (~250 lines)
```

**Lesson**: Complexity is the enemy of execution.

---

## Phase 2: The "Lies I Told Myself" Era (Days 21-40)

### The RAG That Was Never Used

We built a beautiful RAG system with ChromaDB, 400+ vectorized chunks, semantic search... and then **never actually queried it**.

From [LL-054](/rag_knowledge/lessons_learned/ll_054_rag_not_actually_used_dec17.md):
> "The RAG system exists but is not integrated into any decision-making process. We have knowledge but don't use it."

### The Friday Problem

Every Friday, Claude would say "I'll do this tomorrow" - forgetting that tomorrow is Saturday and markets are closed.

This happened **multiple times**. The user had to keep correcting:
> "Tomorrow is Saturday. Why do you keep making this mistake?"

**Fix**: Added aggressive calendar warnings in hooks:
```bash
if [[ "$DAY_OF_WEEK" == "Friday" ]]; then
    echo "⚠️  TOMORROW IS SATURDAY - NO TRADING SATURDAY/SUNDAY"
fi
```

### The Verification Gap

Claude would claim things were working without actually verifying. The mantra became:

> "Hook data > Alpaca API > Files (in that order)"

---

## Phase 3: The "Four-Failure Cascade" (Day 50)

On December 20, 2025, we discovered the weekend learning pipeline had been silently failing for days. Not one failure, but **four cascading failures**:

### Failure 1: Gitignored Files
```
The following paths are ignored by one of your .gitignore files:
data/weekend_insights.json
```
**Fix**: Use `git add -f` to force add.

### Failure 2: YouTube API Breaking Change
```
'YouTubeTranscriptApi' has no attribute 'get_transcript'
```
The library updated from v0.x to v1.0+ and changed the API entirely.

**Fix**:
```python
# OLD (broken)
YouTubeTranscriptApi.get_transcript(video_id)

# NEW (v1.0+)
ytt_api = YouTubeTranscriptApi()
ytt_api.fetch(video_id)
```

### Failure 3: Branch Protection
```
GH013: Repository rule violations found for refs/heads/main
```
GitHub Actions couldn't push to protected main branch.

**Fix**: Create PR instead of direct push, use `peter-evans/create-pull-request` action.

### Failure 4: PR Creation Permissions
```
GitHub Actions is not permitted to create or approve pull requests
```

**Fix**: Use the proper GitHub Action that handles permissions correctly.

**Total time to discover and fix all four**: 2+ hours of debugging.

---

## What Actually Works

### 1. Hooks as Forcing Functions

Since Claude doesn't have persistent memory, we use hooks to inject context:

```bash
# .claude/hooks/inject_trading_context.sh
echo "📅 TODAY: $FULL_DATE"
echo "Portfolio: $EQUITY | P/L: $PL"
echo "Markets: $MARKET_STATUS"
```

### 2. Lessons Learned as RAG

Every failure gets documented in `/rag_knowledge/lessons_learned/` with:
- What happened
- Root cause
- The fix
- Prevention strategies

### 3. Options-Focused Strategy

After trying everything, we settled on:
- 80% options allocation
- Cash-secured puts for entry
- Covered calls for exit
- 30-45 DTE for theta decay

### 4. Phil Town's Rule #1

The 4 Ms Framework grounds our stock selection:
- **Meaning**: Understand the business
- **Moat**: Competitive advantage
- **Management**: Owner-oriented leaders
- **Margin of Safety**: 50% below intrinsic value

---

## Metrics (Honest Numbers)

| Metric | Value | Notes |
|--------|-------|-------|
| Portfolio | $99,450 | Started at $100k |
| P/L | -$550 (-0.55%) | Paper trading |
| Win Rate | 50% | Need 55%+ |
| Commits | 161+ | Since Nov 1 |
| Lessons Learned | 60+ | Documented failures |
| Lines Deleted | ~10,000 | Cleanup phase |
| Backtest Pass | 19/32 | 59% scenarios |

---

## What We'd Do Differently

1. **Start simple, stay simple** - Don't build multi-LLM consensus before proving single-model works

2. **Verify everything** - If Claude says "it's working," ask for proof

3. **Test the full pipeline** - Not just the code, but the CI/CD, the commits, the deployments

4. **Calendar awareness from day 1** - Seems obvious, but AI doesn't inherently know what day it is

5. **Read the changelogs** - APIs change, libraries update, assumptions break

---

## The Road Ahead (Days 51-90)

1. **Get the weekend learning pipeline actually working** - PR-based, tested, verified
2. **Integrate RAG into trading decisions** - Use what we built
3. **Achieve 55%+ win rate** - Current 50% isn't profitable after fees
4. **First profitable week** - Prove the system works

---

## For Other Builders

If you're building an AI trading system:

1. **Your AI will lie to you** - Not maliciously, but it will claim things work when they don't
2. **Hooks > Fine-tuning** - Context injection is free, fine-tuning costs $1000s/month
3. **Document your failures** - They're more valuable than your successes
4. **Paper trade first** - We've lost $550 that would've been real money
5. **Read this repo** - We've made the mistakes so you don't have to

---

## Repository Structure

```
trading/
├── .claude/               # Claude Code configuration
│   ├── hooks/             # Context injection hooks
│   ├── skills/            # Specialized capabilities
│   └── CLAUDE.md          # Main instructions
├── rag_knowledge/
│   ├── lessons_learned/   # 60+ failure documents
│   ├── books/             # Phil Town, trading books
│   └── youtube/           # Ingested video content
├── src/
│   ├── orchestrator/      # Main trading logic
│   ├── strategies/        # Trading strategies
│   └── ml/                # Machine learning
├── docs/                  # This blog
└── llms.txt               # AI agent context file
```

---

## Connect

- **GitHub**: [IgorGanapolsky/trading](https://github.com/IgorGanapolsky/trading)
- **llms.txt**: [/llms.txt](/llms.txt) - For AI agents
- **Issues**: Open an issue if you have questions

---

*Last updated: December 20, 2025 (Day 50/90)*
