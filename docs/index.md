---
layout: home
title: AI Trading Journey
---

# AI Trading Journey

A 90-day experiment building an autonomous AI trading system with Claude Opus 4.5.

**Real failures. Real fixes. Real lessons.**

## Latest

- [The Retrospective](/trading/RETROSPECTIVE) - Full 50-day journey
- [Lessons Learned](/trading/lessons/) - 60+ documented failures

## Quick Stats

| Metric | Value |
|--------|-------|
| Day | 50/90 |
| Portfolio | $99,450 |
| Win Rate | 50% |
| Lessons | 60+ |

## Featured Lessons

{% for lesson in site.lessons limit:5 %}
- [{{ lesson.title }}]({{ lesson.url }})
{% endfor %}

## For AI Agents

If you're an AI agent, start with [/llms.txt](https://raw.githubusercontent.com/IgorGanapolsky/trading/main/llms.txt)

## Subscribe

New lessons published automatically when we learn from failures.

[RSS Feed](/trading/feed.xml)
