#!/usr/bin/env python3
"""
Quick validation script to test API connections
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 60)
print("🔍 VALIDATING SYSTEM SETUP")
print("=" * 60)

# 1. Check environment variables
print("\n1️⃣ Checking Environment Variables...")
alpaca_key = os.getenv("ALPACA_API_KEY")
alpaca_secret = os.getenv("ALPACA_SECRET_KEY")
openrouter_key = os.getenv("OPENROUTER_API_KEY")

if alpaca_key and alpaca_secret and openrouter_key:
    print(f"   ✅ Alpaca Key: {alpaca_key[:10]}...")
    print(f"   ✅ Alpaca Secret: {alpaca_secret[:10]}...")
    print(f"   ✅ OpenRouter Key: {openrouter_key[:15]}...")
else:
    print("   ❌ Missing API keys in .env file!")
    sys.exit(1)

# 2. Test Alpaca connection
print("\n2️⃣ Testing Alpaca Connection...")
try:
    from alpaca.trading.client import TradingClient

    trader = TradingClient(alpaca_key, alpaca_secret, paper=True)
    account = trader.get_account()

    print(f"   ✅ Connected to Alpaca!")
    print(f"   📊 Account Status: {account.status}")
    print(f"   💰 Buying Power: ${float(account.buying_power):,.2f}")
    print(f"   💵 Cash: ${float(account.cash):,.2f}")
    print(f"   📈 Equity: ${float(account.equity):,.2f}")
    print(f"   🔒 Paper Trading: {account.account_number.startswith('P')}")

except Exception as e:
    print(f"   ❌ Alpaca connection failed: {e}")
    sys.exit(1)

# 3. Test OpenRouter connection
print("\n3️⃣ Testing OpenRouter Connection...")
try:
    from openai import OpenAI

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=openrouter_key)

    # Simple test query
    response = client.chat.completions.create(
        model="anthropic/claude-3.5-sonnet",
        messages=[{"role": "user", "content": "Reply with just: WORKING"}],
        max_tokens=10,
    )

    result = response.choices[0].message.content.strip()
    print(f"   ✅ Connected to OpenRouter!")
    print(f"   🤖 Test Response: {result}")
    print(f"   💳 Credits: Available (no error)")

except Exception as e:
    print(f"   ❌ OpenRouter connection failed: {e}")
    sys.exit(1)

# 4. Check file structure
print("\n4️⃣ Checking File Structure...")
required_files = [
    "src/core/multi_llm_analysis.py",
    "src/core/alpaca_trader.py",
    "src/core/risk_manager.py",
    "src/strategies/core_strategy.py",
    "src/strategies/growth_strategy.py",
    "src/strategies/ipo_strategy.py",
    "src/main.py",
    "dashboard/dashboard.py",
]

all_present = True
for file in required_files:
    if os.path.exists(file):
        print(f"   ✅ {file}")
    else:
        print(f"   ❌ {file} - MISSING!")
        all_present = False

if not all_present:
    print("\n   ⚠️  Some files are missing!")
    sys.exit(1)

# 5. Summary
print("\n" + "=" * 60)
print("✅ ALL SYSTEMS GO!")
print("=" * 60)
print("\n📋 Next Steps:")
print("   1. Run paper trade test: python3 src/main.py --mode paper --run-once")
print("   2. Launch dashboard: streamlit run dashboard/dashboard.py")
print("   3. Review logs: tail -f logs/trading.log")
print("\n🎯 Your system is ready for paper trading!")
print("=" * 60)
