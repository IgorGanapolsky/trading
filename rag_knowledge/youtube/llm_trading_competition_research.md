# LLM Trading Competition Research

**Source**: "5 LLMs Tested Trading $100K Each — See Which Won"
**URL**: https://youtu.be/cnPmW3Ir8cI
**Date Captured**: 2025-12-18

## Experiment Summary

A trading simulation compared 5 LLMs (GPT-5, Claude Sonnet 4.5, Gemini 2.5 Pro, Grok 4, DeepSeek) each managing $100K over 180 days in a paper trading environment.

## Key Methodology Elements

### 1. Standardized Data Inputs
- All models received identical data each trading day
- Historical price data (daily OHLCV)
- News and fundamental data
- No future data leakage (time-stepped simulation)

### 2. Structured Output Format
- Models produce standardized outputs:
  - Buy/sell signals
  - Allocation percentages
  - Confidence scores

### 3. Clear Trading Rules
- Confidence threshold gates trades
- Position sizing limits (% of portfolio per trade)
- Asset type restrictions

### 4. Performance Tracking
- Daily portfolio value
- All trades logged
- Risk metrics: drawdowns, volatility
- Benchmark comparison (S&P 500)

## Actionable Insights for Our System

### High Priority (Address Backtest Failures)
1. **Day-by-day simulation** - Prevents data leakage that causes unrealistic backtest results
2. **Standardize LLM Council outputs** - All models should emit same structured format
3. **Add S&P 500 benchmark** - Context for whether we're beating buy-and-hold

### Medium Priority
4. **Model-specific analysis** - Track which LLM in our council performs best
5. **Sector bias detection** - Identify if models favor certain sectors
6. **Simple strategy baseline** - Compare vs moving average crossover

### Implementation Notes
- Our Multi-LLM infrastructure already supports this
- Need to enforce structured output schema across all LLM integrations
- Consider ensemble/meta-decider approach (LLM Council already does this)

## Relevance to Our R&D Phase

| Their Finding | Our Application |
|---------------|-----------------|
| Some models had tech-heavy bias | Monitor sector concentration in our signals |
| Performance tied to market trends | Add regime detection to our strategies |
| Standardized I/O critical | Enforce schema in `src/llm/` modules |

## Tags
`#multi-llm` `#backtesting` `#benchmarking` `#methodology`
