# CTO Decision — 2026-05-21 — Go-to-Market

Authored by Claude (CTO) under explicit autonomous delegation. CEO question:
"Are we selling this as SaaS — do we have a competitive advantage, is the copy
clear, will people pay?" Source data and market research are cited; no projections.

## 1. Verified internal state

- **Trading** (`data/trades.json`, `data/system_state.json`): 69 closed iron
  condors, 23.2% win rate, profit factor 0.22, realized **−$3,958**, equity
  $94,966 (−5.03%). No statistically robust edge — `docs/research/2026-05-19-edge-analysis.md`
  shows the Thursday slice fails Bonferroni correction (adj_p 0.190, K=39).
- **SaaS**: external-customer Stripe revenue **$0.00** (`cto-decision-2026-05-19.md`
  §3.6). Outbound reply→close conversion **0/14**. 32 `ai_revenue*` directories,
  only 2 real repos.

## 2. Market research (2026-05-21, cited)

- The AI trading-bot market is real and paying: ~$3.1B revenue in 2025;
  TrendSpider $107–447/mo, TradeAlgo $49–199/mo, Composer ~$40/mo. **But** the
  field is crowded with funded incumbents and most retail bots underperform.
- "Guardrails for autonomous agents" is a hot, funded category — WitnessAI
  raised $58M; AI policy-enforcement attracts the largest checks. **But**
  Galileo has already **open-sourced** an agent-guardrails control plane and
  OpenAI is acquiring Promptfoo. The generic guardrail layer is being
  commoditized and capitalized at enterprise scale simultaneously.

## 3. Decision — DO NOT launch or market a SaaS now

1. **No product.** The trading strategy loses money; you cannot sell access to
   negative expectancy. The guardrail layer is a feature, not a packaged
   product, and the repo is public — there is nothing to charge for.
2. **No wedge.** Both candidate categories are owned by funded incumbents —
   trading bots (TrendSpider / TradeAlgo / Composer / AriseAlpha) and agent
   guardrails (Galileo open-source + WitnessAI $58M). A solo operator with a
   public repo and $0 revenue has no defensible entry in either.
3. **The data already returned a verdict.** 0/14 reply→close and $0 external
   revenue is not a copywriting problem — it is the market saying "no product."
   Better marketing on a non-existent product is theater.

## 4. What we do instead

- **Focus 100% on the 30-trade validation** (`controlled-experiment.md`). It is
  the one effort with a defined finish line and a possible real asset.
- **The only thing that monetizes for a solo operator here is a verified track
  record** — a real, audited edge. Not a tool, not a course, not signals. If the
  validation produces expectancy > 0 over 30 clean trades, *that* is sellable.
  Until then there is nothing to sell.
- **Consolidate the sprawl**: archive the 30 orphan `ai_revenue*` dirs per
  `cto-decision-2026-05-19.md` §3.2. Stop spreading effort across dead repos.
- **Kill condition**: if the 30-trade validation fails the `kill-criteria.md`
  gate, the honest conclusion is that this is not a business — stop investing
  effort; do not pivot to a SaaS in a category we have no edge in.

## 5. Direct answers to the CEO's three questions

- **Competitive advantage?** No — losing strategy, commodity infra, public repo,
  no moat.
- **Is the copy clear?** No — and fixing the copy is not the binding constraint.
- **Will people pay?** The data says no ($0 external revenue, 0/14 close). People
  pay for a *proven track record*, which we do not yet have.

## 6. A/B + pressure test of the two paths (2026-05-21)

CEO requested a head-to-head stress test of the candidate paths.

- **Path A — Prove the trading edge.** Run the 30-trade validation; if expectancy
  turns positive, monetize a verified track record.
- **Path B — Guardrail / agent-governance SaaS.** Productize the risk-gate layer.

### Pressure test — Path A

- Structural tailwind exists: retail research shows option *selling* (net-credit)
  is the structurally profitable side — naked sales ≈ +20% avg return, option
  *buying* ≈ −4%. Iron condors are net-credit premium selling, so the strategy
  family is on the right side.
- ...but this implementation has destroyed that tailwind: 69 trades, 23.2% win
  rate, −$3,958. The edge has to be rebuilt, not just resumed.
- Base rate is low: ~9% of retail F&O participants are profitable over a full
  year (India regulator data); single-digit to low-double-digit across studies.
  Prior P(durable edge exists) ≈ 10–15%.
- Monetization friction is HIGH at the revenue stage: managing outside money or
  advertising performance triggers the Investment Advisers Act, the SEC Marketing
  Rule (performance must be substantiated, net-of-fees, non-misleading), fiduciary
  duty, Reg BI — registration and ~12–24 months before a dollar.
- BUT the *next step* — the paper validation — has ~$0 cost, zero regulatory
  friction, and a defined kill gate. Failure is cheap and contained.

### Pressure test — Path B

- The category is real and hot but commoditized and capitalized simultaneously:
  Galileo open-sourced an agent-guardrails control plane (free competitor),
  WitnessAI raised $58M (funded competitor), OpenAI is absorbing Promptfoo.
- A solo operator with a PUBLIC repo and a commodity capability has no wedge and
  no moat. The buyer pool for trading-agent-specific guardrails is tiny.
- Failure mode: build and market a product, nobody pays → months of effort sunk.
  Expensive and uncontained.

### Scorecard

| Dimension | Path A (prove edge) | Path B (guardrail SaaS) |
|---|---|---|
| Core assumption supported | Weak but testable | No — incumbents own it |
| Cost of the next step | ~$0 (paper + time) | High (build + market) |
| Resolves the central uncertainty | Yes — binary kill gate | No |
| Moat if it works | Yes — audited track record | None — public, commodity |
| Failure cost | Low / contained | High / sunk |
| Regulatory friction at revenue | High, but downstream | Low |
| Verdict | **PURSUE (next step only)** | **REJECT** |

### Best path — verdict

**Path A, scoped strictly to: run the 30-trade validation to its
`kill-criteria.md` decision gate, and spend nothing on monetization, product, or
marketing until it returns.**

The validation is a cheap option that resolves the one question gating
everything — "is there an edge at all?" — at near-zero cost and zero regulatory
friction. Path B demands expensive, irreversible commitment into a market with no
wedge: negative expected value. Doing both halfway is exactly what produced the
current −$3,958 and $0 revenue.

This is not a go-to-market plan. It is the recognition that the go-to-market
question is downstream of, and contingent on, an experiment that has not yet
returned. Resolve the experiment first.
