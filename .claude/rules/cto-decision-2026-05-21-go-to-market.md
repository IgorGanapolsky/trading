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
