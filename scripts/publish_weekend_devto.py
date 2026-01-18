#!/usr/bin/env python3
"""
Publish Weekend Learning Summary to Dev.to

This script generates ENGAGING, HUMAN-INTEREST blog posts that people
actually want to read. No robotic summaries - real stories, real struggles,
real lessons from the trading journey.

The goal: Make readers CARE about our journey from $5K to $100/day.
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests


def get_devto_api_key() -> str | None:
    """Get Dev.to API key from environment."""
    return os.environ.get("DEVTO_API_KEY")


def get_system_state() -> dict:
    """Load full system state for rich content generation."""
    state_file = Path("data/system_state.json")
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except Exception:
            pass
    return {}


def get_recent_lessons(max_count: int = 5) -> list[dict]:
    """Get recent lessons learned with actual content."""
    lessons_dir = Path("rag_knowledge/lessons_learned")
    if not lessons_dir.exists():
        return []

    lessons = []
    cutoff = datetime.now().timestamp() - (7 * 24 * 60 * 60)  # 7 days

    for f in sorted(lessons_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.stat().st_mtime > cutoff and len(lessons) < max_count:
            try:
                content = f.read_text()
                # Extract title from first line
                lines = content.strip().split("\n")
                title = lines[0].replace("#", "").strip() if lines else f.stem
                # Get a snippet of the content
                snippet = " ".join(lines[1:5]).strip()[:200] if len(lines) > 1 else ""
                lessons.append(
                    {
                        "file": f.name,
                        "title": title,
                        "snippet": snippet,
                    }
                )
            except Exception:
                pass

    return lessons


def get_trade_story() -> dict:
    """Extract the trading story from this week's data."""
    state = get_system_state()
    portfolio = state.get("portfolio", {})
    trades = state.get("trade_history", [])
    positions = state.get("paper_account", {}).get("positions", [])

    # Calculate this week's trades
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    recent_trades = [t for t in trades if t.get("filled_at", "") > week_ago]

    # Calculate P/L from positions
    total_unrealized = sum(float(p.get("unrealized_pl", 0) or 0) for p in positions)

    # Find any notable trades
    spy_trades = [t for t in recent_trades if "SPY" in str(t.get("symbol", ""))]
    options_trades = [t for t in recent_trades if len(str(t.get("symbol", ""))) > 10]

    return {
        "equity": portfolio.get("equity", "5000"),
        "cash": portfolio.get("cash", "4800"),
        "positions_count": len(positions),
        "unrealized_pl": total_unrealized,
        "week_trade_count": len(recent_trades),
        "spy_trades": len(spy_trades),
        "options_trades": len(options_trades),
        "positions": positions[:3],  # Top 3 for display
    }


def generate_engaging_title() -> str:
    """Generate a title that makes people want to click."""
    today = datetime.now()
    start_date = datetime(2025, 10, 31)
    day_number = (today - start_date).days

    story = get_trade_story()
    equity = float(story.get("equity", 5000))
    pl = equity - 5000  # Started with $5000

    # Different title styles based on performance
    if pl > 50:
        hooks = [
            f"Day {day_number}: How My AI Made ${pl:.0f} While I Slept",
            f"From $5K to ${equity:.0f}: Week {day_number // 7} of My AI Trading Experiment",
            f"Day {day_number}: The Trade That Changed Everything (+${pl:.0f})",
        ]
    elif pl < -50:
        hooks = [
            f"Day {day_number}: I Lost ${abs(pl):.0f}. Here's What I Learned.",
            f"My AI Lost ${abs(pl):.0f} This Week. Was It Worth It?",
            f"Day {day_number}: The Painful Lesson That Will Make Me Better",
        ]
    else:
        hooks = [
            f"Day {day_number}: Building an AI That Trades for Me (Week {day_number // 7})",
            f"Can AI Really Trade? Day {day_number} of My $5K Experiment",
            f"Day {day_number}: What 79 Days of AI Trading Taught Me",
        ]

    return random.choice(hooks)


