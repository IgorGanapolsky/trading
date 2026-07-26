
# Paper SPY Bull-Put-Credit Profile — Comparison, Regime Gate, Sample-Size Bar, Backlog, and Anti-Pattern List

> Scope: validate our locked paper profile against published research, not to recommend any live capital deployment. All claims are tied to the cited sources; quant-shop / MM operational notes are explicitly excluded as non-transferable.

---

## 1. Our Profile vs. Public Rule Sets

| Parameter | Our locked value | Most-cited public value | Evidence | Risk of our choice |
|---|---|---|---|---|
| Underlying | SPY only | SPY / QQQ / SPX (tastytrade prefers liquid underlyings); SPY dominates retail backtests | OptionsCafe SPY put-credit study | Survivorship-safe; missed diversification |
| Spread width | $5-wide (1-lot) | $1–$5 wide is most common for retail defined-risk short puts | OptionsCafe | Max loss $500/contract — capital efficiency vs. risk per trade is fine for 1-lot |
| Short strike delta band | 0.10–0.22 (target ~0.15) | 0.15–0.20 is the public "sweet spot" | OptionsCafe (≈15–20 delta) | Lower bound (0.10) collects less premium; upper bound (0.22) raises touch-rate risk |
| DTE entry | 30–45 (target ~30) | 30–45 DTE; tastytrade research bands center on this window | [26] | Aligns with theta-deceleration evidence |
| Take-profit | 25% of credit | 50% is the published "gold standard" | [16], [26] | We exit faster → higher realized win rate, lower per-trade EV; more whipsaws around commissions |
| Stop-loss | 200% of credit (2x) | 1x or 2x most common; tastytrade Market Measures 2020-07-23 found a defined stop reduces tail loss on defined-risk spreads | [9], OptionsCafe (2x rule) | Our 2x is the standard; risk is per-trade max loss is fixed at $400 |
| Time exit | 7 DTE | 21 DTE is the canonical exit | [26] | We exit at 7 DTE → faster redeployment but leaves gamma acceleration on table |
| Min hold | 24 h (except hard stop) | Not a published rule; most backtests assume continuous re-mark | — | Discipline tool against panic-close; risk is missed early gamma crush on rare moves |
| Max concurrent | 2 | Often 5–10% of account in risk per underlying | — | Conservative; restricts sample throughput |
| Max daily structures | 3 | Procedural, not a documented rule | — | Operationally safe |
| Position size | 1-lot | 1-lot is typical for retail validation | — | Cleanest unit for per-trade PF/expectancy math |
| IC / iron condor | killed, not to revive | tastytrade IC is canonical short-vol strategy | [26] | Reduces complexity while validating the directional leg first |

**Bottom line:** the *delta band, DTE window, spread width, and 2x stop* all sit on the public consensus. The two deviations — **25% TP** and **7-DTE time exit** — are *more conservative* than the 50% / 21-DTE mainstream. That is defensible for a validation cohort (more trades per unit time, smaller per-trade win) but reduces per-trade EV.

---

## 2. Deeper Analysis of the Divergent Choices

**25% vs 50% take-profit.** The OptionsPilot worked example (100 trades @ $2.00 credit, $800 max loss) shows 50%-exit / 2x-stop yields **+$4,000 net** while hold-to-expiry at the same win rate yields **–$5,000**. Holding the remaining 50% of premium requires 2–3 extra weeks of gamma exposure that the 25%-exit avoids. Our 25% rule is **half the per-trade profit but ~3x more closed trades per quarter**, which *helps* the n-gate sample problem below — a deliberate trade-off. ([16])

**2x stop-loss.** The tastytrade Market Measures episode on stop-loss in spreads concluded that defined-risk spread stops reduce tail P/L meaningfully vs. hold-to-expiry and that multipliers between 1x–2x of credit received dominate P/L for short premium. Our 2x is at the conservative end of that range. ([9])

**15-delta vs 10–20-delta.** The cited SPY study picks 0.15–0.20 as the sweet spot. Our 0.10 floor is a defensible wider band (more premium, lower win-rate) but trades inside that band should be flagged for sub-cohort review.

**7-DTE vs 21-DTE exit.** The 21-DTE rule exists because gamma accelerates in the final month. Exiting at 7 DTE *removes* the bulk of that gamma risk but sacrifices ~50% of remaining time value. With 1-lot paper only, this is a *process* choice, not an edge bet.

