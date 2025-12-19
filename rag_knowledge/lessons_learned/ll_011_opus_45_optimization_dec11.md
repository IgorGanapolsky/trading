# Lesson Learned: Claude Opus 4.5 Optimization (Dec 11, 2025)

**ID**: ll_011
**Date**: December 11, 2025
**Severity**: OPTIMIZATION
**Category**: AI/ML, Cost Optimization, Model Selection
**Impact**: 40-60% reduction in LLM costs while maintaining quality

## Executive Summary

Implemented effort-based model selection and smart council patterns for Claude Opus 4.5,
enabling significant cost reduction while maintaining decision quality for critical trades.

## The Opportunity

### Before Optimization

| Metric | Value |
|--------|-------|
| Model Used | Full council for ALL trades |
| Cost per Trade | ~$0.08-0.10 |
| Time per Analysis | 15-30 seconds |
| Council Models | Always 3+ models |

### After Optimization

| Metric | Value |
|--------|-------|
| Routine Trades | Single model (Gemini Flash/Sonnet) |
| Standard Trades | 2-model consensus |
| Critical Trades | Full 3-stage council |
| Estimated Savings | 40-60% |

## Implementation

### 1. EffortLevel Enum

```python
class EffortLevel(Enum):
    LOW = "low"      # Haiku/Flash, 500 tokens, temp 0.3
    MEDIUM = "medium"  # Sonnet, 2000 tokens, temp 0.5
    HIGH = "high"    # Opus, 4096 tokens, temp 0.7
```

### 2. Agent-Specific Effort

```python
agent_effort_levels = {
    "execution_agent": EffortLevel.LOW,   # Simple order execution
    "signal_agent": EffortLevel.MEDIUM,   # Standard analysis
    "risk_agent": EffortLevel.MEDIUM,     # Risk calculations
    "research_agent": EffortLevel.HIGH,   # Deep research
    "rl_agent": EffortLevel.HIGH,         # RL reasoning
    "meta_agent": EffortLevel.HIGH,       # Coordination
}
```

### 3. Confidence-Based Escalation

```python
def should_escalate_model(confidence: float, current_effort: EffortLevel) -> bool:
    """Escalate if confidence < 0.7 and not already at HIGH"""
    if current_effort == EffortLevel.HIGH:
        return False
    return confidence < 0.7
```

### 4. Smart Council Modes

| Mode | Use Case | Cost |
|------|----------|------|
| `routine` | Standard signals, routine checks | Single model |
| `standard` | Important trades, unclear signals | 2-model consensus |
| `critical` | Large positions, risky conditions | Full 3-stage council |

## Key Decisions

### When to Use Each Mode

**ROUTINE (80% of trades)**:
- Standard technical signals (MACD, RSI)
- Small position sizes (< $50)
- High historical win rate patterns
- Routine rebalancing

**STANDARD (15% of trades)**:
- Mid-size positions ($50-200)
- Mixed signals (some bullish, some bearish)
- New symbols not in training data
- Market regime uncertainty

**CRITICAL (5% of trades)**:
- Large positions (> $200)
- High volatility conditions
- Major news events
- Position exits (lock in gains/cut losses)

## Verification Tests

### Test 1: Effort Configuration Works
```python
def test_effort_config_levels():
    """Verify effort configs are correctly defined."""
    from src.agent_framework.agent_sdk_config import EffortConfig, EffortLevel

    low = EffortConfig.for_level(EffortLevel.LOW)
    assert low.max_tokens == 500
    assert low.temperature == 0.3

    high = EffortConfig.for_level(EffortLevel.HIGH)
    assert high.max_tokens == 4096
```

### Test 2: Model Selection by Effort
```python
def test_model_selection_by_effort():
    """Verify correct model selection per effort level."""
    from src.agent_framework.agent_sdk_config import get_agent_sdk_config, EffortLevel

    config = get_agent_sdk_config()

    assert "haiku" in config.get_model_for_effort(EffortLevel.LOW)
    assert "sonnet" in config.get_model_for_effort(EffortLevel.MEDIUM)
    assert "opus" in config.get_model_for_effort(EffortLevel.HIGH)
```

### Test 3: Confidence Escalation
```python
def test_confidence_escalation_triggers():
    """Verify escalation triggers at confidence threshold."""
    from src.agent_framework.agent_sdk_config import get_agent_sdk_config, EffortLevel

    config = get_agent_sdk_config()

    # Low confidence should escalate
    assert config.should_escalate_model(0.5, EffortLevel.LOW) == True
    assert config.should_escalate_model(0.5, EffortLevel.MEDIUM) == True

    # High confidence should not escalate
    assert config.should_escalate_model(0.9, EffortLevel.LOW) == False

    # HIGH effort never escalates
    assert config.should_escalate_model(0.3, EffortLevel.HIGH) == False
```

## Metrics to Track

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Cost per trade (routine) | < $0.02 | > $0.05 |
| Cost per trade (critical) | < $0.10 | > $0.15 |
| Win rate (routine) | > 55% | < 50% |
| Win rate (critical) | > 65% | < 55% |
| Escalation rate | < 20% | > 40% |
| Council usage | < 10% | > 25% |

## Key Principles

### 1. Start Low, Escalate on Uncertainty
> "Don't pay for Opus when Haiku will do."

### 2. Full Council Only for Critical Decisions
> "Multi-model consensus is expensive. Use it wisely."

### 3. Confidence-Driven Model Selection
> "Let the model tell you when it needs help."

### 4. Trade Importance Determines Analysis Depth
> "A $10 trade doesn't need a $0.10 analysis."

## Cost Analysis

### Opus 4.5 Pricing (67% cheaper than Opus 3)
| Model | Input (per 1M) | Output (per 1M) |
|-------|----------------|-----------------|
| Opus 4.5 | $5 | $25 |
| Sonnet 4.5 | $3 | $15 |
| Haiku 3.5 | $0.25 | $1.25 |

### Expected Monthly Savings
- Before: ~$50/month (full council every trade)
- After: ~$20/month (smart routing)
- **Savings: ~$30/month (60%)**

## Integration with RAG

This lesson is indexed for:
1. **Model Selection Queries**: "which model should I use for X"
2. **Cost Optimization Queries**: "how to reduce LLM costs"
3. **Agent Configuration Queries**: "how to configure agent effort levels"

## Related Files

- `src/agent_framework/agent_sdk_config.py` - EffortLevel, EffortConfig
- `src/core/multi_llm_analysis.py` - smart_council(), quick_analysis()
- `tests/test_opus_optimization.py` - Verification tests

## Tags

#opus-4.5 #cost-optimization #model-selection #effort-level #smart-council #llm #rag #ml

## Change Log

- 2025-12-11: Initial implementation
- 2025-12-11: Added to RAG lessons learned
