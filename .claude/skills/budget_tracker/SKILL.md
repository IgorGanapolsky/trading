---
skill_id: budget_tracker
name: Budget Tracker
version: 1.0.0
status: active  # Implementation created Dec 24, 2025
description: Skill for budget-aware operations based on Google's BATS framework
author: Trading System CTO
tags: [budget, cost-optimization, api-tracking, resource-management, bats]
tools:
  - track_api_call
  - should_execute_operation
  - get_budget_status
  - get_recommended_model
  - get_budget_prompt
dependencies:
  - src/utils/budget_tracker.py
integrations:
  - src/utils/budget_tracker.py::BudgetTracker
  - src/utils/budget_tracker.py::track
  - src/utils/budget_tracker.py::should_execute
---

# Budget Tracker Skill

Budget-aware operations using Google's BATS (Budget Aware Test-time Scaling) framework to optimize API costs and reduce spending by 31.3%.

## Overview

This skill provides:
- Real-time budget tracking ($100/month allocation)
- API call cost monitoring across all services
- Dynamic operation prioritization based on budget health
- Automatic model selection (Opus/Sonnet/Haiku)
- Budget awareness prompts for LLM agents
- Daily/monthly spending analytics

## Budget Awareness Framework

Based on Google's research: https://arxiv.org/abs/2511.17006

### Key Concepts

1. **Continuous Budget Awareness**: Inject budget status into every LLM prompt
2. **Priority-Based Execution**: Execute critical operations first when budget is tight
3. **Dynamic Model Selection**: Use cheaper models when budget runs low
4. **Proactive Cost Reduction**: Skip optional research when budget health is poor

### Budget Health States

- **Healthy (>50% remaining)**: All operations proceed normally
- **Caution (20-50% remaining)**: Skip low-priority operations, use Sonnet instead of Opus
- **Critical (<20% remaining)**: Only critical trades/risk checks, use Haiku

## Tools

### 1. track_api_call

Track an API call and its associated cost.

**Parameters:**
- `api_name` (required): Name of the API/operation (e.g., "openrouter_sonnet", "gemini_research")
- `cost` (optional): Explicit cost override (default: uses predefined costs)

**API Cost Estimates:**
```python
{
    "alpaca_trade": 0.00,       # Free (paper trading)
    "alpaca_data": 0.001,       # ~$0.001 per data call
    "openrouter_haiku": 0.0003, # $0.25/1M tokens
    "openrouter_sonnet": 0.003, # $3/1M tokens
    "openrouter_opus": 0.015,   # $15/1M tokens
    "gemini_research": 0.01,    # ~$0.01 per research query
    "polygon_data": 0.0001,     # Very cheap
    "yfinance": 0.00,           # Free
    "news_api": 0.001,          # ~$0.001 per call
}
```

**Returns:**
```python
True  # Call should proceed (budget OK)
False # Budget exceeded, skip operation
```

**Usage:**
```python
from src.utils.budget_tracker import track

# Track an API call
if track("openrouter_sonnet", cost=0.003):
    response = llm_client.generate(prompt)
else:
    # Budget exceeded, use fallback
    response = use_cached_response()
```

### 2. should_execute_operation

BATS-style decision: should we execute this operation given current budget?

**Parameters:**
- `operation` (required): Operation name/description
- `priority` (required): Priority level - "critical", "high", "medium", "low"

**Priority Levels:**
- **critical**: Must execute (trades, risk checks) - always runs
- **high**: Important (pre-trade analysis, position sizing) - runs unless critical budget
- **medium**: Nice to have (deep research, extended sentiment) - skipped in caution mode
- **low**: Optional (social media scraping, extra news sources) - skipped unless healthy

**Returns:**
```python
True  # Operation should proceed
False # Skip operation to conserve budget
```

**Usage:**
```python
from src.utils.budget_tracker import should_execute

# Before expensive deep research
if should_execute("gemini_deep_research", priority="medium"):
    research = gemini_client.research_crypto_market("BTC")
else:
    # Skip research, use cached data or simpler analysis
    research = get_cached_research()
```

### 3. get_budget_status

Get comprehensive budget status for agent awareness.

**Returns:**
```python
{
    "monthly_budget": 100.00,
    "spent_this_month": 42.50,
    "remaining": 57.50,
    "daily_average_remaining": 2.68,
    "days_left_in_month": 21,
    "budget_health": "healthy",  # or "caution", "critical"
    "last_updated": "2025-12-13T10:30:00"
}
```

**Usage:**
```python
from src.utils.budget_tracker import get_tracker

tracker = get_tracker()
status = tracker.get_budget_status()

print(f"Budget Health: {status.budget_health}")
print(f"Remaining: ${status.remaining:.2f} ({status.days_left_in_month} days)")
```

