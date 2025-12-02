#!/usr/bin/env python3
"""
Generate RAG Knowledge Base Wiki Page

Creates a visualization of all RAG data sources for the GitHub wiki.
Auto-updates daily with the dashboard workflow.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAG_DIR = DATA_DIR / "rag"
WIKI_DIR = PROJECT_ROOT / "wiki"
OUTPUT_FILE = WIKI_DIR / "RAG-Knowledge-Base.md"


def get_sentiment_rag_stats() -> dict[str, Any]:
    """Query sentiment RAG database for stats."""
    db_path = RAG_DIR / "sentiment_rag.db"
    if not db_path.exists():
        return {"error": "Database not found", "tickers": []}

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get ticker sentiment data
        cursor.execute(
            """
            SELECT
                ticker,
                sentiment_score,
                market_regime,
                confidence,
                snapshot_date,
                freshness
            FROM sentiment_documents
            ORDER BY sentiment_score DESC
        """
        )
        rows = cursor.fetchall()

        tickers = []
        for row in rows:
            tickers.append(
                {
                    "ticker": row[0],
                    "sentiment": row[1],
                    "regime": row[2] or "unknown",
                    "confidence": row[3] or "unknown",
                    "date": row[4],
                    "freshness": row[5] or "unknown",
                }
            )

        conn.close()

        return {
            "count": len(tickers),
            "last_update": tickers[0]["date"] if tickers else "Never",
            "tickers": tickers,
        }
    except Exception as e:
        return {"error": str(e), "tickers": []}


def get_berkshire_stats() -> dict[str, Any]:
    """Get Berkshire Hathaway letters stats."""
    raw_dir = RAG_DIR / "berkshire_letters" / "raw"
    parsed_dir = RAG_DIR / "berkshire_letters" / "parsed"

    raw_files = list(raw_dir.glob("*.pdf")) if raw_dir.exists() else []
    parsed_files = list(parsed_dir.glob("*.txt")) if parsed_dir.exists() else []

    years = sorted([int(f.stem) for f in raw_files if f.stem.isdigit()], reverse=True)
    total_size = sum(f.stat().st_size for f in raw_files) / (1024 * 1024)  # MB

    return {
        "count": len(raw_files),
        "parsed": len(parsed_files),
        "years": years[:5],  # Top 5 most recent
        "year_range": f"{min(years)}-{max(years)}" if years else "N/A",
        "total_size_mb": round(total_size, 2),
    }


def get_bogleheads_stats() -> dict[str, Any]:
    """Get Bogleheads forum data stats."""
    bogleheads_dir = RAG_DIR / "bogleheads"

    if not bogleheads_dir.exists():
        return {"count": 0, "status": "Directory not found"}

    files = list(bogleheads_dir.glob("*.json"))
    total_insights = 0

    for f in files:
        try:
            with open(f) as fp:
                data = json.load(fp)
                if isinstance(data, list):
                    total_insights += len(data)
        except Exception:
            pass

    return {
        "files": len(files),
        "insights": total_insights,
        "status": "Active" if files else "Pending data collection",
    }


def get_sentiment_files_stats() -> dict[str, Any]:
    """Get sentiment JSON files stats."""
    sentiment_dir = DATA_DIR / "sentiment"

    if not sentiment_dir.exists():
        return {"reddit": [], "news": []}

    reddit_files = sorted(sentiment_dir.glob("reddit_*.json"), reverse=True)[:5]
    news_files = sorted(sentiment_dir.glob("news_*.json"), reverse=True)[:5]

    return {
        "reddit": [f.name for f in reddit_files],
        "news": [f.name for f in news_files],
        "reddit_count": len(list(sentiment_dir.glob("reddit_*.json"))),
        "news_count": len(list(sentiment_dir.glob("news_*.json"))),
    }


def get_youtube_stats() -> dict[str, Any]:
    """Get YouTube cache stats."""
    cache_dir = DATA_DIR / "youtube_cache"

    if not cache_dir.exists():
        return {"transcripts": 0, "videos": []}

    transcripts = list(cache_dir.glob("*_transcript.txt"))

    # Get processed videos
    processed_file = cache_dir / "processed_videos.json"
    processed = []
    if processed_file.exists():
        try:
            with open(processed_file) as f:
                processed = json.load(f)
        except Exception:
            pass

    return {
        "transcripts": len(transcripts),
        "processed": len(processed) if isinstance(processed, list) else 0,
        "total_size_kb": sum(f.stat().st_size for f in transcripts) // 1024,
    }


def get_collector_status() -> list[dict[str, Any]]:
    """Get status of all RAG collectors."""
    collectors_dir = PROJECT_ROOT / "src" / "rag" / "collectors"

    collectors = [
        {
            "name": "Reddit",
            "file": "reddit_collector.py",
            "source": "r/wallstreetbets, r/stocks, r/investing",
        },
        {
            "name": "Yahoo Finance",
            "file": "yahoo_collector.py",
            "source": "Yahoo Finance API",
        },
        {
            "name": "Alpha Vantage",
            "file": "alphavantage_collector.py",
            "source": "Alpha Vantage News API",
        },
        {
            "name": "Seeking Alpha",
            "file": "seekingalpha_collector.py",
            "source": "Seeking Alpha RSS",
        },
        {
            "name": "LinkedIn",
            "file": "linkedin_collector.py",
            "source": "LinkedIn Posts API",
        },
        {
            "name": "TikTok",
            "file": "tiktok_collector.py",
            "source": "TikTok Research API",
        },
        {
            "name": "Berkshire Letters",
            "file": "berkshire_collector.py",
            "source": "berkshirehathaway.com",
        },
    ]

    for c in collectors:
        c["exists"] = (collectors_dir / c["file"]).exists()

    return collectors


def sentiment_emoji(score: float) -> str:
    """Convert sentiment score to emoji."""
    if score >= 50:
        return "🟢"
    elif score >= 20:
        return "🟡"
    elif score >= -20:
        return "⚪"
    elif score >= -50:
        return "🟠"
    else:
        return "🔴"


def generate_wiki_page() -> str:
    """Generate the full wiki page content."""
    now = datetime.now()

    # Gather all stats
    sentiment_stats = get_sentiment_rag_stats()
    berkshire_stats = get_berkshire_stats()
    bogleheads_stats = get_bogleheads_stats()
    sentiment_files = get_sentiment_files_stats()
    youtube_stats = get_youtube_stats()
    collectors = get_collector_status()

    # Build the page
    page = f"""# 🧠 RAG Knowledge Base

