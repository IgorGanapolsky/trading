# Anthropic Cowork Integration for Trading Dashboard Automation

## Overview

This guide explains how to use **Anthropic Cowork** to automate screenshots of your trading dashboards and query RAG Webhook about your trading performance.

**What is Cowork?**

- Desktop agent built into Claude macOS app
- Automates file-based tasks (organize, analyze, create reports)
- Requires Claude Max subscription ($100-200/month)
- Works with designated folders for security

**What This System Does:**

1. 📸 **Captures screenshots** of Alpaca and Progress dashboards automatically
2. 💾 **Saves to** `data/screenshots/` with timestamps
3. 🤖 **Cowork analyzes** screenshots via Claude Desktop
4. 💬 **RAG Webhook answers** questions about your trading

---

## Setup

### 1. Screenshot Automation (GitHub Actions)

Screenshots are captured automatically:

- **Daily at 4:15 PM ET** (market close) via GitHub Actions
- **Manual trigger** via workflow_dispatch
- **Saved to** `data/screenshots/{alpaca,dashboard,daily}/`

**Manual capture:**

```bash
# Install dependencies
pip install playwright
playwright install chromium

# Capture all dashboards
python3 scripts/capture_trading_screenshots.py --dashboard all

# Capture specific dashboard
python3 scripts/capture_trading_screenshots.py --dashboard alpaca
python3 scripts/capture_trading_screenshots.py --dashboard progress
```

### 2. Cowork Setup (Local macOS)

**Requirements:**

- macOS with Claude Desktop app
- Claude Max subscription
- Local clone of trading repo

**Steps:**

1. **Clone repo locally:**

   ```bash
   git clone https://github.com/IgorGanapolsky/trading.git ~/trading
   cd ~/trading
   ```

2. **Open Claude Desktop** and enable Cowork

3. **Point Cowork to screenshots folder:**
   - In Claude Desktop, configure Cowork
   - Set folder path: `~/trading/data/screenshots/`
   - Grant read/write permissions

4. **Ask Claude to analyze:**
   ```
   "Analyze my latest Alpaca trading screenshot"
   "Compare today's vs yesterday's portfolio performance"
   "Create a summary report from this week's trading screenshots"
   "Find the screenshot with the highest portfolio value"
   ```

### 3. RAG Webhook Integration

**Query trading data via voice/chat:**

RAG Webhook is deployed at (configure `RAG_WEBHOOK_URL`):

```
https://your-rag-webhook-url
```

**Supported queries:**

- **Portfolio status:** "How much money did we make today?"
- **Readiness check:** "Are we ready to trade tomorrow?"
- **Analytical queries:** "Why did we lose money yesterday?"
- **Lessons learned:** "What lessons did we learn about risk?"
- **Trade history:** "Show me recent SPY trades"

**Example RAG Webhook conversation:**

```
You: "How's my paper trading account?"

RAG Webhook: "📊 Current Portfolio Status (Day 76/90)

Paper Account:
- Equity: $4,989.69
- Total P/L: -$10.31 (-0.21%)
- Positions: 0
- Last Trade: Jan 15, 2026"

You: "Why did we not make money yesterday?"

RAG Webhook: "Based on our lessons learned (LanceDB RAG):
- No trades executed on weekends (market closed)
- Next trading session: Monday 9:30 AM ET
- Automation health: OK (last trade Jan 15)"
```

---

## File Structure

```
data/screenshots/
├── alpaca/                  # Alpaca dashboard screenshots
│   ├── paper_dashboard_20260115_163000.png
│   └── paper_dashboard_20260115_210000.png
├── dashboard/               # Progress dashboard screenshots
│   ├── progress_dashboard_20260115_163000.png
│   └── progress_dashboard_20260115_210000.png
└── daily/                   # Combined daily summaries
    └── daily_summary_20260115_210000.png
```

**Naming convention:**

- `{type}_dashboard_{YYYYMMDD_HHMMSS}.png`
- Timestamps in Eastern Time (market hours)
- Full-page screenshots (1920x1080)

---

## Use Cases

### 1. Daily Portfolio Review (Cowork)

**Ask Claude:**

```
"Analyze all screenshots from today and create a trading summary"
```

**Claude will:**

- Read all PNG files from today
- Extract portfolio values, P/L, positions
- Generate markdown summary
- Compare to previous days
- Highlight significant changes

### 2. Weekly Performance Report (Cowork)

**Ask Claude:**

```
"Create a weekly report from this week's daily summaries"
```

**Claude will:**

- Aggregate all daily*summary*\*.png files
- Calculate weekly P/L trend
- Identify best/worst trading days
- Export as PDF or markdown

### 3. Voice Trading Assistant (RAG Webhook)

**Integration with Google Assistant:**

```
You: "Hey Google, ask Trading Bot how I'm doing"

RAG Webhook: "Your paper account is at $4,989.69, down $10.31
today. No open positions. Last trade was Jan 15."

You: "Are we ready to trade tomorrow?"

RAG Webhook: "🟢 READY (85%) - Market opens 9:30 AM ET.
Capital sufficient, backtests passing, CI green."
```

### 4. Screenshot-Based Alerts (Cowork)

**Ask Claude:**

```
"Monitor screenshots folder and alert me if portfolio drops >5%"
```

**Claude will:**

