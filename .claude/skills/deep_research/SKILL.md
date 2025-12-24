---
skill_id: deep_research
name: Deep Research
version: 1.0.0
status: dormant  # Implementation file does not exist yet
description: Skill for Gemini Deep Research pre-trade market analysis
author: Trading System CTO
tags: [research, gemini, deep-research, market-analysis, pre-trade, autonomous-agents]
tools:
  - research_crypto_market
  - research_stock
  - research_market_conditions
  - get_pre_trade_analysis
dependencies:
  - src/ml/gemini_deep_research.py  # TODO: Create this file
integrations:
  - src/ml/gemini_deep_research.py::GeminiDeepResearch
  - src/ml/gemini_deep_research.py::get_researcher
---

> **STATUS: DORMANT** - This skill describes planned functionality.
> The implementation file `src/ml/gemini_deep_research.py` does not exist yet.
> To activate: Create the implementation and remove `status: dormant` from frontmatter.

# Deep Research Skill

Autonomous market research using Google's Gemini Deep Research agent for comprehensive pre-trade analysis.

## Overview

This skill provides:
- Autonomous multi-source market research
- Cryptocurrency market condition analysis
- Stock fundamental and technical analysis
- Overall market regime detection
- Risk factor identification
- Trading recommendations with confidence levels

Powered by: **Gemini Deep Research Pro** (`deep-research-pro-preview-12-2025`)

## What is Gemini Deep Research?

Gemini Deep Research is Google's autonomous research agent that:
1. **Searches multiple sources**: News, financials, social media, technical data
2. **Synthesizes information**: Combines disparate data into coherent analysis
3. **Identifies patterns**: Detects trends, anomalies, and correlations
4. **Generates reports**: Structured output with recommendations

**Research Time**: 2-5 minutes per query (runs in background)

## When to Use This Skill

**Use Before Trading When:**
- Making significant position changes (>5% of portfolio)
- Entering new asset/sector
- Market conditions are uncertain
- Breaking news requires context
- Budget allows (check with `budget_tracker` skill first)

**Priority Level**: Medium (use `budget_tracker` to check if budget allows)

## Tools

### 1. research_crypto_market

Deep research on cryptocurrency market conditions before trading.

**Parameters:**
- `symbol` (required): Crypto symbol (e.g., "BTC", "ETH", "SOL")

**Research Scope:**
1. Latest news and developments (24-48 hours)
2. Market sentiment from social media and news
3. Key support/resistance levels
4. Upcoming events (ETF decisions, halvings, regulations)
5. Fear & Greed index analysis
6. Whale wallet movements

**Returns:**
```python
{
    "sentiment": "bullish",
    "news_summary": "Bitcoin institutional buying continues as ETF inflows surge...",
    "recommendation": "BUY",
    "confidence": 0.78,
    "key_levels": {
        "support": [95000, 92000, 88000],
        "resistance": [105000, 110000, 120000]
    },
    "upcoming_events": [
        {
            "date": "2025-12-20",
            "event": "Fed interest rate decision",
            "impact": "high"
        }
    ],
    "fear_greed_index": 72,  # 0-100, higher = greed
    "whale_activity": "accumulation",
    "risk_factors": [
        "Regulatory uncertainty in key markets",
        "High leverage in futures markets"
    ]
}
```

**Usage:**
```python
from src.ml.gemini_deep_research import get_researcher

researcher = get_researcher()

# Research Bitcoin market
result = researcher.research_crypto_market("BTC")

if result and result.get("recommendation") == "BUY":
    confidence = result.get("confidence", 0.5)
    if confidence > 0.7:
        print(f"✅ Strong BUY signal (confidence: {confidence:.2f})")
        print(f"Reason: {result.get('news_summary', 'No summary')}")
else:
    print("Research unavailable or negative signal")
```

### 2. research_stock

Deep research on a stock before trading.

**Parameters:**
- `symbol` (required): Stock ticker (e.g., "AAPL", "TSLA", "NVDA")

**Research Scope:**
1. Recent earnings and financial health
2. Latest news and analyst ratings
3. Technical analysis (RSI, MACD, moving averages)
4. Institutional ownership changes
5. Upcoming catalysts (earnings dates, FDA approvals, product launches)
6. Sector performance comparison

**Returns:**
```python
{
    "fundamentals": {
        "pe_ratio": 28.5,
        "revenue_growth_yoy": 0.15,
        "profit_margin": 0.23,
        "debt_to_equity": 1.2,
        "earnings_quality": "strong"
    },
    "technicals": {
        "rsi": 62,
        "macd": "bullish_crossover",
        "moving_average_50": 145.20,
        "moving_average_200": 138.50,
        "trend": "uptrend"
    },
    "sentiment": "positive",
    "analyst_ratings": {
        "buy": 15,
        "hold": 8,
        "sell": 2,
        "average_target": 165.00
    },
    "recommendation": "BUY",
    "confidence": 0.72,
    "target_price": 165.00,
    "upcoming_catalysts": [
        {
            "date": "2025-01-25",
            "event": "Q4 Earnings Report",
            "expected_impact": "positive"
        }
    ],
    "institutional_flow": "accumulation",
    "sector_comparison": "outperforming"
}
```

