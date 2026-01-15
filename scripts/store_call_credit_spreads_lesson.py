#!/usr/bin/env python3
"""
Store Call Credit Spreads lesson in Vertex AI RAG.

Source: YouTube - "Credit Spreads | Call Credit Spreads | Call Credit" by Invest with Henry
URL: https://youtu.be/QTK6C5Cq97s
"""

import sys

sys.path.insert(0, "/home/user/trading")

from src.rag.vertex_rag import get_vertex_rag

LESSON_ID = "LL_215_CALL_CREDIT_SPREADS"
LESSON_TITLE = "Call Credit Spreads for Bearish/Neutral Markets"
LESSON_CONTENT = """
## Source
YouTube - "Credit Spreads | Call Credit Spreads | Call Credit" by Invest with Henry
https://youtu.be/QTK6C5Cq97s

## When to Use Call Credit Spreads

### Market Conditions
- Stock has rallied aggressively and appears to be "peaking"
- Bearish or neutral outlook on underlying
- Technical indicators suggest overbought conditions
- Ideal for generating passive income on overextended stocks

### Technical Entry Signals
1. **Bollinger Bands**: Enter when stock is near or above upper band (20-day, 2 std dev)
2. **RSI**: Overbought conditions (RSI > 70) suggest reversal or sideways movement
3. **Use technical levels as buffer** for strike selection - resistance levels add safety

## Contract Specifications (Invest with Henry Method)

| Parameter | Recommendation | Notes |
|-----------|----------------|-------|
| Expiration | 60+ DTE (2 months) | Longer expiry = higher premiums, more passive |
| Delta | 0.15-0.20 | 85% implied win rate |
| Spread Width | $300-$500 | Narrow spreads have poor liquidity |
| Position Size | 10% max capital | More aggressive than our 5% rule |

## Risk Management Rules

1. **Position Sizing**: 10% max capital per trade (we use stricter 5%)
2. **Diversification**: Maintain 10-12 positions across different underlyings
3. **Balance**: Combine call AND put credit spreads for market neutrality
4. **Monitoring**: Check weekly, not daily - avoid "babysitting"

## Trade Management

### If Trade Goes Against You (Stock Rallies)
- **Roll "Up and Out"**: Higher strike, further expiration
- Collect additional credit on the roll if possible
- Accept losses objectively - 1 in 20 losing trades is normal for professionals

### Key Difference from Put Spreads
| Aspect | Put Credit Spread | Call Credit Spread |
|--------|-------------------|-------------------|
| Bias | Bullish | Bearish/Neutral |
| Threatened by | Market drops | Market rallies |
| Roll direction | Down and out | Up and out |
| When to use | Support levels | Resistance/overbought |

## Integration with Our Current Strategy

### Complementary Approach
- **PUT credit spreads**: Use when market/stock at support, bullish outlook
- **CALL credit spreads**: Use when market/stock at resistance, overbought
- **Combined**: Market-neutral income generation regardless of direction

### Modifications for Our $5K Account
- Stick to 5% position sizing (not 10%)
- Focus on SPY/IWM for liquidity
- Use 45-60 DTE (balance premium vs. time risk)
- Target 0.15-0.20 delta for higher win rate

## Prevention (How to Avoid Losing Trades)

1. Only enter when technical signals align (overbought, near resistance)
2. Use 0.15-0.20 delta for 85%+ implied probability
3. Allow 60+ DTE for time to work in your favor
4. Roll up and out if challenged, don't panic close
5. Diversify with both call AND put spreads

## Key Takeaways

1. Call credit spreads = bearish/neutral complement to our bullish put spreads
2. Technical confirmation required: Bollinger Bands + RSI overbought
3. Higher delta = higher win rate: 0.15-0.20 delta vs. our 0.30 for puts
4. Longer duration: 60+ DTE for passive income approach
5. Losses are normal: 1 in 20 losing trades is acceptable for professionals
"""


def main():
    rag = get_vertex_rag()

    if not rag.is_initialized:
        print("Vertex AI RAG not initialized (likely no GCP credentials)")
        print("Lesson content for reference:")
        print("-" * 60)
        print(LESSON_CONTENT)
        print("-" * 60)
        return False

    success = rag.add_lesson(
        lesson_id=LESSON_ID,
        title=LESSON_TITLE,
        content=LESSON_CONTENT,
        severity="MEDIUM",
        category="strategy",
    )

    if success:
        print(f"Lesson '{LESSON_ID}' stored in Vertex AI RAG")
    else:
        print("Failed to store lesson")

    return success


if __name__ == "__main__":
    main()
