# Lesson Learned: Strategy Thresholds Too Tight - Positions Closed Before Trends Developed

**ID**: LL_051
**Date**: 2025-12-17
**Severity**: CRITICAL
**Category**: Trading
**Tags**: backtest, sharpe, take-profit, stop-loss, position-sizing, options

## Incident Summary

All 13 backtest scenarios failed with negative Sharpe ratios (-7 to -2086). Investigation revealed 5% take-profit and stop-loss thresholds were too tight, causing positions to close on normal daily swings before capturing actual trends.

## Root Cause

**Six critical flaws identified:**

1. **5% take-profit too tight** - SPY moves 3-5% weekly; positions closed on first rally, missed 10-20% trends
2. **5% stop-loss too tight** - Hit by normal daily volatility noise
3. **14-day max hold too short** - Trending positions killed on day 15 before completing
4. **No volatility filter** - Traded same size regardless of VIX level
5. **Momentum entry buys at tops** - Highest momentum = often local peak
6. **Fixed dollar sizing ignores risk** - Same $900/day in calm and volatile markets

**Options comparison revealed:**
- Options showed 75% win rate but losses were 7x larger than wins
- Net P/L was actually -$29.96 (NEGATIVE)
- "High win rate" is misleading without considering loss magnitude

## Impact

- 0/13 backtest scenarios pass
- All Sharpe ratios negative (-7 to -2086)
- Win rate appears acceptable (34-62%) but misleading
- Strategy returns 0.1% vs 4% risk-free rate = mathematically impossible positive Sharpe

## Prevention Measures

**Implemented Dec 17, 2025:**

1. `TAKE_PROFIT_PCT`: 5% → 15% (let winners run)
2. `STOP_LOSS_PCT`: 5% → 8% (wider to avoid noise)
3. `MAX_HOLDING_DAYS`: 14 → 30 (allow trends to develop)
4. `ATR_MULTIPLIER`: 2.0 → 2.5 (adaptive to volatility)
5. Added `VIX_HIGH_THRESHOLD = 35` (skip trading in panic)
6. Added `VIX_POSITION_SCALE = True` (size inversely to VIX)

**Files changed:**
- `src/strategies/core_strategy.py`
- `src/risk/position_manager.py`
- `src/orchestrator/main.py`

## Detection Method

Deep research using parallel agents to:
1. Analyze backtest failure patterns
2. Compare options vs equities performance
3. Identify strategy-to-metric mismatch

## Related Lessons

- LL_021: Backtest thresholds too strict for R&D phase
- LL_040: Catching falling knives (pyramid buying destroyed 96%)
- LL_033: Negative momentum buying

## Key Insight

**High win rate ≠ profitable strategy.** Options showed 75% wins but 7x larger losses = net negative. The correct metrics are:
- Expected value per trade = (win_rate × avg_win) - (loss_rate × avg_loss)
- Risk-adjusted return (Sharpe/Sortino) must be positive
- Position sizing must scale with volatility