**Last Updated**: {now.strftime("%Y-%m-%d %I:%M %p ET")}
**Auto-Updated**: Daily via GitHub Actions

---

## 📊 Knowledge Base Overview

| Source | Records | Status | Last Update |
|--------|---------|--------|-------------|
| **Sentiment RAG** | {sentiment_stats.get("count", 0)} tickers | {"✅ Active" if sentiment_stats.get("count", 0) > 0 else "⚠️ Empty"} | {sentiment_stats.get("last_update", "Never")} |
| **Berkshire Letters** | {berkshire_stats["count"]} PDFs ({berkshire_stats["total_size_mb"]}MB) | {"✅ Downloaded" if berkshire_stats["count"] > 0 else "⚠️ Pending"} | {berkshire_stats["year_range"]} |
| **Bogleheads Forum** | {bogleheads_stats["insights"]} insights | {"✅ Active" if bogleheads_stats["insights"] > 0 else "⏳ " + bogleheads_stats["status"]} | Daily |
| **YouTube Transcripts** | {youtube_stats["transcripts"]} videos ({youtube_stats["total_size_kb"]}KB) | {"✅ Active" if youtube_stats["transcripts"] > 0 else "⚠️ Empty"} | Daily |
| **Reddit Sentiment** | {sentiment_files["reddit_count"]} files | {"✅ Active" if sentiment_files["reddit_count"] > 0 else "⚠️ Empty"} | Daily |
| **News Sentiment** | {sentiment_files["news_count"]} files | {"✅ Active" if sentiment_files["news_count"] > 0 else "⚠️ Empty"} | Daily |

---

## 🎯 Sentiment by Ticker

"""

    # Add sentiment table
    if sentiment_stats.get("tickers"):
        page += """| Ticker | Sentiment | Signal | Regime | Confidence |
|--------|-----------|--------|--------|------------|
"""
        for t in sentiment_stats["tickers"]:
            emoji = sentiment_emoji(t["sentiment"])
            signal = (
                "BULLISH"
                if t["sentiment"] > 20
                else "BEARISH"
                if t["sentiment"] < -20
                else "NEUTRAL"
            )
            page += f"| **{t['ticker']}** | {emoji} {t['sentiment']:+.1f} | {signal} | {t['regime']} | {t['confidence']} |\n"
    else:
        page += "*No sentiment data available yet. Data will populate after market hours.*\n"

    page += f"""
