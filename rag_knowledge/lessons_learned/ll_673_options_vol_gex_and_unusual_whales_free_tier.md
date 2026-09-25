---
id: LL-673
date: 2026-09-24
severity: high
status: active
category: quant-engineering
---

# LL-673: Options Volatility, Dealer GEX, and Unusual Whales Free-Tier Replication

**Date**: September 24, 2026  
**Author**: CTO (Claude) | CEO: Igor Ganapolsky  
**Category**: quant-engineering  

## Summary

Unusual Whales charges $750/month for their basic API and $3,000/month for real-time Kafka access. By reverse-engineering their published specifications (`llms.txt`, endpoint OpenAPI contracts, and alert grammar), we replicated their core proprietary quantitative algorithms in-house at **$0 cost** using our existing Alpaca options chains and local Python libraries.

## Core Formulations Replicated

1. **Dealer Gamma Exposure (GEX) & Regimes**:
   - Spot GEX per strike: $\text{GEX}_K = \Gamma_K \times \text{OI}_K \times S^2 \times 100 \times (\pm 1)$.
   - Call Wall (overhead resistance), Put Wall (downside support), Gamma Magnet (strongest pin), and Gamma Flip ($GEX=0$ zero-crossing).
   - **Regime Rail**: Positive Gamma ($\sum \text{GEX} > 0$) dampens volatility and causes mean-reversion, providing the ideal statistical tailwind for SPY put credit spreads. Negative Gamma ($\sum \text{GEX} < 0$) amplifies volatility and triggers cascade risk, acting as a mandatory safety gate.

2. **Expiration Max Pain**:
   - Minimizes total option holder dollar payout across all strikes:
     $$\text{Max Pain} = \arg\min_K \sum_j [\text{Call OI}_j \cdot \max(0, K - K_j) + \text{Put OI}_j \cdot \max(0, K_j - K)] \times 100$$
   - Predicts expiration price gravitation/pinning for Friday expirations.

3. **Term Structure Backwardation & VRP Richness**:
   - Backwardation gate: Linear IV slope from front-month to 45 DTE $\le -0.00406$ per day.
   - Richness ratio: $IV30 / RV30 \ge 1.25$.
   - Combining backwardation with high VRP creates the optimal regime to sell front-month put credit spreads and harvest rapid volatility crush.

4. **Market Tide & Order Flow Aggressiveness**:
   - Net Call Premium vs. Net Put Premium delta tracking directional momentum.
   - Ask-side volume ratio $\ge 70\%$ over rolling 5-minute intervals flags aggressive institutional buying urgency.

5. **Periscope Market-Maker Positioning (`wales.pdf`)**:
   - **Hedging Flow Direction & Pressure**: Dealers must rebalance $-\text{GEX} \times \Delta S$ in shares. In positive gamma, dealer hedging creates supportive buying on market dips; in negative gamma, dealer hedging forces accelerating selling and cascading liquidations.
   - **Defended vs Abandoned Walls**: When spot price breaks below the Put Wall, dealers abandon support and flip into aggressive underlying sellers, triggering unhedged breakdown conditions.
   - **0DTE Risk Pockets**: Outsized concentration of 0DTE OI ($\ge 35\%$ of total strike OI) near spot creates hyper-sensitive volatility pockets where delta rebalancing occurs with extreme velocity.

## Zero-Cost Engineering Mandate

- Never purchase or subscribe to paid retail flow APIs when the underlying financial mechanics are publicly documented and computable from free broker data.
- Compute option Greeks locally using standard Black-Scholes formulas in microseconds with zero network calls.
- Track political and insider transactions using free public government data (SEC EDGAR Form 4 and House/Senate STOCK Act disclosure portals).

