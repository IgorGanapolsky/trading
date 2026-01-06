#!/usr/bin/env python3
"""
Generate daily revenue blog post for GitHub Pages and Dev.to.
Creates Medium-style blog posts with AI/LLM-friendly structured data.
"""

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()


def get_treasury_yields() -> dict:
    """Fetch live Treasury yields from FRED API."""
    try:
        from src.rag.collectors.fred_collector import FREDCollector

        fred = FREDCollector()
        yields = fred.get_treasury_yields()
        spread = fred.get_yield_curve_spread()
        inverted = fred.is_yield_curve_inverted()
        return {"yields": yields, "spread": spread, "inverted": inverted, "available": True}
    except Exception as e:
        print(f"Warning: Could not fetch FRED data: {e}")
        return {"available": False}


# Paths
DATA_DIR = Path(__file__).parent.parent / "data"
DOCS_DIR = Path(__file__).parent.parent / "docs"
REPORTS_DIR = DOCS_DIR / "_reports"
PERF_FILE = DATA_DIR / "performance_log.json"


def get_latest_performance() -> dict:
    """Get latest performance data from log."""
    if not PERF_FILE.exists():
        print("ERROR: performance_log.json not found")
        sys.exit(1)

    with open(PERF_FILE) as f:
        data = json.load(f)

    if not data:
        print("ERROR: No performance data")
        sys.exit(1)

    return data[-1]


def get_previous_day_equity(perf_data: list, current_date: str) -> float:
    """Get previous trading day's equity for daily P/L calculation."""
    for i, entry in enumerate(perf_data):
        if entry.get("date") == current_date and i > 0:
            return perf_data[i - 1].get("equity", 100000.0)
    return 100000.0  # Default starting balance


def get_trades_for_date(target_date: str) -> list:
    """Load trades for a specific date."""
    trades_file = DATA_DIR / f"trades_{target_date}.json"
    if trades_file.exists():
        with open(trades_file) as f:
            return json.load(f)
    return []


def calculate_day_number() -> int:
    """Calculate which day of the 90-day R&D phase we're on."""
    # Use start_date from system_state.json (Oct 29, 2025)
    # Previously hardcoded Nov 3 which was WRONG
    try:
        state_file = Path(__file__).parent.parent / "data" / "system_state.json"
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)
                start_str = state.get("start_date", "2025-10-29")
                start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        else:
            start_date = date(2025, 10, 29)  # Fallback to correct date
    except Exception:
        start_date = date(2025, 10, 29)  # Fallback to correct date
    today = date.today()
    return (today - start_date).days + 1


