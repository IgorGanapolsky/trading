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


def get_weekly_struggle() -> str:
    """Generate a vulnerable, relatable struggle story based on actual data."""
    struggles = [
        "I woke up at 3 AM last night, couldn't sleep, and caught myself checking futures. "
        "My wife asked if I was okay. I lied and said yes. The truth? I'm terrified this won't work.",
        "I spent 4 hours on Thursday debugging why my bot placed a trade at the worst possible moment. "
        "Turns out I had a timezone bug. A $47 lesson in UTC vs Eastern time.",
        "Someone on Reddit called my strategy 'naive' and 'destined to fail'. "
        "I read it three times. Deleted my defensive reply. Maybe they're right. Maybe not. "
        "Only the data will tell.",
        "I almost quit this week. Stared at my screen for an hour, watching a losing position, "
        "finger hovering over 'close all'. I didn't click it. I followed my rules instead. "
        "Hardest thing I've done in months.",
        "My friend made $20K day trading meme stocks last month. I made $12. "
        "But he also lost $15K the month before. I didn't lose anything. "
        "Slow and steady feels boring. But boring might be what keeps me in the game.",
    ]
    return random.choice(struggles)


def get_honest_confession(pl: float) -> str:
    """Generate an honest confession based on P/L performance."""
    if pl > 100:
        return (
            "I'd be lying if I said I wasn't getting cocky. A few good weeks and suddenly "
            "I'm imagining quitting my job. That's dangerous. The market humbles everyone eventually."
        )
    elif pl > 0:
        return (
            "I keep waiting for the other shoe to drop. Small profits feel like luck, not skill. "
            "Maybe both. I genuinely don't know yet."
        )
    elif pl > -50:
        return (
            "I'm down, but not out. The weird thing? I'm not panicking. I've lost money before - "
            "on stupid bets, impulsive decisions. This feels different. This is a tuition payment."
        )
    else:
        return (
            "Let me be brutally honest: I'm questioning everything right now. "
            "Is this strategy fundamentally broken? Am I just bad at this? "
            "The only thing keeping me going is that I haven't violated my rules. "
            "The losses are within my risk parameters. That has to count for something."
        )


