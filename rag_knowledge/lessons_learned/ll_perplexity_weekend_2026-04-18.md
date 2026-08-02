# Perplexity Trading Intel: weekend

- Generated UTC: `2026-04-18T14:14:24.077673+00:00`
- Recommendation: `BLOCK_NEW_IC`
- Risk score: `1.0`
- Confidence: `0.67`
- API status: `ok`
- Gate reason: Fresh Perplexity event/regime risk score 1.00 blocks new IC entries.

## Query Findings

### iron_condor_research
- Risk score: `1.0`
- Summary: ### SPY/SPX Iron Condor Rules: Evidence Review  **Core Rules Evaluated (10-20 Delta, 30-45 DTE, 50% Profit Exit, 2x Credit Stop, Event Avoidance, VIX Regime Filters)**   Evidence from options trading studies (2018-2025) supports these as standard short premium strategies for SPX/SPY iron condors, emphasizing theta decay in range-bound regimes. Hard blockers: Negative expectancy (-54.76) and low win rate (23.88%) in your context indicate poor edge—**scale_allowed=false** and **verified_edge_available=false** block live scaling. All rules require backtesting in your SPY/SPX paper system before live use due to regime-specific decay (e.g., post-2022 vol spikes).  #### 1. **Deltas: 10-20 per Shor...

### strategy_failure_patterns
- Risk score: `1.0`
- Summary: **Hard blockers for a ~100k paper account entering new SPY/SPX iron condors during high-volatility regime shifts:** Block if **profit_factor < 0.5**, **win_rate < 30%**, **expectancy_per_trade < 0**, or **verified_edge_available = false**—current context shows 0.24 profit_factor, 23.88% win_rate, -54.76 expectancy, and no verified edge, indicating systemic underperformance consistent with short premium strategy failures in vol spikes.[2][3][4]  **Key failure patterns in high-vol regimes for short premium index options (e.g., iron condors):** - **Volatility clustering and surprise spikes:** Realized vol forecasts improve with options-augmented models (e.g., HAR-RV-RHeston), but short premium...

## Citations
- https://arxiv.org/html/2604.02743v2
- https://journalplus.co/journal/spx-index-options
- https://youngandcalculated.substack.com/p/why-so-many-quant-funds-blow-up