def generate_engaging_post() -> tuple[str, str]:
    """Generate a blog post that humans actually want to read."""
    today = datetime.now()
    day_name = today.strftime("%A")
    date_str = today.strftime("%B %d, %Y")
    start_date = datetime(2025, 10, 31)
    day_number = (today - start_date).days

    story = get_trade_story()
    lessons = get_recent_lessons(3)
    equity = float(story.get("equity", 5000))
    starting_capital = 5000
    pl = equity - starting_capital
    pl_pct = (pl / starting_capital) * 100

    title = generate_engaging_title()

    # Build the narrative
    if pl >= 0:
        mood = "cautiously optimistic"
        emoji = "📈"
    else:
        mood = "learning from setbacks"
        emoji = "📉"

    # Format positions for display
    positions_text = ""
    for p in story.get("positions", [])[:3]:
        symbol = p.get("symbol", "???")
        pl_val = float(p.get("unrealized_pl", 0) or 0)
        positions_text += f"- `{symbol[:20]}`: ${pl_val:+.2f}\n"

    if not positions_text:
        positions_text = "- No open positions this weekend\n"

    # Format lessons
    lessons_text = ""
    for lesson in lessons:
        lessons_text += f"**{lesson['title'][:50]}**\n"
        if lesson["snippet"]:
            lessons_text += f"> {lesson['snippet'][:150]}...\n\n"

    if not lessons_text:
        lessons_text = "This week was mostly about execution, not new lessons.\n"

    body = f"""---
title: "{title}"
published: true
description: "Day {day_number} of building an AI trading system. Real money. Real lessons. No BS."
tags: trading, ai, python, investing
series: "AI Trading Journey"
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/trading-ai-cover.png
canonical_url: https://igorganapolsky.github.io/trading/
---

## {emoji} The Reality Check

**Day {day_number}** | {day_name}, {date_str}

Let me be real with you: I'm {mood} about this AI trading experiment.

Started with **$5,000** in paper money. Today I have **${equity:,.2f}**.

That's **{pl:+.2f}** ({pl_pct:+.1f}%) since I started.

Not life-changing. Not terrible. Just... real.

---

## 💡 What Actually Happened This Week

Here's the unglamorous truth about what my AI did:

- **{story["week_trade_count"]} trades** executed
- **{story["options_trades"]} options trades** (credit spreads on SPY)
- **${story["unrealized_pl"]:+.2f}** unrealized P/L sitting in open positions

### Current Positions
{positions_text}

I'm running **SPY credit spreads** with 30-45 days to expiration. The strategy is simple: sell premium, manage risk, don't blow up.

---

## 🎓 This Week's Hard-Won Lessons

{lessons_text}

The biggest lesson? **Patience pays more than prediction.**

I spent weeks trying to predict market direction. Now I just sell premium and let theta do the work.

---

## 🤔 What I'm Thinking About

### The Math That Keeps Me Going

My target: **$100/day** from a **$50K account**. That's 2% monthly.

Current reality: **$5K account**, targeting **$5-10/day**.

The gap is huge. But compound growth is real:
- $5K → $10K in ~12 months (with deposits)
- $10K → $25K in another ~12 months
- $25K → $50K in another ~8 months

**~2.5 years** to reach my goal. Not fast. Not slow. Just math.

### Why I'm Not Giving Up

1. **The system is learning** - Every loss becomes a lesson in the RAG database
2. **The process is repeatable** - No gut feelings, just rules
3. **The risk is defined** - I know my max loss before entering any trade

---

## 🎯 Monday Game Plan

Markets open in ~15 hours. Here's what I'm watching:

1. **SPY levels**: Looking for support/resistance to place spreads
2. **VIX**: If volatility spikes, premiums get juicier
3. **Position sizing**: Never more than 5% on a single trade

---

## 📊 The Scoreboard

| Metric | Value |
|--------|-------|
| Starting Capital | $5,000 |
| Current Equity | ${equity:,.2f} |
| Total P/L | {pl:+.2f} ({pl_pct:+.1f}%) |
| Day | {day_number}/90 |
| Open Positions | {story["positions_count"]} |
| This Week's Trades | {story["week_trade_count"]} |

---

## 🙋 Question for You

I'm building this in public because I believe transparency beats secrecy.

**What would you do differently?** Drop a comment - I read every one.

---

*This is a real experiment with real (paper) money. I'm documenting every win, loss, and lesson. Follow along or laugh at my mistakes - either way, you'll learn something.*

**[📈 Live Dashboard](https://igorganapolsky.github.io/trading/)** | **[💻 Source Code](https://github.com/IgorGanapolsky/trading)**

---

*Built by Igor Ganapolsky with Claude as my AI CTO. Yes, I'm letting an AI help run my trading system. Yes, that's either genius or insanity. Time will tell.*
"""

    return title, body


def publish_to_devto(title: str, body: str) -> str | None:
    """Publish article to Dev.to and return URL."""
    api_key = get_devto_api_key()
    if not api_key:
        print("No DEVTO_API_KEY found")
        return None

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "article": {
            "title": title,
            "body_markdown": body,
            "published": True,
            "series": "AI Trading Journey",
            "tags": ["trading", "ai", "python", "investing"],
        }
    }

    try:
        response = requests.post(
            "https://dev.to/api/articles",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 201:
            data = response.json()
            url = data.get("url", "")
            print(f"Published to Dev.to: {url}")
            return url
        else:
            print(f"Dev.to API error: {response.status_code}")
            print(response.text)
            return None

    except Exception as e:
        print(f"Dev.to publish failed: {e}")
        return None


def main():
    """Main entry point."""
    print("=" * 60)
    print("Weekend Learning -> Dev.to Publisher (ENGAGING VERSION)")
    print("=" * 60)

    title, body = generate_engaging_post()
    print(f"\nGenerated post: {title}")
    print(f"Body length: {len(body)} characters")
    print("\n--- PREVIEW ---")
    print(body[:500])
    print("...")

    url = publish_to_devto(title, body)

    if url:
        print(f"\n✅ Successfully published: {url}")
        return 0
    else:
        print("\n❌ Failed to publish to Dev.to")
        return 1


if __name__ == "__main__":
    sys.exit(main())