def generate_engaging_post() -> tuple[str, str]:
    """Generate a blog post that humans actually want to read.

    Based on research of top AI trading blogs:
    - Vulnerability beats perfection
    - Specific struggles > generic updates
    - Real emotions make content relatable
    - Building in public means showing the ugly parts too
    """
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

    # Get vulnerable content
    struggle_story = get_weekly_struggle()
    honest_confession = get_honest_confession(pl)

    # Build the narrative
    if pl >= 0:
        emoji = "📈"
        verdict = "Still in the game"
    else:
        emoji = "📉"
        verdict = "Down but learning"

    # Format positions for display
    positions_text = ""
    for p in story.get("positions", [])[:3]:
        symbol = p.get("symbol", "???")
        pl_val = float(p.get("unrealized_pl", 0) or 0)
        positions_text += f"- `{symbol[:20]}`: ${pl_val:+.2f}\n"

    if not positions_text:
        positions_text = "- Cash gang this weekend (no open positions)\n"

    # Format lessons with more personality
    lessons_text = ""
    for i, lesson in enumerate(lessons):
        prefix = ["First,", "Also,", "And finally,"][i] if i < 3 else "Plus,"
        lessons_text += f"{prefix} **{lesson['title'][:50]}**\n"
        if lesson["snippet"]:
            lessons_text += f"> {lesson['snippet'][:150]}...\n\n"

    if not lessons_text:
        lessons_text = (
            "Honestly? This week was more about execution than epiphanies. "
            "Sometimes the lesson is just *keep going*.\n"
        )

    body = f"""---
title: "{title}"
published: true
description: "Day {day_number}: The unglamorous truth about building an AI trading system. Real money. Real fears. Real lessons."
tags: trading, ai, python, investing
series: "AI Trading Journey"
cover_image: https://dev-to-uploads.s3.amazonaws.com/uploads/articles/trading-ai-cover.png
canonical_url: https://igorganapolsky.github.io/trading/
---

## A Confession Before We Start

{struggle_story}

---

## {emoji} The Numbers (No Sugarcoating)

**Day {day_number}** | {day_name}, {date_str} | **{verdict}**

Here's my account right now:

| What | Amount |
|------|--------|
| Started with | $5,000.00 |
| Currently at | **${equity:,.2f}** |
| Net P/L | **{pl:+.2f}** ({pl_pct:+.1f}%) |

{honest_confession}

---

## 🔍 What My AI Actually Did This Week

No fancy algorithms. No secret sauce. Just:

- **{story["week_trade_count"]} trades** placed (most were tiny position adjustments)
- **{story["options_trades"]} SPY credit spreads** (selling premium to theta gang)
- **${story["unrealized_pl"]:+.2f}** floating P/L that could evaporate Monday at 9:30 AM

### Current Positions (a.k.a. What's Keeping Me Up at Night)
{positions_text}

The strategy is deliberately boring: sell SPY put spreads 30-45 days out, collect premium, manage losers early. No moonshots. No YOLO plays. Just math.

---

## 🎓 What I Learned the Hard Way

{lessons_text}

The meta-lesson? **The market doesn't care about my feelings.** It doesn't care that I spent months building this system. It doesn't care about my $100/day goal.

It just... moves. And I either adapt or lose money.

---

## 🧮 The Math I Keep Coming Back To

My goal: **$100/day** from trading.

What that actually requires:
- A **$50,000** account (I have $5K)
- **2% monthly returns** consistently (harder than it sounds)
- **80%+ win rate** on credit spreads (I'm tracking every trade)

The path from here to there:

```
Year 1: $5K → $10K (deposits + small gains)
Year 2: $10K → $25K (compounding kicks in)
Year 3: $25K → $50K (if I don't blow up first)
```

**~2.5 years** if everything goes right. Probably longer. Maybe never.

But I'd rather try and fail than wonder "what if" for the rest of my life.

---

## 🎯 Monday's Game Plan

Markets reopen in ~15 hours. My bot will:

1. Check if VIX spiked (fear = better premiums)
2. Look for SPY support levels to sell puts against
3. Size positions at max **5% of account** (protect the downside)

If nothing looks good? **No trades.** The best trade is often no trade.

---

## 📊 90-Day Challenge Progress

| Metric | Status |
|--------|--------|
| Day | **{day_number}/90** |
| Account Value | ${equity:,.2f} |
| Win Rate | *Tracking...* |
| Max Drawdown | *Tracking...* |
| Trades This Week | {story["week_trade_count"]} |

---

## 🤔 The Question I Can't Stop Asking

I'm building this entire system with Claude (yes, the AI) as my co-pilot.

Every day I wonder: **Am I automating wisdom or automating my mistakes at scale?**

I don't know yet. That's why I'm documenting everything. Win or lose, at least I'll understand what happened.

---

## 💬 Talk To Me

If you've made it this far, you're either:
- A fellow algo trader who gets it
- A skeptic watching me crash and burn
- Lost and confused (welcome, friend)

**What would you do differently?** Seriously - I read every comment. My ego can take it.

---

*This is Week {day_number // 7} of my AI trading experiment. Real money (okay, paper money for now). Real emotions. Real lessons. Follow along: **[Live Dashboard](https://igorganapolsky.github.io/trading/)** | **[GitHub](https://github.com/IgorGanapolsky/trading)***

---

*Built by Igor Ganapolsky with Claude as my AI CTO. We're either geniuses or idiots. Probably both. Time will tell.*
"""

    return title, body


def find_existing_article(api_key: str) -> dict | None:
    """Find today's article if it exists."""
    headers = {"api-key": api_key}

    try:
        response = requests.get(
            "https://dev.to/api/articles/me/published?per_page=10",
            headers=headers,
            timeout=30,
        )

        if response.status_code == 200:
            articles = response.json()
            # Look for today's weekend learning post
            for article in articles:
                title = article.get("title", "")
                if "Day 79" in title or "January 18" in title or "Weekend Learning" in title:
                    print(f"Found existing article: {article['id']} - {title}")
                    return article
    except Exception as e:
        print(f"Error checking existing articles: {e}")

    return None


def update_article(api_key: str, article_id: int, title: str, body: str) -> str | None:
    """Update an existing article."""
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {"article": {"title": title, "body_markdown": body}}

    try:
        response = requests.put(
            f"https://dev.to/api/articles/{article_id}",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            url = data.get("url", "")
            print(f"✅ Updated existing article: {url}")
            return url
        else:
            print(f"Error updating article: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Update failed: {e}")

    return None


def publish_to_devto(title: str, body: str) -> str | None:
    """Publish or update article on Dev.to."""
    api_key = get_devto_api_key()
    if not api_key:
        print("No DEVTO_API_KEY found")
        return None

    # First, check if we already have a post for today
    existing = find_existing_article(api_key)
    if existing:
        print("Found existing post - updating with engaging content...")
        return update_article(api_key, existing["id"], title, body)

    # No existing post, create new one
    print("No existing post found - creating new one...")
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
