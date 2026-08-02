# Perplexity Trading Intel: weekend

- Generated UTC: `2026-05-02T14:19:02.137529+00:00`
- Recommendation: `BLOCK_NEW_IC`
- Risk score: `0.935`
- Confidence: `0.75`
- API status: `ok`
- Gate reason: Fresh Perplexity event/regime risk score 0.94 blocks new IC entries.

## Query Findings

### iron_condor_research
- Risk score: `1.0`
- Summary: # Iron Condor Rules: Current Evidence & Backtesting Requirements  ## Hard Blockers from Your Current State  **Your system shows critical regime misalignment:** - Win rate 23.88% vs. baseline 65-70% suggests either delta selection drift, poor event timing, or VIX regime mismatch[1] - Profit factor 0.24 with -$54.76 expectancy per trade indicates rules are not being followed consistently or market conditions have shifted - **Scale blocked + validation reset mode:** Do not increase position sizing until these rules are systematically verified  ---  ## Validated Rules (Cite Before Live Use)  ### Strike Selection: 15-20 Delta Short Strikes **Rule:** Sell 15-20 delta on both put and call sides for...

### strategy_failure_patterns
- Risk score: `0.87`
- Summary: **Hard blockers for 100k paper SPY/SPX iron condor entry pre-high-vol regime shift:** Block if **IV skew shows elevated put IV** (downside fear), **ATM volatility smile** indicates expansion risk, or **high IV persists without event resolution** (overtrading trap).[1]  **Contextual blockers (monitor, not absolute):** - **Historical IV over-reliance** without current news/events (e.g., policy, earnings); forward-looking IV misleads in shifts.[1] - **Unresolved vol spikes** where realized > implied (e.g., VIX spikes persist, short gamma chops).[4] - **Gap patterns** like "gap and fail" in SPX/SPY (post-gap no follow-through signals reversal).[5]  **Failure patterns in short premium during vol...

## Citations
- https://apexvol.com/strategies/iron-condor
- https://learn.eminiethan.com
- https://marketchameleon.com/Overview/PDD/Summary/
- https://www.shareindia.com/knowledge-center/algo/top-7-mistakes-traders-make-when-analysing-iv-in-the-option-chain
- https://journalplus.co/journal/spx-index-options
- https://arxiv.org/html/2604.02743v2
