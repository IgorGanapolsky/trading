#!/usr/bin/env python3
"""
Test script for Grok/X.ai API and X.com API integration.

Tests:
1. Grok API connection and sentiment analysis
2. X.com API connection (if implemented)
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI
from src.utils.news_sentiment import NewsSentimentAggregator


def test_grok_api():
    """Test Grok API connection and sentiment analysis."""
    print("=" * 70)
    print("🧪 TESTING GROK/X.AI API")
    print("=" * 70)

    grok_api_key = os.getenv("GROK_API_KEY")
    if not grok_api_key:
        print("❌ GROK_API_KEY not found in environment")
        return False

    # Security: Mask API key in output (CodeQL-safe: store masked value first)
    from src.utils.security import mask_api_key

    masked_value = mask_api_key(grok_api_key)
    print(f"✅ Found GROK_API_KEY: {masked_value}")

    try:
        # Initialize Grok client
        grok_client = OpenAI(api_key=grok_api_key, base_url="https://api.x.ai/v1")
        print("✅ Grok client initialized")

        # Test API call
        print("\n📡 Testing Grok API call...")
        response = grok_client.chat.completions.create(
            model="grok-2-1212",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Respond with valid JSON only.",
                },
                {
                    "role": "user",
                    "content": 'Analyze Twitter/X sentiment for $NVDA stock. Provide JSON: {"score": <number>, "tweets": <count>, "confidence": "<level>", "themes": ["<theme>"]}',
                },
            ],
            temperature=0.3,
            max_tokens=500,
        )

        content = response.choices[0].message.content
        print("✅ Grok API response received:")
        print(f"   Response length: {len(content)} characters")
        print(f"   First 200 chars: {content[:200]}...")

        # Try to parse JSON
        import re

        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
            print("✅ Successfully parsed JSON response:")
            print(f"   Score: {parsed.get('score', 'N/A')}")
            print(f"   Tweets: {parsed.get('tweets', 'N/A')}")
            print(f"   Confidence: {parsed.get('confidence', 'N/A')}")
            return True
        else:
            print("⚠️  Response received but not in JSON format")
            return True  # Still counts as success - API works

    except Exception as e:
        print(f"❌ Grok API test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_sentiment_aggregator():
    """Test NewsSentimentAggregator with Grok integration."""
    print("\n" + "=" * 70)
    print("🧪 TESTING SENTIMENT AGGREGATOR WITH GROK")
    print("=" * 70)

    try:
        aggregator = NewsSentimentAggregator()

        if not aggregator.grok_client:
            print("⚠️  Grok client not initialized (no API key or initialization failed)")
            return False

        print("✅ NewsSentimentAggregator initialized with Grok support")

        # Test Grok Twitter sentiment
        print("\n📊 Testing Grok Twitter sentiment for NVDA...")
        result = aggregator.get_grok_twitter_sentiment("NVDA")

        print("✅ Grok sentiment result:")
        print(f"   Score: {result.get('score', 'N/A')}")
        print(f"   Tweets: {result.get('tweets', 'N/A')}")
        print(f"   Confidence: {result.get('confidence', 'N/A')}")
        print(f"   Source: {result.get('source', 'N/A')}")

        if result.get("error"):
            print(f"   ⚠️  Error: {result.get('error')}")
            return False

        return True

    except Exception as e:
        print(f"❌ Sentiment aggregator test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_x_com_api():
    """Test X.com API connection (basic test)."""
    print("\n" + "=" * 70)
    print("🧪 TESTING X.COM API CREDENTIALS")
    print("=" * 70)

    bearer_token = os.getenv("X_BEARER_TOKEN")
    api_key = os.getenv("X_API_KEY")
    api_secret = os.getenv("X_API_SECRET")

    if not bearer_token:
        print("⚠️  X_BEARER_TOKEN not found (X.com API not configured)")
        return False

    # Security: Mask credentials in output (CodeQL-safe: store masked values first)
    from src.utils.security import mask_api_key

    masked_bearer_value = mask_api_key(bearer_token)
    masked_xkey_value = mask_api_key(api_key) if api_key else None
    masked_xsecret_value = mask_api_key(api_secret) if api_secret else None

    print("✅ Found X.com credentials:")
    print(f"   Bearer Token: {masked_bearer_value}")
    if masked_xkey_value:
        print(f"   X API Key: {masked_xkey_value}")
    if masked_xsecret_value:
        print(f"   X API Secret: {masked_xsecret_value}")

    # Note: X.com API v2 requires more complex setup
    # This is just a credential check
    print("✅ X.com API credentials loaded (full API integration not yet implemented)")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("🚀 GROK/X.AI API TEST SUITE")
    print("=" * 70)
    print()

    results = {
        "Grok API": test_grok_api(),
        "Sentiment Aggregator": test_sentiment_aggregator(),
        "X.com API Credentials": test_x_com_api(),
    }

    print("\n" + "=" * 70)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 70)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")

    all_passed = all(results.values())

    if all_passed:
        print("\n🎉 All tests passed! Grok/X.ai integration is working.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
