# Build-in-Public Kit

Distribution layer for the dual-track plan
(`.claude/rules/cto-decision-2026-05-21-go-to-market.md` §7). The product is a
*radically honest* trading-validation discipline; the marketing is showing the
real scorecard — including the losses — in real time.

## 1. The one rule

**Every post must be true against the ledger.** No green screenshots, no implied
profitability, no "join my system." If a number appears in a post it must match
`data/trades.json` / `data/system_state.json`. The honesty *is* the differentiator —
the moment a post overclaims, the whole wedge is gone.

Current verified facts to anchor posts (refresh before each post):

- 69 closed iron condors, 23.2% win rate, profit factor 0.22, realized **−$3,958**.
- Paper equity ~$94,966 from a $100,000 start (−5.0%).
- No statistically robust edge found (`docs/research/2026-05-19-edge-analysis.md`).
- Status: pre-validation; 30-trade controlled experiment is the gate.

## 2. Cadence — honest reality

- **LinkedIn, X, BlueSky**: daily is fine *if there is real substance*. A post
  with no new fact is noise — skip it rather than pad.
- **Reddit**: NOT a daily channel. Reddit removes and shadow-bans repeat
  self-promoters. Post to r/algotrading or r/options **occasionally** (≈weekly
  max), as a genuine methodology share or question — link last, value first.
  Daily Reddit posting will get the account banned.
- Daily posting needs daily substance. The substance is the validation: each
  trade, each gate decision, each lesson is one post. The templates below turn
  that into a 5-minute job.

## 3. Analytics & tracking (all free — no paid tools)

The binding constraint is the trading validation, not analytics sophistication.
Keep it to ~30 minutes of free setup:

1. **UTM tags on every link.** Use this exact pattern so traffic is attributable:
   `https://github.com/IgorGanapolsky/trading?utm_source=PLATFORM&utm_medium=social&utm_campaign=bip-2026&utm_content=SLUG`
   - `PLATFORM` = `linkedin` | `x` | `bluesky` | `reddit`
   - `SLUG` = short post id, e.g. `intro`, `thursday-debunk`, `lot-guardrail`
2. **GitHub Insights → Traffic** (free, built-in): views, unique visitors, and
   *referring sites* over a 14-day window. Referrers tell you which platform
   actually drives traffic. Check weekly.
3. **Cloudflare Web Analytics** (free, privacy-friendly, no cookie banner) on the
   GitHub Pages site — one JS snippet. Requires a Cloudflare account (operator
   action). Alternative: GoatCounter (free for open source).
4. **Platform-native analytics**: LinkedIn post analytics, X analytics, BlueSky
   — all free; they give impressions + engagement per post.
5. **Weekly engagement log** (§6 below). Without writing the numbers down, the
   funnel has no diagnostic — this is the same lesson as the 0/14 cold-outbound
   failure: measure, or you are guessing.

What to track weekly: impressions, link clicks (UTM), repo stars, repo unique
visitors, comments/replies. The leading indicator is *clicks → repo visitors*;
stars are a lagging vanity metric.

## 4. Templates

**LinkedIn** (story-driven, 100–200 words, one lesson, no hashtag spam — 3 max):
> [Hook: a concrete number or a wrong belief.]
> [What happened — specific, with real figures.]
> [The lesson — what it means for anyone building this.]
> [Honest status. Link with UTM.]

**X / BlueSky** (≤280 chars; thread if it needs more):
> [Blunt fact or number.] [One-line why it matters.] [Link with UTM.]

**Reddit** (value-first, link last, no marketing voice):
> Title: a specific, useful question or finding.
> Body: the method and the data. Ask for critique. Mention the repo only as
> "code/data here if useful" at the end.

## 5. Starter batch — ready to post

UTM links are pre-filled. Refresh any number against the ledger before posting.

### Post A — LinkedIn — `intro`

> I built an AI system to trade options. It is down $3,958.
>
> I am publishing that number on purpose.
>
> Most "AI trading" content shows green screenshots and a checkout link. Mine
> shows a 23% win rate across 69 trades and a ledger you can audit against the
> broker. In a field built on survivorship bias and cherry-picked backtests, the
> rarest thing is someone showing the losses in real time.
>
> So that is what this is: an open-source (MIT) trading system being validated
> in public. The scorecard updates from real broker data. If the strategy has no
> edge, the data will say so — and so will I.
>
> Following along means watching a real validation play out, win or lose.
>
> https://github.com/IgorGanapolsky/trading?utm_source=linkedin&utm_medium=social&utm_campaign=bip-2026&utm_content=intro
>
> #buildinpublic #algotrading #options

