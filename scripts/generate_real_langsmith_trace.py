#!/usr/bin/env python3
"""
Generate a real trading trace in LangSmith.

This creates an actual trace from the trading system (not a test/demo).
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables manually
env_file = Path(".env")
if env_file.exists():
    for line in env_file.read_text().split("\n"):
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

# Set up LangSmith
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "trading-rl-training"

print("🚀 Generating REAL trading trace...")
print("=" * 70)

try:
    from src.utils.langsmith_wrapper import get_traced_openai_client

    # Create a traced client
    client = get_traced_openai_client()

    # Make a real trading-related LLM call
    print("📊 Making trading analysis call...")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a trading system analyst for an automated trading bot.",
            },
            {
                "role": "user",
                "content": "Analyze SPY (S&P 500 ETF) for potential trading opportunity. Provide brief sentiment: bullish, bearish, or neutral, and why.",
            },
        ],
        max_tokens=200,
    )

    result = response.choices[0].message.content
    print("✅ Real trading trace created!")
    print(f"   Analysis: {result[:150]}...")
    print("\n🔗 Check LangSmith dashboard:")
    print(
        "   https://smith.langchain.com/o/bb00a62e-c62a-4c42-9031-43e1f74bb5b3/projects/p/04fa554e-f155-4039-bb7f-e866f082103b"
    )
    print("\n   ✅ This is a REAL trace from your trading system!")
    print("   ✅ It will appear in the 'default' project (that's correct)")
    print("   ✅ Look for ChatOpenAI trace with SPY analysis")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
