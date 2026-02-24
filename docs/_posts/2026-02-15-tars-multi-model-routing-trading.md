---
layout: post
title: "Tars: Multi-Model Routing for AI Trading"
date: 2026-02-15
last_modified_at: "2026-02-15"
author: Igor Ganapolsky
categories: [ai, trading, architecture]
tags:
  - "tetrate"
  - "tars"
  - "llm-routing"
  - "model-selection"
  - "iron-condors"
  - "ai-trading"
  - "openrouter"
description: "How we use TARS to route trading AI calls across 5 models with budget-aware selection, automatic fallback, and safety guarantees."
excerpt: "Not every AI task needs the most expensive model. Here's how TARS routes our trading decisions across DeepSeek, Mistral, Kimi K2, and Claude Opus — spending $25/month instead of $500."
canonical_url: https://igorganapolsky.github.io/trading/tars-multi-model-routing-trading/
faq: true
questions:
  - question: "What is TARS (Tetrate Agent Router Service)?"
    answer: "TARS is an AI gateway that routes LLM calls to multiple providers through a single OpenAI-compatible API. It supports fallback policies, per-token budgets, traffic splitting, and centralized telemetry."
  - question: "Why use multiple AI models for trading?"
    answer: "Different trading tasks have different complexity levels. Simple text parsing doesn't need a $75/M-token model. Budget-aware routing sends simple tasks to cheap models ($0.30/M) and reserves expensive models for critical decisions like trade execution."
  - question: "What is the BATS framework for model selection?"
    answer: "Budget-Aware Test-time Scaling — a framework that selects the cheapest model capable of handling a task's complexity, with automatic downgrade when daily budget is exceeded and a safety guarantee that critical tasks always use the best available model."
image: "/assets/snapshots/progress_latest.png"

---

## The Cost Problem

Running an AI trading system is expensive. If every LLM call uses Claude Opus ($15 input / $75 output per million tokens), a moderately active system burns through $500+/month easily.

But here's the insight: **most trading tasks don't need the best model.** Parsing a market data response? Classifying sentiment? Generating a notification? These tasks work perfectly with models that cost 100x less.

The hard part is routing correctly — making sure cheap models handle cheap tasks, expensive models handle critical decisions, and nothing falls through the cracks.

## Enter TARS

[Tetrate Agent Router Service (TARS)](https://router.tetrate.ai) gives us a single gateway endpoint that routes to any provider:

![LLM Gateway Architecture](/trading/assets/llm_gateway_architecture.png)

One API key. One base URL. Five models across three providers. The trading code doesn't know or care which model handles a request — it calls the gateway, and the gateway routes.

```python
# src/utils/llm_gateway.py — the entire integration

## Answer Block

> **Answer Block:** Running an AI trading system is expensive. If every LLM call uses Claude Opus ($15 input / $75 output per million tokens), a moderately active system burns thro

def resolve_openai_compatible_config(
    *, default_api_key_env, default_base_url
):
    base_url = get_llm_gateway_base_url() or default_base_url
    api_key = get_llm_gateway_api_key() or _get_env(default_api_key_env)
    return OpenAICompatibleConfig(api_key=api_key, base_url=base_url)
```

## Budget-Aware Model Selection (BATS)

Our `ModelSelector` implements what we call the BATS framework — Budget-Aware Test-time Scaling:

| Task | Model | Cost | Why |
|---|---|---|---|
| Parse market data | DeepSeek V3 | $0.30/$1.20 | Fast, cheap, good enough |
| Analyze technicals | Mistral Medium 3 | $0.40/$2.00 | 90% of Sonnet quality at 8x less |
| Options structure | Kimi K2 | $0.39/$1.90 | #1 on StockBench trading benchmark |
| Pre-trade reasoning | DeepSeek-R1 | $0.70/$2.50 | Chain-of-thought for entry timing |
| **Execute trade** | **Claude Opus** | **$15/$75** | **Never cost-cut on money decisions** |

Daily budget: $0.83. Monthly budget: $25. Compare to $500+/month with Opus-only.

### The Safety Guarantee

One rule is absolute: **trade execution always uses Claude Opus.** The `ModelSelector` enforces this at the code level:

```python
if complexity == TaskComplexity.CRITICAL:
    selected = MODEL_REGISTRY[ModelTier.OPUS]
    return selected.model_id  # No budget check, no downgrade
```

You can exhaust the entire daily budget on analysis calls. The next trade execution still uses Opus. Phil Town Rule #1: don't lose money. That means don't cheap out on the model that decides where your money goes.

### Automatic Fallback Chain

If budget runs low, the selector downgrades gracefully:

```
Opus → Kimi K2 → Mistral → DeepSeek
```

TARS adds a second layer of fallback at the gateway level — if Anthropic's API is down, TARS can auto-route to Google or another provider. Two layers of resilience, zero code changes.

## The Trading Pipeline

Every trade passes through six stages, each with its own model routing:

![Trading Pipeline](/trading/assets/trading_pipeline.png)

1. **Thompson Sampler** — strategy selection (local, no LLM)
2. **Trade Memory** — SQLite pattern matching (local)
3. **RAG Knowledge Retrieval** — LanceDB semantic search over 300+ lessons (embedding via TARS)
4. **Risk Manager** — hard limit enforcement (local)
5. **LLM Council** — multiple models vote on the trade (DeepSeek-R1 + Kimi K2 via TARS)
6. **Alpaca Execution** — order placement (Opus via Anthropic Direct)

Stages 3 and 5 route through TARS. Stage 6 goes direct to Anthropic. Everything else is local computation — no LLM cost.

## Results

- **Monthly LLM cost**: ~$25 (down from projected $500+ with single-model approach)
- **Model diversity**: 5 models across 3 providers, automatically selected per task
- **Safety**: Trade execution always uses the best model, regardless of budget
- **Resilience**: Two-layer fallback (BATS downgrade + TARS gateway fallback)
- **Observability**: TARS request logs + usage dashboard for cost tracking

## Getting Started with TARS

```bash
# .env configuration
LLM_GATEWAY_BASE_URL=https://api.router.tetrate.ai/v1
TETRATE_API_KEY=sk-your-key-here
```

That's it. The gateway resolves automatically in `llm_gateway.py`. Every OpenAI-compatible call in the system routes through TARS with zero code changes.

---

*Built for the [Tetrate AI Buildathon](https://tetrate.ai/buildathon/apply). This post is part of our [AI Trading Journey](https://igorganapolsky.github.io/trading/).*

---

Evidence: https://github.com/IgorGanapolsky/trading