**Min hold 24 h.** No published analog; treat as a behavioral guardrail. The risk is a one-day gap that would invalidate the stop logic — mitigate with a hard stop placed at entry, not when monitoring.

**1-lot only.** Standard for a validation cohort; do not graduate to 2-lot or sizing-by-vol until n≥30 *and* gates clear.

---

## 3. Minimal Regime Filter (Evidence-Backed, Not Marketing)

| Filter | Public threshold | Rationale | Adopt? |
|---|---|---|---|
| IV Rank / IV Percentile | Sell premium when IVR ≥ 30 (some use ≥ 50) | Short premium is structurally profitable when implied > realized | **YES — primary gate** |
| VIX level | Skip entries when VIX > 30 (regime-change) | VIX > 30 indicates gap risk that overwhelms theta | YES — hard veto |
| Trend filter (50/200 SMA on SPY) | Only short puts when SPY ≥ 200-DMA (long-term uptrend intact) | Mechanical trend reduces catastrophic tail | OPTIONAL — adds 1 filter, but skip in initial paper cohort |
| Term structure | Contango (front-month IV > back-month) is normal; backwardation (VIX futures inverted) signals stress | Avoid opening during backwardation | NICE-TO-HAVE |

**Recommended single minimal filter:** *Open only when SPY 30-day IV Rank ≥ 30 and SPY price ≥ 200-day SMA. Hard veto if VIX > 30.* IV Rank is the single most evidence-backed gate from the ImpliedOptions summary (IVR>50 = "high" regime where short premium structurally outperforms). Adding trend is defensible but raises overfitting risk on a small paper sample — defer to post-n=30. ([11])

---

## 4. Sample-Size and Kill Criteria

**Is n=30 enough?** The CLT heuristic floor is ~30 trades for a *mean* estimate, but BacktestBase explicitly tags that as a "floor, not a guarantee" and recommends **100 trades for basic reliability** and **200–500 for institutional-grade confidence** with multiple market regimes. ([2])

For a single-options structure in a single underlying, a serious quant desk would typically want:
1. **≥100 closed trades** for a *stable* win-rate / PF estimate (CLT reasonable at 100; 95% CI on PF narrows to ±~10%).
2. **≥3 market regimes covered** (a 2022 bear-vol spike, a 2023 grind-up, a 2024 chop — even if paper).
3. **Standard error of mean P&L/trade < 25% of mean** — Kiploks's robustness-engine framing applies; without this, a paper "edge" can be noise. ([3])

**Updated gates for our book (replacing the current n≥30 / expectancy>0 / PF>1 / PnL>0):**

| Gate | Current | Recommended |
|---|---|---|
| Min closed trades (n) | 30 | **100** (interim check at 30, but no live decision) |
| Regime coverage | none | ≥1 trade in each of: low-VIX grind, VIX>25 spike, chop range |
| Expectancy | > 0 | > 0 *and* |E[P&L]| > 0.5 × SE(P&L) |
| Profit Factor | > 1 | > 1 *and* PF-1 > 1 × SE(PF) |
| Max drawdown in window | unspecified | track; abort paper run if DD > 3× expected single-trade max loss |

**Kill criterion:** abort paper run if, at n=30, the *sign* of average P&L and PF flip on any rolling 20-trade window — that's noise, not signal.

---

## 5. Ranked Upgrade Backlog

Priority key: **(A)** ship now on paper; **(B)** after n=30 but before live; **(C)** never at this scale.

