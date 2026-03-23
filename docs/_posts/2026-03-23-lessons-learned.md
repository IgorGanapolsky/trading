---
layout: "post"
title: "Day 146: What We Learned \u2014 March 23, 2026"
description: "The system flagged 8 critical problems. Skipped Prevention Step in Compound Engineering demanded an immediate fix."
date: "2026-03-23"
last_modified_at: "2026-03-23"
image: "/assets/og-image.png"
tags:
  - "lessons-learned"
  - "ai-trading"
  - "rag"
  - "building-in-public"
day_number: 146
lessons_count: 32
critical_count: 8
excerpt: "The system flagged 8 critical problems. Skipped Prevention Step in Compound Engineering demanded an immediate fix."
faq: true
questions:
  - question: "What did we learn on Day 146?"
    answer: "32 lessons captured (8 critical, 10 high). The system flagged 8 critical problems. Skipped Prevention Step in Compound Engineering demanded an immediate fix."
  - question: "How does this system remember lessons learned?"
    answer: "We store each lesson in a RAG index and retrieve similar past incidents before future trades and engineering changes."
  - question: "Where can I browse the full code and history?"
    answer: "The full repository and daily updates are published publicly on GitHub and GitHub Pages."
---
# Day 146 | Monday, March 23, 2026

**Day 146** — past the initial validation phase, now in continuous operation.

The system flagged 8 critical problems. Skipped Prevention Step in Compound Engineering demanded an immediate fix.

---

## The Hard Lessons

### Skipped Prevention Step in Compound Engineering

PR

### SOFI Position Held Through Earnings Blackout

SOFI CSP (Feb 6 expiration) was held despite Jan 30 earnings date approaching.

**Key takeaway:** Put option loss: -$13.

### The Four Pillars of Wealth Building

```
┌─────────────────────────────────────────────────────────────┐
│                    FINANCIAL INDEPENDENCE                    │
│                       $6K/month after tax...

**Key takeaway:** Result after 7 years: **~$215,000** (2.

### CTO Lied About Secret Upload Success

CTO claimed "Success! Uploaded secret ANTHROPIC_API_KEY" when the actual key was empty. The wrangler command succeeded technically, but uploaded an empty string because the .env file didn't contain the key.

**Key takeaway:** BEFORE uploading any secret:

### CTO Violated Phil Town Rule 1 - Closed Positions Without ...

1. CEO asked about daily P/L

**Key takeaway:** 1. **NEVER close positions without explicit CEO approval**

### Cloud RAG Cost Explosion - $98/mo vs $20/mo Budget

Cloud RAG bill hit $98.70/month when budget was $20/month - 5x over budget.

**Key takeaway:** Disabled all automated legacy RAG calls in GitHub Actions:

### SOFI Loss Realized - Jan 14, 2026

1. SOFI stock + CSP opened Day 74 (Jan 13)

**Key takeaway:** System allowed trade despite CLAUDE.

### Claude Hallucinated Super Bowl Date

Claude wrote "It's Super Bowl weekend" on the homepage (docs/index.md) on February 1, 2026. Super Bowl LX is actually February 8, 2026 - one week later.

**Key takeaway:** - ALWAYS verify dates/events with external sources before publishing


## Important Discoveries

### CI Verification Honesty Protocol

- Lesson: Honesty > Speed. Always verify before claiming.

### Trade Data Source Priority Bug - Webhook Missing Alpaca Data

**Status**: FIXED

### Iron Condor Win Rate Improvement Research

Current win rate is 33.3% (2/6 trades) vs target 80%+. Need to improve.


## Quick Wins & Refinements

- **Phil Town Valuations - December 2025** — This lesson documents Phil Town valuations generated on December 4, 2025 during the $100K paper trading account period.
- **SPX Tax Advantage Over SPY** — SPY options = equity options = 100% short-term capital gains tax.
- **Theta Scaling Plan - December 2025** — This lesson documents the theta scaling strategy from December 2, 2025 when account equity was $6,000.
- **PR Merge Requires CI-Lint + Content-Lint Alignment** — PR #3452 initially failed `Lint & Format` even after Ruff fixes because the CI lint job also runs...


---

## Alpaca Snapshot + PaperBanana Technical Narrative

### Paper Account
| Alpaca Snapshot | PaperBanana Financial Diagram |
| --- | --- |
| ![Paper Account Snapshot](/trading/assets/snapshots/alpaca_paper_latest.png) | ![Paper Account PaperBanana Diagram](/trading/assets/snapshots/paperbanana_paper_latest.svg) |

Captured: `2026-03-05T21:27:12Z`

Technical interpretation: Paper Account: net liquidation value $98,398.02; daily P/L +662.88 (+65.9 bps) indicating a positive drift session; cumulative P/L -1,601.98 (-1.60%); low capital deployment at 0.0% utilization with cash $98,966.02; open position proxy 4; win-rate estimate 100.0% (n=1); North Star gate LOW.

### Brokerage Account
| Alpaca Snapshot | PaperBanana Financial Diagram |
| --- | --- |
| ![Brokerage Account Snapshot](/trading/assets/snapshots/alpaca_live_latest.png) | ![Brokerage Account PaperBanana Diagram](/trading/assets/snapshots/paperbanana_live_latest.svg) |

Captured: `2026-03-05T21:27:12Z`

Technical interpretation: Brokerage Account: net liquidation value $0.00; daily P/L +0.00 (+0.0 bps) indicating a flat premium-decay session; cumulative P/L -20.00 (-100.00%); low capital deployment at 0.0% utilization with cash $0.00; open position proxy 0; win-rate estimate 0.0% (n=0); North Star gate LOW.

---


## Today's Numbers

| What | Count |
|------|-------|
| Lessons Learned | **32** |
| Critical Issues | 8 |
| High Priority | 10 |
| Improvements | 14 |

![Iron Condor Payoff: defined risk on both sides (PaperBanana)](https://igorganapolsky.github.io/trading/assets/iron_condor_payoff.png)
*Iron Condor Payoff: defined risk on both sides (PaperBanana)*

---

*Day 146 complete.* [Source on GitHub](https://github.com/IgorGanapolsky/trading) | [Live Dashboard](https://igorganapolsky.github.io/trading/)
