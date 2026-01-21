#!/usr/bin/env python3
"""
Store Options Trading Fundamentals lesson in Vertex AI RAG.

Source: HDFC Sky - Introduction to Options Trading
https://youtu.be/Y53nIHUVUFA
"""

import sys

sys.path.insert(0, "/home/user/trading")

from src.rag.vertex_rag import get_vertex_rag

LESSON_ID = "OPTIONS_FUNDAMENTALS_001"
LESSON_TITLE = "Options Trading Fundamentals (CE vs PE, Strike, Premium, Expiry)"
LESSON_CONTENT = """
## Source
HDFC Sky - Introduction to Options Trading
https://youtu.be/Y53nIHUVUFA

## Key Concepts

### 1. Options vs Futures - Critical Difference
- **Futures**: Both buyer AND seller MUST complete the transaction at set price (obligation for both)
- **Options**: Buyer has the RIGHT but NOT obligation. Only seller is obligated if buyer exercises.
- This asymmetry is what makes options powerful for risk management.

### 2. Call Options (CE) vs Put Options (PE)
- **Call Option (CE)**: Right to BUY at strike price. Use when BULLISH (expect price to rise).
- **Put Option (PE)**: Right to SELL at strike price. Use when BEARISH (expect price to fall).
- "E" suffix means European-style: can ONLY exercise on expiry day, not before.

### 3. Key Contract Components (Check Before Every Trade)
- **Strike Price**: The fixed price at which you agree to buy/sell the underlying
- **Expiry Date**:
  - Stocks: Last Thursday of every month
  - Indices (SPY, IWM equivalents): Weekly expiries every Thursday
- **Premium**: Up-front fee buyer pays to seller. This is MAX RISK for buyer.

### 4. Practical Example (Call Option)
Setup: Bullish on stock, buy Call with Strike $270, pay $7.50 premium
- If stock = $300 at expiry: Exercise option, buy at $270, profit = $30 - $7.50 = $22.50
- If stock < $270 at expiry: Don't exercise, lose only the $7.50 premium
- Maximum loss is ALWAYS the premium paid (for option buyers)

## Relevance to Credit Spreads Strategy
Our credit spread strategy SELLS options (we are the "seller" who is obligated).
- When we sell a 30-delta put spread: We receive premium, but must buy stock if price drops
- The bought put (20-delta) limits our max loss
- Understanding buyer vs seller dynamics is CRITICAL for spreads

## Action Items
1. Always verify strike, expiry, and premium before entering trades
2. Remember: As spread SELLERS, we have obligations - manage risk accordingly
3. Use 30+ DTE expiries to benefit from theta decay (as noted in CLAUDE.md)
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
        severity="LOW",  # Foundational knowledge, not a mistake
        category="options_education",
    )

    if success:
        print(f"✅ Lesson '{LESSON_ID}' stored in Vertex AI RAG")
    else:
        print("❌ Failed to store lesson")

    return success


if __name__ == "__main__":
    main()
