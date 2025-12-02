#!/usr/bin/env python3
"""
Process YouTube analysis results and update trading system

This script runs AFTER YouTube analysis agents complete:
- Agent 1: video_2_top_6_stocks_nov_2025.md
- Agent 2: video_4_amzn_openai_deal.md

Actions:
1. Extract stock tickers from analysis files
2. Update data/tier2_watchlist.json
3. Generate recommendation report
4. Update system_state.json
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# Paths
BASE_DIR = Path(__file__).parent.parent
ANALYSIS_DIR = BASE_DIR / "docs" / "youtube_analysis"
DATA_DIR = BASE_DIR / "data"

VIDEO_2_FILE = ANALYSIS_DIR / "video_2_top_6_stocks_nov_2025.md"
VIDEO_4_FILE = ANALYSIS_DIR / "video_4_amzn_openai_deal.md"
WATCHLIST_FILE = DATA_DIR / "tier2_watchlist.json"
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
RECOMMENDATIONS_FILE = ANALYSIS_DIR / "RECOMMENDATIONS_2025-11-04.md"


def check_prerequisites() -> bool:
    """Check if analysis files exist"""
    if not VIDEO_2_FILE.exists():
        print(f"❌ Missing: {VIDEO_2_FILE}")
        return False
    if not VIDEO_4_FILE.exists():
        print(f"❌ Missing: {VIDEO_4_FILE}")
        return False
    print("✅ All analysis files found")
    return True


def extract_stock_tickers(markdown_content: str) -> list[dict[str, str]]:
    """
    Extract stock tickers from markdown analysis

    Looks for patterns like:
    - **TICKER** - Company Name
    - TICKER: Company Name
    - Stock: TICKER (Company)
    """
    stocks = []

    # Pattern 1: **TICKER** - Company Name
    pattern1 = re.findall(r"\*\*([A-Z]{1,5})\*\*\s*[-:]\s*(.+?)(?:\n|$)", markdown_content)
    for ticker, name in pattern1:
        stocks.append({"ticker": ticker, "name": name.strip()})

    # Pattern 2: TICKER: Company Name
    pattern2 = re.findall(r"^([A-Z]{1,5}):\s*(.+?)$", markdown_content, re.MULTILINE)
    for ticker, name in pattern2:
        if ticker not in [s["ticker"] for s in stocks]:
            stocks.append({"ticker": ticker, "name": name.strip()})

    return stocks


def parse_video_2_analysis() -> list[dict[str, Any]]:
    """Parse Video #2 analysis (top 6 stocks)"""
    print("\n📊 Parsing Video #2: Top 6 Stocks...")

    with open(VIDEO_2_FILE) as f:
        content = f.read()

    stocks = extract_stock_tickers(content)

    # Extract rationale for each stock (look for sections after ticker)
    for stock in stocks:
        ticker = stock["ticker"]
        # Find section with this ticker
        pattern = rf"\*\*{ticker}\*\*.*?\n\n(.+?)(?:\n\n|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            rationale = match.group(1).strip()[:200]  # First 200 chars
            stock["rationale"] = rationale
        else:
            stock["rationale"] = "See full analysis for details"

        stock["source"] = "YouTube - Parkev Tatevosian (Top 6 Stocks Nov 2025)"
        stock["date_added"] = datetime.now().strftime("%Y-%m-%d")
        stock["priority"] = "medium"  # Default, can be adjusted
        stock["status"] = "watchlist"

    print(f"✅ Found {len(stocks)} stocks from Video #2")
    return stocks


