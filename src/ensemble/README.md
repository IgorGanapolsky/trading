# Ensemble Voting System

Combines signals from multiple trading models (Momentum, RL, Sentiment) via voting mechanisms to produce a final trading decision.

## Overview

The ensemble voting system provides three voting modes:

1. **Simple Majority**: Most votes win (configurable threshold)
2. **Weighted Voting**: Votes weighted by model confidence and custom weights
3. **Unanimous**: All models must agree (high certainty mode)

## Quick Start

```python
from src.ensemble import EnsembleVoter

# Create voter with custom threshold and weights
voter = EnsembleVoter(
    voting_threshold=0.6,  # 60% agreement required
    weights={"momentum": 0.4, "rl": 0.35, "sentiment": 0.25},
    confidence_floor=0.4  # Ignore votes with confidence < 0.4
)

# Prepare signals from different models
signals = {
    "momentum": {"signal": "buy", "confidence": 0.8},
    "rl": {"signal": "long", "confidence": 0.7},
    "sentiment": {"signal": "bullish", "score": 0.6}
}

# Get ensemble decision
decision = voter.vote(signals)

print(f"Action: {decision.action}")  # "buy", "hold", or "sell"
print(f"Consensus: {decision.consensus_score:.2f}")  # 0.0-1.0
print(f"Confidence: {decision.weighted_confidence:.2f}")  # 0.0-1.0
print(f"Unanimous: {decision.unanimous}")  # True/False
```

## Signal Formats

The ensemble voter accepts signals from different model types and automatically normalizes them:

### Momentum Agent
```python
{
    "momentum": {
        "signal": "buy",  # "buy", "hold", "sell"
        "confidence": 0.8  # 0.0-1.0
    }
}
```

### RL Agent
```python
{
    "rl": {
        "signal": "long",  # "long", "neutral"/"flat", "short"
        "confidence": 0.7  # 0.0-1.0
    }
}
```

### Sentiment Analyzer

**Explicit signal:**
```python
{
    "sentiment": {
        "signal": "bullish",  # "bullish", "neutral_sentiment", "bearish"
        "score": 0.6  # Used as confidence
    }
}
```

**Implicit signal (inferred from score):**
```python
{
    "sentiment": {
        "score": 0.5  # -1.0 to 1.0
        # Converted to:
        # score > 0.2 -> "bullish" (BUY)
        # score < -0.2 -> "bearish" (SELL)
        # -0.2 <= score <= 0.2 -> "neutral" (HOLD)
    }
}
```

## Voting Modes

### 1. Simple Majority

Most votes win, with configurable threshold:

```python
voter = EnsembleVoter(voting_threshold=0.5)  # 50% = simple majority
decision = voter.vote(signals)

# Examples:
# 3 BUY, 0 HOLD, 0 SELL -> BUY (100%)
# 2 BUY, 1 SELL -> BUY (67%)
# 1 BUY, 1 HOLD, 1 SELL -> HOLD (threshold not met)
```

### 2. Weighted Voting

Votes weighted by model weights and confidence:

```python
voter = EnsembleVoter(
    voting_threshold=0.5,
    weights={"momentum": 0.5, "rl": 0.3, "sentiment": 0.2}
)
decision = voter.weighted_vote(signals)

# Each vote's contribution = model_weight * confidence
# Winner = highest weighted score
```

### 3. Unanimous

All models must agree:

```python
voter = EnsembleVoter()
decision = voter.unanimous_required(signals)

# Returns action only if all models vote the same
# Otherwise returns "hold" with consensus_score=0.0
```

## Convenience Functions

For quick usage without creating a voter instance:

```python
from src.ensemble.voting_ensemble import (
    simple_majority_vote,
    weighted_vote,
    unanimous_vote
)

# Simple majority
decision = simple_majority_vote(signals, threshold=0.5)

# Weighted vote
decision = weighted_vote(
    signals,
    weights={"momentum": 0.4, "rl": 0.3, "sentiment": 0.3}
)

# Unanimous
decision = unanimous_vote(signals)
```

## Integration with Orchestrator

### Option 1: Replace Sequential Gating

Replace the sequential gate system with ensemble voting:

```python
# In TradingOrchestrator._process_ticker()

# Gate 1: Momentum
momentum_signal = self.momentum_agent.analyze(ticker)

# Gate 2: RL
rl_decision = self.rl_filter.predict(momentum_signal.indicators)

# Gate 3: Sentiment
llm_result = self.llm_agent.analyze_news(ticker, momentum_signal.indicators)
sentiment_score = llm_result.get("score", 0.0)

# NEW: Ensemble Voting
from src.ensemble import EnsembleVoter

voter = EnsembleVoter(
    voting_threshold=float(os.getenv("ENSEMBLE_THRESHOLD", "0.6")),
    weights={
        "momentum": float(os.getenv("ENSEMBLE_WEIGHT_MOMENTUM", "0.4")),
        "rl": float(os.getenv("ENSEMBLE_WEIGHT_RL", "0.35")),
        "sentiment": float(os.getenv("ENSEMBLE_WEIGHT_SENTIMENT", "0.25")),
    },
    confidence_floor=float(os.getenv("ENSEMBLE_CONFIDENCE_FLOOR", "0.4"))
)

signals = {
    "momentum": {
        "signal": "buy" if momentum_signal.is_buy else "hold",
        "confidence": momentum_signal.strength
    },
    "rl": {
        "signal": rl_decision.get("action"),
        "confidence": rl_decision.get("confidence", 0.0)
    },
    "sentiment": {
        "score": sentiment_score
    }
}

ensemble_decision = voter.weighted_vote(signals)

if ensemble_decision.action != "buy":
    logger.info(
        "Ensemble voting rejected %s: action=%s, consensus=%.2f",
        ticker,
        ensemble_decision.action,
        ensemble_decision.consensus_score
    )
    return

logger.info(
    "Ensemble voting approved %s: consensus=%.2f, confidence=%.2f",
    ticker,
    ensemble_decision.consensus_score,
    ensemble_decision.weighted_confidence
)

# Continue with risk sizing and execution...
```