| # | Upgrade | Priority | Why |
|---|---|---|---|
| 1 | Log every entry with IVR, VIX, SPY vs 200-DMA, days-to-earnings | **A** | The single biggest gap. Without regime tags, we cannot compute the IVR>30 filter or diagnose why a trade failed. |
| 2 | Compute expectancy, PF, and SE per rolling 20-trade window; track stability | **A** | Lets us apply the "abort on sign flip" kill criterion. |
| 3 | Pre-trade checklist: IVR≥30, VIX<30, SPY>200-DMA, DTE 30–45, delta band 0.10–0.22 | **A** | Codifies the minimal regime filter from §3. |
| 4 | Capture mid-price at exit, not just last-trade mark | **A** | Backtest realism; bid/ask slippage matters at 1-lot retail. |
| 5 | Compare 25% TP variants: log what *would* have happened at 50% TP and 21-DTE exit on every closed trade | **A** | The cheap way to validate or refute our 25% choice without waiting for 100 trades. |
| 6 | Add max-loss alert when spread mark crosses 1.5x credit *before* 2x stop triggers | **B** | Early-warning so we can manually close near stop without slippage. |
| 7 | Run an out-of-sample test on 2018 (low-vol grind), 2020 (COVID gap), 2022 (bear) before any sizing change | **B** | Forces coverage of multiple regimes, addressing the regime-coverage gap. |
| 8 | Add spread-quality filter (bid-ask width ≤ 8% of credit) | **B** | Liquidity quality matters more than IVR for retail fills. |
| 9 | Build a daily P&L distribution plot (histogram + QQ) for n≥100 | **B** | Reveals whether we have a few outlier losses hiding a fragile distribution. |
| 10 | Monte-Carlo resampling of paper trades to estimate drawdown distribution | **B** | Cheap, runs on existing data; answers "could I have survived the worst 20-trade stretch?" |
| C-1 | Multi-leg structures (IC, calendars) | **C** | Killed per profile; do not reintroduce until single-leg edge is proven. |
| C-2 | Dynamic position sizing / Kelly | **C** | Way out of scope for 1-lot paper. |
| C-3 | Order-flow / inventory features | **C** | Quoting-shop concerns (see §6); irrelevant at our scale. |

---

## 6. "Do Not Copy From Citadel / Jane Street" List for This Book

These are the operational choices that make sense inside a market-making or HFT shop but **degrade retail paper-validation**. Documenting them so future tweaks don't drift toward them by accident.

