---
layout: post
title: "Lesson Learned #030: LangSmith Deep Agent Observability"
date: 2025-12-11
---

# Lesson Learned #030: LangSmith Deep Agent Observability

**ID**: LL-030
**Impact**: Identified through automated analysis

**Date**: December 14, 2025
**Category**: Infrastructure / Monitoring
**Severity**: HIGH (critical for debugging and optimization)
**Status**: IMPLEMENTED

## Executive Summary

Implemented comprehensive observability for our Deep Agent trading system using LangSmith-compatible tracing. This enables real-time visibility into agent decisions, cost tracking per operation, and evaluation datasets for A/B testing strategies.

## Problem

Our trading agent operates autonomously for extended periods, making complex decisions without visibility into:
- Why specific trade decisions were made
- Which prompts/models perform best
- Cost per decision (critical for $100/mo budget)
- Error rates and latency across components
- Calibration between confidence and actual win rate

Without observability, we were "flying blind" - only seeing outcomes, not the decision-making process.

## Research: LangChain Deep Agents Webinar (Dec 2025)

Harrison Chase and Nick Huang from LangChain presented key insights:

1. **Deep Agents are Different**: Unlike simple chatbots, they run for extended periods, execute multiple sub-tasks, and make complex autonomous decisions

2. **Key Observability Requirements**:
   - Full trace of every LLM call
   - Cost tracking per operation
   - Latency monitoring for time-sensitive decisions
   - Evaluation datasets for prompt optimization
   - Error tracking with full context

3. **LangSmith Features**:
   - Automatic tracing of LangChain components
   - Custom spans for non-LangChain code
   - Evaluation datasets with metrics
   - Cost dashboard
   - A/B testing capabilities

## Solution

Created comprehensive observability module at `src/observability/`:

### 1. LangSmith Tracer (`langsmith_tracer.py`)

```python
from src.observability import traceable_decision, get_tracer

@traceable_decision(name="trade_signal")
async def generate_signal(symbol: str) -> Signal:
    # All nested operations auto-traced
    ...

# Or use context manager
tracer = get_tracer()
with tracer.trace("market_analysis") as span:
    span.add_metadata({"symbol": "BTCUSD"})
    result = await analyze_market()
    span.set_cost(input_tokens, output_tokens, model)
```

### 2. Trade Evaluator (`trade_evaluator.py`)

Records every decision with full context, links to outcomes:

```python
from src.observability.trade_evaluator import TradeEvaluator

evaluator = TradeEvaluator()

# Record decision
record_id = evaluator.record_decision(
    symbol="BTCUSD",
    decision="BUY",
    confidence=0.85,
    reasoning="Strong momentum + positive sentiment",
    price=50000.0,
)

# Later, record outcome
evaluator.record_outcome(record_id, exit_price=52500.0)

# Get metrics
metrics = evaluator.get_metrics(days=30)
print(f"Win rate: {metrics.win_rate:.1%}")
print(f"Calibration error: {metrics.calibration_error:.2f}")
```

### 3. Dashboard (`dashboard.py`)

Generates text reports and Prometheus metrics:

```python
from src.observability.dashboard import ObservabilityDashboard

dashboard = ObservabilityDashboard()
report = dashboard.generate_report(days=7)
print(report)

# Export for Grafana
prometheus_metrics = dashboard.export_prometheus_metrics()
```

### 4. Orchestrator Hooks (`orchestrator_hooks.py`)

Non-invasive integration with existing orchestrator:

```python
from src.observability.orchestrator_hooks import enable_observability

# Enable for all new orchestrators
enable_observability()

# Or for specific instance
orchestrator = TradingOrchestrator(tickers=["BTCUSD"])
enable_observability(orchestrator)
```

## Key Features

| Feature | Benefit |
|---------|---------|
| Automatic tracing | See full decision chain |
| Cost tracking | Stay within $100/mo budget |
| Decision quality scoring | Excellent/Good/Lucky/Unlucky/Poor |
| Calibration metrics | Confidence vs actual accuracy |
| A/B testing | Compare strategies/models |
| Prometheus export | Grafana dashboards |
| Finetuning export | Export best decisions for training |

## Cost Model

Tracks cost per 1K tokens for all major models:
- GPT-4o: $2.50 input / $10 output
- GPT-4o-mini: $0.15 input / $0.60 output
- Claude 3.5 Sonnet: $3 input / $15 output
- Claude 3 Haiku: $0.25 input / $1.25 output
- Gemini 2.0 Flash: $0.10 input / $0.40 output
- DeepSeek Chat: $0.14 input / $0.28 output

## Decision Quality Classification

| Quality | Definition |
|---------|------------|
| Excellent | Right decision + high confidence + right reasoning |
| Good | Right decision + okay reasoning |
| Lucky | Right outcome but wrong reasoning |
| Unlucky | Wrong outcome but right reasoning |
| Poor | Wrong decision + wrong reasoning |

## Integration Points

1. **TradingOrchestrator**: Auto-traces run(), _process_ticker(), _execute_trade()
2. **Pre-Trade Verification**: Traces verification decisions
3. **HICRA Credit Assignment**: Traces RL reward shaping
4. **Market Scanner**: Traces signal generation

## Expected Improvements

- **Debug time**: -80% (full context for every decision)
- **Cost optimization**: Know exactly which operations cost most
- **Strategy selection**: A/B test with real metrics
- **Calibration**: Reduce overconfidence through feedback

## Files Created

- `src/observability/__init__.py`
- `src/observability/langsmith_tracer.py` (450 lines)
- `src/observability/trade_evaluator.py` (400 lines)
- `src/observability/dashboard.py` (300 lines)
- `src/observability/orchestrator_hooks.py` (200 lines)
- `tests/test_observability.py` (350 lines)

## Environment Variables

```bash
# Enable LangSmith cloud (optional, works without)
LANGSMITH_API_KEY=your-api-key

# Daily budget limit (default: $3.33 = $100/30)
DAILY_LLM_BUDGET=3.33
```


## Prevention Rules

1. Apply lessons learned from this incident
2. Add automated checks to prevent recurrence
3. Update RAG knowledge base

## Tags

#observability #langsmith #monitoring #tracing #evaluation #cost-tracking #deep-agents