### Option 2: Add as Additional Gate

Add ensemble voting as a validation step after individual gates:

```python
# After existing gates 1-3...

# Gate 3.5: Ensemble Validation (optional)
ensemble_enabled = os.getenv("ENABLE_ENSEMBLE_VALIDATION", "false").lower() in {"1", "true"}

if ensemble_enabled:
    voter = EnsembleVoter(voting_threshold=0.6)

    signals = {
        "momentum": {"signal": "buy", "confidence": momentum_signal.strength},
        "rl": {"signal": rl_decision.get("action"), "confidence": rl_decision.get("confidence")},
        "sentiment": {"score": sentiment_score}
    }

    ensemble_decision = voter.vote(signals)

    if ensemble_decision.consensus_score < 0.5:
        logger.warning(
            "Gate 3.5 (%s): Low ensemble consensus (%.2f), defaulting to HOLD",
            ticker,
            ensemble_decision.consensus_score
        )
        return
```

### Environment Variables

Add these to `.env` or set as environment variables:

```bash
# Enable ensemble voting
ENABLE_ENSEMBLE_VOTING=true

# Voting mode: "simple", "weighted", "unanimous"
ENSEMBLE_VOTING_MODE=weighted

# Threshold (0.5 = majority, 0.67 = supermajority)
ENSEMBLE_THRESHOLD=0.6

# Model weights (must sum to 1.0, will be normalized)
ENSEMBLE_WEIGHT_MOMENTUM=0.4
ENSEMBLE_WEIGHT_RL=0.35
ENSEMBLE_WEIGHT_SENTIMENT=0.25

# Confidence floor (ignore votes below this)
ENSEMBLE_CONFIDENCE_FLOOR=0.4
```

## Decision Metrics

The `EnsembleDecision` object provides rich metadata:

```python
@dataclass
class EnsembleDecision:
    action: str  # "buy", "hold", "sell"
    consensus_score: float  # 0.0-1.0 (how much agreement)
    votes: dict[str, int]  # {"for": 2, "against": 1, "abstain": 0}
    weighted_confidence: float  # 0.0-1.0 (confidence in decision)
    individual_votes: dict[str, ModelVote]  # Per-model votes
    unanimous: bool  # True if all models agree
    metadata: dict[str, Any]  # Additional info
```

### Using Metrics for Risk Management

```python
decision = voter.weighted_vote(signals)

# Adjust position size based on consensus
if decision.consensus_score >= 0.9:
    position_multiplier = 1.2  # Strong consensus -> larger position
elif decision.consensus_score >= 0.7:
    position_multiplier = 1.0  # Good consensus -> normal position
else:
    position_multiplier = 0.7  # Weak consensus -> smaller position

# Or skip trade if consensus too low
if decision.consensus_score < 0.6:
    logger.info("Skipping trade due to low consensus")
    return

# Or require unanimity for high-risk trades
if high_volatility and not decision.unanimous:
    logger.info("High volatility requires unanimous agreement")
    return
```

## Testing

Run the test suite:

```bash
python -m pytest tests/test_ensemble_voting.py -v
```

Tests cover:
- Signal normalization (all model types)
- Simple majority voting
- Weighted voting
- Unanimous voting
- Confidence floor filtering
- Edge cases (empty signals, ties, etc.)
- Integration scenarios

## Design Principles

1. **Flexible Signal Format**: Automatically normalizes signals from different model types
2. **Confidence-Aware**: Filters low-confidence votes to prevent weak signals from influencing decisions
3. **Configurable Thresholds**: Adjust voting requirements based on market conditions
4. **Rich Metadata**: Provides detailed vote breakdown for analysis and debugging
5. **Fail-Safe**: Defaults to HOLD when votes are unclear or conflicting

## Performance Considerations

- **Latency**: Ensemble voting adds ~1-2ms overhead (negligible compared to model inference)
- **Memory**: Minimal (stores 3 votes + metadata)
- **Logging**: All decisions logged for audit trail and analysis

## Future Enhancements

Potential improvements:
- [ ] Adaptive threshold adjustment based on recent performance
- [ ] Model performance tracking (weight models that perform better)
- [ ] Time-weighted voting (recent model accuracy influences weights)
- [ ] Regime-specific voting rules (different weights per market regime)
- [ ] Confidence calibration (adjust confidence scores based on historical accuracy)

## References

- **Sequential Gating**: Current hybrid funnel in `src/orchestrator/main.py`
- **Momentum Agent**: `src/agents/momentum_agent.py`
- **RL Filter**: `src/agents/rl_agent.py`
- **Multi-LLM Analyzer**: `src/core/multi_llm_analysis.py`
