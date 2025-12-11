# LLM Hallucination RAG Guard

**Created**: December 11, 2025
**Status**: ✅ Production Ready
**Test Coverage**: 35/35 tests passing (100%)

## Overview

The LLM Hallucination RAG Guard is a comprehensive validation system that detects when LLM outputs contain invalid trades, validates against past hallucination patterns, and prevents trading system failures.

### Key Features

1. **Regex-based Field Validation** - Tickers, actions, sides validated with strict patterns
2. **Type Safety Checks** - Detects NaN, null, infinity, and other invalid values
3. **Range Validation** - Ensures sentiment, confidence, amounts within valid bounds
4. **Business Logic** - Position sizing, portfolio constraints, reasoning quality
5. **RAG Integration** - Queries past hallucinations for similar patterns
6. **Actionable Prevention Steps** - Returns specific steps from lessons learned

## Validation Stages

The guard validates LLM outputs through 5 stages:

### Stage 1: Type Safety
```python
# Detects:
- None/null values
- NaN (float("nan"))
- Infinity (float("inf"))
- Invalid strings ("nan", "null", "undefined", "N/A")
```

### Stage 2: Format Validation
```python
# Regex patterns:
- Ticker: ^[A-Z]{1,5}$
- Action: BUY|SELL|HOLD (case-insensitive)
- Side: buy|sell|long|short|hold|neutral
```

### Stage 3: Range Validation
```python
# Bounds:
- Sentiment: [-1.0, 1.0]
- Confidence: [0.0, 1.0]
  - Warning if >0.70 (FACTS Benchmark ceiling)
- Amount: positive numbers only
```

### Stage 4: Business Logic
```python
# Rules:
- Position size: <= 10% of portfolio (configurable)
- Reasoning: minimum 10 characters
- Trade direction: must be valid buy/sell/hold
```

### Stage 5: RAG Lookup
```python
# Queries RAG for:
- Similar past hallucinations
- Prevention steps from lessons learned
- Severity and frequency data
```

## Quick Start

### Basic Usage

```python
from src.verification import create_hallucination_guard

# Create guard with approved tickers
guard = create_hallucination_guard(
    valid_tickers=["SPY", "QQQ", "AAPL"],
    max_position_pct=0.10  # 10% max position size
)

# Validate LLM output
llm_output = {
    "symbol": "SPY",
    "action": "BUY",
    "amount": 10.0,
    "confidence": 0.68,
    "sentiment": 0.3,
    "reasoning": "Strong MACD crossover with volume confirmation"
}

result = guard.validate_output(llm_output)

if result["valid"]:
    print("✅ Output valid, safe to trade")
else:
    print(f"❌ Output invalid: {len(result['violations'])} violations")
    print(f"Risk score: {result['risk_score']}")
```

### Integration Example: Signal Agent

```python
from src.verification import create_hallucination_guard

def validate_signal_before_execution(signal_output):
    guard = create_hallucination_guard(
        valid_tickers=["SPY", "QQQ", "AAPL", "NVDA"],
        max_position_pct=0.10
    )

    result = guard.validate_output(signal_output)

    if not result["valid"]:
        # Log violations
        for violation in result["violations"]:
            if violation["severity"] == "critical":
                logger.error(
                    "CRITICAL: %s - %s",
                    violation["field"],
                    violation["message"]
                )

        # Show prevention steps from RAG
        for step in result["prevention_steps"]:
            logger.info("Prevention: %s", step)

        return False  # Block trade

    return True  # Allow trade
```

## Output Format

The guard returns a detailed validation result:

```python
{
    "valid": bool,                    # True if no critical violations
    "violations": [                   # List of violations
        {
            "field": str,             # Field name
            "severity": str,          # "critical" | "warning" | "info"
            "message": str,           # Human-readable message
            "actual_value": str,      # What was received
            "expected_format": str    # What was expected
        }
    ],
    "similar_hallucinations": [       # From RAG search
        {
            "id": str,
            "title": str,
            "description": str,
            "prevention": str,
            "severity": str,
            "relevance": float        # 0-1 similarity score
        }
    ],
    "prevention_steps": [str],        # Actionable steps
    "risk_score": float,              # 0-1, higher = more risky
    "timestamp": str                  # ISO 8601
}
```

## Known Hallucination Patterns

The guard includes 6 default patterns:

1. **Invalid Ticker** - LLM generates invalid symbols (APPL, sp500)
2. **Confidence Overestimation** - Claims >70% confidence (exceeds FACTS)
3. **NaN Values** - Outputs NaN, null, undefined
4. **Negative Amounts** - Suggests negative trade amounts
5. **Sentiment Out of Range** - Sentiment outside [-1, 1]
6. **Fabricated Prices** - Invents specific prices without data

## Risk Scoring

Risk scores are calculated based on violation severity:

- **Critical violation**: +0.4 to risk score
- **Warning**: +0.2 to risk score
- **Info**: +0.1 to risk score
- **Maximum**: 1.0 (capped)

**Recommended thresholds**:
- Risk < 0.3: Low risk, allow trade
- Risk 0.3-0.6: Medium risk, require review
- Risk > 0.6: High risk, block trade

