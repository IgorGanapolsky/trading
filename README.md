# SPY Iron Condor Trader

Paper-trading SPY iron condors to validate a quantitative options strategy before committing real capital.

> **North Star**: $6K/month after-tax options income.
> **Current Reality**: $95,324 paper equity (started $100K). Proving the edge on 30 trades.
> **Strategy**: 15-delta SPY iron condors, $10-wide wings, 30-45 DTE.

**[Progress Dashboard](https://igorganapolsky.github.io/trading/rag-query/)**

---

## How It Works

1. Check VIX and market conditions (block entry if VIX > 30 or data unavailable)
2. Open a 4-leg iron condor on SPY via Alpaca API
3. Monitor: close at 50% profit, 7 DTE, or 100% stop-loss
4. Record outcome, feed into GRPO learning model
5. Repeat

Execution: `scripts/iron_condor_trader.py`
Position management: `scripts/manage_iron_condor_positions.py`

---

## Risk Rules

- Max 5% risk per position ($5,000)
- Stop-loss at 100% of credit received
- Exit at 50% profit or 7 DTE
- Max 2 concurrent iron condors (8 legs)
- Max 2 new opens per day
- System halts if live price data or VIX unavailable

---

**Maintained by** [Igor Ganapolsky](https://github.com/IgorGanapolsky)
