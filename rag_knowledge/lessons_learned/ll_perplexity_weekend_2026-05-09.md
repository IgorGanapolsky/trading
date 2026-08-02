# Perplexity Trading Intel: weekend

- Generated UTC: `2026-05-09T14:23:16.981050+00:00`
- Recommendation: `BLOCK_NEW_IC`
- Risk score: `0.8`
- Confidence: `0.75`
- API status: `ok`
- Gate reason: Fresh Perplexity event/regime risk score 0.80 blocks new IC entries.

## Query Findings

### iron_condor_research
- Risk score: `0.92`
- Summary: ### SPY/SPX Iron Condor Rules: Evidence Summary  **Core Setup Rules (Supported by Historical Data):** - **Short Strikes: 10-20 Delta.** Targets 75-90% POP per side. Balanced 15-20 delta yields 65-70% unmanaged win rate; 10-16 delta conservative (84-90% POP, lower premium $0.80-1.20). Citation: [1] ApexVol Iron Condor Guide (realized win rates from 30-45 DTE SPY setups). - **DTE: 30-45 Days.** Optimal for theta decay balance vs. gamma risk. Shorter DTE increases gamma exposure; longer dilutes premium. Citation: [1]. - **Spread Width:** $5 (e.g., SPY $450: Put $440/$435, Call $460/$465). Max loss = width - credit (e.g., $350 after $1.50 credit). Citation: [1] SPY example.  **Management Rules (...

### strategy_failure_patterns
- Risk score: `0.68`
- Summary: # Risk Intelligence: Iron Condor Failure Modes – High-Volatility Regime  ## Hard Blockers for New Entry  **Your account signals defensive gate for reason:** - Win rate 23.19% + profit factor 0.22 = severe edge erosion - Negative expectancy (-$57.36/trade) across 69 closed trades - Current 7 open positions in drawdown state  **Do not scale into new iron condors under these conditions.** Scale lock is active.  ---  ## Regime-Specific Failure Pattern: The Path-Risk Wedge  **Source:** ArXiv 2604.19604 – empirical derivatives parity study (SPX/RUT European options)  ### Core Finding: Implementation Gap ≠ Price Gap  - **Parity residuals appear small in price space** (~0 bp vs. futures) - **But car...

## Citations
- https://apexvol.com/strategies/iron-condor
- https://arxiv.org/html/2604.19604
- https://finance.martinsewell.com/stylized-facts/volatility/
- https://articles.stockcharts.com/article/week-ahead-nifty-not-yet-out-of-the-woods-deal-with-upticks-in-this-manner/
