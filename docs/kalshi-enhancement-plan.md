# Kalshi Enhancement Plan

**Created**: December 9, 2025
**Source**: Podcast interview with Kalshi CEO Tarek Mansour
**Status**: Proposed

## Executive Summary

Our current Kalshi implementation treats it as a standalone prediction market trading venue. Based on insights from the Kalshi CEO, we're missing the **primary value proposition**: using prediction market odds as high-quality leading indicators for correlated asset trading.

## Current State vs. Target State

| Dimension | Current | Target |
|-----------|---------|--------|
| **Role** | Standalone Tier 6 | Data oracle + Trading venue |
| **Signal Source** | Price heuristics | Alternative data (polls, sentiment, news) |
| **Trading Style** | Directional bets | Market making + Directional |
| **Architecture** | Poll-based | Event-driven (NLP triggers) |
| **Cross-Asset** | None | Kalshi → Equity/Forex/Crypto signals |

---

## Enhancement 1: Kalshi as "Truth Oracle" (Cross-Asset Signals)

### Concept
> "Prediction markets can extend the news to cover what's about to happen next." - Tarek Mansour [14:11]

Use Kalshi odds as **leading indicators** for other markets before news breaks.

### Implementation

```
Kalshi Market → Signal → Correlated Asset Trade
─────────────────────────────────────────────────
Fed Rate (75%+ hike)     → Short TLT, Long USD
Fed Rate (75%+ cut)      → Long TLT, Short USD
Election (GOP win 60%+)  → Long XLE, XLF, Defense
Election (DEM win 60%+)  → Long XLV, Clean Energy
Recession odds >50%      → Long VIX, Short Russell
BTC >$100K odds rising   → Long BTC via Alpaca
```

### Code Changes Required

1. **New module**: `src/signals/kalshi_oracle.py`
   - Poll Kalshi markets every 15 minutes
   - Emit signals when odds cross thresholds
   - Feed signals to equity/crypto strategies

2. **Cross-tier integration**:
   - Modify `momentum_strategy.py` to accept Kalshi signals
   - Add Kalshi odds as feature in ML models

### Priority: **HIGH** - This is the CEO's primary insight

---

## Enhancement 2: Alternative Data Integration

### Concept
> "I don't think that Citadel has asymmetric information on our political process... The best traders are people that love politics." - Tarek Mansour [22:25]

Our edge comes from **domain-specific data**, not HFT infrastructure.

### Data Sources to Integrate

| Category | Data Source | API/Method |
|----------|-------------|------------|
| **Elections** | 538, RealClearPolitics | Web scraping |
| **Elections** | PredictIt (cross-reference) | REST API |
| **Economics** | FRED (economic indicators) | REST API |
| **Sentiment** | Twitter/X trending topics | API or scraping |
| **Weather** | NOAA hurricane data | REST API |
| **Crypto** | On-chain metrics (Glassnode) | REST API |

### Fair Value Model Upgrade

Replace current contrarian heuristics:
```python
# CURRENT (basic)
if market.yes_price > 85:
    fair_value = market.yes_price - 3

# TARGET (data-driven)
fair_value = calculate_fair_value(
    market_type=market.category,
    current_odds=market.yes_price,
    polling_average=get_polling_data(market.event),
    sentiment_score=get_sentiment(market.event),
    historical_bias=get_market_bias(market.ticker)
)
```

### Priority: **HIGH** - Direct edge improvement

---

## Enhancement 3: Market Making Strategy

### Concept
> "In our model it's an open transparent financial market that is neutral... whether you lose or make money we are not incentivized either way." - Tarek Mansour [43:19]

Unlike sportsbooks that ban winning bots, Kalshi **wants** liquidity providers.

### Strategy Design

```
Market Making Parameters:
- Min Spread Capture: 2 cents
- Max Position: $100 per market
- Inventory Rebalance: Every 5 minutes
- Risk Limit: $500 total inventory

Algorithm:
1. Monitor order book for markets with >3c spread
2. Place limit orders on both sides
3. Capture spread when both sides fill
4. Rebalance inventory to avoid directional risk
5. Exit all positions before event settlement
```