- Watch `data/screenshots/` folder
- Parse new screenshots as they arrive
- Calculate daily P/L changes
- Send alert if threshold breached

---

## Cowork vs RAG Webhook

| Feature                 | Cowork (Local)               | RAG Webhook (Cloud)   |
| ----------------------- | ---------------------------- | -------------------- |
| **Screenshot analysis** | ✅ Visual analysis           | ❌ No image input    |
| **File organization**   | ✅ Rename, sort, organize    | ❌ No file access    |
| **Report generation**   | ✅ Create docs, spreadsheets | ❌ Text only         |
| **Real-time data**      | ❌ Uses screenshots          | ✅ Alpaca API direct |
| **Voice interface**     | ❌ Desktop only              | ✅ Google Assistant  |
| **RAG queries**         | ❌ No RAG                    | ✅ LanceDB RAG       |
| **Trading questions**   | 🟡 Via screenshots           | ✅ Semantic search   |

**Recommendation:** Use both!

- **Cowork:** Visual analysis, reports, file management
- **RAG Webhook:** Live data, voice queries, lessons learned

---

## Advanced: Automated Analysis Pipeline

**Combine GitHub Actions + Cowork + RAG Webhook:**

1. **GitHub Actions** captures screenshots daily (4:15 PM ET)
2. **Cowork** analyzes new screenshots when you open Claude Desktop
3. **RAG Webhook** answers questions about trends/patterns

**Example workflow:**

```bash
# GitHub Actions runs at 4:15 PM ET
# Captures: data/screenshots/daily/daily_summary_20260115_211500.png

# You open Claude Desktop at 5:00 PM
# Cowork detects new file in monitored folder

You: "What changed today?"

Cowork: "New screenshot detected. Portfolio down $10.31 (-0.21%).
No trades executed today. Market hours analysis shows after-hours
price movement in previous positions (closed yesterday)."

You (to RAG Webhook): "Why did we lose money if no trades happened?"

RAG Webhook: "Based on our lessons learned:
- Closed positions yesterday may have settled at different prices
- Mark-to-market adjustments in options positions
- Interest/fees deducted from cash balance
LL-189 explains settlement timing for options trades."
```

---

## Security & Privacy

**Cowork Security:**

- Only accesses designated folder (`data/screenshots/`)
- No internet access (analyzes locally)
- Cannot execute trades or access Alpaca API
- Read-only recommended for production use

**RAG Webhook Security:**

- Webhook requires bearer token authentication
- Rate limited (100 req/min)
- Queries Alpaca API with read-only credentials
- Logs redacted (no sensitive data in logs)

**Best Practices:**

1. Use separate Alpaca API keys for read-only access
2. Never share screenshots containing account numbers
3. Review Cowork folder permissions regularly
4. Rotate RAG Webhook token monthly

---

## Troubleshooting

### Screenshots not capturing

**Check:**

```bash
# Test locally
python3 scripts/capture_trading_screenshots.py --dashboard progress

# Check GitHub Actions
# https://github.com/IgorGanapolsky/trading/actions/workflows/capture-trading-screenshots.yml
```

**Common issues:**

- Playwright not installed: `playwright install chromium`
- Missing credentials: Check `ALPACA_PAPER_TRADING_5K_API_KEY`
- Network timeout: Increase timeout in script

### Cowork not analyzing screenshots

**Check:**

1. Folder path correct in Cowork settings
2. Screenshots exist: `ls -la data/screenshots/alpaca/`
3. File permissions: `chmod 644 data/screenshots/**/*.png`
4. Claude Desktop up to date

### RAG Webhook not responding

**Check webhook health:**

```bash
curl https://your-rag-webhook-url/health

# Should return:
# {"status":"healthy","cloud_ai_rag_enabled":true,...}
```

**Test queries:**

```bash
curl -X POST https://your-rag-webhook-url/webhook \
  -H "Content-Type: application/json" \
  -d '{"text": "How much money did we make today?"}'
```

---

## Cost Optimization

**GitHub Actions:** Free (2,000 min/month)

- Screenshot workflow: ~2 min/day = 40 min/month
- Well within free tier

**Cowork:** $100-200/month (Claude Max subscription)

- Unlimited local analysis
- No usage fees beyond subscription

**RAG Webhook:** Free tier (1,000 requests/month)

- Webhook hosting: Free (Cloud Run free tier)
- LanceDB RAG: $0 (local index + embeddings)

**Total estimated cost:** ~$115-215/month for full automation

---

## Next Steps

1. ✅ **Commit this integration** to the repo
2. 🚀 **Enable GitHub Actions workflow** for daily screenshots
3. 🖥️ **Install Claude Desktop** with Cowork (local macOS)
4. 💬 **Test RAG Webhook queries** via webhook
5. 📊 **Review first daily summary** tomorrow at 4:15 PM ET

**Questions? Ask RAG Webhook:**

```
"Explain the Cowork integration for trading screenshots"
"How do I analyze my portfolio with Claude?"
```

---

## References

- [Anthropic Cowork Announcement](https://www.anthropic.com/news/cowork)
- [RAG Webhook Code](../src/agents/rag_webhook.py)
- [Screenshot Script](../scripts/capture_trading_screenshots.py)
- [GitHub Actions Workflow](../.github/workflows/capture-trading-screenshots.yml)

**Last updated:** Jan 15, 2026
**Status:** ✅ Production-ready
