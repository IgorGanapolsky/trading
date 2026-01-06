# Lesson Learned #083: Evidence-Based LLM Model Selection for Trading

**Date:** 2026-01-06
**Category:** Cost Optimization, Model Selection
**Severity:** HIGH
**Status:** Active

## What Happened

Made cost-cutting recommendations for our LLM budget ($100/month) without first researching what the industry's best practices are in January 2026. CEO correctly challenged: "Did you do deep research to determine your recommendations are actually the best ones?"

## The Mistake

1. Recommended Kimi K2 based on pricing alone, not performance data
2. Missed Mistral Medium 3 entirely (90% of Sonnet at 8x cheaper)
3. Assumed Claude Sonnet was optimal for trading without benchmark data
4. Made recommendations without citing industry research

## What Deep Research Revealed

### StockBench AI Trading Benchmark (14 models, 4 months, $100K portfolio)

| Model | Return | Sortino Ratio | Rank |
|-------|--------|---------------|------|
| **Kimi-K2** | 1.9% | **0.0420** | **#1** |
| Qwen3-235B-Ins | 2.4% | 0.0299 | #2 |
| Claude-4-Sonnet | 2.2% | 0.0245 | Mid |
| DeepSeek-V3.1 | 1.1% | 0.0210 | Lower |
| GPT-5 | 0.3% | 0.0132 | Bottom |

**Kimi K2's Sortino ratio is 40% higher than competitors** - meaning best risk-adjusted returns.

### January 2026 Pricing (per 1M tokens)

| Model | Input | Output | Notes |
|-------|-------|--------|-------|
| Claude Sonnet | $3.00 | $15.00 | Compliance-focused |
| **Mistral Medium 3** | $0.40 | $2.00 | 90% Sonnet quality, 8x cheaper |
| **Kimi K2** | $0.39 | $1.90 | #1 for trading benchmarks |
| DeepSeek V3 | $0.14 | $0.28 | Good for simple tasks |

### TradingAgents Framework Best Practice (arXiv:2412.20138)

Industry-standard multi-agent trading uses **task-specific model routing**:
- Quick-thinking models (gpt-4o-mini) → Data retrieval, summarization
- Deep-thinking models (o1-preview, Kimi K2) → Decision-making, risk assessment

## Correct Recommendations (Evidence-Based)

| Task | Current | Should Be | Cost Impact |
|------|---------|-----------|-------------|
| CRITICAL (execution) | Claude Opus | Keep Opus | None |
| COMPLEX (risk, strategy) | Claude Sonnet | Kimi K2 | -80% |
| MEDIUM (analysis) | Claude Sonnet | Mistral Medium 3 | -87% |
| SIMPLE (classification) | Claude Haiku | DeepSeek V3 | -85% |

**Projected savings: $50-100/month → $15-25/month**

## Root Cause

- Made assumptions without verification
- Did not search for current benchmarks before recommending
- Treated cost optimization as a pricing exercise, not a performance exercise

## Prevention

1. **Before any recommendation**: Search for current industry benchmarks
2. **Cite sources**: Every claim needs a URL or paper reference
3. **Verify performance, not just price**: Cheaper is worthless if it performs worse
4. **Challenge own assumptions**: "What evidence would prove this wrong?"

## Action Items

- [x] Update `src/utils/model_selector.py` with evidence-based model tiers
- [ ] Add Mistral Medium 3 to model registry
- [ ] Enable Kimi K2 for COMPLEX trading tasks
- [ ] Set up cost tracking via Helicone
- [ ] Re-run benchmarks with new model stack

## Sources

- [Neurohive: AI Stock Trading Models Tested](https://neurohive.io/en/news/kimi-k2-and-qwen3-235b-ins-best-ai-models-for-stock-trading-chinese-researchers-found/)
- [TradingAgents Framework (arXiv:2412.20138)](https://arxiv.org/abs/2412.20138)
- [Mistral Medium 3 Announcement](https://mistral.ai/news/mistral-medium-3)
- [Kimi K2 Analysis](https://recodechinaai.substack.com/p/kimi-k2-smarter-than-deepseek-cheaper)

## Tags

`model-selection` `cost-optimization` `kimi-k2` `mistral` `trading` `benchmarks` `evidence-based`
