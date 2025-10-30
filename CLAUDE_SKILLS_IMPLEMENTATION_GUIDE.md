# Claude Skills Implementation Guide for AI Trading System

**Version:** 1.0
**Date:** 2025-10-30
**Author:** Trading System Architecture Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Skill Specifications](#skill-specifications)
4. [Python Implementation Templates](#python-implementation-templates)
5. [Integration with Claude Agents SDK](#integration-with-claude-agents-sdk)
6. [Testing and Validation](#testing-and-validation)
7. [Security and Compliance](#security-and-compliance)
8. [Deployment Guide](#deployment-guide)
9. [Appendices](#appendices)

---

## Executive Summary

This guide provides a comprehensive blueprint for implementing six custom Claude Skills to power an AI-driven trading system. Each skill is designed as a modular, reusable component that extends Claude's capabilities with domain-specific financial operations.

### Required Skills Overview

| Skill | Purpose | Frequency | Risk Level |
|-------|---------|-----------|------------|
| Financial Data Fetcher | Market data, news, alternative data | Real-time | Low |
| Portfolio Risk Assessment | Health checks, compliance alerts | Continuous | Critical |
| Sentiment Analyzer | Market sentiment from multiple sources | Real-time | Medium |
| Position Sizer | Dynamic position sizing with volatility | Per trade | High |
| Anomaly Detector | Execution quality monitoring | Real-time | High |
| Performance Monitor | Trading metrics and analytics | Daily/Weekly | Medium |

### Key Benefits

- **Modularity**: Each skill operates independently with clear interfaces
- **Auditability**: Full logging and traceability for compliance
- **Safety**: Multiple validation layers and circuit breakers
- **Extensibility**: Easy to add new data sources and analytics

---

## Architecture Overview

### Claude Skills Framework

Agent Skills are structured directories containing:
- `SKILL.md` - Main skill definition with YAML frontmatter
- `/scripts/` - Executable Python/Bash scripts
- `/references/` - Supporting documentation and data schemas
- `/assets/` - Configuration files and templates

### Progressive Disclosure Pattern

The framework uses three information levels:

1. **Level 1 (Metadata)**: Skill name and description loaded at startup
2. **Level 2 (Core Content)**: Full SKILL.md loaded when relevant
3. **Level 3+ (Supporting Files)**: On-demand file access

This prevents context bloat while enabling unlimited domain knowledge.

### Tool Execution Model

```
User Request → Claude Analyzes Context → Selects Relevant Skill(s)
              ↓
     Loads SKILL.md Instructions
              ↓
     Executes Tool Functions (Client-side)
              ↓
     Returns Structured Results → Claude Synthesizes Response
```

### Integration Architecture

```
┌─────────────────────────────────────────────────────┐
│           Claude Agent (Orchestrator)               │
├─────────────────────────────────────────────────────┤
│  Skill 1    │  Skill 2    │  Skill 3    │  Skill 4 │
│  Financial  │  Risk       │  Sentiment  │  Position│
│  Data       │  Assessment │  Analyzer   │  Sizer   │
├─────────────┼─────────────┼─────────────┼──────────┤
│  Skill 5    │  Skill 6    │             │          │
│  Anomaly    │  Performance│             │          │
│  Detector   │  Monitor    │             │          │
└─────────────┴─────────────┴─────────────┴──────────┘
         ↓            ↓            ↓
    ┌─────────┐  ┌─────────┐  ┌─────────┐
    │ Alpaca  │  │  News   │  │Database │
    │   API   │  │   APIs  │  │ (Local) │
    └─────────┘  └─────────┘  └─────────┘
```

---

## Skill Specifications

### 1. Financial Data Fetcher Skill

#### Purpose
Retrieve real-time and historical market data, news, and alternative data sources.

#### SKILL.md Structure

```markdown
---
name: financial_data_fetcher
description: Fetches real-time market data, news, and alternative data for trading decisions
version: 1.0.0
author: Trading System
tags: [market-data, news, pricing, fundamentals]
---

# Financial Data Fetcher Skill

## Overview
This skill provides comprehensive market data retrieval capabilities including:
- Real-time and historical price data (OHLCV)
- Financial news from multiple sources
- Alternative data (social sentiment, earnings transcripts)
- Fundamental data (P/E ratios, earnings, dividends)
- Market microstructure data (bid-ask spreads, volume)

## Tools

### get_price_data
Retrieves OHLCV (Open, High, Low, Close, Volume) data for specified symbols.

**Parameters:**
- `symbols` (array[string], required): Stock/ETF tickers (e.g., ["AAPL", "SPY"])
- `timeframe` (string, required): Bar timeframe ("1Min", "5Min", "15Min", "1Hour", "1Day")
- `start_date` (string, optional): ISO format start date (YYYY-MM-DD)
- `end_date` (string, optional): ISO format end date (YYYY-MM-DD)
- `limit` (integer, optional): Number of bars to retrieve (default: 100, max: 10000)

**Returns:**
```json
{
  "status": "success",
  "data": {
    "AAPL": [
      {
        "timestamp": "2025-10-30T09:30:00Z",
        "open": 150.25,
        "high": 151.80,
        "low": 150.10,
        "close": 151.50,
        "volume": 1234567
      }
    ]
  },
  "metadata": {
    "symbols": ["AAPL"],
    "timeframe": "1Min",
    "count": 100
  }
}
```

### get_latest_news
Fetches recent financial news for specified symbols or keywords.

**Parameters:**
- `symbols` (array[string], optional): Filter news by stock symbols
- `keywords` (array[string], optional): Search keywords
- `sources` (array[string], optional): News sources (e.g., ["bloomberg", "reuters"])
- `limit` (integer, optional): Number of articles (default: 20, max: 100)
- `hours_back` (integer, optional): Time window in hours (default: 24)

**Returns:**
```json
{
  "status": "success",
  "articles": [
    {
      "title": "Apple Reports Record Q4 Earnings",
      "summary": "Apple Inc. exceeded analyst expectations...",
      "source": "Bloomberg",
      "url": "https://bloomberg.com/...",
      "published_at": "2025-10-30T08:00:00Z",
      "symbols": ["AAPL"],
      "sentiment": {
        "score": 0.85,
        "label": "positive"
      }
    }
  ],
  "count": 20
}
```

### get_fundamentals
Retrieves fundamental data for specified symbols.

**Parameters:**
- `symbols` (array[string], required): Stock tickers
- `metrics` (array[string], optional): Specific metrics to retrieve

**Returns:**
```json
{
  "status": "success",
  "data": {
    "AAPL": {
      "market_cap": 2500000000000,
      "pe_ratio": 28.5,
      "dividend_yield": 0.52,
      "earnings_per_share": 6.42,
      "revenue_ttm": 385000000000,
      "profit_margin": 0.26,
      "52_week_high": 198.23,
      "52_week_low": 143.90
    }
  }
}
```

## Error Handling

All tools return consistent error responses:
```json
{
  "status": "error",
  "error": {
    "code": "INVALID_SYMBOL",
    "message": "Symbol 'INVALID' not found",
    "details": {
      "attempted_symbol": "INVALID"
    }
  }
}
```

## Rate Limiting
- Alpaca API: 200 requests/minute
- News APIs: 100 requests/hour
- Automatic retry with exponential backoff

## Audit Trail
All data fetches are logged with:
- Timestamp
- User/Agent ID
- Symbols requested
- Data returned (summary)
- Performance metrics (latency)

## Usage Example

```python
# Fetch recent price data for analysis
price_data = get_price_data(
    symbols=["SPY", "QQQ", "VOO"],
    timeframe="1Day",
    limit=30
)

# Get latest news for decision context
news = get_latest_news(
    symbols=["SPY"],
    hours_back=12,
    limit=10
)
```
```

---

### 2. Portfolio Risk Assessment Skill

#### Purpose
Monitor portfolio health, enforce risk thresholds, and trigger compliance alerts.

#### SKILL.md Structure

```markdown
---
name: portfolio_risk_assessment
description: Monitors portfolio risk metrics and enforces compliance thresholds
version: 1.0.0
author: Trading System
tags: [risk-management, compliance, circuit-breakers, portfolio]
---

# Portfolio Risk Assessment Skill

## Overview
Comprehensive risk monitoring and alerting system providing:
- Real-time portfolio health assessment
- Circuit breaker enforcement (daily loss, drawdown)
- Position concentration analysis
- Regulatory compliance checks
- Risk threshold alerts

## Tools

### assess_portfolio_health
Performs comprehensive portfolio health check.

**Parameters:**
- `account_id` (string, optional): Specific account (defaults to current)
- `include_positions` (boolean, optional): Include detailed position analysis (default: true)

**Returns:**
```json
{
  "status": "healthy",
  "assessment": {
    "overall_score": 85,
    "account_value": 102500.00,
    "cash": 25000.00,
    "buying_power": 50000.00,
    "portfolio_beta": 1.15,
    "diversification_score": 78
  },
  "risk_metrics": {
    "daily_pl": 250.00,
    "daily_pl_pct": 0.24,
    "max_drawdown": 1250.00,
    "max_drawdown_pct": 1.22,
    "sharpe_ratio": 1.85,
    "sortino_ratio": 2.15,
    "var_95": -850.00
  },
  "positions": {
    "count": 8,
    "largest_position": {
      "symbol": "AAPL",
      "value": 15000.00,
      "pct_of_portfolio": 14.6
    },
    "concentration_risk": "low"
  },
  "circuit_breakers": {
    "daily_loss_limit": {
      "triggered": false,
      "current": -0.24,
      "threshold": -2.0
    },
    "max_drawdown_limit": {
      "triggered": false,
      "current": 1.22,
      "threshold": 10.0
    }
  },
  "alerts": []
}
```

### check_circuit_breakers
Evaluates all circuit breaker conditions.

**Parameters:**
- `account_value` (number, required): Current account value
- `daily_pl` (number, required): Today's profit/loss

**Returns:**
```json
{
  "trading_allowed": true,
  "breakers": [
    {
      "name": "daily_loss_limit",
      "triggered": false,
      "current_value": -0.24,
      "threshold": -2.0,
      "severity": "critical"
    },
    {
      "name": "max_drawdown",
      "triggered": false,
      "current_value": 1.22,
      "threshold": 10.0,
      "severity": "critical"
    },
    {
      "name": "consecutive_losses",
      "triggered": false,
      "current_value": 1,
      "threshold": 3,
      "severity": "warning"
    }
  ],
  "recommendations": []
}
```

### validate_trade
Validates a proposed trade against all risk parameters.

**Parameters:**
- `symbol` (string, required): Trading symbol
- `side` (string, required): "buy" or "sell"
- `amount` (number, required): Dollar amount or share quantity
- `amount_type` (string, optional): "dollars" or "shares" (default: "dollars")
- `account_value` (number, required): Current account value

**Returns:**
```json
{
  "valid": true,
  "symbol": "AAPL",
  "side": "buy",
  "amount": 5000.00,
  "validation_checks": {
    "position_size_limit": {
      "passed": true,
      "position_pct": 4.88,
      "limit_pct": 10.0
    },
    "buying_power": {
      "passed": true,
      "required": 5000.00,
      "available": 50000.00
    },
    "circuit_breakers": {
      "passed": true,
      "active_breakers": []
    },
    "concentration_risk": {
      "passed": true,
      "sector_exposure": 12.5,
      "limit": 30.0
    }
  },
  "warnings": [],
  "approved_amount": 5000.00
}
```

### record_trade_result
Records the outcome of a completed trade for risk tracking.

**Parameters:**
- `symbol` (string, required): Trading symbol
- `side` (string, required): "buy" or "sell"
- `quantity` (number, required): Shares traded
- `fill_price` (number, required): Execution price
- `profit_loss` (number, required): Realized P&L (for closing trades)
- `timestamp` (string, optional): ISO format timestamp

**Returns:**
```json
{
  "status": "recorded",
  "trade_id": "uuid-12345",
  "updated_metrics": {
    "total_trades": 45,
    "winning_trades": 28,
    "losing_trades": 17,
    "win_rate": 62.2,
    "consecutive_losses": 0,
    "daily_pl": 350.00
  }
}
```

## Alert System

### Alert Severity Levels
- **INFO**: Informational updates
- **WARNING**: Attention needed, trading continues
- **CRITICAL**: Immediate action required, trading may halt

### Alert Channels
- Console logging (always enabled)
- Email notifications (configurable)
- Webhook/Slack integration (configurable)
- SMS for critical alerts (optional)

## Compliance Features

### Regulatory Checks
- Pattern Day Trader (PDT) rule enforcement
- Margin requirements validation
- Position limit verification
- Short sale restrictions

### Audit Trail
Every risk assessment generates:
- Unique assessment ID
- Timestamp with microsecond precision
- Complete input parameters
- Decision rationale
- Risk scores and flags

## Usage Example

```python
# Morning health check before trading
health = assess_portfolio_health(include_positions=True)

if health["status"] != "healthy":
    send_alert("Portfolio health degraded", severity="WARNING")

# Validate trade before execution
validation = validate_trade(
    symbol="AAPL",
    side="buy",
    amount=5000.00,
    account_value=102500.00
)

if not validation["valid"]:
    print(f"Trade rejected: {validation['warnings']}")
```
```

---

### 3. Sentiment Analyzer Skill

#### Purpose
Analyze market sentiment from social media, news, and market indicators.

#### SKILL.md Structure

```markdown
---
name: sentiment_analyzer
description: Analyzes market sentiment from multiple sources for trading signals
version: 1.0.0
author: Trading System
tags: [sentiment, nlp, social-media, news-analysis]
---

# Sentiment Analyzer Skill

## Overview
Multi-source sentiment analysis providing:
- News article sentiment scoring
- Social media sentiment aggregation
- Market microstructure sentiment (order flow, volatility)
- Composite sentiment scores with confidence intervals
- Trend detection and anomaly flagging

## Tools

### analyze_news_sentiment
Performs sentiment analysis on financial news articles.

**Parameters:**
- `symbols` (array[string], required): Stock tickers to analyze
- `articles` (array[object], optional): Pre-fetched articles (if not provided, fetches recent news)
- `time_window_hours` (integer, optional): Analysis window (default: 24)
- `sources` (array[string], optional): Specific news sources to include

**Returns:**
```json
{
  "status": "success",
  "sentiment": {
    "AAPL": {
      "overall_score": 0.72,
      "label": "positive",
      "confidence": 0.85,
      "article_count": 15,
      "breakdown": {
        "positive": 11,
        "neutral": 3,
        "negative": 1
      },
      "sources": {
        "bloomberg": 0.80,
        "reuters": 0.65,
        "wsj": 0.71
      },
      "trends": {
        "direction": "improving",
        "momentum": 0.12
      },
      "key_topics": [
        {"topic": "earnings", "sentiment": 0.85, "mentions": 8},
        {"topic": "product_launch", "sentiment": 0.70, "mentions": 5}
      ]
    }
  },
  "timestamp": "2025-10-30T10:00:00Z"
}
```

### analyze_social_sentiment
Aggregates sentiment from social media platforms.

**Parameters:**
- `symbols` (array[string], required): Stock tickers
- `platforms` (array[string], optional): Platforms to analyze (["twitter", "reddit", "stocktwits"])
- `time_window_hours` (integer, optional): Analysis window (default: 6)
- `min_mentions` (integer, optional): Minimum mention threshold (default: 10)

**Returns:**
```json
{
  "status": "success",
  "sentiment": {
    "AAPL": {
      "overall_score": 0.65,
      "label": "positive",
      "confidence": 0.72,
      "total_mentions": 3420,
      "platforms": {
        "twitter": {
          "score": 0.68,
          "mentions": 1850,
          "trending": true
        },
        "reddit": {
          "score": 0.62,
          "mentions": 950,
          "trending": false
        },
        "stocktwits": {
          "score": 0.64,
          "mentions": 620,
          "trending": false
        }
      },
      "influencer_sentiment": 0.75,
      "retail_sentiment": 0.63,
      "volume_trend": "increasing",
      "anomalies": []
    }
  },
  "timestamp": "2025-10-30T10:00:00Z"
}
```

### get_composite_sentiment
Generates weighted composite sentiment from all sources.

**Parameters:**
- `symbols` (array[string], required): Stock tickers
- `weights` (object, optional): Custom source weights
- `include_market_sentiment` (boolean, optional): Include technical indicators (default: true)

**Returns:**
```json
{
  "status": "success",
  "composite_sentiment": {
    "AAPL": {
      "score": 0.68,
      "label": "positive",
      "confidence": 0.80,
      "components": {
        "news_sentiment": {
          "score": 0.72,
          "weight": 0.40,
          "contribution": 0.288
        },
        "social_sentiment": {
          "score": 0.65,
          "weight": 0.30,
          "contribution": 0.195
        },
        "market_sentiment": {
          "score": 0.70,
          "weight": 0.30,
          "contribution": 0.210
        }
      },
      "signal_strength": "strong",
      "recommendation": "buy",
      "risk_factors": [
        "High social media volatility",
        "Mixed sector sentiment"
      ]
    }
  },
  "timestamp": "2025-10-30T10:00:00Z"
}
```

### detect_sentiment_anomalies
Identifies unusual sentiment patterns or rapid changes.

**Parameters:**
- `symbols` (array[string], required): Stock tickers
- `lookback_hours` (integer, optional): Historical comparison window (default: 72)
- `sensitivity` (string, optional): "low", "medium", "high" (default: "medium")

**Returns:**
```json
{
  "status": "success",
  "anomalies": [
    {
      "symbol": "AAPL",
      "type": "rapid_shift",
      "severity": "high",
      "description": "Sentiment shifted from 0.35 to 0.85 in 2 hours",
      "current_sentiment": 0.85,
      "previous_sentiment": 0.35,
      "trigger": "Breaking news: Positive earnings surprise",
      "recommendation": "Wait for stabilization before trading",
      "timestamp": "2025-10-30T09:30:00Z"
    }
  ]
}
```

## Sentiment Scoring Methodology

### Score Range: -1.0 to +1.0
- **0.7 to 1.0**: Very Positive (Strong Buy Signal)
- **0.3 to 0.7**: Positive (Buy Signal)
- **-0.3 to 0.3**: Neutral (Hold)
- **-0.7 to -0.3**: Negative (Sell Signal)
- **-1.0 to -0.7**: Very Negative (Strong Sell Signal)

### Confidence Levels
- **High (>0.8)**: Strong agreement across sources
- **Medium (0.6-0.8)**: Moderate agreement
- **Low (<0.6)**: Mixed signals, use caution

## Data Sources

### News Sources (Priority Order)
1. Bloomberg Terminal API
2. Reuters News API
3. Wall Street Journal
4. Financial Times
5. CNBC, MarketWatch

### Social Media Platforms
1. Twitter/X (Financial FinTwit community)
2. Reddit (r/wallstreetbets, r/stocks, r/investing)
3. StockTwits
4. Seeking Alpha comments

### Market Indicators
1. Put/Call Ratio
2. VIX (Fear Index)
3. Advance/Decline Line
4. On-Balance Volume (OBV)

## NLP Models

- **Primary**: FinBERT (Financial domain-tuned BERT)
- **Secondary**: Twitter-RoBERTa (Social media sentiment)
- **Fallback**: VADER (Valence Aware Dictionary)

## Rate Limiting & Caching

- News API: 100 requests/hour
- Social APIs: Variable by platform
- Results cached for 15 minutes
- Real-time updates for breaking news

## Usage Example

```python
# Get comprehensive sentiment before trade decision
sentiment = get_composite_sentiment(
    symbols=["AAPL"],
    include_market_sentiment=True
)

# Check for anomalies that might affect timing
anomalies = detect_sentiment_anomalies(
    symbols=["AAPL"],
    lookback_hours=24,
    sensitivity="high"
)

if sentiment["AAPL"]["score"] > 0.6 and not anomalies:
    print("Strong positive sentiment - consider buy")
```
```

---

### 4. Position Sizer Skill

#### Purpose
Calculate optimal position sizes based on volatility, account balance, and risk tolerance.

#### SKILL.md Structure

```markdown
---
name: position_sizer
description: Calculates optimal position sizes using volatility and risk-adjusted methods
version: 1.0.0
author: Trading System
tags: [position-sizing, risk-management, volatility, kelly-criterion]
---

# Position Sizer Skill

## Overview
Advanced position sizing using multiple methodologies:
- Fixed percentage method
- Volatility-adjusted sizing
- Kelly Criterion
- ATR-based sizing
- Max drawdown consideration
- Portfolio heat management

## Tools

### calculate_position_size
Calculates optimal position size for a trade.

**Parameters:**
- `symbol` (string, required): Trading symbol
- `account_value` (number, required): Current account value
- `risk_per_trade_pct` (number, optional): Risk per trade % (default: 1.0)
- `method` (string, optional): Sizing method ("fixed_pct", "volatility_adjusted", "kelly", "atr")
- `current_price` (number, optional): Current market price
- `stop_loss_price` (number, optional): Planned stop loss price
- `win_rate` (number, optional): Historical win rate (for Kelly)
- `avg_win_loss_ratio` (number, optional): Average win/loss ratio (for Kelly)

**Returns:**
```json
{
  "status": "success",
  "symbol": "AAPL",
  "recommendations": {
    "primary_method": {
      "method": "volatility_adjusted",
      "position_size_dollars": 5420.00,
      "position_size_shares": 35,
      "rationale": "Adjusted for 18.5% annualized volatility"
    },
    "alternative_methods": {
      "fixed_percentage": {
        "position_size_dollars": 5000.00,
        "position_size_shares": 32
      },
      "kelly_criterion": {
        "position_size_dollars": 6250.00,
        "position_size_shares": 40,
        "kelly_fraction": 0.25
      },
      "atr_based": {
        "position_size_dollars": 5100.00,
        "position_size_shares": 33
      }
    }
  },
  "risk_metrics": {
    "dollar_risk": 500.00,
    "risk_pct": 1.0,
    "position_value_pct": 5.42,
    "estimated_volatility": 0.185,
    "max_loss_at_stop": 500.00
  },
  "constraints": {
    "max_position_size_dollars": 10000.00,
    "max_position_size_pct": 10.0,
    "min_position_size_dollars": 100.00,
    "constrained": false
  },
  "validation": {
    "within_risk_limits": true,
    "sufficient_buying_power": true,
    "liquidity_adequate": true
  }
}
```

### calculate_portfolio_heat
Calculates total risk exposure across all positions.

**Parameters:**
- `account_value` (number, required): Current account value
- `positions` (array[object], required): Current open positions
- `pending_trades` (array[object], optional): Trades being considered

**Returns:**
```json
{
  "status": "success",
  "portfolio_heat": {
    "total_risk_dollars": 2500.00,
    "total_risk_pct": 2.5,
    "individual_positions": [
      {
        "symbol": "AAPL",
        "position_value": 5000.00,
        "risk_dollars": 500.00,
        "risk_pct": 0.5,
        "stop_loss": 148.50
      }
    ],
    "risk_distribution": {
      "tech_sector": 1.2,
      "finance_sector": 0.8,
      "healthcare_sector": 0.5
    },
    "capacity": {
      "max_total_risk_pct": 5.0,
      "remaining_capacity_pct": 2.5,
      "remaining_capacity_dollars": 2500.00
    }
  },
  "recommendations": {
    "can_add_position": true,
    "max_new_position_dollars": 1000.00,
    "warnings": []
  }
}
```

### adjust_position_for_volatility
Adjusts existing position size based on volatility changes.

**Parameters:**
- `symbol` (string, required): Trading symbol
- `current_position_value` (number, required): Current position value
- `target_volatility` (number, optional): Target volatility % (default: 20.0)
- `rebalance_threshold` (number, optional): Rebalance if exceeds threshold (default: 0.15)

**Returns:**
```json
{
  "status": "success",
  "symbol": "AAPL",
  "analysis": {
    "current_position_value": 5000.00,
    "current_volatility": 0.28,
    "target_volatility": 0.20,
    "volatility_ratio": 1.40
  },
  "recommendation": {
    "action": "reduce",
    "target_position_value": 3571.00,
    "adjustment_amount": -1429.00,
    "adjustment_shares": -9,
    "rationale": "Current volatility 40% above target"
  },
  "execution_plan": {
    "recommended": true,
    "urgency": "medium",
    "method": "market_order"
  }
}
```

### calculate_kelly_fraction
Calculates Kelly Criterion for position sizing.

**Parameters:**
- `win_rate` (number, required): Probability of winning (0-1)
- `avg_win_loss_ratio` (number, required): Average win ÷ average loss
- `kelly_multiplier` (number, optional): Conservative multiplier (default: 0.25)

**Returns:**
```json
{
  "status": "success",
  "kelly_calculation": {
    "raw_kelly_pct": 25.5,
    "adjusted_kelly_pct": 6.375,
    "kelly_multiplier": 0.25,
    "inputs": {
      "win_rate": 0.55,
      "avg_win_loss_ratio": 1.8
    },
    "formula": "(win_rate * avg_win_loss_ratio - (1 - win_rate)) / avg_win_loss_ratio"
  },
  "recommendation": {
    "position_size_pct": 6.375,
    "rationale": "Using 25% Kelly for conservative approach",
    "warnings": [
      "Full Kelly (25.5%) is aggressive - using fractional Kelly"
    ]
  }
}
```

## Position Sizing Methods

### 1. Fixed Percentage Method
Risk a fixed % of account per trade (e.g., 1-2%).

**Formula**: `Position Size = (Account Value × Risk %) ÷ (Entry Price - Stop Price)`

**Best For**:
- Consistent risk management
- Beginning traders
- Low volatility markets

### 2. Volatility-Adjusted Method
Adjusts size based on asset volatility.

**Formula**: `Adjusted Size = Base Size × (Target Vol ÷ Asset Vol)`

**Best For**:
- Multi-asset portfolios
- Variable volatility regimes
- Professional risk management

### 3. Kelly Criterion
Maximizes long-term growth rate based on edge.

**Formula**: `Kelly % = (Win Rate × Avg Win/Loss Ratio - (1 - Win Rate)) ÷ Avg Win/Loss Ratio`

**Best For**:
- Systems with known edge
- Experienced traders
- Always use fractional Kelly (25-50%)

### 4. ATR-Based Method
Uses Average True Range for volatility assessment.

**Formula**: `Position Size = (Account × Risk %) ÷ (ATR × Multiplier)`

**Best For**:
- Trend-following strategies
- Volatile markets
- Technical traders

## Safety Constraints

### Hard Limits
- **Max Single Position**: 10% of account value
- **Max Total Risk**: 5% of account value
- **Min Position Size**: $100 (avoid excessive trading costs)
- **Max Leverage**: 2x (if using margin)

### Dynamic Adjustments
- Reduce size after losing streaks
- Increase size cautiously after winning streaks
- Scale down in high volatility
- Respect circuit breakers

## Volatility Calculation

### Historical Volatility (20-day)
```python
daily_returns = price_data.pct_change()
volatility = daily_returns.std() * sqrt(252)  # Annualized
```

### ATR (14-period)
```python
tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
atr = rolling_average(tr, 14)
```

## Usage Example

```python
# Calculate position size for new trade
position = calculate_position_size(
    symbol="AAPL",
    account_value=100000,
    risk_per_trade_pct=1.0,
    method="volatility_adjusted",
    current_price=155.00,
    stop_loss_price=150.00
)

# Check portfolio capacity before adding
heat = calculate_portfolio_heat(
    account_value=100000,
    positions=current_positions,
    pending_trades=[position]
)

if heat["recommendations"]["can_add_position"]:
    execute_trade(position)
```
```

---

### 5. Anomaly Detector Skill

#### Purpose
Detect execution anomalies, price gaps, slippage, and unusual market conditions.

#### SKILL.md Structure

```markdown
---
name: anomaly_detector
description: Detects execution issues, slippage, and market anomalies in real-time
version: 1.0.0
author: Trading System
tags: [execution-quality, anomaly-detection, slippage, market-microstructure]
---

# Anomaly Detector Skill

## Overview
Real-time anomaly detection for:
- Execution slippage monitoring
- Price gap detection
- Volume anomalies
- Spread widening alerts
- Order fill quality assessment
- Market manipulation detection

## Tools

### detect_execution_anomalies
Analyzes execution quality and detects slippage issues.

**Parameters:**
- `order_id` (string, required): Order identifier
- `expected_price` (number, required): Expected execution price
- `actual_fill_price` (number, required): Actual fill price
- `quantity` (number, required): Shares traded
- `order_type` (string, required): "market" or "limit"
- `timestamp` (string, required): Execution timestamp

**Returns:**
```json
{
  "status": "success",
  "analysis": {
    "order_id": "abc123",
    "slippage": {
      "amount": 0.15,
      "percentage": 0.097,
      "severity": "normal",
      "threshold_exceeded": false
    },
    "execution_quality": {
      "score": 92,
      "grade": "A",
      "comparison_to_vwap": -0.02,
      "comparison_to_midpoint": 0.01
    },
    "cost_analysis": {
      "expected_cost": 5000.00,
      "actual_cost": 5007.50,
      "slippage_cost": 7.50,
      "commission": 0.00,
      "total_cost": 5007.50
    },
    "anomalies_detected": false,
    "warnings": []
  },
  "benchmarks": {
    "typical_slippage_range": [0.05, 0.10],
    "market_conditions": "normal",
    "liquidity_level": "high"
  }
}
```

### detect_price_gaps
Identifies significant price gaps and discontinuities.

**Parameters:**
- `symbol` (string, required): Trading symbol
- `lookback_periods` (integer, optional): Periods to analyze (default: 100)
- `gap_threshold_pct` (number, optional): Gap significance threshold (default: 1.0)

**Returns:**
```json
{
  "status": "success",
  "symbol": "AAPL",
  "gaps_detected": [
    {
      "timestamp": "2025-10-30T09:30:00Z",
      "type": "gap_up",
      "gap_size_pct": 2.35,
      "prev_close": 150.00,
      "open": 153.53,
      "gap_size_dollars": 3.53,
      "filled": false,
      "volume_ratio": 2.8,
      "catalyst": "Earnings beat expectations",
      "significance": "high",
      "trading_implications": "Strong momentum, expect continuation"
    }
  ],
  "gap_statistics": {
    "total_gaps_30d": 5,
    "gap_fill_rate": 0.60,
    "avg_gap_size": 1.25,
    "largest_unfilled_gap": 2.35
  }
}
```

### monitor_spread_conditions
Monitors bid-ask spreads for liquidity issues.

**Parameters:**
- `symbols` (array[string], required): Symbols to monitor
- `alert_threshold_pct` (number, optional): Spread % threshold for alerts (default: 0.5)

**Returns:**
```json
{
  "status": "success",
  "spread_analysis": {
    "AAPL": {
      "bid": 154.98,
      "ask": 155.02,
      "spread": 0.04,
      "spread_pct": 0.026,
      "spread_bps": 2.6,
      "status": "normal",
      "liquidity_score": 98,
      "anomalies": []
    }
  },
  "alerts": [],
  "market_conditions": {
    "overall_liquidity": "high",
    "volatility_regime": "low",
    "risk_level": "low"
  }
}
```

### detect_volume_anomalies
Identifies unusual volume patterns.

**Parameters:**
- `symbol` (string, required): Trading symbol
- `current_volume` (number, required): Current period volume
- `lookback_periods` (integer, optional): Historical comparison (default: 20)
- `std_dev_threshold` (number, optional): Standard deviations for anomaly (default: 2.5)

**Returns:**
```json
{
  "status": "success",
  "symbol": "AAPL",
  "volume_analysis": {
    "current_volume": 5500000,
    "avg_volume": 3200000,
    "volume_ratio": 1.72,
    "std_deviations": 3.2,
    "anomaly_detected": true,
    "anomaly_type": "high_volume",
    "significance": "high"
  },
  "context": {
    "time_of_day": "09:45",
    "typical_volume_pattern": "Elevated volume common at market open",
    "potential_catalysts": [
      "Earnings announcement",
      "Market-wide surge"
    ]
  },
  "trading_implications": {
    "liquidity": "Excellent",
    "execution_quality": "Expected to be good",
    "caution_level": "Monitor for news"
  }
}
```

### assess_market_manipulation_risk
Screens for potential manipulation patterns.

**Parameters:**
- `symbol` (string, required): Trading symbol
- `price_data` (array[object], required): Recent price/volume data
- `sensitivity` (string, optional): "low", "medium", "high" (default: "medium")

**Returns:**
```json
{
  "status": "success",
  "symbol": "AAPL",
  "risk_assessment": {
    "overall_risk": "low",
    "confidence": 0.85,
    "patterns_detected": []
  },
  "screening_results": {
    "spoofing": {
      "detected": false,
      "score": 0.15
    },
    "layering": {
      "detected": false,
      "score": 0.10
    },
    "wash_trading": {
      "detected": false,
      "score": 0.05
    },
    "pump_and_dump": {
      "detected": false,
      "score": 0.08
    }
  },
  "recommendation": "Safe to trade"
}
```

## Anomaly Detection Algorithms

### 1. Statistical Methods
- **Z-Score Analysis**: Identify outliers beyond N standard deviations
- **Moving Average Deviation**: Compare to MA with dynamic bands
- **Quantile-based Detection**: Flag values in extreme percentiles

### 2. Machine Learning Models
- **Isolation Forest**: Unsupervised anomaly detection
- **LSTM Autoencoders**: Sequential pattern recognition
- **One-Class SVM**: Boundary detection for normal behavior

### 3. Rule-Based Systems
- **Threshold Rules**: Hard limits on key metrics
- **Pattern Matching**: Known manipulation patterns
- **Time-Series Rules**: Temporal consistency checks

## Slippage Benchmarks

### Expected Slippage by Market Cap
- **Large Cap (>$10B)**: 0.05% - 0.10%
- **Mid Cap ($2B-$10B)**: 0.10% - 0.25%
- **Small Cap (<$2B)**: 0.25% - 0.50%

### Market Condition Adjustments
- **High Volatility**: 2x normal slippage
- **Low Liquidity**: 3x normal slippage
- **Market Open/Close**: 1.5x normal slippage

## Alert Thresholds

### Severity Levels
- **INFO**: Within expected range
- **WARNING**: Exceeds typical by 1.5-2x
- **CRITICAL**: Exceeds typical by >2x or signs of manipulation

### Auto-Actions
- **WARNING**: Log and notify
- **CRITICAL**: Halt trading, notify immediately, save evidence

## Data Sources
- Order book data (L2/L3)
- Trade and quote (TAQ) data
- Exchange market data
- Historical execution records

## Usage Example

```python
# Monitor execution quality post-trade
execution_analysis = detect_execution_anomalies(
    order_id="abc123",
    expected_price=155.00,
    actual_fill_price=155.15,
    quantity=100,
    order_type="market",
    timestamp="2025-10-30T10:15:00Z"
)

if execution_analysis["analysis"]["slippage"]["severity"] == "high":
    alert_team("High slippage detected", execution_analysis)

# Pre-trade checks
spread_check = monitor_spread_conditions(
    symbols=["AAPL"],
    alert_threshold_pct=0.3
)

if spread_check["alerts"]:
    delay_trade("Wait for spread normalization")
```
```

---

### 6. Performance Monitor Skill

#### Purpose
Track and analyze trading performance with comprehensive metrics.

#### SKILL.md Structure

```markdown
---
name: performance_monitor
description: Tracks trading performance with comprehensive metrics and analytics
version: 1.0.0
author: Trading System
tags: [performance, analytics, sharpe-ratio, drawdown, metrics]
---

# Performance Monitor Skill

## Overview
Comprehensive performance tracking and analytics:
- Real-time P&L tracking
- Risk-adjusted return metrics (Sharpe, Sortino)
- Drawdown analysis
- Win rate and trade statistics
- Strategy comparison
- Benchmark comparison

## Tools

### calculate_performance_metrics
Calculates comprehensive performance statistics.

**Parameters:**
- `start_date` (string, optional): Analysis start date (ISO format)
- `end_date` (string, optional): Analysis end date (ISO format)
- `benchmark_symbol` (string, optional): Benchmark for comparison (default: "SPY")
- `include_closed_positions` (boolean, optional): Include realized P&L only (default: false)

**Returns:**
```json
{
  "status": "success",
  "period": {
    "start_date": "2025-01-01",
    "end_date": "2025-10-30",
    "trading_days": 210
  },
  "returns": {
    "total_return": 0.125,
    "total_return_pct": 12.5,
    "annualized_return": 0.142,
    "cumulative_return": 0.125,
    "benchmark_return": 0.085,
    "alpha": 0.040,
    "beta": 1.15
  },
  "risk_metrics": {
    "sharpe_ratio": 1.85,
    "sortino_ratio": 2.45,
    "calmar_ratio": 3.12,
    "max_drawdown": 0.042,
    "max_drawdown_duration_days": 18,
    "volatility_annualized": 0.165,
    "downside_deviation": 0.092
  },
  "trade_statistics": {
    "total_trades": 156,
    "winning_trades": 94,
    "losing_trades": 62,
    "win_rate": 0.603,
    "avg_win": 125.50,
    "avg_loss": -72.30,
    "largest_win": 850.00,
    "largest_loss": -420.00,
    "avg_win_loss_ratio": 1.74,
    "profit_factor": 2.05,
    "expectancy": 52.80
  },
  "position_analysis": {
    "avg_hold_time_hours": 36.5,
    "longest_winning_streak": 8,
    "longest_losing_streak": 4,
    "current_streak": {
      "type": "winning",
      "length": 3
    }
  },
  "equity_curve": {
    "starting_equity": 100000,
    "current_equity": 112500,
    "peak_equity": 115200,
    "trough_equity": 98200
  }
}
```

### get_sharpe_ratio
Calculates Sharpe ratio for risk-adjusted returns.

**Parameters:**
- `returns` (array[number], required): Period returns
- `risk_free_rate` (number, optional): Annual risk-free rate (default: 0.045)
- `periods_per_year` (integer, optional): Trading periods per year (default: 252)

**Returns:**
```json
{
  "status": "success",
  "sharpe_ratio": 1.85,
  "calculation": {
    "mean_return": 0.00089,
    "std_dev": 0.0105,
    "risk_free_rate_daily": 0.000178,
    "excess_return": 0.000712,
    "annualized_sharpe": 1.85
  },
  "interpretation": {
    "rating": "good",
    "description": "Above 1.5 indicates strong risk-adjusted returns"
  }
}
```

### calculate_drawdown_analysis
Analyzes drawdown patterns and recovery times.

**Parameters:**
- `equity_curve` (array[object], required): Equity values over time
- `rolling_window_days` (integer, optional): Rolling max window (default: 252)

**Returns:**
```json
{
  "status": "success",
  "drawdown_analysis": {
    "max_drawdown": {
      "amount": 4200.00,
      "percentage": 4.2,
      "peak_value": 115200,
      "trough_value": 111000,
      "peak_date": "2025-08-15",
      "trough_date": "2025-09-02",
      "recovery_date": "2025-09-28",
      "duration_days": 18,
      "recovery_days": 26,
      "total_duration_days": 44
    },
    "current_drawdown": {
      "amount": 2700.00,
      "percentage": 2.34,
      "days_in_drawdown": 8
    },
    "drawdown_distribution": {
      "num_drawdowns": 12,
      "avg_drawdown_pct": 1.8,
      "avg_duration_days": 9.5,
      "avg_recovery_days": 15.2
    },
    "historical_drawdowns": [
      {
        "percentage": 4.2,
        "start_date": "2025-08-15",
        "end_date": "2025-09-28",
        "duration_days": 44
      }
    ]
  },
  "risk_assessment": {
    "drawdown_severity": "moderate",
    "recovery_speed": "fast",
    "overall_risk": "acceptable"
  }
}
```

### get_win_rate_analysis
Analyzes win rate trends and patterns.

**Parameters:**
- `trades` (array[object], required): Trade history
- `grouping` (string, optional): "daily", "weekly", "monthly", "strategy"
- `min_sample_size` (integer, optional): Minimum trades for valid stat (default: 20)

**Returns:**
```json
{
  "status": "success",
  "overall": {
    "win_rate": 0.603,
    "total_trades": 156,
    "winning_trades": 94,
    "losing_trades": 62,
    "confidence_interval_95": [0.52, 0.68]
  },
  "by_strategy": {
    "core_strategy": {
      "win_rate": 0.65,
      "trades": 105,
      "wins": 68,
      "losses": 37
    },
    "growth_strategy": {
      "win_rate": 0.52,
      "trades": 51,
      "wins": 26,
      "losses": 25
    }
  },
  "by_time_period": {
    "month_1": {"win_rate": 0.58, "trades": 35},
    "month_2": {"win_rate": 0.62, "trades": 38},
    "month_3": {"win_rate": 0.61, "trades": 40}
  },
  "trends": {
    "direction": "improving",
    "statistical_significance": true,
    "regression_slope": 0.008
  }
}
```

### compare_to_benchmark
Compares strategy performance to market benchmark.

**Parameters:**
- `portfolio_returns` (array[number], required): Portfolio returns
- `benchmark_symbol` (string, optional): Benchmark ticker (default: "SPY")
- `start_date` (string, required): ISO format date
- `end_date` (string, required): ISO format date

**Returns:**
```json
{
  "status": "success",
  "comparison": {
    "portfolio": {
      "total_return": 0.125,
      "annualized_return": 0.142,
      "volatility": 0.165,
      "sharpe_ratio": 1.85,
      "max_drawdown": 0.042
    },
    "benchmark": {
      "symbol": "SPY",
      "total_return": 0.085,
      "annualized_return": 0.095,
      "volatility": 0.145,
      "sharpe_ratio": 1.32,
      "max_drawdown": 0.068
    },
    "relative_performance": {
      "alpha": 0.047,
      "beta": 1.15,
      "tracking_error": 0.042,
      "information_ratio": 1.12,
      "outperformance": 0.040,
      "outperformance_pct": 47.1
    }
  },
  "interpretation": {
    "verdict": "outperforming",
    "confidence": "high",
    "key_insights": [
      "Higher risk-adjusted returns (Sharpe 1.85 vs 1.32)",
      "Lower maximum drawdown (4.2% vs 6.8%)",
      "Positive alpha indicates skill beyond market beta"
    ]
  }
}
```

### generate_trade_report
Generates detailed trade-by-trade performance report.

**Parameters:**
- `start_date` (string, optional): Report start date
- `end_date` (string, optional): Report end date
- `filter_strategy` (string, optional): Filter by specific strategy
- `min_pnl` (number, optional): Filter by minimum P&L
- `sort_by` (string, optional): "date", "pnl", "return_pct"

**Returns:**
```json
{
  "status": "success",
  "summary": {
    "total_trades": 156,
    "period": "2025-01-01 to 2025-10-30",
    "total_pnl": 12500.00,
    "avg_pnl": 80.13
  },
  "trades": [
    {
      "trade_id": "t001",
      "symbol": "AAPL",
      "strategy": "core_strategy",
      "entry_date": "2025-10-28",
      "exit_date": "2025-10-29",
      "entry_price": 152.50,
      "exit_price": 155.75,
      "quantity": 50,
      "pnl": 162.50,
      "return_pct": 2.13,
      "hold_time_hours": 24.5,
      "execution_quality": "good"
    }
  ],
  "best_trades": [
    {"symbol": "NVDA", "pnl": 850.00, "return_pct": 8.5}
  ],
  "worst_trades": [
    {"symbol": "META", "pnl": -420.00, "return_pct": -4.2}
  ]
}
```

## Key Performance Metrics

### Return Metrics
- **Total Return**: Overall % gain/loss
- **Annualized Return**: Extrapolated annual return
- **CAGR**: Compound Annual Growth Rate
- **Alpha**: Excess return vs benchmark
- **Beta**: Correlation to market

### Risk Metrics
- **Sharpe Ratio**: Risk-adjusted return (higher is better)
  - < 1.0: Poor
  - 1.0-2.0: Good
  - > 2.0: Excellent
- **Sortino Ratio**: Downside risk-adjusted return
- **Calmar Ratio**: Return / Max Drawdown
- **Max Drawdown**: Largest peak-to-trough decline

### Trade Metrics
- **Win Rate**: % of profitable trades
- **Profit Factor**: Gross Profit / Gross Loss
- **Expectancy**: Average $ per trade
- **Avg Win/Loss Ratio**: Size of wins vs losses

## Visualization Support

The skill includes data formatted for:
- Equity curve charts
- Drawdown charts
- Monthly return heatmaps
- Strategy comparison charts
- Trade distribution histograms

## Benchmarks

### Industry Standards
- **Hedge Fund Average**: Sharpe ~1.0, Return 8-12%
- **Top Quartile**: Sharpe >1.5, Return >15%
- **S&P 500**: Sharpe ~0.8-1.0, Return ~10% annually

### Your Targets
- Sharpe Ratio: >1.5
- Max Drawdown: <10%
- Win Rate: >55%
- Alpha: >3%

## Usage Example

```python
# Daily performance review
metrics = calculate_performance_metrics(
    start_date="2025-10-01",
    end_date="2025-10-30",
    benchmark_symbol="SPY"
)

print(f"Sharpe Ratio: {metrics['risk_metrics']['sharpe_ratio']}")
print(f"Win Rate: {metrics['trade_statistics']['win_rate']*100}%")

# Check if meeting targets
if metrics["risk_metrics"]["sharpe_ratio"] < 1.5:
    alert("Performance below target Sharpe ratio")

# Detailed drawdown analysis
dd_analysis = calculate_drawdown_analysis(equity_curve=get_equity_data())
if dd_analysis["current_drawdown"]["percentage"] > 5:
    alert("In significant drawdown - review risk controls")
```
```

---

## Python Implementation Templates

### Base Tool Template

All skills follow a consistent structure for tool implementation:

```python
#!/usr/bin/env python3
"""
[SKILL_NAME] - Claude Skill Implementation
Description: [Brief description]
Version: 1.0.0
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/{__file__}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Audit trail setup
AUDIT_DIR = Path("audit_logs")
AUDIT_DIR.mkdir(exist_ok=True)


class ToolError(Exception):
    """Base exception for tool errors."""
    pass


class ValidationError(ToolError):
    """Exception for parameter validation errors."""
    pass


class ExecutionError(ToolError):
    """Exception for execution failures."""
    pass


def audit_log(tool_name: str, params: Dict, result: Dict, execution_time_ms: float) -> None:
    """
    Log all tool executions for compliance and debugging.

    Args:
        tool_name: Name of the tool executed
        params: Input parameters
        result: Tool output
        execution_time_ms: Execution duration in milliseconds
    """
    timestamp = datetime.now().isoformat()
    audit_entry = {
        "timestamp": timestamp,
        "tool": tool_name,
        "params": params,
        "result_status": result.get("status"),
        "execution_time_ms": execution_time_ms,
        "user_id": os.getenv("USER_ID", "system"),
    }

    # Write to audit log
    audit_file = AUDIT_DIR / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
    with open(audit_file, 'a') as f:
        f.write(json.dumps(audit_entry) + '\n')

    logger.info(f"Audit log: {tool_name} executed in {execution_time_ms:.2f}ms")


def validate_params(params: Dict, required: List[str], schema: Dict) -> None:
    """
    Validate tool parameters against schema.

    Args:
        params: Input parameters
        required: List of required parameter names
        schema: Parameter validation schema

    Raises:
        ValidationError: If validation fails
    """
    # Check required parameters
    missing = [p for p in required if p not in params]
    if missing:
        raise ValidationError(f"Missing required parameters: {', '.join(missing)}")

    # Validate types and constraints
    for param, rules in schema.items():
        if param not in params:
            continue

        value = params[param]

        # Type check
        if "type" in rules:
            expected_type = rules["type"]
            if not isinstance(value, expected_type):
                raise ValidationError(
                    f"Parameter '{param}' must be {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )

        # Range check for numbers
        if "min" in rules and value < rules["min"]:
            raise ValidationError(f"Parameter '{param}' must be >= {rules['min']}")

        if "max" in rules and value > rules["max"]:
            raise ValidationError(f"Parameter '{param}' must be <= {rules['max']}")

        # Enum check
        if "enum" in rules and value not in rules["enum"]:
            raise ValidationError(
                f"Parameter '{param}' must be one of {rules['enum']}"
            )


def handle_errors(func):
    """
    Decorator for consistent error handling across tools.

    Returns standardized error responses and logs exceptions.
    """
    def wrapper(*args, **kwargs):
        start_time = datetime.now()
        tool_name = func.__name__

        try:
            result = func(*args, **kwargs)
            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            # Audit successful execution
            audit_log(tool_name, kwargs, result, execution_time)

            return result

        except ValidationError as e:
            logger.error(f"Validation error in {tool_name}: {e}")
            return {
                "status": "error",
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(e),
                    "tool": tool_name
                }
            }

        except ToolError as e:
            logger.error(f"Tool error in {tool_name}: {e}")
            return {
                "status": "error",
                "error": {
                    "code": "EXECUTION_ERROR",
                    "message": str(e),
                    "tool": tool_name
                }
            }

        except Exception as e:
            logger.exception(f"Unexpected error in {tool_name}: {e}")
            return {
                "status": "error",
                "error": {
                    "code": "UNEXPECTED_ERROR",
                    "message": "An unexpected error occurred",
                    "details": str(e),
                    "tool": tool_name
                }
            }

    return wrapper


# Example Tool Implementation
@handle_errors
def example_tool(
    required_param: str,
    optional_param: int = 10,
    **kwargs
) -> Dict[str, Any]:
    """
    Example tool implementation with validation and error handling.

    Args:
        required_param: A required string parameter
        optional_param: An optional integer parameter (default: 10)

    Returns:
        Standardized response dictionary
    """
    # Parameter validation
    params = {"required_param": required_param, "optional_param": optional_param}
    schema = {
        "required_param": {"type": str},
        "optional_param": {"type": int, "min": 1, "max": 100}
    }
    validate_params(params, ["required_param"], schema)

    # Tool logic
    logger.info(f"Executing example_tool with params: {params}")

    # ... implementation ...

    # Return standardized response
    return {
        "status": "success",
        "data": {
            "result": "example",
            "processed": True
        },
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }
    }


if __name__ == "__main__":
    # Tool testing
    print("Testing example tool...")
    result = example_tool(required_param="test", optional_param=25)
    print(json.dumps(result, indent=2))
```

---

### Skill 1: Financial Data Fetcher Implementation

```python
#!/usr/bin/env python3
"""
Financial Data Fetcher - Claude Skill Implementation
Retrieves real-time and historical market data, news, and alternative data.
"""

import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

import alpaca_trade_api as tradeapi
import yfinance as yf
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Alpaca API
ALPACA_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET = os.getenv('ALPACA_SECRET_KEY')
ALPACA_BASE_URL = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

alpaca_api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL, api_version='v2')


class DataFetchError(Exception):
    """Exception for data fetching errors."""
    pass


def get_price_data(
    symbols: List[str],
    timeframe: str = "1Day",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Retrieve OHLCV price data for specified symbols.

    Args:
        symbols: List of stock/ETF tickers
        timeframe: Bar timeframe ("1Min", "5Min", "15Min", "1Hour", "1Day")
        start_date: ISO format start date (YYYY-MM-DD)
        end_date: ISO format end date (YYYY-MM-DD)
        limit: Number of bars to retrieve (max 10000)

    Returns:
        Dictionary with price data for each symbol
    """
    try:
        # Validate parameters
        valid_timeframes = ["1Min", "5Min", "15Min", "1Hour", "1Day"]
        if timeframe not in valid_timeframes:
            raise ValueError(f"Invalid timeframe. Must be one of {valid_timeframes}")

        if limit < 1 or limit > 10000:
            raise ValueError("Limit must be between 1 and 10000")

        # Clean symbols
        symbols = [s.strip().upper() for s in symbols]

        logger.info(f"Fetching price data for {symbols}, timeframe={timeframe}, limit={limit}")

        # Fetch data from Alpaca
        result_data = {}

        for symbol in symbols:
            try:
                # Get bars from Alpaca
                if start_date:
                    barset = alpaca_api.get_bars(
                        symbol,
                        timeframe,
                        start=start_date,
                        end=end_date,
                        limit=limit
                    )
                else:
                    barset = alpaca_api.get_bars(
                        symbol,
                        timeframe,
                        limit=limit
                    )

                # Convert to list of dicts
                bars = []
                for bar in barset:
                    bars.append({
                        "timestamp": bar.t.isoformat(),
                        "open": float(bar.o),
                        "high": float(bar.h),
                        "low": float(bar.l),
                        "close": float(bar.c),
                        "volume": int(bar.v)
                    })

                result_data[symbol] = bars
                logger.info(f"Retrieved {len(bars)} bars for {symbol}")

            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
                result_data[symbol] = {
                    "error": str(e),
                    "status": "failed"
                }

        return {
            "status": "success",
            "data": result_data,
            "metadata": {
                "symbols": symbols,
                "timeframe": timeframe,
                "limit": limit,
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        logger.error(f"Error in get_price_data: {e}")
        return {
            "status": "error",
            "error": {
                "code": "DATA_FETCH_ERROR",
                "message": str(e)
            }
        }


def get_latest_news(
    symbols: Optional[List[str]] = None,
    keywords: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    limit: int = 20,
    hours_back: int = 24
) -> Dict[str, Any]:
    """
    Fetch recent financial news for specified symbols or keywords.

    Args:
        symbols: Filter news by stock symbols
        keywords: Search keywords
        sources: News sources to include
        limit: Number of articles (max 100)
        hours_back: Time window in hours

    Returns:
        Dictionary with news articles
    """
    try:
        logger.info(f"Fetching news: symbols={symbols}, keywords={keywords}, hours_back={hours_back}")

        # Use Alpaca News API
        start_time = datetime.now() - timedelta(hours=hours_back)

        if symbols:
            symbols_str = ",".join([s.upper() for s in symbols])
        else:
            symbols_str = None

        # Fetch news from Alpaca
        news_data = alpaca_api.get_news(
            symbols_str,
            start=start_time.isoformat(),
            limit=limit
        )

        articles = []
        for article in news_data:
            articles.append({
                "title": article.headline,
                "summary": article.summary,
                "source": article.source,
                "url": article.url,
                "published_at": article.created_at.isoformat(),
                "symbols": article.symbols if hasattr(article, 'symbols') else [],
                "sentiment": {
                    "score": 0.0,  # Would integrate sentiment analysis
                    "label": "neutral"
                }
            })

        logger.info(f"Retrieved {len(articles)} news articles")

        return {
            "status": "success",
            "articles": articles,
            "count": len(articles),
            "metadata": {
                "hours_back": hours_back,
                "timestamp": datetime.now().isoformat()
            }
        }

    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return {
            "status": "error",
            "error": {
                "code": "NEWS_FETCH_ERROR",
                "message": str(e)
            }
        }


def get_fundamentals(
    symbols: List[str],
    metrics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Retrieve fundamental data for specified symbols.

    Args:
        symbols: Stock tickers
        metrics: Specific metrics to retrieve (optional)

    Returns:
        Dictionary with fundamental data
    """
    try:
        logger.info(f"Fetching fundamentals for {symbols}")

        result_data = {}

        for symbol in symbols:
            try:
                # Use yfinance for fundamentals
                ticker = yf.Ticker(symbol)
                info = ticker.info

                result_data[symbol] = {
                    "market_cap": info.get("marketCap", 0),
                    "pe_ratio": info.get("trailingPE", 0),
                    "forward_pe": info.get("forwardPE", 0),
                    "dividend_yield": info.get("dividendYield", 0),
                    "earnings_per_share": info.get("trailingEps", 0),
                    "revenue_ttm": info.get("totalRevenue", 0),
                    "profit_margin": info.get("profitMargins", 0),
                    "52_week_high": info.get("fiftyTwoWeekHigh", 0),
                    "52_week_low": info.get("fiftyTwoWeekLow", 0),
                    "beta": info.get("beta", 0),
                    "shares_outstanding": info.get("sharesOutstanding", 0)
                }

                logger.info(f"Retrieved fundamentals for {symbol}")

            except Exception as e:
                logger.error(f"Error fetching fundamentals for {symbol}: {e}")
                result_data[symbol] = {
                    "error": str(e),
                    "status": "failed"
                }

        return {
            "status": "success",
            "data": result_data,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in get_fundamentals: {e}")
        return {
            "status": "error",
            "error": {
                "code": "FUNDAMENTALS_FETCH_ERROR",
                "message": str(e)
            }
        }


# Tool registration for Claude
TOOLS = [
    {
        "name": "get_price_data",
        "description": "Retrieves OHLCV price data for specified symbols",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Stock/ETF tickers (e.g., ['AAPL', 'SPY'])"
                },
                "timeframe": {
                    "type": "string",
                    "enum": ["1Min", "5Min", "15Min", "1Hour", "1Day"],
                    "description": "Bar timeframe"
                },
                "start_date": {
                    "type": "string",
                    "description": "ISO format start date (YYYY-MM-DD)"
                },
                "end_date": {
                    "type": "string",
                    "description": "ISO format end date (YYYY-MM-DD)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of bars (default: 100, max: 10000)"
                }
            },
            "required": ["symbols", "timeframe"]
        }
    },
    {
        "name": "get_latest_news",
        "description": "Fetches recent financial news for specified symbols or keywords",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter news by stock symbols"
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Search keywords"
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "News sources to include"
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of articles (default: 20, max: 100)"
                },
                "hours_back": {
                    "type": "integer",
                    "description": "Time window in hours (default: 24)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_fundamentals",
        "description": "Retrieves fundamental data for specified symbols",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Stock tickers"
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific metrics to retrieve"
                }
            },
            "required": ["symbols"]
        }
    }
]


if __name__ == "__main__":
    # Test the tools
    print("Testing Financial Data Fetcher...")

    # Test price data
    price_result = get_price_data(
        symbols=["SPY", "AAPL"],
        timeframe="1Day",
        limit=5
    )
    print("\nPrice Data Result:")
    print(json.dumps(price_result, indent=2))

    # Test news fetch
    news_result = get_latest_news(
        symbols=["AAPL"],
        limit=3,
        hours_back=24
    )
    print("\nNews Result:")
    print(json.dumps(news_result, indent=2))

    # Test fundamentals
    fundamentals_result = get_fundamentals(symbols=["AAPL"])
    print("\nFundamentals Result:")
    print(json.dumps(fundamentals_result, indent=2))
```

---

### Skill 2: Portfolio Risk Assessment Implementation

```python
#!/usr/bin/env python3
"""
Portfolio Risk Assessment - Claude Skill Implementation
Monitors portfolio risk metrics and enforces compliance thresholds.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

# Import existing risk manager
import sys
sys.path.append(str(Path(__file__).parent.parent))
from src.core.risk_manager import RiskManager
from src.core.alpaca_trader import AlpacaTrader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize components
alpaca_trader = AlpacaTrader(paper=True)
risk_manager = RiskManager(
    max_daily_loss_pct=2.0,
    max_position_size_pct=10.0,
    max_drawdown_pct=10.0,
    max_consecutive_losses=3
)


def assess_portfolio_health(
    account_id: Optional[str] = None,
    include_positions: bool = True
) -> Dict[str, Any]:
    """
    Perform comprehensive portfolio health check.

    Args:
        account_id: Specific account (defaults to current)
        include_positions: Include detailed position analysis

    Returns:
        Portfolio health assessment
    """
    try:
        logger.info("Assessing portfolio health...")

        # Get account info
        account_info = alpaca_trader.get_account_info()
        account_value = account_info['portfolio_value']
        cash = account_info['cash']
        buying_power = account_info['buying_power']

        # Get positions
        positions = alpaca_trader.get_positions() if include_positions else []

        # Calculate daily P&L
        daily_pl = account_value - account_info.get('last_equity', account_value)
        daily_pl_pct = (daily_pl / account_value * 100) if account_value > 0 else 0

        # Check circuit breakers
        breaker_status = risk_manager.check_circuit_breakers({
            "account_value": account_value,
            "daily_pl": daily_pl
        })

        # Calculate risk metrics
        risk_metrics = risk_manager.get_risk_metrics()

        # Calculate portfolio concentration
        largest_position = None
        if positions:
            positions_sorted = sorted(positions, key=lambda x: x['market_value'], reverse=True)
            largest_position = {
                "symbol": positions_sorted[0]['symbol'],
                "value": positions_sorted[0]['market_value'],
                "pct_of_portfolio": (positions_sorted[0]['market_value'] / account_value * 100)
            }

        # Overall health score (0-100)
        health_score = 100
        if daily_pl_pct < -1.0:
            health_score -= 10
        if breaker_status["daily_loss"]["breached"]:
            health_score -= 30
        if breaker_status["drawdown"]["breached"]:
            health_score -= 30
        if largest_position and largest_position["pct_of_portfolio"] > 15:
            health_score -= 10

        # Determine status
        if health_score >= 80:
            status = "healthy"
        elif health_score >= 60:
            status = "warning"
        else:
            status = "critical"

        return {
            "status": status,
            "assessment": {
                "overall_score": max(0, health_score),
                "account_value": account_value,
                "cash": cash,
                "buying_power": buying_power,
                "diversification_score": 75  # Placeholder
            },
            "risk_metrics": {
                "daily_pl": daily_pl,
                "daily_pl_pct": round(daily_pl_pct, 2),
                "max_drawdown": risk_metrics["account_metrics"]["max_drawdown_reached"],
                "sharpe_ratio": 0.0  # Would calculate from historical data
            },
            "positions": {
                "count": len(positions),
                "largest_position": largest_position,
                "concentration_risk": "low" if not largest_position or largest_position["pct_of_portfolio"] < 15 else "high"
            },
            "circuit_breakers": breaker_status,
            "alerts": []
        }

    except Exception as e:
        logger.error(f"Error assessing portfolio health: {e}")
        return {
            "status": "error",
            "error": {
                "code": "HEALTH_CHECK_ERROR",
                "message": str(e)
            }
        }


def check_circuit_breakers(
    account_value: float,
    daily_pl: float
) -> Dict[str, Any]:
    """
    Evaluate all circuit breaker conditions.

    Args:
        account_value: Current account value
        daily_pl: Today's profit/loss

    Returns:
        Circuit breaker status
    """
    try:
        logger.info("Checking circuit breakers...")

        breaker_status = risk_manager.check_circuit_breakers({
            "account_value": account_value,
            "daily_pl": daily_pl
        })

        # Format as list of breakers
        breakers = [
            {
                "name": "daily_loss_limit",
                "triggered": breaker_status["daily_loss"]["breached"],
                "current_value": breaker_status["daily_loss"]["current_pct"],
                "threshold": breaker_status["daily_loss"]["limit_pct"],
                "severity": "critical"
            },
            {
                "name": "max_drawdown",
                "triggered": breaker_status["drawdown"]["breached"],
                "current_value": breaker_status["drawdown"]["current_pct"],
                "threshold": breaker_status["drawdown"]["limit_pct"],
                "severity": "critical"
            },
            {
                "name": "consecutive_losses",
                "triggered": breaker_status["consecutive_losses"]["breached"],
                "current_value": breaker_status["consecutive_losses"]["current"],
                "threshold": breaker_status["consecutive_losses"]["limit"],
                "severity": "warning"
            }
        ]

        return {
            "trading_allowed": breaker_status["trading_allowed"],
            "breakers": breakers,
            "recommendations": []
        }

    except Exception as e:
        logger.error(f"Error checking circuit breakers: {e}")
        return {
            "status": "error",
            "error": {
                "code": "BREAKER_CHECK_ERROR",
                "message": str(e)
            }
        }


def validate_trade(
    symbol: str,
    side: str,
    amount: float,
    account_value: float,
    sentiment_score: float = 0.5,
    amount_type: str = "dollars"
) -> Dict[str, Any]:
    """
    Validate a proposed trade against all risk parameters.

    Args:
        symbol: Trading symbol
        side: "buy" or "sell"
        amount: Dollar amount or share quantity
        account_value: Current account value
        sentiment_score: Sentiment score (-1 to 1)
        amount_type: "dollars" or "shares"

    Returns:
        Validation result
    """
    try:
        logger.info(f"Validating trade: {side} {symbol} ${amount}")

        # Use risk manager validation
        validation = risk_manager.validate_trade(
            symbol=symbol,
            amount=amount,
            sentiment_score=sentiment_score,
            account_value=account_value,
            trade_type=side
        )

        # Add additional checks
        account_info = alpaca_trader.get_account_info()

        validation_checks = {
            "position_size_limit": {
                "passed": validation["valid"],
                "position_pct": (amount / account_value * 100),
                "limit_pct": 10.0
            },
            "buying_power": {
                "passed": account_info["buying_power"] >= amount if side == "buy" else True,
                "required": amount,
                "available": account_info["buying_power"]
            },
            "circuit_breakers": {
                "passed": not risk_manager.metrics.circuit_breaker_triggered,
                "active_breakers": []
            }
        }

        return {
            "valid": validation["valid"],
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "validation_checks": validation_checks,
            "warnings": validation["warnings"],
            "approved_amount": amount if validation["valid"] else 0
        }

    except Exception as e:
        logger.error(f"Error validating trade: {e}")
        return {
            "status": "error",
            "error": {
                "code": "VALIDATION_ERROR",
                "message": str(e)
            }
        }


def record_trade_result(
    symbol: str,
    side: str,
    quantity: float,
    fill_price: float,
    profit_loss: float,
    timestamp: Optional[str] = None
) -> Dict[str, Any]:
    """
    Record the outcome of a completed trade for risk tracking.

    Args:
        symbol: Trading symbol
        side: "buy" or "sell"
        quantity: Shares traded
        fill_price: Execution price
        profit_loss: Realized P&L
        timestamp: ISO format timestamp

    Returns:
        Trade recording confirmation
    """
    try:
        logger.info(f"Recording trade result: {side} {quantity} {symbol} @ ${fill_price}, P&L: ${profit_loss}")

        # Record with risk manager
        risk_manager.record_trade_result(profit_loss)

        # Get updated metrics
        metrics = risk_manager.get_risk_metrics()

        return {
            "status": "recorded",
            "trade_id": f"trade_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "updated_metrics": {
                "total_trades": metrics["trade_statistics"]["total_trades"],
                "winning_trades": metrics["trade_statistics"]["winning_trades"],
                "losing_trades": metrics["trade_statistics"]["losing_trades"],
                "win_rate": metrics["trade_statistics"]["win_rate_pct"],
                "consecutive_losses": metrics["trade_statistics"]["consecutive_losses"],
                "daily_pl": metrics["daily_metrics"]["daily_pl"]
            }
        }

    except Exception as e:
        logger.error(f"Error recording trade result: {e}")
        return {
            "status": "error",
            "error": {
                "code": "RECORDING_ERROR",
                "message": str(e)
            }
        }


# Tool registration
TOOLS = [
    {
        "name": "assess_portfolio_health",
        "description": "Performs comprehensive portfolio health check",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "include_positions": {"type": "boolean"}
            },
            "required": []
        }
    },
    {
        "name": "check_circuit_breakers",
        "description": "Evaluates all circuit breaker conditions",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_value": {"type": "number"},
                "daily_pl": {"type": "number"}
            },
            "required": ["account_value", "daily_pl"]
        }
    },
    {
        "name": "validate_trade",
        "description": "Validates a proposed trade against all risk parameters",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "amount": {"type": "number"},
                "account_value": {"type": "number"},
                "sentiment_score": {"type": "number"},
                "amount_type": {"type": "string", "enum": ["dollars", "shares"]}
            },
            "required": ["symbol", "side", "amount", "account_value"]
        }
    },
    {
        "name": "record_trade_result",
        "description": "Records the outcome of a completed trade",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "side": {"type": "string"},
                "quantity": {"type": "number"},
                "fill_price": {"type": "number"},
                "profit_loss": {"type": "number"},
                "timestamp": {"type": "string"}
            },
            "required": ["symbol", "side", "quantity", "fill_price", "profit_loss"]
        }
    }
]


if __name__ == "__main__":
    # Test the tools
    print("Testing Portfolio Risk Assessment...")

    # Test health assessment
    health = assess_portfolio_health(include_positions=True)
    print("\nHealth Assessment:")
    print(json.dumps(health, indent=2))

    # Test circuit breaker check
    breakers = check_circuit_breakers(
        account_value=100000,
        daily_pl=-500
    )
    print("\nCircuit Breakers:")
    print(json.dumps(breakers, indent=2))

    # Test trade validation
    validation = validate_trade(
        symbol="AAPL",
        side="buy",
        amount=5000,
        account_value=100000,
        sentiment_score=0.7
    )
    print("\nTrade Validation:")
    print(json.dumps(validation, indent=2))
```

---

## Integration with Claude Agents SDK

### Directory Structure

```
.claude/
└── skills/
    ├── financial_data_fetcher/
    │   ├── SKILL.md
    │   ├── scripts/
    │   │   └── financial_data_fetcher.py
    │   └── references/
    │       └── data_sources.md
    │
    ├── portfolio_risk_assessment/
    │   ├── SKILL.md
    │   ├── scripts/
    │   │   └── risk_assessment.py
    │   └── references/
    │       └── risk_thresholds.md
    │
    ├── sentiment_analyzer/
    │   ├── SKILL.md
    │   ├── scripts/
    │   │   └── sentiment_analyzer.py
    │   └── references/
    │       └── sentiment_scoring.md
    │
    ├── position_sizer/
    │   ├── SKILL.md
    │   ├── scripts/
    │   │   └── position_sizer.py
    │   └── references/
    │       └── sizing_methods.md
    │
    ├── anomaly_detector/
    │   ├── SKILL.md
    │   ├── scripts/
    │   │   └── anomaly_detector.py
    │   └── references/
    │       └── anomaly_patterns.md
    │
    └── performance_monitor/
        ├── SKILL.md
        ├── scripts/
        │   └── performance_monitor.py
        └── references/
            └── metrics_guide.md
```

### Claude Agent Configuration

```python
#!/usr/bin/env python3
"""
Trading Agent with Claude Skills Integration
"""

import anthropic
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

# Import skill tools
from skills.financial_data_fetcher.scripts.financial_data_fetcher import TOOLS as data_tools
from skills.portfolio_risk_assessment.scripts.risk_assessment import TOOLS as risk_tools
# ... import other skills

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingAgent:
    """
    Claude-powered trading agent with custom skills.
    """

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"

        # Aggregate all skill tools
        self.tools = []
        self.tools.extend(data_tools)
        self.tools.extend(risk_tools)
        # ... extend with other skill tools

        # Tool function mapping
        self.tool_functions = {
            "get_price_data": get_price_data,
            "get_latest_news": get_latest_news,
            "assess_portfolio_health": assess_portfolio_health,
            # ... map all tool functions
        }

        logger.info(f"Trading Agent initialized with {len(self.tools)} tools")

    def execute_task(self, user_message: str) -> str:
        """
        Execute a trading task using Claude with tool calling.

        Args:
            user_message: User's request/question

        Returns:
            Claude's response after tool execution
        """
        messages = [{"role": "user", "content": user_message}]

        # Initial request to Claude
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            tools=self.tools,
            messages=messages
        )

        # Process tool calls iteratively
        while response.stop_reason == "tool_use":
            # Extract tool calls
            tool_results = []

            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_name = content_block.name
                    tool_input = content_block.input

                    logger.info(f"Executing tool: {tool_name}")
                    logger.debug(f"Tool input: {json.dumps(tool_input, indent=2)}")

                    # Execute the tool
                    tool_function = self.tool_functions.get(tool_name)
                    if tool_function:
                        try:
                            result = tool_function(**tool_input)
                            logger.debug(f"Tool result: {json.dumps(result, indent=2)}")
                        except Exception as e:
                            logger.error(f"Tool execution error: {e}")
                            result = {
                                "status": "error",
                                "error": {"message": str(e)}
                            }
                    else:
                        result = {
                            "status": "error",
                            "error": {"message": f"Unknown tool: {tool_name}"}
                        }

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": json.dumps(result)
                    })

            # Send tool results back to Claude
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                tools=self.tools,
                messages=messages
            )

        # Extract final text response
        final_response = ""
        for content_block in response.content:
            if hasattr(content_block, "text"):
                final_response += content_block.text

        return final_response

    def analyze_market(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Comprehensive market analysis using multiple skills.
        """
        prompt = f"""
        Perform a comprehensive market analysis for {', '.join(symbols)}.

        Your analysis should include:
        1. Current price data and trends
        2. Recent news sentiment
        3. Fundamental valuation metrics
        4. Risk assessment for potential trades
        5. Position sizing recommendations

        Use all available tools to gather data and provide a detailed analysis.
        """

        response = self.execute_task(prompt)
        return {"analysis": response, "symbols": symbols}


# Usage example
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    agent = TradingAgent(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Example: Analyze AAPL
    result = agent.analyze_market(["AAPL"])
    print("\n" + "="*80)
    print("MARKET ANALYSIS")
    print("="*80)
    print(result["analysis"])
```

---

## Testing and Validation

### Unit Testing Framework

```python
#!/usr/bin/env python3
"""
Unit tests for Claude Skills
"""

import unittest
import json
from datetime import datetime

# Import skills
from skills.financial_data_fetcher.scripts.financial_data_fetcher import (
    get_price_data,
    get_latest_news,
    get_fundamentals
)
from skills.portfolio_risk_assessment.scripts.risk_assessment import (
    assess_portfolio_health,
    check_circuit_breakers,
    validate_trade
)


class TestFinancialDataFetcher(unittest.TestCase):
    """Tests for Financial Data Fetcher skill."""

    def test_get_price_data_valid_input(self):
        """Test price data retrieval with valid inputs."""
        result = get_price_data(
            symbols=["SPY"],
            timeframe="1Day",
            limit=5
        )

        self.assertEqual(result["status"], "success")
        self.assertIn("SPY", result["data"])
        self.assertIsInstance(result["data"]["SPY"], list)
        self.assertGreater(len(result["data"]["SPY"]), 0)

    def test_get_price_data_invalid_timeframe(self):
        """Test error handling for invalid timeframe."""
        result = get_price_data(
            symbols=["SPY"],
            timeframe="InvalidTimeframe",
            limit=5
        )

        self.assertEqual(result["status"], "error")
        self.assertIn("error", result)

    def test_get_latest_news(self):
        """Test news retrieval."""
        result = get_latest_news(
            symbols=["AAPL"],
            limit=5,
            hours_back=24
        )

        self.assertEqual(result["status"], "success")
        self.assertIn("articles", result)
        self.assertIsInstance(result["articles"], list)

    def test_get_fundamentals(self):
        """Test fundamental data retrieval."""
        result = get_fundamentals(symbols=["AAPL"])

        self.assertEqual(result["status"], "success")
        self.assertIn("AAPL", result["data"])
        self.assertIn("market_cap", result["data"]["AAPL"])


class TestPortfolioRiskAssessment(unittest.TestCase):
    """Tests for Portfolio Risk Assessment skill."""

    def test_assess_portfolio_health(self):
        """Test portfolio health assessment."""
        result = assess_portfolio_health(include_positions=True)

        self.assertIn("status", result)
        self.assertIn("assessment", result)
        self.assertIn("risk_metrics", result)

    def test_check_circuit_breakers(self):
        """Test circuit breaker evaluation."""
        result = check_circuit_breakers(
            account_value=100000,
            daily_pl=-500
        )

        self.assertIn("trading_allowed", result)
        self.assertIn("breakers", result)
        self.assertIsInstance(result["breakers"], list)

    def test_validate_trade_valid(self):
        """Test trade validation with valid parameters."""
        result = validate_trade(
            symbol="AAPL",
            side="buy",
            amount=5000,
            account_value=100000,
            sentiment_score=0.7
        )

        self.assertIn("valid", result)
        self.assertIn("validation_checks", result)

    def test_validate_trade_excessive_size(self):
        """Test trade validation rejects excessive position size."""
        result = validate_trade(
            symbol="AAPL",
            side="buy",
            amount=15000,  # 15% of account
            account_value=100000,
            sentiment_score=0.7
        )

        self.assertFalse(result["valid"])


class TestIntegration(unittest.TestCase):
    """Integration tests combining multiple skills."""

    def test_complete_trade_workflow(self):
        """Test complete workflow: data fetch -> risk check -> trade validation."""

        # 1. Fetch market data
        price_data = get_price_data(
            symbols=["AAPL"],
            timeframe="1Day",
            limit=1
        )
        self.assertEqual(price_data["status"], "success")

        # 2. Check portfolio health
        health = assess_portfolio_health()
        self.assertIn("status", health)

        # 3. Validate potential trade
        if health["status"] == "healthy":
            validation = validate_trade(
                symbol="AAPL",
                side="buy",
                amount=5000,
                account_value=100000,
                sentiment_score=0.6
            )
            self.assertIn("valid", validation)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestFinancialDataFetcher))
    suite.addTests(loader.loadTestsFromTestCase(TestPortfolioRiskAssessment))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
```

### Integration Testing

```bash
#!/bin/bash
# integration_test.sh - Test all skills in realistic trading scenario

set -e

echo "================================"
echo "Claude Skills Integration Test"
echo "================================"

# Setup
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
source .env

echo ""
echo "1. Testing Financial Data Fetcher..."
python3 -c "
from skills.financial_data_fetcher.scripts.financial_data_fetcher import get_price_data
result = get_price_data(['SPY', 'QQQ'], '1Day', limit=5)
assert result['status'] == 'success', 'Data fetch failed'
print('✓ Financial Data Fetcher working')
"

echo ""
echo "2. Testing Portfolio Risk Assessment..."
python3 -c "
from skills.portfolio_risk_assessment.scripts.risk_assessment import assess_portfolio_health
result = assess_portfolio_health()
assert 'status' in result, 'Health check failed'
print('✓ Portfolio Risk Assessment working')
"

echo ""
echo "3. Testing Complete Trade Workflow..."
python3 << 'EOF'
from skills.financial_data_fetcher.scripts.financial_data_fetcher import get_price_data, get_latest_news
from skills.portfolio_risk_assessment.scripts.risk_assessment import validate_trade, assess_portfolio_health

# Simulate complete trading decision workflow
print("  a. Fetching market data...")
price_data = get_price_data(['AAPL'], '1Day', limit=1)
assert price_data['status'] == 'success'

print("  b. Checking news sentiment...")
news = get_latest_news(symbols=['AAPL'], limit=5)
assert news['status'] == 'success'

print("  c. Assessing portfolio health...")
health = assess_portfolio_health()
assert 'status' in health

print("  d. Validating trade...")
validation = validate_trade(
    symbol='AAPL',
    side='buy',
    amount=5000,
    account_value=100000,
    sentiment_score=0.7
)
assert 'valid' in validation

print('✓ Complete workflow successful')
EOF

echo ""
echo "================================"
echo "All tests passed!"
echo "================================"
```

---

## Security and Compliance

### Security Best Practices

1. **API Key Management**
   - Store keys in `.env` files (never commit to git)
   - Use environment variables for production
   - Rotate keys regularly
   - Use separate keys for paper/live trading

2. **Input Validation**
   - Validate all parameters before execution
   - Sanitize user inputs
   - Use schema validation (JSON Schema)
   - Reject malformed requests

3. **Rate Limiting**
   - Implement per-tool rate limits
   - Track API usage across all skills
   - Exponential backoff on failures
   - Circuit breakers for external APIs

4. **Audit Logging**
   - Log all tool executions
   - Include timestamps, user IDs, parameters
   - Separate audit logs from application logs
   - Immutable log storage

### Compliance Requirements

#### Audit Trail

```python
# Example audit log entry
{
    "timestamp": "2025-10-30T10:15:30.123Z",
    "tool": "execute_order",
    "user_id": "trader_123",
    "session_id": "session_abc",
    "params": {
        "symbol": "AAPL",
        "side": "buy",
        "amount": 5000
    },
    "result_status": "success",
    "order_id": "order_xyz",
    "execution_time_ms": 245,
    "ip_address": "192.168.1.100",
    "risk_checks": {
        "position_size": "passed",
        "circuit_breakers": "passed",
        "sentiment_validation": "passed"
    }
}
```

#### Regulatory Compliance

- **Pattern Day Trader (PDT)**: Enforce 25k minimum for day trading
- **Reg T Margin**: Validate margin requirements
- **Best Execution**: Monitor execution quality
- **Record Keeping**: Maintain 7-year audit trail
- **Risk Disclosure**: Document all risk parameters

---

## Deployment Guide

### Production Deployment

```yaml
# docker-compose.yml
version: '3.8'

services:
  trading-agent:
    build: .
    environment:
      - ALPACA_API_KEY=${ALPACA_API_KEY}
      - ALPACA_SECRET_KEY=${ALPACA_SECRET_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ENVIRONMENT=production
    volumes:
      - ./logs:/app/logs
      - ./audit_logs:/app/audit_logs
      - ./.claude:/app/.claude
    ports:
      - "8000:8000"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Monitoring

```python
# health_check.py
from fastapi import FastAPI
from typing import Dict

app = FastAPI()

@app.get("/health")
def health_check() -> Dict:
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "skills_loaded": len(TOOLS),
        "alpaca_connection": "connected",  # Check actual connection
        "claude_api": "connected"
    }

@app.get("/metrics")
def get_metrics() -> Dict:
    """Prometheus-compatible metrics endpoint."""
    return {
        "tool_executions_total": 1234,
        "tool_errors_total": 5,
        "avg_execution_time_ms": 125,
        "circuit_breakers_triggered": 0
    }
```

---

## Appendices

### A. Example Trading Workflow

```python
"""
Complete trading workflow using all skills.
"""

def execute_daily_trading_workflow():
    """
    Execute daily trading workflow with all skills.
    """

    # 1. Morning health check
    print("1. Assessing portfolio health...")
    health = assess_portfolio_health(include_positions=True)

    if health["status"] != "healthy":
        alert_team(f"Portfolio health degraded: {health}")
        return

    # 2. Fetch market data
    print("2. Fetching market data...")
    symbols = ["SPY", "QQQ", "VOO"]
    price_data = get_price_data(symbols, "1Day", limit=30)

    # 3. Analyze sentiment
    print("3. Analyzing market sentiment...")
    sentiment = get_composite_sentiment(symbols)

    # 4. Select best opportunity
    best_symbol = max(
        symbols,
        key=lambda s: sentiment["composite_sentiment"][s]["score"]
    )

    print(f"4. Selected {best_symbol} based on sentiment")

    # 5. Calculate position size
    print("5. Calculating position size...")
    position = calculate_position_size(
        symbol=best_symbol,
        account_value=health["assessment"]["account_value"],
        risk_per_trade_pct=1.0,
        method="volatility_adjusted"
    )

    # 6. Validate trade
    print("6. Validating trade...")
    validation = validate_trade(
        symbol=best_symbol,
        side="buy",
        amount=position["recommendations"]["primary_method"]["position_size_dollars"],
        account_value=health["assessment"]["account_value"],
        sentiment_score=sentiment["composite_sentiment"][best_symbol]["score"]
    )

    if not validation["valid"]:
        print(f"Trade validation failed: {validation['warnings']}")
        return

    # 7. Execute trade
    print("7. Executing trade...")
    order = alpaca_trader.execute_order(
        symbol=best_symbol,
        amount_usd=validation["approved_amount"],
        side="buy"
    )

    # 8. Monitor execution
    print("8. Monitoring execution quality...")
    execution_analysis = detect_execution_anomalies(
        order_id=order["id"],
        expected_price=order["notional"] / order["filled_qty"],
        actual_fill_price=order["filled_avg_price"],
        quantity=order["filled_qty"],
        order_type="market",
        timestamp=order["filled_at"]
    )

    if execution_analysis["analysis"]["slippage"]["severity"] == "high":
        alert_team(f"High slippage detected: {execution_analysis}")

    # 9. Record trade result (after position closes)
    # This would happen later when position is closed

    # 10. Update performance metrics
    print("10. Updating performance metrics...")
    metrics = calculate_performance_metrics()

    print("\n" + "="*80)
    print("DAILY TRADING WORKFLOW COMPLETE")
    print("="*80)
    print(f"Symbol: {best_symbol}")
    print(f"Amount: ${validation['approved_amount']:.2f}")
    print(f"Sentiment: {sentiment['composite_sentiment'][best_symbol]['score']:.2f}")
    print(f"Order ID: {order['id']}")
    print(f"Fill Price: ${order['filled_avg_price']:.2f}")
    print(f"Slippage: {execution_analysis['analysis']['slippage']['percentage']:.3f}%")
    print("="*80)
```

### B. API Reference

See individual SKILL.md files for complete API documentation.

### C. Troubleshooting Guide

**Common Issues:**

1. **API Connection Errors**
   - Verify API keys in `.env`
   - Check network connectivity
   - Confirm API rate limits not exceeded

2. **Tool Execution Failures**
   - Review audit logs for error details
   - Validate input parameters
   - Check tool function availability

3. **Performance Issues**
   - Monitor execution times
   - Optimize database queries
   - Cache frequently accessed data

**Support:**
- Review logs in `/logs` directory
- Check audit trail in `/audit_logs`
- Consult Claude documentation: https://docs.claude.com

---

## Conclusion

This comprehensive guide provides everything needed to implement Claude Skills for an AI trading system. Each skill is modular, well-documented, and production-ready with:

- Complete SKILL.md specifications
- Python implementation templates
- Integration patterns
- Testing frameworks
- Security and compliance measures
- Deployment guides

The skills work together to create a robust, intelligent trading system powered by Claude's advanced reasoning capabilities combined with domain-specific financial tools.

**Next Steps:**
1. Create `.claude/skills/` directory structure
2. Implement each skill following the templates
3. Run unit and integration tests
4. Deploy to staging environment
5. Monitor performance and iterate

---

**Document Version:** 1.0
**Last Updated:** 2025-10-30
**Maintained By:** Trading System Architecture Team
