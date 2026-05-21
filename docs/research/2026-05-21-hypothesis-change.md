# Hypothesis Change for the Next 30-Trade Validation Cohort

**Authored:** 2026-05-21. Supersedes any prior implicit hypothesis. Tied
to `.claude/rules/controlled-experiment.md` and `.claude/rules/kill-criteria.md`.

## 1. Why a written change is required

The May-19 edge audit (`docs/research/2026-05-19-edge-analysis-DEEPER.md`)
tested 39 conditional cells with Wilson-CI + Bonferroni correction. **Zero
survived at α=0.05.** The minimum adjusted p-value was 0.529. The strongest
in-sample signal (Thursday × 31-45 DTE: n=9, 55.6% win rate, +$3.78 expectancy)
was retired in PR #4037 because its point estimate (55.6%) is _below_ the
realized break-even win rate (58.1% given avg_win $70.50 / avg_loss $97.81).

The kill-criteria rule forbids resuming entries without a written hypothesis
change. This document is that change.

## 2. The audit's diagnosis of _why_ we have no edge

Three structural findings, not in-sample slices:

1. **53/69 trades closed in < 24 h.** Strategy collected almost no theta;
   the realized hold distribution was incompatible with a premium-selling
   thesis. Already fixed in `.claude/rules/controlled-experiment.md` with
   the 24-h minimum hold. _The new cohort will not resemble the historical
   ledger because of this single rule._

2. **avg_win ($70.50) < avg_loss ($97.81).** Even at 80% win rate the
   strategy bleeds unless the loss tail compresses. Break-even win rate is
   58.1% — every cohort with avg_loss > avg_win must clear that bar.

3. **The ledger never recorded VIX, IV rank, regime, or momentum at entry.**
   The factors most likely to discriminate winners from losers were
   invisible to the audit. Any future audit using only the historical
   ledger will be equally thin.

## 3. The hypothesis change

**Single, written, testable change** (per controlled-experiment.md rule):

> Enter iron condors **only when the IV-rank proxy at entry is ≥ 30**
> (already enforced by `MIN_IV_RANK_FOR_CREDIT` in `src/risk/trade_gateway.py`),
> hold to **50% of max profit** (instead of the prior 25-50% range), with
> a **24-h minimum hold** (enforced in `src/strategies/iron_condor/ic_simple.py`),
> on **SPY only**, with **1-lot per entry** (enforced by
> `MAX_CONTRACTS_PER_TRADE=1` after PR #4034), at **15-20 delta short
> strikes**, **30-45 DTE**, **$10 wing width**.

**Why this set:**

- The 50% profit target (vs 25%) targets a higher avg_win, attacking
  finding #2 directly. Realized avg_win must move from $70.50 toward
  > $98 for the strategy to break even at the realized loss tail.
- The IV-rank gate ensures we only enter when premium is rich enough to
  pay for the realized risk. This factor was always nominally enforced
  (`MIN_IV_RANK_FOR_CREDIT=30`) but never recorded post-hoc in the
  ledger; the next cohort will record it.
- The 24-h minimum hold + 1-lot + SPY-only are not new (they are the
  controlled-experiment baseline). They are listed for completeness so
  the hypothesis is _complete_.

**What is explicitly NOT in the hypothesis:**

- Day-of-week filter (retired 2026-05-20, Bonferroni adj_p=0.190).
- Calendar-month filter, week-of-month filter, hold-time-bucket filter.
- Sequence/lag-1 conditioning on prior outcome.

## 4. Ledger enrichment (shipped this PR)

Each entry persisted to `data/ic_entries.json` now records a
`market_snapshot` block:

| Field            | Source                                            | Use                 |
| ---------------- | ------------------------------------------------- | ------------------- |
| `vix_level`      | `src/signals/vix_mean_reversion_signal.py`        | regime conditioning |
| `vix_3day_ma`    | same                                              | regime trend        |
| `vix_percentile` | same (best-effort)                                | IV regime           |
| `iv_rank_proxy`  | `src/markets/iv_rank.py` (VIX 52w pct)            | IV regime           |
| `spy_price`      | `get_underlying_price()` (Alpaca live mid)        | level conditioning  |
| `spy_5d_return`  | `src/markets/spy_momentum.py` (Alpaca daily bars) | short momentum      |
| `spy_20d_return` | same                                              | long momentum       |
| `weekday`        | `datetime.now(UTC).weekday()`                     | already in audit    |

Each block is **best-effort**: a missing data source records `null` for
that field but does not block trade persistence. Auditors must filter on
completeness before conditioning on a factor.

## 5. Kill criteria (unchanged from `.claude/rules/kill-criteria.md`)

The new cohort is killed if **any** of:

1. Expectancy ≤ 0 over 30 closed validation trades.
2. Profit factor ≤ 1.0 over 30 closed validation trades.
3. Win rate below the realized break-even level (58.1% as of this audit;
   recompute each kill check).
4. 3 consecutive max-loss stops in the validation cohort.
5. Account drawdown exceeds 10% from validation start
   ($93,723 → below $84,351).

The 69 historical trades are training data and are _not_ counted toward
this cohort's kill gating.

## 6. Honest expected outcome

The null hypothesis is **no edge**. Even with the structural change, the
cohort's expected expectancy is _unknown_. The realized break-even win
rate (58.1%) is high; the historical aggregate (23.2%) is far below it.
A change in the profit target moves avg_win and avg_loss simultaneously
— there is no guarantee it shifts the win/loss ratio favorably without
real data.

This document is a hypothesis to test, **not a claim of edge**. If the
cohort kills under any criterion in §5, the answer is structural
redesign (path b in the May-19 audit recommendation), not another
hypothesis spin. If the cohort passes, the result is grounds to consider
careful scale-up, not a guarantee of future returns.

## 7. What this does NOT do

- Does not unblock live trading. Live brokerage stays at $0 until 30
  paper trades validate the hypothesis.
- Does not change `MAX_CONTRACTS_PER_TRADE` (still 1).
- Does not remove the TradeGateway, kill-switch, or magic-word override.
- Does not promise the North Star is reachable. The North Star pivot
  ([[project_north_star_pivot_b2b_guardrail_saas]]) remains: the
  guardrail layer is the revenue path, trading is the demo + research
  lab.