**Usage:**
```python
from src.ml.gemini_deep_research import get_researcher

researcher = get_researcher()

# Research Apple stock
result = researcher.research_stock("AAPL")

if result:
    print(f"Recommendation: {result.get('recommendation')}")
    print(f"Target Price: ${result.get('target_price', 0):.2f}")
    print(f"Fundamentals: {result['fundamentals']['earnings_quality']}")
    print(f"Technicals: {result['technicals']['trend']}")
```

### 3. research_market_conditions

Research overall market conditions for risk management and allocation.

**Research Scope:**
1. S&P 500 and major indices trend
2. VIX (volatility index) analysis
3. Fed policy and interest rate outlook
4. Geopolitical risks
5. Sector rotation trends
6. Risk-on vs Risk-off sentiment

**Returns:**
```python
{
    "market_regime": "bullish",  # bullish, bearish, neutral, volatile
    "vix_analysis": {
        "current": 14.5,
        "level": "low",  # low (<15), medium (15-25), high (>25)
        "trend": "declining"
    },
    "fed_outlook": {
        "next_meeting": "2025-12-18",
        "expected_action": "hold",
        "rate_path": "neutral"
    },
    "allocation": {
        "stocks": 60,   # Recommended % allocation
        "crypto": 25,
        "cash": 15
    },
    "risk_level": "moderate",  # low, moderate, high
    "key_risks": [
        "Inflation persistence",
        "Geopolitical tensions in Middle East",
        "Tech sector concentration risk"
    ],
    "sector_rotation": {
        "outperforming": ["technology", "financials"],
        "underperforming": ["utilities", "real_estate"]
    },
    "sentiment": "risk_on"  # risk_on, risk_off, mixed
}
```

**Usage:**
```python
from src.ml.gemini_deep_research import get_researcher

researcher = get_researcher()

# Research overall market
result = researcher.research_market_conditions()

if result:
    print(f"Market Regime: {result['market_regime']}")
    print(f"VIX Level: {result['vix_analysis']['level']}")
    print(f"Recommended Allocation:")
    print(f"  Stocks: {result['allocation']['stocks']}%")
    print(f"  Crypto: {result['allocation']['crypto']}%")
    print(f"  Cash: {result['allocation']['cash']}%")
```

### 4. get_pre_trade_analysis

Comprehensive pre-trade analysis before executing a trade.

**Parameters:**
- `symbol` (required): Trading symbol
- `asset_type` (optional): "crypto" or "stock" (default: "crypto")

**Returns:**
```python
{
    "symbol": "BTC",
    "timestamp": "2025-12-13T10:30:00Z",
    "analysis_available": True,
    "recommendation": "BUY",
    "confidence": 0.75,
    "research": {
        # Full research results from research_crypto_market or research_stock
    }
}
```

**Usage:**
```python
from src.ml.gemini_deep_research import get_researcher

researcher = get_researcher()

# Before trading BTC
analysis = researcher.get_pre_trade_analysis("BTC", asset_type="crypto")

if analysis["analysis_available"]:
    if analysis["recommendation"] == "BUY" and analysis["confidence"] > 0.7:
        # Strong buy signal - execute trade
        execute_buy_order("BTC", quantity=0.1)
    else:
        print("Weak signal - holding off on trade")
else:
    print("Deep research unavailable - using simpler analysis")
```

## Integration with Trading System

### Pre-Trade Workflow with Budget Awareness

```python
from src.utils.budget_tracker import should_execute, track
from src.ml.gemini_deep_research import get_researcher

# 1. Check budget before expensive research
if should_execute("gemini_research", priority="medium"):

    # 2. Track the API call
    track("gemini_research", cost=0.01)

    # 3. Run deep research
    researcher = get_researcher()
    analysis = researcher.get_pre_trade_analysis("BTC")

    # 4. Use results in trading decision
    if analysis["confidence"] > 0.7:
        execute_trade_with_confidence(analysis)
else:
    # Budget constrained - use cheaper analysis methods
    use_cached_or_simple_analysis()
```

### Integration with Text Analyzer Skill

```python
from src.ml.gemini_deep_research import get_researcher
from src.ml.text_feature_engineering import get_news_signal

# 1. Quick text analysis (cheap)
headlines = get_recent_news("BTC")
text_signal = get_news_signal(headlines)

# 2. If text signal is strong, do deep research for confirmation
if text_signal["confidence"] > 0.65:
    researcher = get_researcher()
    deep_analysis = researcher.research_crypto_market("BTC")

    # 3. Combine signals
    if (text_signal["signal"] == deep_analysis.get("recommendation") and
        deep_analysis.get("confidence", 0) > 0.7):
        print("✅ Both signals agree - high conviction trade")
```