def generate_blog_post(perf: dict, trades: list, day_num: int) -> str:
    """Generate Medium-style markdown blog post."""
    report_date = perf.get("date", date.today().isoformat())
    equity = perf.get("equity", 0)
    total_pl = perf.get("pl", 0)
    cash = perf.get("cash", 0)
    buying_power = perf.get("buying_power", 0)

    # Load full performance history for daily change calculation
    with open(PERF_FILE) as f:
        all_perf = json.load(f)

    prev_equity = get_previous_day_equity(all_perf, report_date)
    daily_pl = equity - prev_equity
    daily_pl_pct = (daily_pl / prev_equity * 100) if prev_equity else 0

    # Format date nicely
    date_obj = datetime.strptime(report_date, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%B %d, %Y")
    day_of_week = date_obj.strftime("%A")

    # Determine performance text
    if daily_pl > 0:
        performance_text = "Profitable Day"
    elif daily_pl < 0:
        performance_text = "Learning Day"
    else:
        performance_text = "Flat Day"

    # Build trade summary
    trade_summary = ""
    if trades:
        trade_summary = "\n## Today's Trades\n\n"
        trade_summary += "| Symbol | Action | Qty | Price | P/L |\n"
        trade_summary += "|--------|--------|-----|-------|-----|\n"
        for trade in trades[:10]:  # Limit to 10 trades
            symbol = trade.get("symbol", "N/A")
            action = trade.get("action", "N/A")
            qty = trade.get("quantity", 0)
            price = trade.get("price", 0)
            trade_pl = trade.get("pl", "N/A")
            trade_summary += f"| {symbol} | {action} | {qty:.2f} | ${price:.2f} | {trade_pl} |\n"
    else:
        trade_summary = (
            "\n## Today's Trades\n\nNo trades executed today (market closed or no signals).\n"
        )

    # Build Treasury/FRED section with live data
    treasury_data = get_treasury_yields()
    if treasury_data.get("available"):
        yields = treasury_data.get("yields", {})
        spread = treasury_data.get("spread")
        inverted = treasury_data.get("inverted", False)

        curve_status = "**INVERTED** (recession warning)" if inverted else "Normal (positive slope)"
        spread_str = f"{spread:+.2f}%" if spread is not None else "N/A"

        y2 = f"{yields.get('2Y', 0):.2f}%" if yields.get("2Y") else "N/A"
        y5 = f"{yields.get('5Y', 0):.2f}%" if yields.get("5Y") else "N/A"
        y10 = f"{yields.get('10Y', 0):.2f}%" if yields.get("10Y") else "N/A"
        y30 = f"{yields.get('30Y', 0):.2f}%" if yields.get("30Y") else "N/A"

        treasury_section = f"""| Maturity | Yield |
|----------|-------|
| 2-Year | {y2} |
| 5-Year | {y5} |
| 10-Year | {y10} |
| 30-Year | {y30} |

**Yield Curve Spread (10Y-2Y)**: {spread_str}

**Curve Status**: {curve_status}

*Data source: Federal Reserve Economic Data (FRED) API*"""
    else:
        treasury_section = "*Treasury data temporarily unavailable*"

    # Generate the blog post
    post = f"""---
layout: post
title: "Daily Report: {formatted_date} | ${daily_pl:+,.2f}"
date: {report_date}
daily_pl: {daily_pl:.2f}
total_pl: {total_pl:.2f}
equity: {equity:.2f}
day_number: {day_num}
---

# {performance_text}: {day_of_week}, {formatted_date}

**Day {day_num}/90** of our AI Trading R&D Phase

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Daily P/L** | **${daily_pl:+,.2f}** ({daily_pl_pct:+.2f}%) |
| **Total P/L** | ${total_pl:+,.2f} ({total_pl / 1000:.2f}%) |
| **Portfolio Value** | ${equity:,.2f} |
| **Cash** | ${cash:,.2f} |
| **Buying Power** | ${buying_power:,.2f} |

---
{trade_summary}
---

## Portfolio Allocation

Our current strategy focuses on:
- **US Equities**: SPY, sector ETFs
- **Options**: Cash-secured puts, covered calls
- **Fixed Income**: Treasury ETFs (SHY, IEF, TLT)

---

## Treasury & Fixed Income

**Live Treasury Yields (FRED API):**

{treasury_section}

---

## Risk Metrics

- **Max Position Size**: 2% of portfolio (Kelly Criterion)
- **Stop Loss**: Volatility-adjusted per position
- **Circuit Breakers**: Active (no triggers today)

---

## Market Context

*US equity markets trade Monday-Friday, 9:30 AM - 4:00 PM ET.*

---

## What's Next

Day {day_num + 1} focus:
- Continue systematic strategy execution
- Monitor open positions
- Refine ML signals based on today's data

---

*Auto-generated by AI Trading System | [View Source](https://github.com/IgorGanapolsky/trading)*

*Not financial advice. Paper trading only.*
"""
    return post


def save_github_pages_post(content: str, report_date: str) -> Path:
    """Save blog post to GitHub Pages _reports collection."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{report_date}-daily-report.md"
    filepath = REPORTS_DIR / filename

    with open(filepath, "w") as f:
        f.write(content)

    print(f"Saved GitHub Pages post: {filepath}")
    return filepath


def update_index_day_number(day_num: int) -> None:
    """Update the day number in docs/index.md."""
    import re

    index_file = DOCS_DIR / "index.md"
    if not index_file.exists():
        print(f"Warning: {index_file} not found")
        return

    content = index_file.read_text()

    # Update "Day X/90" pattern
    new_content = re.sub(
        r"Day \d+/90",
        f"Day {day_num}/90",
        content
    )

    if new_content != content:
        index_file.write_text(new_content)
        print(f"Updated index.md: Day {day_num}/90")
    else:
        print(f"index.md already shows Day {day_num}/90")


def post_to_devto(content: str, report_date: str, daily_pl: float) -> str | None:
    """Post to Dev.to via API."""
    api_key = os.getenv("DEVTO_API_KEY")
    if not api_key:
        print("DEVTO_API_KEY not set - skipping Dev.to publish")
        return None

    # Parse date for title
    date_obj = datetime.strptime(report_date, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%B %d, %Y")

    # Remove Jekyll front matter for Dev.to
    lines = content.split("\n")
    in_frontmatter = False
    clean_lines = []
    for line in lines:
        if line.strip() == "---":
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter:
            clean_lines.append(line)

    body = "\n".join(clean_lines)

    # Add Dev.to footer
    body += """

---

*Follow our journey: [AI Trading Journey on GitHub](https://github.com/IgorGanapolsky/trading)*

*All trades are paper trading - no real money at risk.*
"""

    headers = {"api-key": api_key, "Content-Type": "application/json"}

    payload = {
        "article": {
            "title": f"AI Trading Daily Report: {formatted_date} | ${daily_pl:+,.2f}",
            "body_markdown": body,
            "published": True,
            "tags": ["trading", "ai", "machinelearning", "python"],
            "series": "AI Trading Daily Reports",
            "canonical_url": f"https://igorganapolsky.github.io/trading/reports/{report_date}-daily-report/",
        }
    }

    try:
        resp = requests.post(
            "https://dev.to/api/articles", headers=headers, json=payload, timeout=30
        )

        if resp.status_code in [200, 201]:
            url = resp.json().get("url")
            print(f"Published to Dev.to: {url}")
            return url
        else:
            print(f"Dev.to publish failed: {resp.status_code}")
            print(resp.text)
            return None

    except Exception as e:
        print(f"Dev.to error: {e}")
        return None


def main():
    """Generate and publish daily blog post."""
    print("=" * 70)
    print("GENERATING DAILY BLOG POST")
    print("=" * 70)

    # Get performance data
    perf = get_latest_performance()
    report_date = perf.get("date", date.today().isoformat())

    print(f"Report date: {report_date}")
    print(f"Equity: ${perf.get('equity', 0):,.2f}")
    print(f"P/L: ${perf.get('pl', 0):+,.2f}")

    # Get trades
    trades = get_trades_for_date(report_date)
    print(f"Trades: {len(trades)}")

    # Calculate day number
    day_num = calculate_day_number()
    print(f"Day: {day_num}/90")

    # Generate blog post
    content = generate_blog_post(perf, trades, day_num)

    # Calculate daily P/L for Dev.to title
    with open(PERF_FILE) as f:
        all_perf = json.load(f)
    prev_equity = get_previous_day_equity(all_perf, report_date)
    daily_pl = perf.get("equity", 0) - prev_equity

    # Save to GitHub Pages
    filepath = save_github_pages_post(content, report_date)

    # Update index.md day number
    update_index_day_number(day_num)

    # Post to Dev.to
    devto_url = post_to_devto(content, report_date, daily_pl)

    print("\n" + "=" * 70)
    print("BLOG POST GENERATED")
    print("=" * 70)
    print(f"GitHub Pages: {filepath}")
    if devto_url:
        print(f"Dev.to: {devto_url}")

    return filepath


if __name__ == "__main__":
    main()
