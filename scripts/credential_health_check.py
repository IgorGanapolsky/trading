#!/usr/bin/env python3
"""
CREDENTIAL HEALTH CHECK

Pre-trading credential validation. This runs BEFORE any trading activity
to verify all API credentials are valid and working.

CRITICAL: If this fails, trading MUST NOT proceed. Stale/invalid credentials
caused 5 consecutive workflow failures (Jan 2026 incident).

Usage:
    python scripts/credential_health_check.py
    python scripts/credential_health_check.py --notify-on-failure
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def check_alpaca_credentials() -> dict:
    """Check Alpaca API credentials are valid."""
    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret_key = get_alpaca_credentials()
    paper_mode = os.getenv("PAPER_TRADING", "true").lower() == "true"

    result = {
        "service": "Alpaca",
        "status": "unknown",
        "message": "",
        "details": {},
    }

    if not api_key or not secret_key:
        result["status"] = "missing"
        result["message"] = "ALPACA_API_KEY or ALPACA_SECRET_KEY not set"
        return result

    # Determine the correct base URL
    if paper_mode:
        base_url = "https://paper-api.alpaca.markets"
    else:
        base_url = "https://api.alpaca.markets"

    try:
        req = Request(
            f"{base_url}/v2/account",
            headers={
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": secret_key,
            },
        )
        with urlopen(req, timeout=10) as response:
            if response.status == 200:
                account = json.loads(response.read().decode("utf-8"))
                result["status"] = "valid"
                result["message"] = "Credentials verified"
                result["details"] = {
                    "account_status": account.get("status"),
                    "equity": float(account.get("equity", 0)),
                    "buying_power": float(account.get("buying_power", 0)),
                    "mode": "paper" if paper_mode else "live",
                }
                return result
    except HTTPError as e:
        if e.code == 401:
            result["status"] = "invalid"
            result["message"] = "Unauthorized - credentials are invalid or expired"
        elif e.code == 403:
            result["status"] = "invalid"
            result["message"] = "Forbidden - check if keys match paper/live mode"
        else:
            result["status"] = "error"
            result["message"] = f"HTTP error {e.code}: {e.reason}"
    except URLError as e:
        result["status"] = "error"
        result["message"] = f"Network error: {e.reason}"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Unexpected error: {e}"

    return result


def check_anthropic_credentials() -> dict:
    """Check Anthropic API credentials."""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    result = {
        "service": "Anthropic",
        "status": "unknown",
        "message": "",
        "details": {},
    }

    if not api_key:
        result["status"] = "missing"
        result["message"] = "ANTHROPIC_API_KEY not set (will use fallback)"
        return result

    # We don't actually call the API - just verify the key format
    if api_key.startswith("sk-ant-"):
        result["status"] = "valid"
        result["message"] = "Key format valid (not tested - optional service)"
    else:
        result["status"] = "warning"
        result["message"] = "Key format unexpected (may still work)"

    return result


def check_openrouter_credentials() -> dict:
    """Check OpenRouter API credentials."""
    api_key = os.getenv("OPENROUTER_API_KEY")

    result = {
        "service": "OpenRouter",
        "status": "unknown",
        "message": "",
        "details": {},
    }

    if not api_key:
        result["status"] = "missing"
        result["message"] = "OPENROUTER_API_KEY not set (will use fallback)"
        return result

    # Test with a simple API call
    try:
        req = Request(
            "https://openrouter.ai/api/v1/auth/key",
            headers={
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                result["status"] = "valid"
                result["message"] = "Credentials verified"
                result["details"] = {
                    "label": data.get("data", {}).get("label", "unknown"),
                    "usage_limit": data.get("data", {}).get("limit", 0),
                }
                return result
    except HTTPError as e:
        if e.code == 401:
            result["status"] = "invalid"
            result["message"] = "Unauthorized - API key invalid"
        else:
            result["status"] = "warning"
            result["message"] = f"Could not verify (HTTP {e.code}) - may still work"
    except Exception as e:
        result["status"] = "warning"
        result["message"] = f"Could not verify ({e}) - may still work"

    return result


def check_finnhub_credentials() -> dict:
    """Check Finnhub API credentials."""
    api_key = os.getenv("FINNHUB_API_KEY")

    result = {
        "service": "Finnhub",
        "status": "unknown",
        "message": "",
        "details": {},
    }

    if not api_key:
        result["status"] = "missing"
        result["message"] = "FINNHUB_API_KEY not set (economic calendar disabled)"
        return result

    try:
        req = Request(
            f"https://finnhub.io/api/v1/stock/profile2?symbol=AAPL&token={api_key}",
        )
        with urlopen(req, timeout=10) as response:
            if response.status == 200:
                result["status"] = "valid"
                result["message"] = "Credentials verified"
                return result
    except HTTPError as e:
        if e.code == 401:
            result["status"] = "invalid"
            result["message"] = "Unauthorized - API key invalid"
        elif e.code == 429:
            result["status"] = "valid"
            result["message"] = "Rate limited but credentials valid"
        else:
            result["status"] = "warning"
            result["message"] = f"Could not verify (HTTP {e.code})"
    except Exception as e:
        result["status"] = "warning"
        result["message"] = f"Could not verify ({e})"

    return result


def run_health_check(notify_on_failure: bool = False) -> bool:
    """
    Run credential health check for all services.

    Returns True if critical credentials are valid.
    """
    print("\n" + "=" * 70)
    print("🔑 CREDENTIAL HEALTH CHECK")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print("=" * 70 + "\n")

    # Check all services
    checks = [
        check_alpaca_credentials(),
        check_anthropic_credentials(),
        check_openrouter_credentials(),
        check_finnhub_credentials(),
    ]

    # Display results
    critical_services = ["Alpaca"]  # These MUST be valid
    critical_passed = True
    warnings = []

    for check in checks:
        service = check["service"]
        status = check["status"]
        message = check["message"]

        if status == "valid":
            print(f"✅ {service}: {message}")
            if check["details"]:
                for key, value in check["details"].items():
                    if isinstance(value, float):
                        print(f"   {key}: ${value:,.2f}")
                    else:
                        print(f"   {key}: {value}")
        elif status == "missing":
            if service in critical_services:
                print(f"❌ {service}: {message}")
                critical_passed = False
            else:
                print(f"⚠️  {service}: {message}")
                warnings.append(f"{service}: {message}")
        elif status == "invalid":
            print(f"❌ {service}: {message}")
            if service in critical_services:
                critical_passed = False
            else:
                warnings.append(f"{service}: {message}")
        elif status == "warning":
            print(f"⚠️  {service}: {message}")
            warnings.append(f"{service}: {message}")
        else:
            print(f"❓ {service}: {message}")

    print("\n" + "=" * 70)

    # Save health check result
    health_file = Path("data/credential_health.json")
    health_file.parent.mkdir(exist_ok=True)

    health_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "critical_passed": critical_passed,
        "warnings": warnings,
        "checks": checks,
    }

    with open(health_file, "w") as f:
        json.dump(health_data, f, indent=2)

    if critical_passed:
        if warnings:
            print(f"✅ CREDENTIAL CHECK PASSED (with {len(warnings)} warnings)")
        else:
            print("✅ CREDENTIAL CHECK PASSED - All credentials valid")
        print("=" * 70 + "\n")
        return True
    else:
        print("❌ CREDENTIAL CHECK FAILED - Critical credentials invalid!")
        print("   Trading cannot proceed until credentials are fixed.")
        print("=" * 70 + "\n")

        # Notify CEO if requested
        if notify_on_failure:
            try:
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from scripts.notify_ceo import notify_ceo

                failed_services = [
                    c["service"]
                    for c in checks
                    if c["status"] in ("invalid", "missing") and c["service"] in critical_services
                ]

                notify_ceo(
                    f"""🔑 CREDENTIAL HEALTH CHECK FAILED

**Failed Services:** {", ".join(failed_services)}

**Action Required:**
1. Check GitHub Secrets for outdated API keys
2. Regenerate keys if needed (Alpaca Dashboard)
3. Update GitHub Secrets with new keys
4. Re-run the workflow

**Impact:** Trading is BLOCKED until credentials are fixed.
""",
                    alert_type="critical",
                )
            except ImportError:
                print("⚠️  Could not import notify_ceo - notification not sent")
            except Exception as e:
                print(f"⚠️  Notification failed: {e}")

        return False


def main():
    parser = argparse.ArgumentParser(description="Check credential health")
    parser.add_argument(
        "--notify-on-failure",
        action="store_true",
        help="Send CEO notification if credentials fail",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )

    args = parser.parse_args()

    result = run_health_check(notify_on_failure=args.notify_on_failure)

    if args.json:
        health_file = Path("data/credential_health.json")
        if health_file.exists():
            print(health_file.read_text())

    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(main())
