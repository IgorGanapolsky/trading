# Minimal Viable Trading System

**Created:** December 11, 2025
**Status:** ACTIVE - Replacing complex system

## The Problem

Our trading system has grown too complex:

| Metric | Current | Problem |
|--------|---------|---------|
| Live Win Rate | 0% | System doesn't work |
| Backtest Sharpe | -7 to -72 | ALL NEGATIVE |
| Entry Gates | 8-10 | 90% of signals blocked |
| Agent Frameworks | 5 | LangChain, DeepAgents, ADK, DiscoRL, SB3 |
| RL Filters | 3 | None validated with real trades |
| Circuit Breakers | 6+ | Too many stops |

**Root Cause:** We built a "Don't Lose Money" machine instead of a "Make Money" machine.

## The Solution: Minimal Trading

Strip everything down to basics:

### What We Keep

| Component | Details |
|-----------|---------|
| Entry Signal | SMA(20) crosses above SMA(50) + price > SMA(20) |
| Exit Signal | -3% stop-loss, +5% take-profit, SMA reversal |
| Position Size | 2% of portfolio per trade |
| Max Positions | 5 |
| Circuit Breaker | -2% daily loss limit |
| Universe | SPY, QQQ, AAPL, MSFT, GOOGL, AMZN, NVDA, META |

### What We Remove

- ❌ LangChain agent framework
- ❌ DeepAgents framework
- ❌ ADK framework
- ❌ DiscoRL (bleeding edge, 0 validated trades)
- ❌ SB3 RL framework
- ❌ LLM sentiment analysis
- ❌ Mental toughness coaching
- ❌ Macro context adjustments
- ❌ Multi-tier circuit breakers
- ❌ VIX circuit breaker
- ❌ Kelly criterion sizing
- ❌ ATR-based stops
- ❌ Volume confirmation filters
- ❌ Spread validation gates
- ❌ Market hours validation (use built-in Alpaca)
- ❌ Complex risk layers (10 of them!)

## Usage

```bash
# Run minimal trader (paper)
python -m src.orchestrator.minimal_trader

# Run minimal trader (live) - USE WITH CAUTION
python -m src.orchestrator.minimal_trader --live
```

## Philosophy

1. **Trade more, learn faster** - Can't learn from trades that never happen
2. **Simple rules > complex ML** - Until ML proves edge, use simple rules
3. **Prove edge first** - Add complexity only after proving we can make money

## A/B Test Plan

| System | Description | Measure |
|--------|-------------|---------|
| Complex | Current 8-10 gate system | Win rate, Sharpe |
| Minimal | This simple system | Win rate, Sharpe |

Run both in paper trading for 30 days. Keep the one that makes money.

## Success Criteria

To add complexity back, minimal system must achieve:

- [ ] Win rate > 50%
- [ ] Sharpe ratio > 0.5
- [ ] At least 20 closed trades
- [ ] Positive total P/L

Only then do we consider adding:
1. One RL filter (proven to improve)
2. One sentiment layer (proven to improve)
3. Additional risk management (if needed)

## File Location

- Main code: `src/orchestrator/minimal_trader.py`
- Config: Set `USE_MINIMAL_TRADER=true` in `.env`
- This doc: `docs/MINIMAL_TRADING_SYSTEM.md`

## Comparison

| Feature | Complex System | Minimal System |
|---------|---------------|----------------|
| Lines of code | ~50,000+ | ~400 |
| Entry gates | 8-10 | 1 |
| Exit conditions | 7+ | 3 |
| Agent frameworks | 5 | 0 |
| RL models | 3 | 0 |
| LLM calls | Multiple | 0 |
| Time to trade | Minutes | Seconds |
| Understandable | No | Yes |
| Debuggable | Hard | Easy |

## Next Steps

1. Deploy minimal system in paper trading
2. Run for 30 days
3. Compare results to complex system
4. Keep winner, discard loser

---

**Remember:** A system that never trades can never make money.
Let's trade first, optimize later.