def parse_video_4_analysis() -> dict[str, Any]:
    """Parse Video #4 analysis (AMZN OpenAI deal)"""
    print("\n📊 Parsing Video #4: AMZN OpenAI Deal...")

    with open(VIDEO_4_FILE) as f:
        content = f.read()

    # Extract AMZN recommendation
    amzn_stock = {
        "ticker": "AMZN",
        "name": "Amazon.com Inc.",
        "source": "YouTube - OpenAI Partnership Analysis",
        "date_added": datetime.now().strftime("%Y-%m-%d"),
        "status": "watchlist",
    }

    # Look for recommendation section
    if "recommend" in content.lower():
        # Extract recommendation sentiment
        if any(word in content.lower() for word in ["strong buy", "add", "bullish"]):
            amzn_stock["priority"] = "high"
        elif any(word in content.lower() for word in ["monitor", "watch", "neutral"]):
            amzn_stock["priority"] = "medium"
        else:
            amzn_stock["priority"] = "low"
    else:
        amzn_stock["priority"] = "medium"

    # Extract rationale (first paragraph after "Summary" or "Recommendation")
    summary_match = re.search(
        r"(?:Summary|Recommendation|Analysis).*?\n\n(.+?)(?:\n\n|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if summary_match:
        amzn_stock["rationale"] = summary_match.group(1).strip()[:200]
    else:
        amzn_stock["rationale"] = "OpenAI partnership - see full analysis"

    print(f"✅ AMZN analysis complete (Priority: {amzn_stock['priority']})")
    return amzn_stock


def update_watchlist(video_2_stocks: list[dict], amzn_stock: dict) -> None:
    """Update tier2_watchlist.json with new stocks"""
    print("\n📝 Updating watchlist...")

    # Load current watchlist
    with open(WATCHLIST_FILE) as f:
        watchlist = json.load(f)

    # Add new stocks to watchlist section
    all_new_stocks = video_2_stocks + [amzn_stock]

    for stock in all_new_stocks:
        # Check if already exists
        existing_tickers = [s["ticker"] for s in watchlist.get("watchlist", [])]
        if stock["ticker"] not in existing_tickers:
            watchlist.setdefault("watchlist", []).append(stock)
            print(f"  ✅ Added {stock['ticker']} - {stock['name']}")
        else:
            print(f"  ⏭️  Skipped {stock['ticker']} (already in watchlist)")

    # Update metadata
    watchlist["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    # Save
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(watchlist, f, indent=2)

    print(f"✅ Watchlist updated: {len(all_new_stocks)} new stocks")


def generate_recommendations_report(video_2_stocks: list[dict], amzn_stock: dict) -> None:
    """Generate final recommendations report"""
    print("\n📋 Generating recommendations report...")

    report = f"""# YouTube Analysis Stock Recommendations - November 4, 2025

**Analysis Date**: November 4-5, 2025
**Sources**: Parkev Tatevosian (2 videos)
**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## Executive Summary

**Total Stocks Analyzed**: {len(video_2_stocks) + 1}
- Video #2: {len(video_2_stocks)} stocks (Top 6 for November 2025)
- Video #4: 1 stock (AMZN - OpenAI partnership)

**Recommended for Tier 2**: {len([s for s in video_2_stocks + [amzn_stock] if s["priority"] == "high"])} high-priority
**Monitor/Consider**: {len([s for s in video_2_stocks + [amzn_stock] if s["priority"] == "medium"])} medium-priority
**Lower Priority**: {len([s for s in video_2_stocks + [amzn_stock] if s["priority"] == "low"])} low-priority

---

## Video #2: Top 6 Stocks for November 2025
**Analyst**: Parkev Tatevosian
**Date**: November 2025

"""

    # Add each stock from Video #2
    for i, stock in enumerate(video_2_stocks, 1):
        report += f"""
### {i}. **{stock["ticker"]}** - {stock["name"]}
- **Rationale**: {stock["rationale"]}
- **Priority**: {stock["priority"].upper()}
- **Action**: {"Add to Tier 2" if stock["priority"] == "high" else "Monitor" if stock["priority"] == "medium" else "Low priority"}
- **Timeline**: {"Immediate" if stock["priority"] == "high" else "Month 2-3" if stock["priority"] == "medium" else "Future consideration"}

"""

    # Add AMZN section
    report += f"""
---

## Video #4: Amazon OpenAI Partnership Analysis
**Catalyst**: OpenAI partnership announcement
**Date**: November 2025

### AMZN Assessment

- **Ticker**: {amzn_stock["ticker"]}
- **Company**: {amzn_stock["name"]}
- **Partnership Impact**: {amzn_stock["rationale"]}
- **Priority**: {amzn_stock["priority"].upper()}
- **Action**: {"Add to Tier 2" if amzn_stock["priority"] == "high" else "Monitor" if amzn_stock["priority"] == "medium" else "Low priority"}
- **Timeline**: {"Immediate" if amzn_stock["priority"] == "high" else "Month 2-3" if amzn_stock["priority"] == "medium" else "Future consideration"}

---

## Implementation Plan

### Current Tier 2 Holdings
- **NVDA** (NVIDIA Corporation) - AI chip leader
- **GOOGL** (Alphabet Inc.) - AI/ML platform

### Immediate Additions (High Priority)
"""

    high_priority = [s for s in video_2_stocks + [amzn_stock] if s["priority"] == "high"]
    if high_priority:
        for stock in high_priority:
            report += f"- {stock['ticker']} ({stock['name']})\n"
    else:
        report += "- None (all stocks medium/low priority)\n"

    report += "\n### Monitor (Medium Priority)\n"
    medium_priority = [s for s in video_2_stocks + [amzn_stock] if s["priority"] == "medium"]
    if medium_priority:
        for stock in medium_priority:
            report += f"- {stock['ticker']} ({stock['name']})\n"
    else:
        report += "- None\n"

    report += "\n### Lower Priority\n"
    low_priority = [s for s in video_2_stocks + [amzn_stock] if s["priority"] == "low"]
    if low_priority:
        for stock in low_priority:
            report += f"- {stock['ticker']} ({stock['name']})\n"
    else:
        report += "- None\n"

    report += """
---

## Next Steps

1. **CEO Review** - Approve high-priority additions
2. **Update CoreStrategy** - Add approved tickers to Tier 2 rotation
3. **30-Day Validation** - Monitor performance of new stocks
4. **Adjust Allocation** - If expanding beyond 2-3 stocks, reduce per-stock allocation

---

## Risk Assessment

**Concentration Risk**: Current portfolio is tech-heavy (NVDA, GOOGL)
**Mitigation**: YouTube picks provide diversification opportunities
**Validation**: 30-day monitoring period before full allocation

**Source Risk**: Single analyst (Parkev Tatevosian)
**Mitigation**: Cross-reference with MultiLLM analysis before execution

---

**Generated by**: YouTube Analysis Integration System
**Report Date**: {datetime.now().strftime("%Y-%m-%d")}
**Next Review**: 30 days after implementation
"""

    # Save report
    with open(RECOMMENDATIONS_FILE, "w") as f:
        f.write(report)

    print(f"✅ Report generated: {RECOMMENDATIONS_FILE}")


def update_system_state() -> None:
    """Update system_state.json with YouTube analysis integration"""
    print("\n🔧 Updating system state...")

    with open(SYSTEM_STATE_FILE) as f:
        state = json.load(f)

    # Add note about YouTube analysis
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    note = f"[{timestamp}] YouTube analysis integrated - Stock picks from Parkev Tatevosian added to watchlist"

    if "notes" in state:
        state["notes"].append(note)
    else:
        state["notes"] = [note]

    # Update metadata
    state["meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Save
    with open(SYSTEM_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

    print("✅ System state updated")


def main():
    """Main processing function"""
    print("=" * 60)
    print("YouTube Analysis Processing Script")
    print("=" * 60)

    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ BLOCKING: Waiting for analysis agents to complete")
        print("   Required files:")
        print(f"   - {VIDEO_2_FILE}")
        print(f"   - {VIDEO_4_FILE}")
        print("\n   Run this script again after agents complete.")
        return

    # Parse analysis files
    video_2_stocks = parse_video_2_analysis()
    amzn_stock = parse_video_4_analysis()

    # Update watchlist
    update_watchlist(video_2_stocks, amzn_stock)

    # Generate report
    generate_recommendations_report(video_2_stocks, amzn_stock)

    # Update system state
    update_system_state()

    print("\n" + "=" * 60)
    print("✅ COMPLETE: YouTube analysis integration finished")
    print("=" * 60)
    print("\nNext steps:")
    print(f"1. Review: {RECOMMENDATIONS_FILE}")
    print(f"2. Check: {WATCHLIST_FILE}")
    print("3. CEO approval for high-priority stocks")
    print("4. Update CoreStrategy with approved tickers")


if __name__ == "__main__":
    main()
