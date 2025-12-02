# LLM Council Integration Guide

## Overview

The LLM Council system implements a multi-stage consensus approach for trading decisions, inspired by [Karpathy's llm-council](https://github.com/karpathy/llm-council). Instead of relying on a single LLM, the system:

1. **Stage 1: First Opinions** - Queries multiple LLMs (Gemini 3 Pro, Claude Sonnet 4, GPT-4o, optional DeepSeek) in parallel
2. **Stage 2: Peer Review** - Each LLM reviews and ranks other responses (anonymized to prevent bias)
3. **Stage 3: Chairman Synthesis** - A designated chairman LLM compiles the final consensus answer

This approach provides higher quality decisions through peer review and consensus, reducing the risk of single-model errors or biases.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM Council Process                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Stage 1: First Opinions                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Gemini 3  │  │  Claude   │  │   GPT-4  │               │
│  │   Pro     │  │  Sonnet   │  │     o    │               │
│  └──────────┘  └──────────┘  └──────────┘               │
│       │             │             │                        │
│       └─────────────┼─────────────┘                        │
│                     │                                       │
│  Stage 2: Peer Review (Anonymized)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Gemini 3  │  │  Claude   │  │   GPT-4  │               │
│  │ Reviews   │  │  Reviews  │  │  Reviews │               │
│  │ Others    │  │  Others   │  │  Others  │               │
│  └──────────┘  └──────────┘  └──────────┘               │
│       │             │             │                        │
│       └─────────────┼─────────────┘                        │
│                     │                                       │
│  Stage 3: Chairman Synthesis                               │
│                     │                                       │
│              ┌──────────────┐                             │
│              │   Chairman    │                             │
│              │  (Gemini 3)   │                             │
│              └──────────────┘                             │
│                     │                                       │
│              Final Consensus Answer                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Enable LLM Council for enhanced consensus decisions
LLM_COUNCIL_ENABLED=true

# OpenRouter API key (required)
OPENROUTER_API_KEY=sk-or-v1-...

# Optional: add DeepSeek via OpenRouter (for reasoning-heavy votes)
OPENROUTER_ENABLE_DEEPSEEK=true
# OPENROUTER_DEEPSEEK_MODEL=deepseek/deepseek-r1
```

### Code Configuration

The council models and chairman can be customized:

```python
from src.core.multi_llm_analysis import LLMModel
from src.core.llm_council_integration import TradingCouncil

# Custom council configuration
council = TradingCouncil(
    council_models=[
        LLMModel.GEMINI_3_PRO,
        LLMModel.CLAUDE_SONNET_4,
        LLMModel.GPT4O,
        LLMModel.DEEPSEEK_R1,
    ],
    chairman_model=LLMModel.GEMINI_3_PRO,  # Chairman model
    enabled=True,
)
```

## Usage

### Basic Usage

```python
from src.core.llm_council_integration import TradingCouncil
import asyncio

async def main():
    council = TradingCouncil(enabled=True)

    # Validate a trade
    result = await council.validate_trade(
        symbol="SPY",
        action="BUY",
        market_data={
            "price": 652.42,
            "rsi": 45,
            "macd_histogram": 0.15,
        },
        context={"portfolio_value": 100000},
    )

    if result["approved"]:
        print(f"Trade approved with {result['confidence']:.2%} confidence")
    else:
        print(f"Trade rejected: {result['reasoning']}")

asyncio.run(main())
```

### Integration with CoreStrategy

The LLM Council is automatically integrated into `CoreStrategy` when enabled:

1. Set `LLM_COUNCIL_ENABLED=true` in your `.env`
2. The council will validate trades before execution
3. Trades are rejected if council consensus is negative

### Trading Council Methods

#### `validate_trade()`

Validates a trading decision using council consensus.

```python
result = await council.validate_trade(
    symbol="SPY",
    action="BUY",
    market_data={...},
    context={...},
)

# Returns:
# {
#     "approved": bool,
#     "confidence": float (0-1),
#     "reasoning": str,
#     "council_response": CouncilResponse,
#     "individual_responses": Dict[str, str],
#     "reviews": Dict[str, Dict],
# }
```

#### `get_trading_recommendation()`

Gets a trading recommendation from the council.

```python
result = await council.get_trading_recommendation(
    symbol="GOOGL",
    market_data={...},
    context={...},
)

# Returns:
# {
#     "action": "BUY" | "SELL" | "HOLD",
#     "confidence": float (0-1),
#     "reasoning": str,
#     ...
# }
```

#### `assess_risk()`

Assesses risk of a proposed position.

```python
result = await council.assess_risk(
    symbol="QQQ",
    position_size=30000,
    market_data={...},
    portfolio_context={...},
)

# Returns:
# {
#     "risk_level": "LOW" | "MEDIUM" | "HIGH",
#     "approved": bool,
#     "confidence": float (0-1),
#     "reasoning": str,
#     ...
# }
```

## Testing

Run the test script to verify the council system:

```bash
python scripts/test_llm_council.py
```

This will run 4 tests:
1. Trade validation
2. Trading recommendation
3. Risk assessment
4. Full 3-stage council process

## Cost Considerations

The LLM Council uses multiple LLM calls:

- **Stage 1**: 3 LLM calls (one per council member)
- **Stage 2**: 3 LLM calls (one review per member)
- **Stage 3**: 1 LLM call (chairman synthesis)

**Total**: ~7 LLM calls per decision

### Estimated Costs (per decision)

| Model | Input Tokens | Output Tokens | Cost per Decision |
|-------|-------------|---------------|-------------------|
| Gemini 3 Pro | ~1000 | ~500 | ~$0.002 |
| Claude Sonnet 4 | ~1000 | ~500 | ~$0.003 |
| GPT-4o | ~1000 | ~500 | ~$0.002 |

**Total per decision**: ~$0.02-0.03

### When to Enable

- ✅ **Enable**: When making significant trading decisions (>$100)
- ✅ **Enable**: For high-confidence validation before large positions
- ⚠️ **Consider**: For daily small trades ($6-10) - cost may exceed benefit
- ❌ **Disable**: During testing/paper trading with small amounts

## Performance

- **Latency**: ~10-15 seconds per decision (7 LLM calls)
- **Reliability**: Higher than single LLM (consensus reduces errors)
- **Quality**: Improved through peer review and synthesis

## Limitations

1. **Latency**: Takes longer than single LLM (10-15s vs 2-3s)
2. **Cost**: ~7x more expensive than single LLM
3. **API Dependencies**: Requires all council models to be available
4. **Fail-Open**: System fails open (approves trades) if council unavailable

## Best Practices

1. **Enable for important decisions**: Use council for significant trades
2. **Monitor costs**: Track API usage and costs
3. **Fail-open design**: System continues if council unavailable
4. **Review council reasoning**: Log and review council decisions for learning
5. **Adjust confidence thresholds**: Tune approval thresholds based on results

## Troubleshooting

### Council Not Initializing

- Check `OPENROUTER_API_KEY` is set
- Verify API key has credits
- Check network connectivity

### High Latency

- Consider disabling Stage 2 (peer review) for faster decisions
- Use fewer council members
- Cache responses when possible

### High Costs

- Disable for small trades
- Use council only for high-value decisions
- Monitor and set budget limits

## Future Enhancements

- [ ] Caching of council responses
- [ ] Adaptive council size (fewer models for simple decisions)
- [ ] Cost optimization (skip Stage 2 for low-value trades)
- [ ] Historical performance tracking
- [ ] Confidence calibration based on past performance
