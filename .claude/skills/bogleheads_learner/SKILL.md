---
skill_id: bogleheads_learner
name: Bogleheads Forum Learner
version: 1.0.0
status: active
description: Continuously learns from Bogleheads.org forum to extract investing wisdom and integrate into RL trading engine
author: Trading System CTO
tags: [learning, forum-analysis, investing-wisdom, rl-integration, mcp]
tools:
  - monitor_bogleheads_forum
  - extract_investing_insights
  - store_insights_to_rag
  - get_bogleheads_signal
  - analyze_market_regime_bogleheads
dependencies:
  - requests
  - beautifulsoup4
  - anthropic
  - langchain
scripts:
  - .claude/skills/bogleheads_learner/scripts/bogleheads_learner.py
---

# Bogleheads Forum Learner Skill

Continuously monitors and learns from [Bogleheads.org](https://www.bogleheads.org/forum/index.php) to extract investing wisdom and integrate insights into the RL trading engine.

## Overview

Bogleheads is a community focused on passive investing, index funds, and long-term wealth building (inspired by Jack Bogle, founder of Vanguard). This skill:

- **Monitors** forum discussions for investing insights
- **Extracts** wisdom about market regimes, risk management, and strategy
- **Stores** insights in RAG for retrieval
- **Integrates** insights as a factor in RL engine decision-making

## Why Bogleheads?

1. **Wisdom of the Crowd**: 147,000+ members, 8M+ posts
2. **Long-Term Perspective**: Focus on decades, not days
3. **Risk Management**: Strong emphasis on diversification and risk control
4. **Market Regime Awareness**: Discussions about market conditions
5. **Contrarian Signals**: Often identifies when markets are overheated/oversold

## Tools

### `monitor_bogleheads_forum`

Monitor Bogleheads forum for new discussions and insights.

**Parameters**:
- `topics`: List of topics to monitor (default: ["Personal Investments", "Investing - Theory, News & General"])
- `keywords`: Keywords to filter for (default: ["market timing", "rebalancing", "risk", "volatility", "bear market", "bull market"])
- `max_posts`: Maximum posts to analyze per run (default: 50)
- `min_replies`: Minimum replies for post to be considered (default: 5)

**Returns**:
- `posts_analyzed`: Number of posts analyzed
- `insights_extracted`: Number of insights extracted
- `topics_found`: List of relevant topics found

### `extract_investing_insights`

Extract investing insights from forum posts using Claude.

**Parameters**:
- `post_content`: Forum post content
- `post_metadata`: Post metadata (author, replies, date)

**Returns**:
- `insight_type`: Type of insight (market_regime, risk_management, strategy, sentiment)
- `insight_text`: Extracted insight
- `confidence`: Confidence score (0-1)
- `relevance_score`: Relevance to trading (0-1)
- `actionable`: Whether insight is actionable

### `store_insights_to_rag`

Store extracted insights in RAG storage for retrieval.

**Parameters**:
- `insights`: List of insight dictionaries
- `embedding_model`: Model to use for embeddings (default: "text-embedding-3-small")

**Returns**:
- `stored_count`: Number of insights stored
- `rag_path`: Path to RAG storage

### `get_bogleheads_signal`

Get trading signal based on Bogleheads forum wisdom.

**Parameters**:
- `symbol`: Symbol to analyze
- `market_context`: Current market context
- `query`: Specific query (e.g., "What do Bogleheads say about SPY in current market?")

**Returns**:
- `signal`: BUY/SELL/HOLD recommendation
- `confidence`: Confidence score (0-1)
- `reasoning`: Reasoning based on forum wisdom
- `insights_used`: List of insights that informed the signal

### `analyze_market_regime_bogleheads`

Analyze current market regime based on Bogleheads discussions.

**Parameters**:
- `timeframe`: Timeframe to analyze (default: "30d")

**Returns**:
- `regime`: Market regime classification (bull, bear, choppy, uncertain)
- `sentiment`: Overall sentiment (bullish, bearish, neutral)
- `key_themes`: List of key themes discussed
- `risk_level`: Perceived risk level (low, medium, high)

## Integration with RL Engine

Bogleheads insights are integrated as a **factor** in the RL engine:

1. **State Space Enhancement**: Adds "bogleheads_sentiment" feature
2. **Signal Weighting**: Bogleheads signal contributes 5-10% to ensemble voting
3. **Risk Adjustment**: Uses Bogleheads risk perception to adjust position sizing
4. **Regime Detection**: Uses Bogleheads regime analysis for context

## Usage Example

```python
from claude.skills.bogleheads_learner.scripts.bogleheads_learner import BogleheadsLearner

learner = BogleheadsLearner()

# Monitor forum
results = learner.monitor_bogleheads_forum(
    topics=["Personal Investments", "Investing - Theory"],
    keywords=["market timing", "risk"],
    max_posts=50
)

# Get signal for symbol
signal = learner.get_bogleheads_signal(
    symbol="SPY",
    market_context={"volatility": "high", "trend": "bullish"},
    query="What do Bogleheads recommend for SPY in high volatility?"
)

# Use in RL engine
rl_state["bogleheads_sentiment"] = signal["confidence"]
rl_state["bogleheads_regime"] = signal["regime"]
```

## Continuous Learning Schedule

- **Daily**: Monitor new posts (runs at 2 AM UTC)
- **Weekly**: Deep analysis of trending topics
- **Monthly**: Regime analysis and strategy review

## Data Privacy

- Respects forum terms of service
- Only analyzes publicly available posts
- No personal information stored
- Rate-limited to avoid overloading forum