### Code Changes Required

1. **New strategy**: `src/strategies/kalshi_market_maker.py`
2. **Order book monitoring**: WebSocket or frequent polling
3. **Inventory management**: Track net position, rebalance

### Priority: **MEDIUM** - Consistent returns, lower alpha

---

## Enhancement 4: Event-Driven Architecture

### Concept
> "The volumes will basically ebb and flow whatever is in the news, whatever is trending on X." - Tarek Mansour [05:53]

Trade when events are **trending**, not on a fixed schedule.

### Architecture

```
Event Sources          NLP Processing         Trading Trigger
─────────────         ──────────────         ───────────────
Twitter/X trends  →   Topic extraction   →   High-attention event detected
Google Trends     →   Entity matching    →   Map to Kalshi market
News headlines    →   Sentiment scoring  →   Signal strength determination
Economic calendar →   Event timing       →   Pre-event positioning
```

### Implementation

1. **Event monitor service**: Background process
2. **NLP pipeline**: Extract entities, match to Kalshi markets
3. **Trigger system**: When attention score > threshold, trade

### Example Workflow

```
1. NLP detects "Hurricane Milton" trending
2. System finds KXHURRICANE-* markets on Kalshi
3. Cross-reference NOAA data for actual storm path
4. If market mispriced vs. NOAA data → Trade
5. Increase position size due to high attention (liquidity)
```

### Priority: **MEDIUM** - Requires NLP infrastructure

---

## Enhancement 5: Arbitrage Opportunities

### Cross-Platform Arbitrage

```
Kalshi vs. PredictIt vs. Polymarket

If same event has different odds:
  Kalshi: Trump wins @ 55c
  PredictIt: Trump wins @ 52c

  Action:
  - Buy on PredictIt @ 52c
  - Sell on Kalshi @ 55c
  - Lock in 3c profit regardless of outcome
```

### Intra-Kalshi Arbitrage

```
Correlated markets that should sum to 100%:

"Fed raises rates" + "Fed holds rates" + "Fed cuts rates" = 100%

If sum > 100%: Sell all positions (overpriced)
If sum < 100%: Buy all positions (underpriced)
```

### Priority: **LOW** - Requires multi-platform integration

---

## Implementation Roadmap

### Phase 1: Cross-Asset Signals (Week 1-2)
- [ ] Create `kalshi_oracle.py` module
- [ ] Implement threshold-based signal emission
- [ ] Integrate signals into momentum strategy
- [ ] Test with paper trading

### Phase 2: Alternative Data (Week 3-4)
- [ ] Integrate polling data (538, RCP)
- [ ] Build fair value model for elections
- [ ] Add economic calendar integration
- [ ] Replace heuristic pricing

### Phase 3: Event-Driven (Week 5-6)
- [ ] Set up news/social monitoring
- [ ] Build NLP entity extraction
- [ ] Create event-to-market mapping
- [ ] Implement attention-triggered trading

### Phase 4: Market Making (Week 7-8)
- [ ] Order book monitoring
- [ ] Spread capture algorithm
- [ ] Inventory management
- [ ] Risk controls

---

## Budget Impact

| Enhancement | Monthly Cost | Expected Return |
|-------------|--------------|-----------------|
| Cross-Asset Signals | $0 (uses existing data) | Higher equity returns |
| Alternative Data | ~$50 (API costs) | +5-10% Kalshi win rate |
| Event-Driven | ~$20 (news APIs) | Better timing |
| Market Making | $0 | Consistent small gains |

**Total**: ~$70/month additional cost, well within $100/mo budget

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Kalshi Win Rate | Unknown (paper) | >55% |
| Cross-Asset Signal Accuracy | N/A | >60% |
| Market Making ROI | N/A | >0.5%/day |
| Event Prediction Lead Time | N/A | >2 hours |

---

## References

- Podcast: Kalshi CEO Tarek Mansour interview
- Kalshi API Docs: https://trading-api.readme.kalshi.com/
- Current implementation: `src/brokers/kalshi_client.py`, `src/strategies/prediction_strategy.py`
