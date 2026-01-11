---
layout: post
title: "LL-068: Google ADK Integration is Month 3 Priority"
date: 2026-01-11
---

# LL-068: Google ADK Integration is Month 3 Priority

**Date**: December 24, 2025
**Severity**: Low (Not urgent)
**Status**: Deferred to Month 3

## Context

Google ADK (Agent Development Kit) is already integrated:
- Go service: `go/adk_trading/trading_orchestrator` (28MB compiled binary)
- Python client: `src/orchestration/adk_client.py`
- Integration: `src/orchestration/adk_integration.py`
- Enabled via: `ENABLE_ADK_AGENTS=true` (default)

## Why Defer?

1. **Working system** - Current Python orchestrator works fine for paper trading
2. **Complexity** - ADK requires separate Go service on port 8080
3. **Priority** - Day 50/90, focus on Phil Town completeness and win rate first
4. **Risk** - Adding complexity during R&D phase increases failure modes

## When to Enable

Enable Google ADK when:
- [ ] Win rate consistently >55%
- [ ] Day 75+ of R&D phase
- [ ] Phil Town RAG completeness >90%
- [ ] All CI checks passing consistently
- [ ] Moving from paper to live trading

## How to Enable

```bash
# 1. Start Go ADK service
cd go/adk_trading && ./trading_orchestrator

# 2. Verify service is running
curl http://localhost:8080/health

# 3. Set environment variable
export ENABLE_ADK_AGENTS=true

# 4. Run trading orchestrator
python3 -m src.orchestrator.main
```

## Reminder Mechanism

This lesson will surface via:
1. RAG mandatory check (mentions "ADK" keyword)
2. Feature list tracking (`feature_list.json`)
3. Month 3 milestone review

## Tags
- #deferred
- #month3
- #google-adk
- #orchestration
