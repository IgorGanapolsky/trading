#!/usr/bin/env python3
"""
Integration test for RAG Webhook.

This test verifies the webhook can load trade data.
Catches issues like LL-230 where trades_loaded=0 on Cloud Run.

Created: Jan 17, 2026
"""

import json
import os
import urllib.request

import pytest

WEBHOOK_URL = os.environ.get("RAG_WEBHOOK_URL", "").strip()


def test_webhook_health():
    """Verify webhook is healthy and has trade data loaded."""
    print("🔍 Testing webhook health endpoint...")
    if not WEBHOOK_URL:
        pytest.skip("RAG_WEBHOOK_URL not set")

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
            pytest.fail("trades_loaded=0; webhook data source does not match canonical state")

        if data.get("status") != "healthy":
            pytest.fail(f"unexpected webhook status: {data.get('status')}")

        if data.get("rag_mode") != "lancedb_first":
            pytest.fail(f"unexpected RAG mode: {data.get('rag_mode')}")

        print(f"\n✅ PASS: Webhook healthy with {trades_loaded} trades loaded")

    except Exception as e:
        pytest.fail(f"could not reach webhook: {e}", pytrace=False)


def test_webhook_trade_query():
    """Verify webhook can respond to trade queries."""
    print("\n🔍 Testing webhook trade query...")
    if not WEBHOOK_URL:
        pytest.skip("RAG_WEBHOOK_URL not set")

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
            pytest.fail("no messages in webhook response")

        text = messages[0].get("text", {}).get("text", [""])[0]
        if not text:
            pytest.fail("empty webhook response text")

        # Should contain trade info, not "No trades found"
        if "No trades found" in text:
            pytest.fail("webhook returned 'No trades found'")

        print(f"  Response length: {len(text)} chars")
        print(f"  Preview: {text[:100]}...")
        print("\n✅ PASS: Webhook returned trade data")

    except Exception as e:
        pytest.fail(f"trade query failed: {e}", pytrace=False)


def test_webhook_compound_query():
    """Verify webhook handles compound P/L + analytical queries correctly.

    FIX Jan 21, 2026: Tests the compound query routing fix.
    "How much money did we make today and why?" should return analysis,
    NOT a raw trade dump.
    """
    print("\n🔍 Testing webhook compound P/L + analytical query...")
    if not WEBHOOK_URL:
        pytest.skip("RAG_WEBHOOK_URL not set")

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
            pytest.fail("no messages in compound webhook response")

        text = messages[0].get("text", {}).get("text", [""])[0]
        if not text:
            pytest.fail("empty compound webhook response text")

        # Should NOT be a raw trade dump (starts with "Trade History (found X trades)")
        # Should be a compound response with P/L + analysis
        if "Trade History (found" in text and "P/L: $0.00" in text:
            pytest.fail("compound query returned a raw trade dump")

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

    except Exception as e:
        pytest.fail(f"compound query failed: {e}", pytrace=False)