---

## 📚 Warren Buffett's Wisdom (Berkshire Letters)

**Years Available**: {berkshire_stats["year_range"]}
**Total Letters**: {berkshire_stats["count"]} PDFs
**Total Size**: {berkshire_stats["total_size_mb"]} MB

### Recent Letters
"""

    if berkshire_stats["years"]:
        for year in berkshire_stats["years"]:
            page += f"- 📄 **{year}** Annual Letter\n"
    else:
        page += "*No letters downloaded yet. Run `download_all_letters()` to populate.*\n"

    page += f"""
### How to Query Buffett's Wisdom

```python
from src.rag.collectors.berkshire_collector import BerkshireLettersCollector

collector = BerkshireLettersCollector()

# Search for investment advice
results = collector.search("index funds vs stock picking")

# Get stock mentions
apple_wisdom = collector.get_stock_mentions("AAPL")
```

---

## 🗣️ Bogleheads Forum Insights

**Status**: {bogleheads_stats["status"]}
**Total Insights**: {bogleheads_stats["insights"]}
**Data Files**: {bogleheads_stats["files"]}

### Forums Monitored
- Personal Investments
- Investing - Theory, News & General

### Topics Tracked
- Market timing, rebalancing, risk
- Diversification, asset allocation
- Index funds, ETFs (SPY, QQQ, VOO)

---

## 🎬 YouTube Financial Analysis

**Transcripts Cached**: {youtube_stats["transcripts"]}
**Videos Processed**: {youtube_stats["processed"]}
**Total Size**: {youtube_stats["total_size_kb"]} KB

### Channels Monitored
- Parkev Tatevosian, CFA
- Joseph Carlson
- Let's Talk Money! with Joseph Hogue
- Financial Education
- Everything Money

---

## 🔌 Data Collectors Status

| Collector | Source | Status |
|-----------|--------|--------|
"""

    for c in collectors:
        status = "✅ Installed" if c["exists"] else "❌ Missing"
        page += f"| **{c['name']}** | {c['source']} | {status} |\n"

    page += """
---

## 📁 Data Storage Structure

```
data/
├── rag/
│   ├── sentiment_rag.db          # SQLite: Ticker sentiment embeddings
│   ├── sentiment.db              # SQLite: Sentiment cache
│   ├── berkshire_letters/
│   │   ├── raw/                  # Original PDF files
│   │   └── parsed/               # Extracted text
│   ├── bogleheads/               # Forum insights JSON
│   ├── chroma_db/                # ChromaDB vector store
│   └── vector_store/             # FAISS indices
├── sentiment/
│   ├── reddit_*.json             # Daily Reddit sentiment
│   └── news_*.json               # Daily news sentiment
└── youtube_cache/
    └── *_transcript.txt          # Video transcripts
```

---

## 🔄 Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Data Sources   │────▶│   Collectors    │────▶│   RAG Store     │
│                 │     │                 │     │                 │
│ • Reddit        │     │ • Parse         │     │ • Embeddings    │
│ • YouTube       │     │ • Extract       │     │ • Vector Index  │
│ • Seeking Alpha │     │ • Normalize     │     │ • SQLite Cache  │
│ • LinkedIn      │     │ • Score         │     │                 │
│ • TikTok        │     │                 │     │                 │
│ • Bogleheads    │     │                 │     │                 │
│ • Berkshire     │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │ Trading System  │
                                               │                 │
                                               │ • Unified       │
                                               │   Sentiment     │
                                               │ • Trade         │
                                               │   Decisions     │
                                               └─────────────────┘
```

---

## 🔗 Quick Links

- [Progress Dashboard](Progress-Dashboard)
- [Repository](https://github.com/IgorGanapolsky/trading)
- [GitHub Actions](https://github.com/IgorGanapolsky/trading/actions)

---

*This page is automatically updated daily by GitHub Actions.*
"""

    return page


def main():
    """Generate and save the RAG wiki page."""
    # Ensure wiki directory exists
    WIKI_DIR.mkdir(parents=True, exist_ok=True)

    # Generate content
    content = generate_wiki_page()

    # Write to file
    OUTPUT_FILE.write_text(content)
    print(f"✅ RAG Knowledge Base wiki generated: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