### 4. get_recommended_model

BATS-style model selection based on budget health.

**Returns:**
```python
"opus"    # Best quality (healthy budget)
"sonnet"  # Balanced (caution mode)
"haiku"   # Cheapest (critical budget)
```

**Usage:**
```python
from src.utils.budget_tracker import get_model

model = get_model()
# Returns: "opus", "sonnet", or "haiku" based on budget

response = openrouter_client.generate(
    prompt=prompt,
    model=f"anthropic/claude-3.5-{model}-latest"
)
```

### 5. get_budget_prompt

Get budget awareness prompt injection for LLM agents.

This is the core BATS technique - inject budget context into every prompt.

**Returns:**
```text
[BUDGET AWARENESS]
Monthly Budget: $100.00
Spent: $42.50
Remaining: $57.50 (21 days left)
Daily Allowance: $2.74/day
Status: HEALTHY

GUIDANCE:
- Proceed normally with all operations
```

**Usage:**
```python
from src.utils.budget_tracker import get_budget_prompt

# Inject into LLM prompts for budget awareness
system_prompt = f"""
You are a trading agent with budget constraints.

{get_budget_prompt()}

Analyze market conditions and make trading decisions.
"""
```

## Integration with Trading System

### Pre-Trade Checklist

```python
from src.utils.budget_tracker import should_execute, get_model, track

# 1. Check if we should do deep research
if should_execute("gemini_research", priority="medium"):
    track("gemini_research")
    research = gemini_client.research_crypto_market("BTC")

# 2. Use budget-appropriate model
model = get_model()
track(f"openrouter_{model}")
analysis = llm_client.analyze(prompt, model=model)

# 3. Always execute critical trade operations
if should_execute("execute_trade", priority="critical"):
    track("alpaca_trade")  # Free, but tracked for analytics
    alpaca.submit_order(...)
```

### CEO Hook Integration

The budget tracker is integrated into `.claude/hooks/ceo/conversation-start.md` to provide real-time budget awareness at the start of every conversation.

## Budget Analytics

Track spending patterns over time:

```bash
# View budget file
cat data/budget_tracker.json

# Example output:
{
  "monthly_budget": 100.0,
  "spent_this_month": 45.23,
  "api_calls": {
    "openrouter_sonnet": 125,
    "gemini_research": 8,
    "news_api": 34
  },
  "daily_spending": {
    "2025-12-01": 2.34,
    "2025-12-02": 3.12,
    "2025-12-03": 1.89
  }
}
```

## Usage Example

```python
from src.utils.budget_tracker import (
    track,
    should_execute,
    get_budget_prompt,
    get_model,
    get_tracker
)

# 1. Get budget status
tracker = get_tracker()
status = tracker.get_budget_status()
print(f"Budget: ${status.remaining:.2f} remaining ({status.budget_health})")

# 2. Check before expensive operation
if should_execute("deep_research", priority="medium"):
    track("gemini_research", cost=0.01)
    research_result = run_deep_research()
else:
    print("Skipping research due to budget constraints")

# 3. Use appropriate model
model = get_model()
print(f"Using {model} model based on budget")

# 4. Inject budget awareness into prompts
prompt = f"""
{get_budget_prompt()}

Analyze BTC market and provide trading recommendation.
"""
```

## CLI Usage

```bash
# Test budget tracker
python -c "from src.utils.budget_tracker import get_tracker; \
           tracker = get_tracker(); \
           print(tracker.get_prompt_injection())"

# Check if operation should execute
python -c "from src.utils.budget_tracker import should_execute; \
           print(should_execute('gemini_research', 'medium'))"

# Get recommended model
python -c "from src.utils.budget_tracker import get_model; \
           print(get_model())"
```

## Best Practices

1. **Always track expensive operations**: Track all API calls that cost money
2. **Set appropriate priorities**: Critical = trades/risk, High = pre-trade analysis, Medium = research, Low = optional features
3. **Use budget prompts**: Inject budget awareness into all LLM prompts for autonomous decision-making
4. **Monitor daily spending**: Check `data/budget_tracker.json` regularly
5. **Adjust if needed**: If consistently hitting limits, review priority assignments

## Cost Savings Impact

Based on Google's BATS research:
- **31.3% cost reduction** on average
- **No degradation** in critical trading performance
- **Automatic scaling** based on budget health
- **Prevents budget overruns** with hard limits

## References

- Google BATS Paper: https://arxiv.org/abs/2511.17006
- Implementation: `/home/user/trading/src/utils/budget_tracker.py`
- Integration: `.claude/hooks/ceo/conversation-start.md`
