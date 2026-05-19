# CTO Decision — 2026-05-19

Authored by Claude (CTO) under explicit autonomous delegation. Source data is cited; no projections.

## 1. Account state (verified)

`data/system_state.json` (mtime 2026-05-19T19:02 UTC):

- Equity: **$94,966.31** (start $100,000 → drawdown **-5.03%**)
- Cash: $102,655.31
- Open positions: 8 option legs across 2 ICs
  - SPY 2026-06-12 IC, **1-lot** — compliant with `.claude/rules/controlled-experiment.md`
  - SPY 2026-06-18 IC, **50/51-lot** — **violates the 1-lot rule** in the same file
- Closed trades (paired): **69**, win rate 23.19%, profit factor **0.22**, expectancy **-$58.78/trade**, realized P/L **-$3,958**
- Validation cohort since 2026-04-09: **3 closed, 0 wins, -$556**

## 2. Kill-criteria status (`.claude/rules/kill-criteria.md`)

| Condition | Threshold | Current | Verdict |
|---|---|---|---|
| Expectancy ≤ 0 over 30 validation | 30 | 3 | n/a yet |
| Profit factor ≤ 1.0 over 30 validation | 30 | 3 | n/a yet |
| Win rate below break-even | 30 | 3 | n/a yet |
| 3 consecutive max-loss stops | n | 0 in cohort | not triggered |
| Drawdown > 10% from validation start | $93,723 floor | $94,966 | **inside the limit by $1,243 (1.3%)** |

Formal kill gate has not fired (sample too small). All-time data (n=69) however shows a strategy with PF 0.22 and negative expectancy. "Sample too small to kill" is not the same as "we have edge."

## 3. Decisions

### 3.1 Trading — REDESIGN, do not scale

- **Block any *new* iron-condor entries** until a written hypothesis change is committed (see `.claude/rules/controlled-experiment.md`: "No same-expiry re-entry after a loss" + "Pass only if realized expectancy > 0").
- **Keep existing positions running to natural exit.** Closing positions outside the guardian workflow is a hard-block per `.claude/rules/boundary-policy.md`; we do not touch them.
- **Add `MAX_LOT_SIZE = 1` enforcement** to `src/risk/trade_gateway.py` so the next entry cannot replicate the 50-lot 06-18 IC. The 50-lot exists from before the controlled-experiment rule was in force; we let it expire / be managed but never repeat it.
- **Write a new hypothesis** before un-blocking entries. Candidate (from prior RAG lesson): *Thursday-only entries showed historical 60% win rate vs <20% Mon/Tue/Fri across 69 trades. Restart 30-trade validation with Thursday-only entries.* This is a hypothesis, not a claim of edge.

### 3.2 SaaS revenue — consolidate to ONE repo, archive 31

Filesystem audit of `~/workspace/git/igor/`:

