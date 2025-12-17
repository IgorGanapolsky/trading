#!/usr/bin/env python3
"""
Pre-Trade Deep Research Script

Runs Gemini Deep Research analysis before trading sessions.
Used by: .github/workflows/pre-trade-research.yml

Created: December 2025
"""

import json
import os
import sys
import time
from datetime import datetime


def run_research(symbol: str = "SPY") -> bool:
    """Run deep research on a symbol using Google Gemini."""
    try:
        from google import genai

        client = genai.Client()

        query = f"""
        Analyze {symbol} for today's trading decision:
        1. Current price action and trend
        2. Key news in last 24 hours
        3. Market sentiment (bullish/bearish/neutral)
        4. Risk factors
        5. Trading recommendation: BUY, SELL, or HOLD

        Be concise and actionable for a day trader.
        """

        print(f"🔍 Researching {symbol}...")

        interaction = client.interactions.create(
            input=query,
            agent="deep-research-pro-preview-12-2025",
            background=True,
        )

        # Wait for completion (5 min timeout)
        for _ in range(30):
            interaction = client.interactions.get(interaction.id)
            if interaction.status == "completed":
                print("=" * 60)
                print(f"DEEP RESEARCH: {symbol}")
                print("=" * 60)
                print(interaction.outputs[-1].text)

                # Save to file
                os.makedirs("data", exist_ok=True)
                output_file = (
                    f'data/research_{symbol}_{datetime.now().strftime("%Y%m%d")}.json'
                )
                with open(output_file, "w") as f:
                    json.dump(
                        {
                            "symbol": symbol,
                            "timestamp": datetime.utcnow().isoformat(),
                            "research": interaction.outputs[-1].text,
                        },
                        f,
                        indent=2,
                    )
                print(f"\n✅ Saved to {output_file}")
                return True
            elif interaction.status == "failed":
                print(f"❌ Research failed: {interaction.error}")
                return False
            time.sleep(10)

        print("⏱️ Research timeout")
        return False

    except ImportError:
        print("⚠️ google-genai not available")
        return False
    except Exception as e:
        print(f"⚠️ Research error: {e}")
        print("Continuing without deep research...")
        return False


def main():
    """Main entry point."""
    symbol = os.getenv("INPUT_SYMBOL", "SPY")
    if len(sys.argv) > 1:
        symbol = sys.argv[1]

    success = run_research(symbol)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
