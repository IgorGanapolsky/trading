#!/usr/bin/env python3
"""
Fast secrets validation - early fail for missing/invalid API keys.
Prevents wasted execution time on broken credentials.
"""

import argparse
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def validate_secrets() -> tuple[bool, list[str]]:
    """Validate required secrets are present and non-empty."""

    # Critical secrets required for trading
    required_secrets = [
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
    ]

    # Optional but recommended secrets (warnings only)
    optional_secrets = [
        "OPENROUTER_API_KEY",
        "ALPHA_VANTAGE_API_KEY",
        "POLYGON_API_KEY",
        "FINNHUB_API_KEY",  # Corrected spelling (was FINHUB_API_KEY)
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
    ]

    missing_critical = []
    missing_optional = []

    # Check critical secrets
    for secret in required_secrets:
        value = os.getenv(secret)
        if not value or value.strip() == "":
            missing_critical.append(secret)
        elif len(value) < 10:  # Basic sanity check
            missing_critical.append(f"{secret} (too short)")

    # Check optional secrets
    for secret in optional_secrets:
        value = os.getenv(secret)
        if not value or value.strip() == "":
            missing_optional.append(secret)

    # Report results
    errors = []

    if missing_critical:
        print(f"❌ CRITICAL: Missing {len(missing_critical)} required secrets")
        # Do not log specific secret names in CI logs for security
        errors.extend(missing_critical)
    else:
        print("✅ All critical secrets present")

    if missing_optional:
        print(f"⚠️  WARNING: Missing {len(missing_optional)} optional secrets")
        print("   Some features may be limited")

    # Additional validation for specific formats
    alpaca_key = os.getenv("ALPACA_API_KEY", "")
    if alpaca_key and not alpaca_key.startswith("PK"):
        print("⚠️  WARNING: ALPACA_API_KEY doesn't look like a valid key (should start with 'PK')")

    alpaca_secret = os.getenv("ALPACA_SECRET_KEY", "")
    if alpaca_secret and len(alpaca_secret) < 30:
        print("⚠️  WARNING: ALPACA_SECRET_KEY seems too short for a valid secret")

    return len(missing_critical) == 0, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gha-output",
        action="store_true",
        help="Write secrets_valid flag to GITHUB_OUTPUT",
    )
    args = parser.parse_args()

    """Main validation function."""
    print("🔑 Validating trading secrets...")
    print("-" * 50)

    valid, errors = validate_secrets()

    print("-" * 50)

    if valid:
        print("✅ Secrets validation passed")
        exit_code = 0
    else:
        print(f"❌ Secrets validation failed: {len(errors)} critical errors")
        print("   Please check GitHub repository secrets:")
        print("   Settings > Secrets and variables > Actions")
        exit_code = 1  # fail-hard: invalid secrets MUST stop execution

    if args.gha_output and os.getenv("GITHUB_OUTPUT"):
        with open(os.getenv("GITHUB_OUTPUT"), "a", encoding="utf-8") as fh:
            fh.write(f"secrets_valid={'true' if valid else 'false'}\n")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