- 32 `ai_revenue*` directories total. **Only 2 are real git repos with GitHub remotes:**
  - `ai_revenue28` → `IgorGanapolsky/ai_revenue28` (last activity 2026-05-17, has `.git`, has `business_os`, has Stripe-adjacent scripts)
  - `ai_revenue31` → `IgorGanapolsky/AutoGemini-Boilerplate` (folder is misnamed; it's a different project)
- The other 30 are orphan local directories with no remote, no commits, ~1.5 GB total disk.
- The canonical revenue-state memory file (`~/.openclaw/memory/current-revenue-state.md`) references paths like `ai_revenue18/scripts/gumroad_publish.py` and `site/api/webhook.py` that **do not exist on this disk** — that memory is stale.

**Decision: `ai_revenue28` is the canonical SaaS repo going forward.**

- Rename the 30 orphan local dirs `ai_revenue_ARCHIVED_<original>` (or tar them to a single archive and remove) — recommendation; not auto-executed because it's irreversible. Awaiting CEO `yes` to physical delete.
- `ai_revenue31` is mislabeled and should be renamed to `~/workspace/git/igor/AutoGemini-Boilerplate` to match its remote.
- Update the canonical revenue-state memory file to point at `ai_revenue28` and remove stale references to ai_revenue18.

### 3.3 Security incident — token rotation required

Found a GitHub personal-access token (`ghp_…wcdP…`) hardcoded in `.git/config` of two local repos. Token stripped from both files this session. **CEO must rotate the token at https://github.com/settings/tokens** — it has been on disk in cleartext for an unknown duration and may be in shell history.

### 3.4 Moat — current state is broken; concrete fix

- `trading` repo is PUBLIC. Description: "Paper-first SPY options validation platform with broker-backed scorecards, hard risk gates, paired-trade accounting, and live dashboards." There is no proven edge, so public is acceptable today; the moment expectancy > 0 over 30 trades, **make the strategy files private** (move ML/GRPO/signal code to a private companion repo `trading-core`).
- Of 30 GitHub repos, only 3 are private: `lucid-xr`, `skool_top1percent`, `ThumbGate-Core`. **Public `ThumbGate` + private `ThumbGate-Core` competes with itself.** Fix: rewrite `ThumbGate` README to "open-core demo only; the productized version is private and sold via Stripe link X" and prune ThumbGate's public source to a minimum demo subset.
- Public `claude-ops-starter` and `ai-ops-side-business` directly undercut the $49 / $99 / $499 Claude-ops offers. Either privatize them, or accept they are intentional lead-gen and refactor them to be obviously inferior to the paid pack.

### 3.5 Observability — 3 patches in order

Implement in `ai_revenue28` (the survivor repo):

1. **UTM tags on every outbound link.** Update the cold-email link generator to append `?utm_source={lead.vertical}&utm_medium=cold-email&utm_campaign={campaign_id}&utm_content={lead.id}`. Cost: 1 helper function.
2. **Stripe failure-path webhooks.** Add `checkout.session.expired` and `payment_intent.payment_failed` handlers next to the existing `checkout.session.completed` handler. Write rows to `analytics_events` so abandonment is queryable.
3. **One pageview pixel** (PostHog free tier or Plausible) on the 3 Stripe-link landing pages + the Gumroad page. PostHog free tier covers our traffic.

Cost: ~2 hours of focused work. Do not skip — without this, the 0% close rate has no diagnostic.

### 3.6 "Are we making money?" — for the record

- **Trading: NO.** Realized -$3,958 over 69 trades; equity drawdown 5.03%; 1.3% away from kill floor.
- **SaaS: NO.** Stripe lifetime external-customer revenue $0.00. The ~$159 in Stripe history is 100% founder self-purchase and should not be cited as revenue.
- Outbound is healthy (deliverability 100% on the latest batch). The break is reply→close conversion at 0/14.

### 3.7 Out-of-scope drift detected and reverted

- `scripts/record_account_to_rag.py` had an uncommitted addition importing `PromoterAgent` and calling `broadcast()` on gain detection. This violates the Simplification Mandate ("Public publishing surfaces are archived") and would also be misleading given the account is currently at -$5,034 P/L. Reverted in PR (linked at session end).

## 4. North Star — recalibrated, not abandoned

Required: $6,000/mo after-tax on ~$300K @ 2.0% monthly. Current equity is $94,966, **70%** of the way to the *capital* benchmark and **0%** of the way to the *edge* benchmark. The binding constraint is **edge**, not capital — adding capital to a PF-0.22 strategy compounds losses faster.

Sequence: **prove edge on Thursday-only hypothesis → 30 clean trades → if expectancy > 0, scale capital, not before.** Anything else is theater.

## 5. Pending CEO sign-offs (irreversible actions)

- [ ] Rotate the leaked GitHub PAT (URL above)
- [ ] Approve physical deletion / archival of 30 orphan `ai_revenue*` directories
- [ ] Approve `MAX_LOT_SIZE = 1` enforcement landing in `trade_gateway.py`
- [ ] Approve `ThumbGate` README/scope rewrite (open-core minimum demo)