### Integration with Risk Manager

```python
from src.ml.gemini_deep_research import get_researcher
from src.core.risk_manager import RiskManager

# 1. Research market conditions
researcher = get_researcher()
market = researcher.research_market_conditions()

# 2. Adjust risk parameters based on market regime
risk_mgr = RiskManager()

if market["risk_level"] == "high" or market["vix_analysis"]["level"] == "high":
    # Reduce position sizes in high volatility
    risk_mgr.update_config(max_position_size_pct=5.0)
else:
    # Normal position sizes
    risk_mgr.update_config(max_position_size_pct=10.0)
```

## Research Quality & Reliability

**Pros:**
- Multi-source synthesis
- Autonomous deep dive
- Identifies non-obvious patterns
- Comprehensive coverage

**Cons:**
- 2-5 minute latency (not real-time)
- ~$0.01 per research query
- Requires GOOGLE_API_KEY
- May hallucinate details (verify critical facts)

**Best Practices:**
1. **Always verify critical facts**: Don't blindly trust recommendations
2. **Use for confirmation**: Combine with other signals
3. **Check timestamps**: Ensure research is recent
4. **Budget awareness**: Only use when budget allows
5. **Handle failures gracefully**: API may timeout or fail

## Setup Requirements

### 1. Install Dependencies
```bash
pip install google-genai
```

### 2. Set API Key
```bash
export GOOGLE_API_KEY="your-gemini-api-key"
# Or in .env file:
GOOGLE_API_KEY=your-key
```

### 3. Test Connection
```python
from src.ml.gemini_deep_research import get_researcher

researcher = get_researcher()
if researcher.client:
    print("✅ Gemini connected")
else:
    print("❌ No API key or connection failed")
```

## CLI Usage

```bash
# Test crypto research
python src/ml/gemini_deep_research.py

# Research specific crypto
python -c "from src.ml.gemini_deep_research import get_researcher; \
           import json; \
           result = get_researcher().research_crypto_market('BTC'); \
           print(json.dumps(result, indent=2))"

# Check if Gemini is available
python -c "from src.ml.gemini_deep_research import get_researcher; \
           r = get_researcher(); \
           print('Available' if r.client else 'Not available')"
```

## Cost Management

**Per Query Cost**: ~$0.01
**Monthly Budget**: $100
**Max Queries**: ~10,000 (if only using Gemini)

**Recommended Usage** (with $100/month budget):
- 5-10 queries per day (market conditions + key trades)
- Use priority="medium" in budget tracker
- Cache results for 1-2 hours
- Skip during "caution" or "critical" budget states

## Error Handling

```python
from src.ml.gemini_deep_research import get_researcher

researcher = get_researcher()
result = researcher.research_crypto_market("BTC")

if result is None:
    # Handle failure
    print("Research failed - using fallback analysis")
    result = get_cached_research() or use_simple_analysis()
elif "raw_research" in result:
    # JSON parsing failed, but raw text available
    print("Structured data unavailable, using raw text:")
    print(result["raw_research"])
else:
    # Success - use structured data
    print(f"Recommendation: {result['recommendation']}")
```

## Timeout & Background Execution

Research runs in **background mode** with 5-minute timeout:

```python
interaction = client.interactions.create(
    input=query,
    agent='deep-research-pro-preview-12-2025',
    background=True  # Non-blocking
)

# Poll every 10 seconds until complete or timeout
while time.time() - start < 300:  # 5 min timeout
    interaction = client.interactions.get(interaction.id)
    if interaction.status == "completed":
        return interaction.outputs[-1].text
    time.sleep(10)
```

## Example Output (Real Research)

```json
{
  "sentiment": "bullish",
  "news_summary": "Bitcoin continues institutional adoption wave with major ETF inflows totaling $2.1B this week. MicroStrategy announced additional $500M purchase. Technical indicators show strong momentum above key moving averages.",
  "recommendation": "BUY",
  "confidence": 0.82,
  "key_levels": {
    "support": [98000, 95000, 92000],
    "resistance": [105000, 110000, 115000]
  },
  "fear_greed_index": 75,
  "risk_factors": [
    "Overbought RSI (74) suggests potential short-term pullback",
    "High futures open interest may lead to volatility"
  ]
}
```

## References

- Gemini Deep Research: https://ai.google.dev/gemini-api/docs/interactions
- Implementation: `/home/user/trading/src/ml/gemini_deep_research.py`
- Integration: Works with `budget_tracker`, `text_analyzer`, and `sentiment_analyzer` skills
