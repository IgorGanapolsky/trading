---
layout: "post"
title: "Day 116: What We Learned \u2014 February 21, 2026"
description: "Today tested our resilience. 8 critical issues, 31 total lessons. CTO Violated Phil Town Rule 1 - Closed Positions Without ... was the headline."
date: "2026-02-21"
last_modified_at: "2026-02-21"
image: "/assets/og-image.png"
tags:
  - "lessons-learned"
  - "ai-trading"
  - "rag"
  - "building-in-public"
day_number: 116
lessons_count: 31
critical_count: 8
excerpt: "Today tested our resilience. 8 critical issues, 31 total lessons. CTO Violated Phil Town Rule 1 - Closed Positions Without ... was the headline."
faq: true
questions:
  - question: "What did we learn on Day 116?"
    answer: "31 lessons captured (8 critical, 10 high). Today tested our resilience. 8 critical issues, 31 total lessons. CTO Violated Phil Town Rule 1 - Closed Positions Without ... was the headline."
  - question: "How does this system remember lessons learned?"
    answer: "We store each lesson in a RAG index and retrieve similar past incidents before future trades and engineering changes."
  - question: "Where can I browse the full code and history?"
    answer: "The full repository and daily updates are published publicly on GitHub and GitHub Pages."
---
# Day 116 | Saturday, February 21, 2026

**Day 116** — past the initial validation phase, now in continuous operation.

Today tested our resilience. 8 critical issues, 31 total lessons. CTO Violated Phil Town Rule 1 - Closed Positions Without ... was the headline.

---

## The Hard Lessons

### CTO Violated Phil Town Rule 1 - Closed Positions Without ...

1. CEO asked about daily P/L

**Key takeaway:** 1. **NEVER close positions without explicit CEO approval**

### Cloud RAG Cost Explosion - $98/mo vs $20/mo Budget

Cloud RAG bill hit $98.70/month when budget was $20/month - 5x over budget.

**Key takeaway:** Disabled all automated legacy RAG calls in GitHub Actions:

### CTO Lied About Secret Upload Success

CTO claimed "Success! Uploaded secret ANTHROPIC_API_KEY" when the actual key was empty. The wrangler command succeeded technically, but uploaded an empty string because the .env file didn't contain the key.

**Key takeaway:** BEFORE uploading any secret:

### SOFI Position Held Through Earnings Blackout

SOFI CSP (Feb 6 expiration) was held despite Jan 30 earnings date approaching.

**Key takeaway:** Put option loss: -$13.

### Skipped Prevention Step in Compound Engineering

PR

### Claude Hallucinated Super Bowl Date

Claude wrote "It's Super Bowl weekend" on the homepage (docs/index.md) on February 1, 2026. Super Bowl LX is actually February 8, 2026 - one week later.

**Key takeaway:** - ALWAYS verify dates/events with external sources before publishing

### The Four Pillars of Wealth Building

```
┌─────────────────────────────────────────────────────────────┐
│                    FINANCIAL INDEPENDENCE                    │
│                       $6K/month after tax...

**Key takeaway:** Result after 7 years: **~$215,000** (2.

### SOFI Loss Realized - Jan 14, 2026

1. SOFI stock + CSP opened Day 74 (Jan 13)

**Key takeaway:** System allowed trade despite CLAUDE.


## Important Discoveries

### Iron Condor Entry Signals & Timing

System not generating enough trade signals. Need clear entry criteria.

### Q1 2026 Tax Action Plan

Concrete action items for Q1 2026 tax planning. This is the "do this now" version of the comprehensive tax strategy (LL-297).

### Iron Condor Optimization for $30K Account

New $30K paper account established. Need optimized iron condor parameters for:


## Quick Wins & Refinements

- **RAG Webhook Compound Query Routing Fix** — LL-274: RAG Webhook Compound Query Routing Fix

 Date

2026-01-22

 Severity

HIGH

 Summary

Fixed RAG Webhook to...
- **Automated Position Management Requirements** — Automated Position Management Requirements (Feb 8, 2026)

 Source: Tastylive best practices, Option Alpha, system gap...
- **SPX Tax Advantage Over SPY** — SPY options = equity options = 100% short-term capital gains tax.
- **Iron Condor Backtest Findings** — Iron Condor Backtest Findings (Feb 8, 2026)

 Source: Web Research + OptionsTrading IQ + Spintwig

 Key Backtest...


---

## Alpaca Snapshot + PaperBanana Technical Narrative

### Paper Account
| Alpaca Snapshot | PaperBanana Financial Diagram |
| --- | --- |
| ![Paper Account Snapshot](/trading/assets/snapshots/alpaca_paper_latest.png) | ![Paper Account PaperBanana Diagram](/trading/assets/snapshots/paperbanana_paper_latest.svg) |

Captured: `2026-02-20T21:24:10Z`

Technical interpretation: Paper Account: net liquidation value $101,224.20; daily P/L -141.20 (-13.9 bps) indicating a negative drift session; cumulative P/L +1,224.20 (+1.22%); low capital deployment at 0.0% utilization with cash $101,817.20; open position proxy 6; win-rate estimate 100.0% (n=1); North Star gate LOW.

### Brokerage Account
| Alpaca Snapshot | PaperBanana Financial Diagram |
| --- | --- |
| ![Brokerage Account Snapshot](/trading/assets/snapshots/alpaca_live_latest.png) | ![Brokerage Account PaperBanana Diagram](/trading/assets/snapshots/paperbanana_live_latest.svg) |

Captured: `2026-02-20T21:24:10Z`

Technical interpretation: Brokerage Account: net liquidation value $209.42; daily P/L +0.00 (+0.0 bps) indicating a flat premium-decay session; cumulative P/L +189.42 (+947.10%); high capital deployment at 90.4% utilization with cash $40.00; open position proxy 0; win-rate estimate 0.0% (n=0); North Star gate LOW.

---


## Today's Numbers

| What | Count |
|------|-------|
| Lessons Learned | **31** |
| Critical Issues | 8 |
| High Priority | 10 |
| Improvements | 13 |

![Iron Condor Payoff: defined risk on both sides (PaperBanana)](https://igorganapolsky.github.io/trading/assets/iron_condor_payoff.png)
*Iron Condor Payoff: defined risk on both sides (PaperBanana)*

---

*Day 116 complete.* [Source on GitHub](https://github.com/IgorGanapolsky/trading) | [Live Dashboard](https://igorganapolsky.github.io/trading/)
