#!/usr/bin/env python3
"""
LinkedIn Blog Publisher

Publishes RLHF blog posts to LinkedIn profile.
Uses LinkedIn API v2 with OAuth 2.0.

Setup:
1. Get access token via OAuth flow (one-time)
2. Store in LINKEDIN_ACCESS_TOKEN environment variable
3. Script posts to profile automatically
"""

from __future__ import annotations

import os
import sys
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo("America/New_York")

# LinkedIn API endpoints
LINKEDIN_API_BASE = "https://api.linkedin.com"
LINKEDIN_POST_URL = f"{LINKEDIN_API_BASE}/v2/ugcPosts"  # UGC Posts API
LINKEDIN_ME_URL = f"{LINKEDIN_API_BASE}/v2/userinfo"  # OpenID Connect endpoint


def get_linkedin_credentials() -> dict:
    """Get LinkedIn credentials from environment."""
    import re

    raw_token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    # Remove ALL whitespace (newlines, carriage returns, spaces) from token
    token = re.sub(r"\s+", "", raw_token) if raw_token else None
    return {
        "client_id": os.environ.get("LINKEDIN_CLIENT_ID"),
        "client_secret": os.environ.get("LINKEDIN_CLIENT_SECRET"),
        "access_token": token,
    }


def get_user_urn(access_token: str) -> str | None:
    """Get the user's LinkedIn URN (unique identifier) using OpenID Connect."""
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        response = requests.get(LINKEDIN_ME_URL, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            # OpenID Connect returns 'sub' as the user ID
            user_id = data.get("sub")
            if user_id:
                print(f"Found user: {data.get('name', 'Unknown')}")
                return f"urn:li:person:{user_id}"
            print(f"No 'sub' field in response: {data}")
            return None
        else:
            print(f"Failed to get user info: {response.status_code} - {response.text}")
            if response.status_code == 403:
                print(
                    "Note: OpenID Connect permissions may take a few minutes to propagate after app setup"
                )
            return None
    except Exception as e:
        print(f"Error getting user URN: {e}")
        return None


def create_linkedin_post(
    access_token: str,
    user_urn: str,
    text: str,
    article_url: str | None = None,
    article_title: str | None = None,
) -> dict | None:
    """Create a LinkedIn post using the UGC Posts API."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Build the post payload for UGC Posts API
    payload = {
        "author": user_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    # Add article if provided
    if article_url:
        payload["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = (
            "ARTICLE"
        )
        payload["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [
            {
                "status": "READY",
                "originalUrl": article_url,
                "title": {"text": article_title or "Read more"},
            }
        ]

    try:
        response = requests.post(
            LINKEDIN_POST_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 201:
            print("✅ Posted to LinkedIn successfully!")
            data = response.json()
            post_id = data.get("id", "")
            print(f"Post ID: {post_id}")
            return data
        else:
            print(f"❌ LinkedIn post failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error posting to LinkedIn: {e}")
        return None


def generate_linkedin_text(signal: str, context: str, equity: float = 0.0) -> str:
    """Generate engaging LinkedIn post text from RLHF feedback."""
    import json
    from pathlib import Path

    state = {}
    state_file = Path("data/system_state.json")
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)

    # Load equity from canonical source if not provided
    if equity <= 0:
        equity = state.get("paper_account", {}).get("equity", 0.0)

    starting = 100000.0
    if state:
        starting = state.get("paper_account", {}).get("starting_balance", 100000.0)
    live_equity = state.get("live_account", {}).get("current_equity", 0.0)

    gain = equity - starting
    gain_pct = (gain / starting) * 100 if starting > 0 else 0

    # Load RLHF stats for technical details
    rlhf_stats = {"positive": 0, "negative": 0, "total": 0, "alpha": 1.0, "beta": 1.0}
    stats_file = Path("data/feedback/stats.json")
    if stats_file.exists():
        with open(stats_file) as f:
            rlhf_stats = json.load(f)

    model_file = Path("models/ml/feedback_model.json")
    if model_file.exists():
        with open(model_file) as f:
            model = json.load(f)
            rlhf_stats["alpha"] = model.get("alpha", 20.75)
            rlhf_stats["beta"] = model.get("beta", 4.0)

    success_rate = rlhf_stats["alpha"] / (rlhf_stats["alpha"] + rlhf_stats["beta"]) * 100

    if signal == "positive":
        emoji = "🎯"
        intro = "Small win today in the AI trading journey."
    else:
        emoji = "📚"
        intro = "Lesson learned today in the AI trading journey."

    # Keep it concise for LinkedIn (under 3000 chars, ideally ~1500)
    text = f"""{emoji} {intro}

{context[:200]}

	📊 Current Status:
	• Paper account: ${equity:,.2f} ({gain_pct:+.1f}% vs paper start)
	• Brokerage account: ${live_equity:,.2f} (opportunistic deployment)
	• Strategy: SPY iron condors (15-20 delta, $10-wide, up to 8 open legs ~2 concurrent condors)
	• North Star: $6K/month after-tax, reached as fast as safely possible

🧠 How Our RLHF System Works:

This post was auto-triggered by a {"👍 thumbs up" if signal == "positive" else "👎 thumbs down"}.

The technical pipeline:
1️⃣ CEO feedback captured by UserPromptSubmit hook
2️⃣ Thompson Sampling model updated (α={rlhf_stats["alpha"]:.1f}, β={rlhf_stats["beta"]:.1f})
3️⃣ LanceDB RAG queries past mistakes to prevent repeats
4️⃣ ShieldCortex stores long-term patterns
5️⃣ GitHub Actions publishes this blog (GitHub Pages + Dev.to + LinkedIn)

Current model success rate: {success_rate:.1f}%
Total feedback signals: {rlhf_stats.get("total", 104)}

Why RLHF for trading? A trade can be profitable AND wrong.

Example: System buys SOFI instead of SPY (wrong ticker, happened to win). Backtest says "good trade." CEO gives 👎. RLHF learns the PROCESS was broken.

Our system captures:
• Real-time correction injection (immediate, not next session)
• Frustration detection (profanity = higher intensity update)
• Session mistake tracking (reminded before repeating errors)
• Phil Town Rule #1 enforcement (behavioral, not just code)

The system now has:
✅ 1300+ automated tests
✅ Thompson Sampling feedback loop
✅ Semantic RAG with LanceDB
✅ Self-healing CI/CD pipelines

Follow along: https://igorganapolsky.github.io/trading/

#AITrading #RLHF #ThompsonSampling #MachineLearning #BuildingInPublic #FinancialIndependence"""

    return text


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Publish to LinkedIn")
    parser.add_argument("--signal", required=True, choices=["positive", "negative"])
    parser.add_argument("--context", required=True, help="Feedback context")
    parser.add_argument("--dry-run", action="store_true", help="Don't post, just preview")

    args = parser.parse_args()

    print("=" * 60)
    print("LINKEDIN PUBLISHER")
    print("=" * 60)

    # Get credentials
    creds = get_linkedin_credentials()

    if not creds["access_token"]:
        print("❌ LINKEDIN_ACCESS_TOKEN not set")
        print("\nTo get an access token:")
        print("1. Go to LinkedIn Developer Portal")
        print("2. Create an app and get OAuth 2.0 credentials")
        print("3. Complete the OAuth flow to get an access token")
        print("4. Set LINKEDIN_ACCESS_TOKEN environment variable")
        return 1

    # Generate post text
    text = generate_linkedin_text(args.signal, args.context)
    print(f"\n📝 Generated post ({len(text)} chars):\n")
    print(text)
    print()

    if args.dry_run:
        print("--- DRY RUN (not posting) ---")
        return 0

    # Get user URN
    user_urn = get_user_urn(creds["access_token"])
    if not user_urn:
        print("❌ Could not get LinkedIn user info")
        return 1

    print(f"User URN: {user_urn}")

    # Post to LinkedIn
    result = create_linkedin_post(
        access_token=creds["access_token"],
        user_urn=user_urn,
        text=text,
        article_url="https://igorganapolsky.github.io/trading/",
        article_title="AI Trading System - Building in Public",
    )

    if result:
        print("\n✅ LinkedIn post published!")
        return 0
    else:
        print("\n❌ Failed to publish to LinkedIn")
        return 1


if __name__ == "__main__":
    sys.exit(main())
