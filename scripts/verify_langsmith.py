#!/usr/bin/env python3
"""
LangSmith Verification Script

Verifies that LangSmith tracing is properly configured and working.
Run this script to diagnose LangSmith integration issues.

Usage:
    python3 scripts/verify_langsmith.py
"""

import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def check_env_vars():
    """Check required environment variables."""
    print("\n" + "=" * 60)
    print("LANGSMITH ENVIRONMENT VARIABLE CHECK")
    print("=" * 60)

    # Check both naming conventions
    langchain_key = os.getenv("LANGCHAIN_API_KEY")
    langsmith_key = os.getenv("LANGSMITH_API_KEY")
    langchain_project = os.getenv("LANGCHAIN_PROJECT")
    langsmith_project = os.getenv("LANGSMITH_PROJECT")
    tracing_v2 = os.getenv("LANGCHAIN_TRACING_V2")

    issues = []

    if langchain_key:
        print(f"  LANGCHAIN_API_KEY: {'*' * 8}...{langchain_key[-4:]}")
    elif langsmith_key:
        print(f"  LANGSMITH_API_KEY: {'*' * 8}...{langsmith_key[-4:]}")
    else:
        print("  LANGCHAIN_API_KEY: NOT SET")
        print("  LANGSMITH_API_KEY: NOT SET")
        issues.append("No API key found (set LANGCHAIN_API_KEY or LANGSMITH_API_KEY)")

    project = langchain_project or langsmith_project or "trading-system"
    print(f"  Project: {project}")
    print(f"  LANGCHAIN_TRACING_V2: {tracing_v2 or 'NOT SET'}")

    return len(issues) == 0, issues


def check_wrapper_status():
    """Check if the wrapper is properly initialized."""
    print("\n" + "=" * 60)
    print("LANGSMITH WRAPPER STATUS")
    print("=" * 60)

    try:
        from src.utils.langsmith_wrapper import (
            LANGSMITH_ENABLED,
            get_observability_status,
            is_langsmith_enabled,
        )

        status = get_observability_status()
        print(f"  LANGSMITH_ENABLED: {LANGSMITH_ENABLED}")
        print(f"  is_langsmith_enabled(): {is_langsmith_enabled()}")
        print(f"  Project: {status['langsmith'].get('project', 'N/A')}")
        print(f"  Dashboard: {status['langsmith'].get('dashboard', 'N/A')}")

        return is_langsmith_enabled()
    except ImportError as e:
        print(f"  ERROR: Could not import wrapper: {e}")
        return False


def check_langsmith_sdk():
    """Check if langsmith SDK is installed and working."""
    print("\n" + "=" * 60)
    print("LANGSMITH SDK CHECK")
    print("=" * 60)

    try:
        import langsmith
        from langsmith import Client

        print(f"  langsmith version: {langsmith.__version__}")

        # Try to create a client
        try:
            client = Client()
            print("  Client initialized: True")
            print(f"  API URL: {client.api_url}")
            return True
        except Exception as e:
            print(f"  Client initialization failed: {e}")
            return False

    except ImportError:
        print("  ERROR: langsmith package not installed")
        print("  Run: pip install langsmith")
        return False


def send_test_trace():
    """Send a test trace to verify connection."""
    print("\n" + "=" * 60)
    print("SENDING TEST TRACE")
    print("=" * 60)

    try:
        from langsmith import traceable

        @traceable(name="langsmith_verification_test")
        def test_function():
            """A simple test function that gets traced."""
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "message": "LangSmith verification test completed",
            }

        result = test_function()
        print(f"  Test function executed: {result['status']}")
        print(f"  Timestamp: {result['timestamp']}")
        print("  Check LangSmith dashboard for 'langsmith_verification_test' trace")
        return True

    except Exception as e:
        print(f"  ERROR sending test trace: {e}")
        return False


def check_openai_wrapper():
    """Check if OpenAI client wrapping works."""
    print("\n" + "=" * 60)
    print("OPENAI CLIENT WRAPPER CHECK")
    print("=" * 60)

    try:
        from src.utils.langsmith_wrapper import get_traced_openai_client

        client = get_traced_openai_client()
        print(f"  Client type: {type(client).__name__}")
        print(f"  Base URL: {getattr(client, 'base_url', 'N/A')}")

        # Check if it's wrapped
        if hasattr(client, "_langsmith_extra"):
            print("  LangSmith wrapping: ACTIVE")
        else:
            print("  LangSmith wrapping: Unknown (may still be active)")

        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    """Run all verification checks."""
    print("\n" + "=" * 60)
    print("LANGSMITH VERIFICATION REPORT")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    results = {}

    # Run all checks
    env_ok, env_issues = check_env_vars()
    results["env_vars"] = env_ok

    results["wrapper"] = check_wrapper_status()
    results["sdk"] = check_langsmith_sdk()
    results["openai_wrapper"] = check_openai_wrapper()

    if results["sdk"] and results["wrapper"]:
        results["test_trace"] = send_test_trace()
    else:
        print("\n  Skipping test trace (SDK or wrapper not working)")
        results["test_trace"] = False

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_passed = all(results.values())
    for check, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {check}: {status}")

    print()
    if all_passed:
        print("ALL CHECKS PASSED - LangSmith should be working")
        print("View traces at: https://smith.langchain.com")
    else:
        print("SOME CHECKS FAILED - Review issues above")
        if not results["env_vars"]:
            print("\nTo fix: Set LANGCHAIN_API_KEY in your environment or .env file")
            print("Get your API key from: https://smith.langchain.com/settings")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