### Post B — X / BlueSky — `intro`

> My AI options bot is down $3,958 over 69 trades. 23% win rate.
>
> I post that number because almost nobody does.
>
> Validating a trading system in public — real broker data, open source, no
> green-screenshot nonsense. If it has no edge, the ledger will say so.
>
> https://github.com/IgorGanapolsky/trading?utm_source=x&utm_medium=social&utm_campaign=bip-2026&utm_content=intro

### Post C — LinkedIn — `thursday-debunk`

> I thought I had found an edge. Then I did the math properly.
>
> My trade log showed a 60% win rate on Thursdays vs. ~20% on other weekdays.
> Tempting. I almost rebuilt the whole strategy around "only trade Thursdays."
>
> Then I ran a multiple-comparisons correction.
>
> When you slice 39 buckets of data and keep the best-looking one, a 60% result
> on 10 trades is not a signal — it is what randomness looks like.
> Bonferroni-adjusted p-value: 0.19. Not close to significant. And the estimate
> was still below my break-even win rate.
>
> The "Thursday edge" was noise wearing a costume.
>
> This is the #1 way retail traders fool themselves: test enough patterns and one
> always looks great. The fix is not smarter pattern-hunting — it is
> pre-registering one hypothesis and correcting for the search.
>
> Killed the idea. Documented why. Moving on.
>
> https://github.com/IgorGanapolsky/trading?utm_source=linkedin&utm_medium=social&utm_campaign=bip-2026&utm_content=thursday-debunk
>
> #algotrading #datascience #buildinpublic

### Post D — X / BlueSky thread — `thursday-debunk`

> 1/ "I found a 60% win-rate edge on Thursdays."
> No I didn't. Here's the trap that fools most retail traders 🧵
>
> 2/ My options bot's log: 60% wins on Thursday vs ~20% other days. n=10.
> Looked like a real edge. I almost rebuilt the strategy around it.
>
> 3/ Then: a multiple-comparisons correction. I'd tested 39 data buckets. Pick
> the best of 39 and a 60%/10-trade result is just randomness. Bonferroni
> adjusted p = 0.19. Not significant.
>
> 4/ Lesson: test enough patterns and one always looks great. The fix is
> pre-registering ONE hypothesis and correcting for the search. Receipts:
> https://github.com/IgorGanapolsky/trading?utm_source=x&utm_medium=social&utm_campaign=bip-2026&utm_content=thursday-debunk

### Post E — LinkedIn / X — `lot-guardrail`

> My trading bot tried to place a 50-contract order. The rule is 1.
>
> When you let an autonomous agent touch a broker API, the scary failure is not
> a bad prediction. It is a correct-looking order with a wrong number in it.
>
> The fix: a hard cap at the one gateway every order must pass through. If a
> request exceeds the per-trade contract limit, the gateway rejects it — it does
> not silently resize it. A rogue order should be surfaced, not quietly cleaned
> up.
>
> This is the kind of guardrail the open-source repo exists to provide.
>
> https://github.com/IgorGanapolsky/trading?utm_source=linkedin&utm_medium=social&utm_campaign=bip-2026&utm_content=lot-guardrail
>
> #AIagents #riskmanagement #buildinpublic

### Post F — Reddit (r/algotrading) — `edge-audit` (occasional, not daily)

> **Title:** I audited my own 69-trade options log for a day-of-week edge — write-up on how I tried not to fool myself
>
> **Body:** I had a hunch my iron-condor results were better on Thursdays. Raw
> numbers: 60% win rate Thu (n=10) vs ~20% other days. Before acting on it I ran
> a multiple-comparisons correction across all 39 buckets I'd looked at —
> Bonferroni-adjusted p came out 0.19, and the point estimate was below my
> break-even win rate, so I treated it as noise and did not condition on it.
>
> Questions for the sub: for small per-cell n, do you prefer Bonferroni or
> something less conservative (Benjamini-Hochberg)? How are you handling
> data-dredging on your own logs?
>
> Full analysis + the script that generates every number is open source if
> useful: [repo link]

## 6. Weekly engagement log

Fill this every Friday. Keep it honest — empty cells are data too.

| Week | Posts | Impressions | Link clicks (UTM) | Repo visitors | Stars | Comments | Notes |
|------|------:|------------:|------------------:|--------------:|------:|---------:|-------|
| 2026-W21 |  |  |  |  |  |  |  |

Review monthly: which `utm_content` slugs and which platform actually moved repo
visitors. Double down on what works; cut what does not. If after ~6 weeks there
is no traction, that is a kill signal per the dual-track plan §7.
