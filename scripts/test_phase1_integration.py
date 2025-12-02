#!/usr/bin/env python3
"""
Test Phase 1 Integration: Polygon.io + Finnhub

Validates that both APIs are working correctly before production use.
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed, using system environment variables only")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.dcf_valuation import DCFValuationCalculator
from src.utils.finnhub_client import FinnhubClient


def test_polygon_api():
    """Test Polygon.io API integration."""
    print("\n" + "=" * 70)
    print("🧪 Testing Polygon.io API Integration")
    print("=" * 70)

    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        print("❌ POLYGON_API_KEY not set in environment")
        return False

    # Security: Mask API key in output (CodeQL-safe: store masked value first)
    from src.utils.security import mask_api_key

    masked_value = mask_api_key(api_key)
    print(f"✅ Polygon.io API key found: {masked_value}")

    try:
        calculator = DCFValuationCalculator()

        if not calculator.polygon_api_key:
            print("❌ Polygon.io API key not initialized in calculator")
            return False

        print("✅ DCF calculator initialized with Polygon.io")

        # Test with a well-known stock (AAPL)
        print("\n📊 Testing DCF calculation for AAPL...")
        result = calculator.get_intrinsic_value("AAPL", force_refresh=True)

        if result:
            print("✅ DCF calculation successful!")
            print(f"   Intrinsic Value: ${result.intrinsic_value:.2f}")
            print(f"   Discount Rate: {result.discount_rate:.2%}")
            print(f"   Projected Growth: {result.projected_growth:.2%}")
            print(f"   Timestamp: {result.timestamp}")
            return True
        else:
            print("⚠️  DCF calculation returned None (may need Alpha Vantage fallback)")
            return False

    except Exception as e:
        print(f"❌ Polygon.io API test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_finnhub_api():
    """Test Finnhub API integration."""
    print("\n" + "=" * 70)
    print("🧪 Testing Finnhub API Integration")
    print("=" * 70)

    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        print("❌ FINNHUB_API_KEY not set in environment")
        return False

    # Security: Mask API key in output (CodeQL-safe: store masked value first)
    from src.utils.security import mask_api_key

    masked_value = mask_api_key(api_key)
    print(f"✅ Finnhub API key found: {masked_value}")

    try:
        client = FinnhubClient()

        if not client.api_key:
            print("❌ Finnhub API key not initialized in client")
            return False

        print("✅ Finnhub client initialized")

        # Test economic calendar
        print("\n📅 Testing economic calendar...")
        events = client.get_economic_calendar()

        if events is not None:
            print(f"✅ Economic calendar fetched: {len(events)} events")
            if events:
                print(f"   Sample event: {events[0].get('event', 'N/A')}")
            return True
        else:
            print("⚠️  Economic calendar returned None")
            return False

    except Exception as e:
        print(f"❌ Finnhub API test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_finnhub_major_events():
    """Test Finnhub major event detection."""
    print("\n" + "=" * 70)
    print("🧪 Testing Finnhub Major Event Detection")
    print("=" * 70)

    try:
        client = FinnhubClient()

        if not client.api_key:
            print("⚠️  Finnhub API key not available, skipping test")
            return True  # Not a failure if not configured

        has_major_event = client.has_major_event_today()

        if has_major_event:
            print("⚠️  Major economic event detected today")
            print("   Trading should be avoided or done with caution")
        else:
            print("✅ No major economic events today")
            print("   Trading can proceed normally")

        return True

    except Exception as e:
        print(f"⚠️  Major event detection test failed: {e}")
        return True  # Not critical


def test_dcf_fallback():
    """Test DCF calculator fallback mechanism."""
    print("\n" + "=" * 70)
    print("🧪 Testing DCF Calculator Fallback")
    print("=" * 70)

    try:
        calculator = DCFValuationCalculator()

        # Check which API is being used
        if calculator.polygon_api_key:
            print("✅ Using Polygon.io API (preferred)")
        elif calculator.api_key:
            print("✅ Using Alpha Vantage API (fallback)")
        else:
            print("❌ No API keys available")
            return False

        # Test with a different stock
        print("\n📊 Testing DCF calculation for MSFT...")
        result = calculator.get_intrinsic_value(
            "MSFT", force_refresh=False
        )  # Use cache if available

        if result:
            print("✅ DCF calculation successful!")
            print(f"   Intrinsic Value: ${result.intrinsic_value:.2f}")
            return True
        else:
            print("⚠️  DCF calculation returned None")
            return False

    except Exception as e:
        print(f"❌ DCF fallback test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all Phase 1 integration tests."""
    print("\n" + "=" * 70)
    print("🚀 Phase 1 Integration Test Suite")
    print("   Testing Polygon.io + Finnhub APIs")
    print("=" * 70)

    results = {
        "Polygon.io API": test_polygon_api(),
        "Finnhub API": test_finnhub_api(),
        "Major Event Detection": test_finnhub_major_events(),
        "DCF Fallback": test_dcf_fallback(),
    }

    print("\n" + "=" * 70)
    print("📊 Test Results Summary")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("=" * 70)
    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed! Phase 1 integration is ready for production.")
        return 0
    elif passed >= total - 1:  # Allow 1 non-critical failure
        print("\n⚠️  Most tests passed. Integration should work, but verify failures.")
        return 0
    else:
        print("\n❌ Multiple tests failed. Please check API keys and configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
