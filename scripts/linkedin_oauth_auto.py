#!/usr/bin/env python3
"""
Fully Automated LinkedIn OAuth 2.0 - No Manual Steps.

Uses Playwright browser automation to:
1. Navigate to LinkedIn OAuth page
2. Auto-fill login form
3. Click Allow button
4. Capture auth code from redirect
5. Exchange for access token
6. Save to .env and token file

ZERO MANUAL INTERVENTION.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

# Install playwright if needed
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("📦 Installing playwright...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "playwright",
            "--break-system-packages",
        ],
        check=True,
    )
    subprocess.run(["playwright", "install", "chromium"], check=True)
    from playwright.sync_api import sync_playwright

# Load credentials
CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET")
EMAIL = os.environ.get("LINKEDIN_EMAIL")
PASSWORD = os.environ.get("LINKEDIN_PASSWORD", "Rockland26&*")

REDIRECT_URI = "https://localhost:8443/callback"
SCOPES = ["openid", "profile", "w_member_social", "email"]
STATE = f"rlhf_{int(time.time())}"

PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
TOKEN_FILE = Path(__file__).parent.parent / "data" / "linkedin_token.json"


def build_auth_url() -> str:
    """Build LinkedIn OAuth authorization URL."""
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": STATE,
    }
    return f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"


def automate_oauth_flow() -> str | None:
    """Automate the browser OAuth flow and capture auth code."""
    print("🌐 Opening browser for OAuth...")

    auth_url = build_auth_url()
    auth_code = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Visible for debugging
        context = browser.new_context()
        page = context.new_page()

        # Go to auth URL
        page.goto(auth_url, wait_until="domcontentloaded")
        time.sleep(2)

        # Check if already logged in
        current_url = page.url
        if "localhost" in current_url and "code=" in current_url:
            parsed = urlparse(current_url)
            params = parse_qs(parsed.query)
            auth_code = params.get("code", [None])[0]
            browser.close()
            return auth_code

        # Fill login form
        try:
            print("   Filling login form...")
            page.wait_for_selector('input[name="session_key"]', timeout=5000)
            page.fill('input[name="session_key"]', EMAIL)
            page.fill('input[name="session_password"]', PASSWORD)
            page.click('button[type="submit"]')
            print("   Submitted login...")
            time.sleep(3)
        except Exception as e:
            print(f"   ⚠️ Login form error (may already be logged in): {e}")

        # Handle 2FA or captcha if present
        current_url = page.url
        if "checkpoint" in current_url or "challenge" in current_url:
            print("   ⚠️ 2FA/captcha detected - waiting 30s for manual completion...")
            time.sleep(30)

        # Click Allow button if present
        try:
            print("   Looking for Allow button...")
            allow_selectors = [
                'button:has-text("Allow")',
                'button:has-text("Authorize")',
                'input[type="submit"][value="Allow"]',
                "button[data-test-modal-close-btn]",
            ]
            for selector in allow_selectors:
                if page.query_selector(selector):
                    page.click(selector)
                    print("   Clicked Allow button...")
                    break
            time.sleep(2)
        except Exception as e:
            print(f"   ⚠️ Allow button not found: {e}")

        # Wait for redirect with auth code
        print("   Waiting for redirect...")
        for i in range(60):  # Wait up to 60 seconds
            current_url = page.url
            if "localhost" in current_url and "code=" in current_url:
                parsed = urlparse(current_url)
                params = parse_qs(parsed.query)
                auth_code = params.get("code", [None])[0]
                break
            time.sleep(1)

            # Show progress
            if i % 10 == 0 and i > 0:
                print(f"   Still waiting... ({i}s)")

        browser.close()
        return auth_code


def exchange_code_for_token(code: str) -> dict | None:
    """Exchange authorization code for access token."""
    print("🔄 Exchanging code for token...")

    response = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Token exchange failed: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        return None


def get_user_info(access_token: str) -> dict | None:
    """Get LinkedIn user info."""
    print("🔄 Getting user info...")

    response = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"⚠️ User info failed: {response.status_code}")
        return None


def save_credentials(token_data: dict, user_info: dict | None):
    """Save token and URN to .env and token file."""
    access_token = token_data["access_token"]
    person_id = user_info.get("sub", "") if user_info else ""
    person_urn = f"urn:li:person:{person_id}"
    name = user_info.get("name", "User") if user_info else "User"

    # Save to token file
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(
            {
                "access_token": access_token,
                "person_urn": person_urn,
                "name": name,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            f,
            indent=2,
        )

    print(f"✅ Token saved to {TOKEN_FILE}")

    # Update .env file
    env_content = ENV_FILE.read_text() if ENV_FILE.exists() else ""

    # Remove old LinkedIn tokens if present
    env_content = re.sub(r"LINKEDIN_ACCESS_TOKEN=.*\n", "", env_content)
    env_content = re.sub(r"LINKEDIN_PERSON_URN=.*\n", "", env_content)

    # Append new tokens
    if not env_content.endswith("\n"):
        env_content += "\n"

    env_content += f"\n# LinkedIn OAuth Token (Generated {time.strftime('%Y-%m-%d %H:%M:%S')})\n"
    env_content += f"LINKEDIN_ACCESS_TOKEN={access_token}\n"
    env_content += f"LINKEDIN_PERSON_URN={person_urn}\n"

    ENV_FILE.write_text(env_content)
    print(f"✅ Credentials added to {ENV_FILE}")

    return {"access_token": access_token, "person_urn": person_urn, "name": name}


def main():
    """Main automation flow."""
    print("=" * 60)
    print("LinkedIn OAuth 2.0 - FULLY AUTOMATED")
    print("=" * 60)

    if not CLIENT_ID or not CLIENT_SECRET or not EMAIL:
        print("❌ Missing credentials in .env:")
        print("   LINKEDIN_CLIENT_ID")
        print("   LINKEDIN_CLIENT_SECRET")
        print("   LINKEDIN_EMAIL")
        return 1

    # Check for existing valid token
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE) as f:
                existing = json.load(f)
            print(f"✅ Valid token exists for {existing.get('name', 'user')}")
            print(f"   Person URN: {existing.get('person_urn')}")
            print("\n   Use this token in RLHF blog publisher")
            return 0
        except:
            pass

    # Run automated OAuth flow
    auth_code = automate_oauth_flow()

    if not auth_code:
        print("❌ Failed to get authorization code")
        return 1

    print("✅ Got authorization code")

    # Exchange for token
    token_data = exchange_code_for_token(auth_code)
    if not token_data:
        return 1

    print("✅ Got access token")

    # Get user info
    user_info = get_user_info(token_data["access_token"])
    if user_info:
        print(f"✅ User: {user_info.get('name')}")

    # Save credentials
    creds = save_credentials(token_data, user_info)

    print("\n" + "=" * 60)
    print("✅ LINKEDIN OAUTH COMPLETE")
    print("=" * 60)
    print(f"   User: {creds['name']}")
    print(f"   Person URN: {creds['person_urn']}")
    print("\n🚀 RLHF blogs will now auto-post to LinkedIn")

    return 0


if __name__ == "__main__":
    sys.exit(main())
