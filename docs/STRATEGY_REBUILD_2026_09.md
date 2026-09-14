# Strategy rebuild — Sept 2026 (AGENT-616)

**North Star:** `$6,000/month after-tax` ≈ `$300,000` capital @ ~`2.0%/mo`
(`src/core/trading_constants.py`).

**Rule #1 (Buffett / Phil Town):** do not lose money. Defined risk only. Live
capital stays **blocked** until paired cohort gates clear.

## What the books already proved (local ledger)

| Family                          |   n |    WR |   PF | Expectancy | Realized |
| ------------------------------- | --: | ----: | ---: | ---------: | -------: |
| iron_condor (killed)            | 161 | 13.7% | 0.17 |    −$47.59 |  −$7,662 |
| spy_put_credit (legacy profile) |   3 |  100% |  n/a |       +$25 |     +$75 |
| Live equity                     |   — |     — |    — |          — |   **$0** |

Paper P/L is not revenue. IC is dead. Put-credit n=3 is not edge.

## Sept 2026 external research (Parallel.ai out of credit — free rails)

| Finding                                                                                                          | Source (dated)                                     | Action                                  |
| ---------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | --------------------------------------- |
| High WR ≠ edge; 0DTE IC won ~75% and still lost (fills)                                                          | OptionKrafter 2026-09-09                           | Forbid 0DTE / IC entries                |
| IC buys the richest OTM puts (eats variance premium)                                                             | CI Volatility 2026-02; Sharpe Two 2026-08-31       | Keep IC killed                          |
| Under **realistic fills**, only ~**60 DTE** SPY put-credit stayed positive across 7/14/30/45/60 arms (2013–2025) | OptionKrafter 2026-08-10 (rev 2026-08-23)          | Default target **60 DTE**, band 45–70   |
| Trade less → keep more (spread crossings kill fast arms)                                                         | Same                                               | `max_daily=1`, `max_concurrent=1`       |
| Professional premium-seller rulebook: 30–60 DTE, Δ 0.15–0.30, TP ~50% credit, stop ~2× credit                    | The Option Premium 2026-04/09; StrikeWatch 2026-03 | TP **50%**, stop **200%**, Δ **0.15**   |
| Position size 1–3% of equity for defined risk                                                                    | tastytrade sizing; PurePower 2026-07               | Cap max loss at **1% equity**           |
| Buffett put selling = only at prices you’d welcome owning; assignment ok                                         | Rule #1 Investing 2026-04                          | Require SPY **≥ 200-DMA** for bull puts |

## Winning strategy we implement (paper)

Profile: **`spy-put-credit-buffett`** (new default).

| Knob               | Value                                         |
| ------------------ | --------------------------------------------- |
| Structure          | SPY bull put credit, **$5** wide, **1-lot**   |
| DTE                | target **60**, band **45–70**                 |
| Short delta        | **0.15** (band 0.10–0.20)                     |
| Take profit        | **50%** of credit                             |
| Stop               | **200%** of credit                            |
| Time exit          | **30 DTE** remaining (~half life)             |
| Concurrent / daily | **1 / 1**                                     |
| Regime             | VIX ≤ 30; SPY ≥ 200-DMA (hard); IVR soft      |
| Risk budget        | max loss ≤ **1%** equity                      |
| Live               | **blocked** until n≥30, expectancy>0, PF>1.05 |

Legacy profile `spy-put-credit` remains in the registry for journal replay only.

## What we will not do

- Revive iron condors / 0DTE gambling / multi-lot before gates
- Claim profitability from n&lt;30 or paper equity
- Deploy live capital while Field equity is $0 and edge unproven

## Verification

```bash
python -c "from src.core.trading_profiles import get_put_credit_profile; print(get_put_credit_profile().name)"
python scripts/audit_active_scope.py --json  # if present on branch
pytest tests/test_buffett_rebuild.py tests/test_put_credit_regime.py tests/test_active_strategy.py -q
```