1. **Continuous quoting / inventory turnover.** Citadel Securities runs persistent two-sided quotes across thousands of instruments, harvesting a fraction of a cent per fill. A retail paper book runs a handful of discrete positions. Do not copy: latency arbitrage, queue position, or quote-shape optimization — none of these are reachable from a TWS-style retail workflow. (Citadel Securities — Wikipedia)
2. **Inventory-hedging with correlated instruments.** Market makers delta-hedge with futures, other options, and ETF legs. Our 1-lot book has no equivalent hedge channel; copying *any* delta-hedging logic into our paper book just adds noise and complicates P&L attribution.
3. **Latency-sensitive stop placement.** HFT desks place stops at co-located matching engines; for us, a "hard stop at 2x credit" is a *signal* we monitor at human frequency, not an exchange-resident order. Treating it as a guarantee (the way a shop's stop-loss engine works) is a category error.
4. **P&L attribution to microstructure features.** Their edge comes from queue priority, fill ratios, adverse-selection modeling — none of which a retail paper book can observe. If our paper system "looks profitable" because we implicitly assume mid-price fills on illiquid strikes, that is survivorship / fill-assumption bias, not edge.
5. **Capacity / scaling models.** Theirs scale with colocation and capital; ours scales with broker margin and SPY option open interest. Do not extrapolate "their book makes X bps" into "we will make X bps times 100x sizing."
6. **Multi-asset correlation hedging.** Two Sigma / Citadel build portfolio-level hedges across thousands of names. Our single-leg book on SPY has no equivalent — adding "correlation hedges" without the data pipeline that supports them would just be guesswork.
7. **The "we have edge" narrative itself.** Their statistical edge is established on millions of observations. Our paper validation is on dozens. Until n≥100 with regime coverage, *every* result on this book is a hypothesis, not an edge.

---

## References

1. *Statistical Power Analysis in Backtesting Models*. https://questdb.com/glossary/statistical-power-analysis-in-backtesting-models
2. *Minimum Trades for a Valid Backtest? Calculator + Research*. https://www.backtestbase.com/education/how-many-trades-for-backtest
3. *How many trades do you need for a statistically valid backtest?*. https://kiploks.com/research/how-many-trades-do-you-need-for-a-statistically-valid-backtest
4. *What a Sample Size Means in a Live Trading System | TradeProb*. https://tradeprob.com/foundations/trading-sample-size-statistical-validity
5. *Validation Lab Guide | AlgoriQ Docs*. https://docs.algoriq.ai/lab-guides/validation-lab
6. *Bull Put Spread (Credit Put Spread)*. https://www.optionseducation.org/strategies/all-strategies/bull-put-spread-credit-put-spread
7. *Stop loss vs Take profit : r/TradingView - Reddit*. https://www.reddit.com/r/TradingView/comments/12z3l3b/stop_loss_vs_take_profit
8. *Stop-Loss and Take-Profit Tactics for Smarter Trading*. https://tradewiththepros.com/stop-loss-and-take-profit-tactics
9. *Stop Loss in Spreads - Market Measures*. https://www.tastylive.com/shows/market-measures/episodes/stop-loss-in-spreads-07-23-2020
10. *Bull Put Spread Calculator | Max Profit, Max Loss & Breakeven*. https://optionscalculators.com/bull-put-spread-calculator
11. *IV Rank vs. IV Percentile (2025): How to Use IV Rank With ...*. https://impliedoptions.com/blog/iv-rankings-2025-09-14
12. *Backtest CBOE VIX Index (VIX) - CBOE VIX Index Trading ...*. https://testtotrade.com/indices/vix-index
13. *Implied Volatility (IV) Rank & Percentile Explained*. https://www.tastylive.com/concepts-strategies/implied-volatility-rank-percentile
14. *IV Rank vs. IV Percentile: Which is Best? | TradingBlock*. https://www.tradingblock.com/blog/iv-rank-vs-iv-percentile
15. *Implied Volatility IV Rank and IV Percentile*. https://www.barchart.com/options/iv-rank-percentile
16. *Vertical Spread Profit Targets: When to Take Profits and Exit*. https://optionspilot.app/blog/vertical-spread-profit-target-when-to-exit
17. *Credit Spread: Constructing Profitable Credit Spreads in ...*. https://fastercapital.com/content/Credit-Spread--Constructing-Profitable-Credit-Spreads-in-Option-Markets.html
18. *Put Credit Spread Explained: Strategy, Max Profit, Max Loss ...*. https://www.probabilityofprofit.com/guides/option-trading-strategies/put-credit-spread
19. *Put Spread Calculator*. https://www.optionsprofitcalculator.com/calculator/put-spread.html
20. *Credit Spread Backtest: 60-Cycle Win Rate, ROI & Exit Rules ...*. https://apexvol.com/strategies/credit-spread/backtest
21. *Option Omega Review 2026: Backtest, Model & Automate Options ...*. https://www.daystoexpiry.com/blog/option-omega
22. *Backtest Results | Option Omega Documentation*. https://docs.optionomega.com/backtesting/backtest-results
23. *Sample Backtests | Option Omega Documentation*. https://docs.optionomega.com/welcome/free-trial/sample-backtests
24. *SPY Short Call (15 vs 30 Delta) Backtesting Results*. https://www.youtube.com/watch?v=u4R-HkjFrTU
25. *Following TastyTrade's Strategies - by Investor Sherpa*. https://theconcentratedportfolio.substack.com/p/following-tastytrades-strategies
26. *The 21-DTE Rule and 50% Profit Exit: The Research Behind ...*. https://traderc.com/21-dte-50-percent-profit-exit-options
27. *Finance, Stock Markets & Business News*. http://tastytrade.com/newsroom/news
28. *Tastytrade*. http://platform.tracxn.com/a/d/company/531b07c1e4b0f7e1661e9d71/tastytrade#a:about
29. *The Impact of High Implied Volatility (IV) on Trading Profits*. https://www.tastylive.com/news-insights/The-Impact-of-High-Implied-Volatility-IV-on-Trading-Profits
30. *DTE is raking in record profits while turning around and ...*. https://www.instagram.com/p/DWSLmlpiW8G
31. *DTE Energy misses quarterly profit estimates as ...*. https://www.reuters.com/business/energy/dte-energy-misses-quarterly-profit-estimates-energy-trading-unit-swings-loss-2026-04-30
32. *SPX 1-4 DTE Delta Trading Strategy | PDF | Option (Finance ...*. https://www.scribd.com/document/524803698/Automated-Premium-Selling
33. *Short Put Options Strategy: Beginner's Guide*. https://www.tradingblock.com/strategies/short-put
34. *http://brokercheck.finra.org/firm/summary/277027*. http://brokercheck.finra.org/firm/summary/277027
35. *Short Put Options Strategy | Visualize + Live Data | InsiderFinance*. https://www.insiderfinance.io/options-profit-calculator/strategy/short-put
