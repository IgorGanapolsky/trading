# AI Trading Dashboard

World-class trading dashboard with professional UI/UX, designed for efficiency and clarity.

## Quick Start

```bash
# Launch the main dashboard
./scripts/run_dashboard.sh

# Or manually with streamlit
streamlit run dashboard/main.py
```

Open http://localhost:8501 in your browser.

---

## Dashboards

### 1. Main Dashboard (NEW - Recommended)
**File:** `dashboard/main.py`

The unified control center with:
- **Hero Metrics** - Portfolio value, Daily P/L, Win Rate, Theta Income, R&D Progress
- **Progress to $100/Day** - Visual progress bar with projection
- **4 Clean Tabs** - Overview, Positions, Options, Performance
- **Real-time Updates** - 30-second refresh with live Alpaca data
- **Dark Theme** - Professional trading UI

### 2. Sentiment Dashboard
**File:** `dashboard/sentiment_dashboard.py`

- **Real-time sentiment scores** with color-coded gauges (green/yellow/red)
- **Market regime detection** (Risk On / Risk Off / Neutral)
- **Top 5 tickers** by sentiment strength
- **Detailed breakdown table** with combined Reddit + News scores
- **Auto-refresh** capability (60-second intervals)
- **Stale data warning** (alerts if data >24 hours old)

### 2. Overview Page (📊)
- High-level market sentiment metrics
- Bull/Bear ratio calculation
- Sentiment distribution (Bullish/Neutral/Bearish)
- Top movers (most bullish and bearish tickers)
- Data freshness indicators

### 3. Historical Trends Page (📈)
- 30-day sentiment timeline for top tickers
- Sentiment statistics (averages, volatility)
- Correlation analysis (sentiment vs actual returns)
- Win rate by sentiment level
- Data quality metrics

### 4. Trade Impact Page (💰)
- Performance comparison (with vs without sentiment)
- ROI attribution analysis (waterfall chart)
- Sentiment-driven trade examples
- Integration roadmap tracker
- Key insights and expected improvements

### 5. Data Sources Page (🔍)
- Source breakdown (Reddit, Yahoo, Stocktwits, Alpha Vantage)
- Reddit sentiment details (mentions, keywords)
- News sentiment details (articles by source)
- API usage metrics and rate limits
- Data collection schedule
- Quality metrics (coverage, freshness, confidence)

## Installation

### 1. Install Dependencies

```bash
cd /Users/igorganapolsky/workspace/git/apps/trading
pip install -r requirements.txt
```

This will install:
- `streamlit==1.29.0` - Dashboard framework
- `plotly==5.18.0` - Interactive charts
- All other existing dependencies

### 2. Verify Data Directory

Ensure sentiment data exists in:
```
data/sentiment/
├── reddit_YYYY-MM-DD.json
└── news_YYYY-MM-DD.json
```

If no data exists, run the sentiment collection scripts first:
```bash
python scripts/collect_reddit_sentiment.py
python scripts/collect_news_sentiment.py
```

## Usage

### Launch Dashboard

```bash
cd /Users/igorganapolsky/workspace/git/apps/trading
streamlit run dashboard/sentiment_dashboard.py
```

The dashboard will automatically open in your browser at `http://localhost:8501`

### Navigation

- **Main page**: Overview with real-time sentiment gauges
- **Sidebar**: Use the page selector to navigate between sections
  - 📊 Overview
  - 📈 Historical Trends
  - 💰 Trade Impact
  - 🔍 Data Sources

### Configuration

**Sidebar Options:**
- **Date Selector**: View historical sentiment data
- **Auto-refresh**: Toggle 60-second auto-refresh
- **Days to Analyze**: Adjust historical window (7-30 days)
- **Top Tickers**: Select how many tickers to display (3-10)

## Data Format

### Reddit Sentiment Data (`reddit_YYYY-MM-DD.json`)

```json
{
  "meta": {
    "date": "2025-11-09",
    "timestamp": "2025-11-09T17:18:15.125362",
    "subreddits": ["wallstreetbets", "stocks"],
    "total_posts": 100,
    "total_tickers": 5
  },
  "sentiment_by_ticker": {
    "TICKER": {
      "score": 150,
      "mentions": 45,
      "confidence": "high",
      "bullish_keywords": 30,
      "bearish_keywords": 5
    }
  }
}
```

### News Sentiment Data (`news_YYYY-MM-DD.json`)

```json
{
  "meta": {
    "date": "2025-11-09",
    "timestamp": "2025-11-09T17:18:15.125365",
    "sources": ["yahoo", "stocktwits", "alphavantage"],
    "tickers_analyzed": 4
  },
  "sentiment_by_ticker": {
    "TICKER": {
      "ticker": "TICKER",
      "score": 35.0,
      "confidence": "high",
      "sources": {
        "yahoo": {"score": 40, "articles": 15},
        "stocktwits": {"score": 30, "messages": 50}
      }
    }
  }
}
```

## Architecture

