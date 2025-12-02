#!/usr/bin/env python3
"""
Verify API credentials are loaded correctly from environment.

This script checks that credentials are properly configured without
making actual API calls (which require dependencies).
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.utils.security import mask_api_key

load_dotenv()


def verify_grok_credentials():
    """Verify Grok API credentials."""
    print("=" * 70)
    print("🔐 VERIFYING GROK/X.AI API CREDENTIALS")
    print("=" * 70)

    grok_key = os.getenv("GROK_API_KEY")

    if not grok_key:
        print("❌ GROK_API_KEY not found in environment")
        return False

    if not grok_key.startswith("xai-"):
        masked = mask_api_key(grok_key)
        print(f"⚠️  GROK_API_KEY format unexpected (should start with 'xai-'): {masked}")
        return False

    print("✅ GROK_API_KEY found")
    masked = mask_api_key(grok_key)
    print(f"   Key: {masked}")
    print(f"   Length: {len(grok_key)} characters")
    return True


def verify_x_com_credentials():
    """Verify X.com API credentials."""
    print("\n" + "=" * 70)
    print("🔐 VERIFYING X.COM API CREDENTIALS")
    print("=" * 70)

    credentials = {
        "X_API_KEY": os.getenv("X_API_KEY"),
        "X_API_SECRET": os.getenv("X_API_SECRET"),
        "X_BEARER_TOKEN": os.getenv("X_BEARER_TOKEN"),
        "X_CLIENT_ID": os.getenv("X_CLIENT_ID"),
        "X_CLIENT_SECRET": os.getenv("X_CLIENT_SECRET"),
        "X_ACCESS_TOKEN": os.getenv("X_ACCESS_TOKEN"),
        "X_ACCESS_TOKEN_SECRET": os.getenv("X_ACCESS_TOKEN_SECRET"),
    }

    found = []
    missing = []

    for name, value in credentials.items():
        if value:
            found.append(name)
            # Mask value for security (CodeQL-safe pattern)
            masked = mask_api_key(value)
            print(f"✅ {name}: {masked}")
        else:
            missing.append(name)
            print(f"⚠️  {name}: Not found")

    if missing:
        print(f"\n⚠️  Missing credentials: {', '.join(missing)}")
        return len(found) > 0  # Partial success if some credentials found
    else:
        print(f"\n✅ All X.com credentials found ({len(found)} total)")
        return True


def main():
    """Run credential verification."""
    print("\n" + "=" * 70)
    print("🚀 API CREDENTIAL VERIFICATION")
    print("=" * 70)
    print()

    results = {
        "Grok API": verify_grok_credentials(),
        "X.com API": verify_x_com_credentials(),
    }

    print("\n" + "=" * 70)
    print("📊 VERIFICATION SUMMARY")
    print("=" * 70)

    for name, passed in results.items():
        status = "✅ VERIFIED" if passed else "❌ MISSING"
        print(f"   {name}: {status}")

    all_verified = all(results.values())

    if all_verified:
        print("\n🎉 All API credentials verified and ready to use!")
        print("\n💡 Next steps:")
        print("   1. Credentials are loaded from .env file")
        print("   2. System will use them automatically when making API calls")
        print("   3. Test actual API calls with: python3 scripts/test_grok_x_api.py")
    else:
        print("\n⚠️  Some credentials are missing. Check your .env file.")

    return 0 if all_verified else 1


if __name__ == "__main__":
    sys.exit(main())
