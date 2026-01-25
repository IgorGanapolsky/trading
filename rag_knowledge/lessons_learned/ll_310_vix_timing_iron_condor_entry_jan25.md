# LL-310: VIX Timing for Iron Condor Entry

**Date**: 2026-01-25
**Category**: Strategy / Entry Timing
**Status**: RESEARCH

## Key Finding: IV Rank and VIX Level Matter

### Optimal Entry Conditions

| Parameter | Recommended Range | Our Current Setup |
|-----------|------------------|-------------------|
| IV Rank | 50-70% (≥70% preferred) | Not tracked |
| VIX Level | 15-25 | Not filtered |
| DTE | 30-45 days | ✅ 30-45 DTE |
| Short Strike Delta | 15-25 | ✅ 15-20 delta |
| Profit Target | 50% max profit | ✅ 50% exit |

### Why VIX Timing Matters

1. **High IV = Rich Premium**: IV Rank ≥50% means options are expensive relative to history
2. **Vol Crush Benefit**: When IV drops after entry, position profits faster
3. **Mean Reversion**: VIX tends to spike then revert - enter AFTER spikes, not during

### VIX Guidelines

- **VIX 15-25**: Optimal range for iron condor entry
- **VIX < 15**: Premium too thin, risk/reward unfavorable
- **VIX > 30**: Market panic, spreads widen, avoid new entries
- **VIX > 40**: Extreme panic, close positions or stay flat

### Best Entry Timing

1. Wait for VIX spike (fear event)
2. Let VIX start to decline (mean reversion beginning)
3. Enter when VIX crosses back below 25
4. Confirm IV Rank ≥50% on SPY

### Implementation Recommendations

1. **Add VIX filter to entry logic**: `if 15 <= VIX <= 25`
2. **Track IV Rank**: Add IV percentile check before entry
3. **Alert system**: Notify when conditions are optimal
4. **Avoid entries**: During VIX spikes or extreme low VIX

## Action Items

- [ ] Add VIX level check to iron condor entry criteria
- [ ] Implement IV Rank tracking for SPY
- [ ] Create alert when VIX enters 15-25 range after spike
- [ ] Backtest: entries with VIX filter vs without

## Risk Note

Even with optimal VIX timing, maintain:
- 5% max position size
- 200% stop-loss on credit
- 7 DTE exit for gamma protection

## Sources

- [TradingView: IV Rank & Percentile Guide](https://www.tradingview.com/chart/VIX/ruLfEtZR-Watch-this-BEFORE-taking-Iron-Condors-IV-Rank-Percentile/)
- [AdvancedAutoTrades: SPX Iron Condor](https://advancedautotrades.com/iron-condor-strategy/)
- [ApexVol: Iron Condor Strategy 2026](https://apexvol.com/strategies/iron-condor)
- [Option Alpha: Iron Condor Guide](https://optionalpha.com/strategies/iron-condor)
- [QuantBeckman: Iron Condor Code](https://www.quantbeckman.com/p/with-code-options-iron-condor-strategy)
