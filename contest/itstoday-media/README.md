# Profit Gate - It Today Media Build Challenge

Profit Gate is a working media-buying decision agent. It takes offer economics, tracking readiness, and channel context, then returns:

- launch/test/hold gate decision
- break-even CPC, ROAS, expected profit, and stop-loss cap
- channel-specific ad angles for Google, Meta, TikTok, and Taboola
- landing-page brief and proof requirements
- exportable JSON for a media buyer, developer, or analyst

## Why This Tool

The contest asks for a tool that can make a media-buying team more money. The fastest path is not prettier creative by itself; it is better test selection and faster budget discipline.

This repo already has a relevant pattern: the trading system uses deterministic gates, stop-loss rules, and audit trails before risk is allowed to scale. The trading strategy is not currently profitable, and this submission does not pretend otherwise. The useful asset is the operating model: define risk before action, measure the economics, and only scale when the evidence clears the gate.

Profit Gate applies that model to affiliate media buying:

- Bad campaign math is blocked before spend.
- Thin-sample tests are capped instead of scaled.
- Creative ideas ship with required proof and kill criteria.
- The JSON export keeps the handoff auditable.

## Run Locally

From the repo root:

```bash
python3 scripts/build_itstoday_submission.py
python3 -m http.server 8765 --directory contest/itstoday-media
```

Then open:

```text
http://127.0.0.1:8765
```

## Verify

```bash
npx vitest run contest/itstoday-media/src/profitGate.test.js
python3 scripts/build_itstoday_submission.py
```

## What I Would Build Next

- Connect ad-platform spend and conversion exports so gates use live campaign data.
- Add an LLM creative reviewer that rewrites hooks against channel policy and historical winners.
- Add postback/pixel diagnostics so tracking failures block launches automatically.
- Turn the JSON export into a queue for landing-page generation and media-buyer approval.
- Add cohort-level learning so every failed test updates future gate thresholds.
