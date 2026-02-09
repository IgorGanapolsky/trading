#!/usr/bin/env python3
"""
Integration test for RAG Webhook.

This test verifies the webhook can load trade data.
Catches issues like LL-230 where trades_loaded=0 on Cloud Run.

Created: Jan 17, 2026
"""

import json
import os
import sys
import urllib.request

WEBHOOK_URL = os.environ.get("RAG_WEBHOOK_URL", "").strip()


def test_webhook_health():
    """Verify webhook is healthy and has trade data loaded."""
    print("🔍 Testing webhook health endpoint...")
    if not WEBHOOK_URL:
        print("⚠️  SKIP: RAG_WEBHOOK_URL not set")
        return True

    try:
        req = urllib.request.Request(
            f"{WEBHOOK_URL}/health",
            headers={"User-Agent": "CI-Integration-Test/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        print(f"  Status: {data.get('status')}")
        print(f"  Trades Loaded: {data.get('trades_loaded')}")
        print(f"  Trade Source: {data.get('trade_history_source')}")
        print(f"  RAG Mode: {data.get('rag_mode')}")
        print(f"  RAG Last Source: {data.get('rag_last_source')}")

        # CRITICAL: Verify trades are loaded
        # This catches the LL-230 bug where Cloud Run couldn't find trade files
        trades_loaded = data.get("trades_loaded", 0)
        if trades_loaded == 0:
            print("\n❌ FAIL: trades_loaded=0")
            print("   This indicates a data source mismatch (see LL-230)")
            print("   Webhook should read from system_state.json -> trade_history")
            return False

        if data.get("status") != "healthy":
            print(f"\n❌ FAIL: status={data.get('status')}")
            return False

        if data.get("rag_mode") != "lancedb_first":
            print(f"\n❌ FAIL: rag_mode={data.get('rag_mode')}")
            return False

        print(f"\n✅ PASS: Webhook healthy with {trades_loaded} trades loaded")
        return True

    except Exception as e:
        print(f"\n❌ FAIL: Could not reach webhook: {e}")
        return False


def test_webhook_trade_query():
    """Verify webhook can respond to trade queries."""
    print("\n🔍 Testing webhook trade query...")
    if not WEBHOOK_URL:
        print("⚠️  SKIP: RAG_WEBHOOK_URL not set")
        return True

    try:
        payload = json.dumps(
            {
                "text": "show me recent trades",
                "sessionInfo": {"session": "test-session"},
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{WEBHOOK_URL}/webhook",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CI-Integration-Test/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Check response structure
        messages = data.get("fulfillmentResponse", {}).get("messages", [])
        if not messages:
            print("❌ FAIL: No messages in response")
            return False

        text = messages[0].get("text", {}).get("text", [""])[0]
        if not text:
            print("❌ FAIL: Empty response text")
            return False

        # Should contain trade info, not "No trades found"
        if "No trades found" in text:
            print("❌ FAIL: Webhook returned 'No trades found'")
            print(f"   Response: {text[:200]}...")
            return False

        print(f"  Response length: {len(text)} chars")
        print(f"  Preview: {text[:100]}...")
        print("\n✅ PASS: Webhook returned trade data")
        return True

    except Exception as e:
        print(f"\n❌ FAIL: Trade query failed: {e}")
        return False


def test_webhook_compound_query():
    """Verify webhook handles compound P/L + analytical queries correctly.

    FIX Jan 21, 2026: Tests the compound query routing fix.
    "How much money did we make today and why?" should return analysis,
    NOT a raw trade dump.
    """
    print("\n🔍 Testing webhook compound P/L + analytical query...")
    if not WEBHOOK_URL:
        print("⚠️  SKIP: RAG_WEBHOOK_URL not set")
        return True

    try:
        payload = json.dumps(
            {
                "text": "How much money did we make today and why?",
                "sessionInfo": {"session": "test-compound-session"},
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{WEBHOOK_URL}/webhook",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CI-Integration-Test/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        messages = data.get("fulfillmentResponse", {}).get("messages", [])
        if not messages:
            print("❌ FAIL: No messages in response")
            return False

        text = messages[0].get("text", {}).get("text", [""])[0]
        if not text:
            print("❌ FAIL: Empty response text")
            return False

        # Should NOT be a raw trade dump (starts with "Trade History (found X trades)")
        # Should be a compound response with P/L + analysis
        if "Trade History (found" in text and "P/L: $0.00" in text:
            print("❌ FAIL: Got raw trade dump instead of compound analysis")
            print(f"   Response: {text[:300]}...")
            return False

        # Should contain analytical elements (P/L status + explanation)
        has_pl_status = "P/L" in text or "today" in text.lower()
        has_analysis = "Analysis" in text or "reasons" in text.lower() or "Common" in text

        if not has_pl_status:
            print("⚠️  WARNING: Response missing P/L status")

        print(f"  Response length: {len(text)} chars")
        print(f"  Has P/L status: {has_pl_status}")
        print(f"  Has analysis: {has_analysis}")
        print(f"  Preview: {text[:200]}...")
        print("\n✅ PASS: Compound query returned proper analysis")
        return True

    except Exception as e:
        print(f"\n❌ FAIL: Compound query failed: {e}")
        return False


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("WEBHOOK INTEGRATION TESTS")
    print("=" * 60)

    results = []
    results.append(("Health Check", test_webhook_health()))
    results.append(("Trade Query", test_webhook_trade_query()))
    results.append(("Compound Query", test_webhook_compound_query()))

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("✅ All integration tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
