#!/usr/bin/env python3
"""
Direct Gemini 3 Test - No Dependencies

Tests Gemini 3 integration directly without importing full trading system.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("🧪 DIRECT GEMINI 3 TEST")
print("=" * 80)

# Check API key
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("\n❌ GOOGLE_API_KEY not found")
    print("   Set it in .env file")
    sys.exit(1)

# Security: Mask API key in output (CodeQL-safe: store masked value first)
from src.utils.security import mask_api_key

masked_value = mask_api_key(api_key)
print(f"\n✅ GOOGLE_API_KEY found: {masked_value}")

# Test direct Gemini API
try:
    import google.generativeai as genai

    print("\n🔧 Configuring Gemini API...")
    genai.configure(api_key=api_key)

    print("✅ Gemini API configured")

    # Test simple generation
    print("\n📝 Testing simple generation...")
    model = genai.GenerativeModel("gemini-3.0-pro")

    prompt = """You are a trading AI assistant. Analyze this scenario:

Symbol: SPY
Current Price: $652.42
Entry Price: $682.70
Loss: -4.44%

Provide a brief analysis (2-3 sentences) of whether this is a good entry point."""

    response = model.generate_content(prompt)

    print("\n" + "=" * 80)
    print("📋 GEMINI 3 RESPONSE")
    print("=" * 80)
    print(f"\n{response.text}")

    print("\n" + "=" * 80)
    print("✅ GEMINI 3 TEST SUCCESSFUL")
    print("=" * 80)
    print("\n✅ API connection working")
    print("✅ Model responding")
    print("✅ Ready for integration")

except ImportError as e:
    print(f"\n❌ Import error: {e}")
    print("   Install: pip install google-generativeai")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
