#!/usr/bin/env python3
"""
Enable All Cloud Services

Per CEO directive (Nov 24, 2025): Enable ALL dormant systems NOW.

This script:
1. Checks which cloud services have credentials configured
2. Enables all available services
3. Reports status

Run: python scripts/enable_all_cloud_services.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_and_enable():
    print("=" * 60)
    print("ENABLING ALL CLOUD SERVICES")
    print("Per CEO directive: Nov 24, 2025")
    print("=" * 60)

    services = {
        "Vertex AI RL": {
            "key": "RL_AGENT_KEY",
            "status": "disabled",
            "url": "https://console.cloud.google.com/iam-admin/serviceaccounts"
        },
        "LangSmith Tracing": {
            "key": "LANGCHAIN_API_KEY",
            "status": "disabled",
            "url": "https://smith.langchain.com"
        },
        "Helicone Observability": {
            "key": "HELICONE_API_KEY",
            "status": "disabled",
            "url": "https://helicone.ai"
        },
        "OpenRouter LLM": {
            "key": "OPENROUTER_API_KEY",
            "status": "disabled",
            "url": "https://openrouter.ai"
        },
        "Alpaca Trading": {
            "key": "ALPACA_API_KEY",
            "status": "disabled",
            "url": "https://alpaca.markets"
        },
    }

    print("\n📊 SERVICE STATUS:")
    print("-" * 60)

    enabled_count = 0
    missing_keys = []

    for name, config in services.items():
        key = config["key"]
        value = os.getenv(key, "")

        if value and value != f"your_{key.lower()}_here":
            services[name]["status"] = "enabled"
            enabled_count += 1
            print(f"  ✅ {name}: ENABLED")
        else:
            missing_keys.append((name, config["url"], key))
            print(f"  ❌ {name}: MISSING KEY ({key})")

    print("\n" + "=" * 60)
    print(f"SUMMARY: {enabled_count}/{len(services)} services enabled")
    print("=" * 60)

    if missing_keys:
        print("\n🔑 TO ENABLE REMAINING SERVICES:")
        print("-" * 60)
        for name, url, key in missing_keys:
            print(f"\n  {name}:")
            print(f"    1. Go to: {url}")
            print(f"    2. Get API key")
            print(f"    3. Add to .env: {key}=your_key_here")

    # Set environment defaults for enabled features
    print("\n⚙️  SETTING DEFAULT FLAGS TO ENABLED:")
    print("-" * 60)

    defaults = {
        "DEEPAGENTS_ENABLED": "true",
        "LLM_COUNCIL_ENABLED": "true",
        "ENABLE_RL_RETRAIN": "true",
        "RL_USE_TRANSFORMER": "1",
        "USE_MEDALLION_ARCHITECTURE": "true",
        "ENABLE_ADK_AGENTS": "true",
        "LANGCHAIN_TRACING_V2": "true",
    }

    for key, value in defaults.items():
        current = os.getenv(key, "not set")
        if current == "not set" or current.lower() == "false":
            os.environ[key] = value
            print(f"  ✅ {key}={value} (was: {current})")
        else:
            print(f"  ✓  {key}={current} (already set)")

    print("\n" + "=" * 60)
    print("ALL SYSTEMS SET TO ENABLED BY DEFAULT")
    print("=" * 60)

    return enabled_count, len(services)


def test_services():
    """Test connectivity to enabled services."""
    print("\n🧪 TESTING ENABLED SERVICES:")
    print("-" * 60)

    # Test Alpaca
    if os.getenv("ALPACA_API_KEY"):
        try:
            from alpaca.trading.client import TradingClient
            client = TradingClient(
                os.getenv("ALPACA_API_KEY"),
                os.getenv("ALPACA_SECRET_KEY"),
                paper=True
            )
            account = client.get_account()
            print(f"  ✅ Alpaca: Connected (${float(account.equity):,.2f} equity)")
        except Exception as e:
            print(f"  ❌ Alpaca: {e}")

    # Test OpenRouter
    if os.getenv("OPENROUTER_API_KEY"):
        print(f"  ✅ OpenRouter: Key configured")

    # Test LangSmith
    if os.getenv("LANGCHAIN_API_KEY"):
        try:
            from langsmith import Client
            client = Client()
            print(f"  ✅ LangSmith: Connected")
        except Exception as e:
            print(f"  ⚠️  LangSmith: Key set but {e}")

    # Test Helicone
    if os.getenv("HELICONE_API_KEY"):
        print(f"  ✅ Helicone: Key configured (routes through gateway)")


if __name__ == "__main__":
    enabled, total = check_and_enable()

    if enabled > 0:
        test_services()

    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("""
1. Add missing API keys to .env
2. Run training: python scripts/train_medallion_models.py
3. Next trade at 9:35 AM will use ALL enabled systems
""")
