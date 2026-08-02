# Perplexity Trading Intel: weekend

- Generated UTC: `2026-04-25T14:16:12.991394+00:00`
- Recommendation: `CAUTION`
- Risk score: `0.57`
- Confidence: `0.75`
- API status: `ok`
- Gate reason: Perplexity event/regime risk score 0.57 requires caution.

## Query Findings

### iron_condor_research
- Risk score: `0.55`
- Summary: **SPY/SPX iron condor rules with 10-20 delta shorts, 30-45 DTE, 50% profit exits, 2x credit stops, event avoidance, and VIX filters show partial support in recent sources, but profit targets, stops, and filters lack direct evidence and require backtesting before live use.[1]**  ### Supported Rules - **Delta selection (10-20 delta short strikes):** Conservative 10-16 delta yields 84-90% probability of profit (POP) with low premium ($0.80-$1.20); balanced 20 delta aligns with 75-80% POP and medium premium ($1.20-$1.80), targeting 65-70% win rate overall.[1] - **DTE (30-45 days):** Optimal for theta decay balance, avoiding slow decay (too far) or high gamma risk (too close).[1] - **VIX regime f...

### strategy_failure_patterns
- Risk score: `0.59`
- Summary: **High-volatility regime shifts fail short premium strategies like SPY/SPX iron condors when VIX trends upward, futures trade at premiums to spot VIX, and markets hit overbought extremes, amplifying tail risks from events like earnings or geopolitics.[1]**  For a ~100k paper account (current equity $93,574, 8 positions, profit factor 0.24, win rate 23.88%, scale_allowed false, verified_edge_available false), block new iron condors on these failure patterns[1][2]:  - **VIX above 200-day MA for 3+ days**: Signals volatility trend reversal; current setup matches with VIX "worry-wart" status amid Iran/oil risks, demanding SPX puts.[1] - **Upward-sloping VIX futures term structure with futures >...

## Citations
- https://apexvol.com/strategies/iron-condor
- https://www.morningstar.com/news/marketwatch/20260423525/cheap-stock-options-suggest-a-big-post-earnings-swing-next-week-for-meta-and-other-tech-titans
- https://journalplus.co/journal/spx-index-options
