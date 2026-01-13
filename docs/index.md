---
layout: home
title: "AI Trading Journey"
description: "90-day experiment building an autonomous AI options trading system with Claude Opus 4.5."
---

# AI Trading Journey

**Igor Ganapolsky & Claude** — Building an autonomous AI trading system.

We're documenting every win, loss, and lesson as we build an AI that trades options using Phil Town's Rule #1 investing principles.

---

## Latest Posts

{% for post in site.posts limit:5 %}
### [{{ post.title }}]({{ post.url | relative_url }})
*{{ post.date | date: "%B %d, %Y" }}* — {{ post.description | truncate: 120 }}

{% endfor %}

---

## Current Status (Day 74/90)

| Metric | Value |
|--------|-------|
| Paper Account | $5,000 |
| Brokerage Capital | $60 |
| Lessons Learned | 16 |
| Next Goal | Reach $500 for first CSP |

---

## The Strategy

**Sell cash-secured puts on quality stocks at prices we'd love to own them.**

- Follow Phil Town's Rule #1: Don't lose money
- Use AI to remove emotion from trading
- Learn from every trade via RAG memory
- Start small, compound over time

---

## Links

- **[All Lessons](/trading/lessons/)** — 16 documented lessons
- **[GitHub](https://github.com/IgorGanapolsky/trading)** — Source code
- **[RSS](/trading/feed.xml)** — Subscribe

---

*This is a 90-day experiment. Can AI make better trading decisions by being more disciplined? Follow along.*
