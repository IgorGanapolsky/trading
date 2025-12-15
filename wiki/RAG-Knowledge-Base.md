# 🧠 RAG Knowledge Base

**Last Updated**: 2025-12-01 08:23 AM ET
**Auto-Updated**: Daily via GitHub Actions

---

## 📊 Knowledge Base Overview

| Source | Records | Status | Last Update |
|--------|---------|--------|-------------|
| **Sentiment RAG** | 10 tickers | ✅ Active | 2025-11-09 |
| **Berkshire Letters** | 14 PDFs (4.15MB) | ✅ Downloaded | 2010-2023 |
| **Bogleheads Forum** | 0 insights | ⏳ Pending data collection | Daily |
| **YouTube Transcripts** | 5 videos (100KB) | ✅ Active | Daily |
| **Reddit Sentiment** | 3 files | ✅ Active | Daily |
| **News Sentiment** | 2 files | ✅ Active | Daily |

---

## 🎯 Sentiment by Ticker

| Ticker | Sentiment | Signal | Regime | Confidence |
|--------|-----------|--------|--------|------------|
| **AMZN** | 🟢 +64.0 | BULLISH | neutral | medium |
| **NVDA** | 🟢 +60.0 | BULLISH | neutral | high |
| **QQQ** | 🟡 +41.0 | BULLISH | neutral | medium |
| **SPY** | 🟡 +35.0 | BULLISH | neutral | high |
| **AAPL** | 🟡 +35.0 | BULLISH | neutral | medium |
| **GME** | 🟡 +28.0 | BULLISH | neutral | low |
| **AMD** | 🟡 +23.0 | BULLISH | neutral | low |
| **TSLA** | ⚪ +5.0 | NEUTRAL | neutral | medium |
| **GOOGL** | 🟠 -30.0 | BEARISH | neutral | medium |
| **PLTR** | 🟠 -34.0 | BEARISH | neutral | medium |

---

## 📚 Warren Buffett's Wisdom (Berkshire Letters)

**Years Available**: 2010-2023
**Total Letters**: 14 PDFs
**Total Size**: 4.15 MB

### Recent Letters
- 📄 **2023** Annual Letter
- 📄 **2022** Annual Letter
- 📄 **2021** Annual Letter
- 📄 **2020** Annual Letter
- 📄 **2019** Annual Letter

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

**Status**: Pending data collection
**Total Insights**: 0
**Data Files**: 0

### Forums Monitored
- Personal Investments
- Investing - Theory, News & General

### Topics Tracked
- Market timing, rebalancing, risk
- Diversification, asset allocation
- Index funds, ETFs (SPY, QQQ, VOO)

---

## 🎬 YouTube Financial Analysis

**Transcripts Cached**: 5
**Videos Processed**: 0
**Total Size**: 100 KB

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
| **Reddit** | r/wallstreetbets, r/stocks, r/investing | ✅ Installed |
| **Yahoo Finance** | Yahoo Finance API | ✅ Installed |
| **Alpha Vantage** | Alpha Vantage News API | ✅ Installed |
| **Seeking Alpha** | Seeking Alpha RSS | ✅ Installed |
| **Berkshire Letters** | berkshirehathaway.com | ✅ Installed |

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
│ • Bogleheads    │     │ • Score         │     │                 │
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