```
dashboard/
├── sentiment_dashboard.py       # Main entry point
├── pages/
│   ├── 1_📊_Overview.py        # Overview page
│   ├── 2_📈_Historical_Trends.py # Trends analysis
│   ├── 3_💰_Trade_Impact.py    # Performance comparison
│   └── 4_🔍_Data_Sources.py    # Source breakdown
└── utils/
    ├── __init__.py
    └── chart_builders.py        # Reusable Plotly charts
```

## Features in Detail

### Real-time Sentiment Gauges
- Range: -100 (Very Bearish) to +100 (Very Bullish)
- Color-coded: Red (bearish), Yellow (neutral), Green (bullish)
- Confidence levels: High, Medium, Low
- Interactive tooltips

### Market Regime Detection
Determines overall market sentiment:
- **Risk On** (avg score > 20): Bullish market conditions
- **Risk Off** (avg score < -20): Bearish market conditions
- **Neutral** (-20 to 20): Mixed signals

### Combined Scoring Algorithm
```python
reddit_score = normalize_to_100(reddit_raw_score)
news_score = news_raw_score  # Already -100 to 100

combined_score = (reddit_score * 0.4) + (news_score * 0.6)
```

Weighting: 40% Reddit, 60% News (news is more reliable)

### Data Quality Indicators

**Freshness:**
- 🟢 Green: < 1 hour old
- 🟡 Yellow: 1-6 hours old
- 🔴 Red: > 6 hours old

**Coverage:**
- Percentage of target tickers with data
- Target tickers: SPY, QQQ, NVDA, GOOGL, AMZN, TSLA

**Confidence:**
- High: Strong signal (|score| > 30)
- Medium: Moderate signal (10 < |score| < 30)
- Low: Weak signal (|score| < 10)

## Troubleshooting

### No Data Available
**Problem:** Dashboard shows "No sentiment data available"

**Solution:**
```bash
# Run sentiment collection scripts
python scripts/collect_reddit_sentiment.py
python scripts/collect_news_sentiment.py

# Verify files created
ls data/sentiment/
```

### Stale Data Warning
**Problem:** Data is more than 24 hours old

**Solution:**
Set up automated collection (cron job or scheduler):
```bash
# Add to crontab (Linux/Mac)
0 */2 * * * cd /path/to/trading && python scripts/collect_news_sentiment.py
0 */4 * * * cd /path/to/trading && python scripts/collect_reddit_sentiment.py
```

### Dashboard Won't Start
**Problem:** `streamlit: command not found`

**Solution:**
```bash
pip install streamlit==1.29.0
```

### Import Errors
**Problem:** `ModuleNotFoundError: No module named 'plotly'`

**Solution:**
```bash
pip install plotly==5.18.0
```

## Performance

- **Load Time:** < 2 seconds with 30 days of data
- **Refresh Rate:** 60 seconds (configurable)
- **Memory Usage:** ~100-200MB
- **Concurrent Users:** Supports multiple viewers

## Mobile Support

Dashboard is mobile-responsive:
- Gauges stack vertically on small screens
- Tables scroll horizontally
- Charts resize automatically
- Touch-friendly navigation

## Theme

**Dark Trading Theme:**
- Background: `#0e1117` (dark blue-black)
- Grid: `#262730` (charcoal)
- Text: `#fafafa` (off-white)
- Bullish: `#00ff88` (bright green)
- Bearish: `#ff4444` (bright red)
- Neutral: `#ffd700` (gold)

## Future Enhancements

### Phase 1 (Current)
- ✅ Real-time sentiment visualization
- ✅ Multi-source data aggregation
- ✅ Historical trend analysis
- ✅ Data quality metrics

### Phase 2 (Planned)
- [ ] Live trade execution tracking
- [ ] Sentiment-based alerts/notifications
- [ ] Backtesting integration
- [ ] Custom ticker watchlists

### Phase 3 (Future)
- [ ] Machine learning model performance
- [ ] Real-time WebSocket updates
- [ ] Export reports (PDF/CSV)
- [ ] Multi-user authentication

## Contributing

To add new pages or charts:

1. **New Page:**
   ```bash
   # Create file in pages/ directory
   touch dashboard/pages/5_🎯_New_Page.py
   ```

2. **New Chart:**
   ```python
   # Add to dashboard/utils/chart_builders.py
   def create_new_chart(data: pd.DataFrame) -> go.Figure:
       # Your chart code here
       pass
   ```

3. **Test:**
   ```bash
   streamlit run dashboard/sentiment_dashboard.py
   ```

## API Reference

See `dashboard/utils/chart_builders.py` for chart builder functions:

- `create_sentiment_gauge(ticker, score, confidence)` - Gauge chart
- `create_sentiment_timeline(df, tickers)` - Line chart
- `create_correlation_heatmap(correlation_df)` - Heatmap
- `create_source_breakdown_pie(source_data)` - Pie chart
- `create_win_rate_by_sentiment_bar(win_rate_data)` - Bar chart
- `create_performance_comparison_table(comparison_data)` - Table
- `create_roi_attribution_waterfall(attribution_data)` - Waterfall
- `create_mentions_timeline(df)` - Area chart

## Support

For issues or questions:
1. Check this README
2. Review error messages in terminal
3. Verify data files exist and are valid JSON
4. Check Streamlit logs: `~/.streamlit/logs/`

## License

Part of the AI Trading System project.
