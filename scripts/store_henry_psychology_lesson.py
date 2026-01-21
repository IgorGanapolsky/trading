#!/usr/bin/env python3
"""
Store Trading Psychology and Strategy Management lessons from Invest with Henry.

Source: Secret Options Trading Strategies to Outsmart the Market (Full Course)
https://youtu.be/OQhahDREU0g
"""

import sys

sys.path.insert(0, "/home/user/trading")

from src.rag.vertex_rag import get_vertex_rag

LESSON_ID = "PSYCHOLOGY_HENRY_001"
LESSON_TITLE = "Trading Psychology & Strategy Management (Invest with Henry)"
LESSON_CONTENT = """
## Source
Invest with Henry - Secret Options Trading Strategies to Outsmart the Market
https://youtu.be/OQhahDREU0g

## Core Thesis
Trading success is 20% finance, 80% psychology.

## 1. Strategic Trade Management

### Rolling Options (CRITICAL)
- Roll positions BEFORE expiration to avoid assignment
- Buy back current option, sell new one further out in time
- Example: 5 DTE put getting close? Roll to 30 DTE to collect more premium

### Delta as Risk Gauge
- Keep delta at 20-30 when selling puts/covered calls
- 20 delta = ~80% probability of expiring OTM (profitable)
- 30 delta = ~70% probability of expiring OTM
- NEVER sell ATM options (50 delta = coin flip)

### Ex-Dividend Warning (FOR COVERED CALLS)
- Check ex-dividend dates before selling covered calls
- Options may be exercised EARLY to capture dividend
- Can result in unexpected stock being called away

## 2. Market Inefficiency Exploitation

### IV Rank (IVR) - Entry Timing
- IVR > 80% = Premiums unusually high = OPTIMAL time to sell
- IVR 50-80% = Good selling environment
- IVR < 30% = Consider buying premium or waiting
- Our MIN_IV_RANK=20 is for filtering, but 80%+ is IDEAL

### Momentum Wheel Strategy
- Focus on high-quality, high-momentum stocks
- Targets: SPY, IWM (already in our watchlist)
- Sell puts on pullbacks to potentially enter at better prices

## 3. Psychological Bias Defense

### Overconfidence Combat
- NEVER think you're "above average"
- Stick to system even during winning streaks
- Avoid "revenge trading" after losses

### Confirmation Bias
- Don't "fall in love" with any stock
- ACTIVELY seek bearish news even on bullish positions
- Example: Before trading SOFI, check for negative analyst reports

### Gambler's Fallacy
- Past results DON'T predict future outcomes
- 5 green days in a row doesn't change tomorrow's probability
- Each trade is independent

## 4. Risk Management Rules

### Position Sizing - 15% MAX
- Video recommends 15% max per position
- Our current: 25% (too aggressive?)
- Consider tightening for psychological comfort

### Expected Value > Win Rate
- 90% win rate is worthless if losses wipe gains
- Focus on Positive Expected Value setups
- Example: Win $50 on 70% of trades, lose $100 on 30%
  = Expected value: (0.7 × $50) + (0.3 × -$100) = $35 - $30 = +$5/trade

### Trade Less, Earn More
- Overtrading benefits brokers, not you
- Target 10-15 high-conviction trades per week
- Quality over quantity

## Implementation for Our System

### Already Implemented ✅
- Delta 20-30 target (trading_thresholds.py)
- IV Rank tracking (iv_data_provider.py)
- Stop loss at 2x premium
- Take profit at 50%

### TODO - New Additions
1. Add rolling logic before 5 DTE
2. Add ex-dividend check for covered calls
3. Consider tightening MAX_POSITION_PCT from 25% to 15%
4. Add trade frequency limiter (max 15/week)

## Key Quotes
- "Trading is 20% finance, 80% psychology"
- "Never allocate more than 15% to any single position"
- "Focus on expected value, not win rate"
"""


def main():
    rag = get_vertex_rag()

    if not rag.is_initialized:
        print("⚠️  Vertex AI RAG not initialized (likely no GCP credentials)")
        print("Lesson content for reference:")
        print("-" * 60)
        print(LESSON_CONTENT)
        print("-" * 60)
        return False

    success = rag.add_lesson(
        lesson_id=LESSON_ID,
        title=LESSON_TITLE,
        content=LESSON_CONTENT,
        severity="MEDIUM",  # Contains actionable improvements
        category="psychology_risk_management",
    )

    if success:
        print(f"✅ Lesson '{LESSON_ID}' stored in Vertex AI RAG")
    else:
        print("❌ Failed to store lesson")

    return success


if __name__ == "__main__":
    main()