## Integration with Existing Systems

### HallucinationPreventionPipeline

The guard **complements** the existing `HallucinationPreventionPipeline`:

| Feature | LLMHallucinationGuard | HallucinationPreventionPipeline |
|---------|----------------------|--------------------------------|
| Focus | **Immediate validation** | **Long-term learning** |
| Timing | Pre-trade (real-time) | Pre/during/post-trade |
| Method | Regex + range checks | Prediction tracking |
| RAG | Pattern similarity | Mistake learning |
| Use Case | Block invalid trades | Learn from outcomes |

**Use both together**:
```python
from src.verification import (
    create_hallucination_guard,
    create_hallucination_pipeline
)

# Guard: Immediate validation
guard = create_hallucination_guard()
guard_result = guard.validate_output(llm_output)

if not guard_result["valid"]:
    return "BLOCKED BY GUARD"

# Pipeline: Record prediction for learning
pipeline = create_hallucination_pipeline()
prediction_id = pipeline.record_prediction(
    model="claude-3.5-sonnet",
    symbol="SPY",
    predicted_action="BUY",
    predicted_direction="UP",
    confidence=0.68,
    reasoning="MACD crossover"
)

# Execute trade...

# Later: Verify prediction outcome
pipeline.verify_prediction(
    prediction_id=prediction_id,
    actual_direction="UP",
    actual_pnl=5.25
)
```

### FACTS Benchmark Integration

The guard enforces FACTS Benchmark limits:

```python
# FACTS Benchmark (Google DeepMind, Dec 2025):
# - No top LLM achieves >70% factuality
# - Gemini 3 Pro: 68.8%
# - Claude models: ~66-67%
# - GPT-4o: ~65.8%

# Guard warns when confidence >0.70:
output = {"confidence": 0.85}  # Exceeds ceiling
result = guard.validate_output(output)
# Warning: "Confidence 0.85 exceeds FACTS ceiling (0.70)"
```

## Testing

**Test Coverage**: 35 tests, 100% passing

Run tests:
```bash
pytest tests/test_llm_hallucination_guard.py -v
```

Test categories:
- Type validation (5 tests)
- Format validation (5 tests)
- Range validation (8 tests)
- Business logic (4 tests)
- Pattern matching (2 tests)
- RAG integration (2 tests)
- Risk scoring (4 tests)
- Factory function (2 tests)
- Complex scenarios (3 tests)

## Examples

See `/home/user/trading/examples/llm_hallucination_guard_integration.py` for:

1. Signal Agent integration
2. RL Agent validation
3. Pre-trade validation pipeline
4. Multi-LLM council validation

Run examples:
```bash
PYTHONPATH=/home/user/trading python3 examples/llm_hallucination_guard_integration.py
```

## Performance

**Validation Speed**: ~0.001s per output (1ms)
**Memory**: ~5MB (includes RAG index)
**Dependencies**:
- Core: None (works without RAG)
- Optional: `sentence-transformers` for RAG similarity search

## Files

| File | Purpose |
|------|---------|
| `src/verification/llm_hallucination_rag_guard.py` | Main guard implementation |
| `tests/test_llm_hallucination_guard.py` | Comprehensive test suite |
| `examples/llm_hallucination_guard_integration.py` | Integration examples |
| `docs/llm_hallucination_guard.md` | This documentation |

## Best Practices

1. **Always validate before execution**:
   ```python
   result = guard.validate_output(llm_output)
   if not result["valid"]:
       return "BLOCKED"
   execute_trade(llm_output)
   ```

2. **Log violations for learning**:
   ```python
   if result["violations"]:
       for v in result["violations"]:
           logger.warning("Violation: %s", v["message"])
   ```

3. **Use prevention steps**:
   ```python
   if result["prevention_steps"]:
       for step in result["prevention_steps"]:
           apply_prevention(step)
   ```

4. **Monitor risk scores**:
   ```python
   if result["risk_score"] > 0.6:
       alert_team("High risk LLM output detected")
   ```

5. **Combine with pipeline**:
   ```python
   # Guard validates, pipeline learns
   guard.validate_output(output)
   pipeline.record_prediction(...)
   ```

## Future Enhancements

- [ ] ML-based pattern detection (beyond regex)
- [ ] Auto-learning from production violations
- [ ] Integration with alerting system
- [ ] Historical violation dashboard
- [ ] Per-model hallucination tracking

## References

- [Google DeepMind FACTS Benchmark](https://deepmind.google/blog/facts-benchmark-suite)
- [Lesson Learned: FACTS Benchmark](/home/user/trading/rag_knowledge/lessons_learned/ll_011_facts_benchmark_factuality_ceiling.md)
- [HallucinationPreventionPipeline](/home/user/trading/src/verification/hallucination_prevention.py)
- [Verification Framework](/home/user/trading/docs/verification-protocols.md)

## Support

For issues or questions:
1. Check test suite for examples
2. Review integration examples
3. Consult hallucination prevention pipeline docs
4. Check RAG lessons learned for similar patterns
