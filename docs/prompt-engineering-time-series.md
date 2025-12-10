# Prompt Engineering for Time Series Analysis

**Source**: [MachineLearningMastery](https://machinelearningmastery.com/prompt-engineering-for-time-series-analysis/)
**Added**: 2025-12-09
**Relevance**: Direct application to our Multi-LLM trading analysis

## Overview

LLMs can be leveraged for time series analysis when prompts are properly engineered. The key is translating prompt engineering skills to the specific temporal analysis scenario.

## Seven Key Strategies

### 1. Provide Temporal Context

Tell the LLM about the temporal structure:
- Upward/downward trends
- Seasonality patterns
- Known cycles (market hours, earnings, holidays)
- Current market regime

**Example for Trading**:
```
You are analyzing intraday price data for SPY.
Current context:
- Market session: Regular hours (9:30 AM - 4:00 PM ET)
- Day type: Tuesday (historically lower volatility)
- Recent trend: Upward momentum over past 3 days
- VIX level: 15.2 (low volatility regime)
```

### 2. Feature Extraction Before Forecasting

Don't ask for predictions from raw numbers. Extract features first:
- Latent patterns
- Anomalies
- Correlations
- Support/resistance levels

**Two-Step Approach**:
```
Step 1: "Analyze this price data and identify:
- Current trend direction and strength
- Key support/resistance levels
- Any anomalous price movements
- Volume confirmation signals"

Step 2: "Based on the patterns you identified,
what is the likely price direction in the next hour?"
```

### 3. Use Structured Data Formats

Raw time series are poorly suited for LLM input. Use:
- JSON schemas
- Compact tables
- Labeled data points

**Structured Input Example**:
```json
{
  "symbol": "SPY",
  "timeframe": "5min",
  "data": [
    {"time": "09:35", "close": 450.25, "volume": 125000, "rsi": 55},
    {"time": "09:40", "close": 450.50, "volume": 98000, "rsi": 58}
  ],
  "indicators": {
    "macd": {"value": 0.25, "signal": 0.18, "histogram": 0.07},
    "trend": "bullish"
  }
}
```

### 4. Specify Analysis Type

Be explicit about what kind of analysis you need:
- Trend detection
- Anomaly identification
- Forecast (short/medium/long term)
- Pattern recognition
- Regime classification

### 5. Include Domain Knowledge

Embed relevant domain expertise in prompts:
- Market microstructure (spreads, liquidity)
- Sector correlations
- Typical daily patterns (opening volatility, lunch lull)
- Event awareness (FOMC, earnings)

### 6. Request Confidence Levels

Ask the LLM to quantify uncertainty:
```
"Provide your analysis with a confidence level (low/medium/high)
and explain what additional data would increase your confidence."
```

### 7. Iterative Refinement

Use multi-turn conversations:
1. Initial analysis
2. Follow-up questions on specific patterns
3. Final recommendation synthesis

## Application to Our LLM Council

### Current Implementation
Our `multi_llm_analyzer.py` sends market data to multiple LLMs.

### Recommended Enhancements

1. **Temporal Context Header**:
   Add market context to every query (session type, volatility regime, trend state)

2. **Two-Pass Analysis**:
   - Pass 1: Feature extraction (patterns, anomalies)
   - Pass 2: Trading decision based on extracted features

3. **Structured Price Schema**:
   Define JSON schema for all price data with labeled indicators

4. **Confidence Thresholds**:
   Only act on recommendations with high confidence consensus

## Research Backing

- **Time-LLM (ICLR 2024)**: Reprogramming framework for LLMs in time series, cited 1000+ times
- LLMs excel with clear patterns/trends but struggle with aperiodic data
- External knowledge in prompts improves forecasting accuracy
- Paraphrasing positively affects LLM time series performance

## Implementation Priority

| Enhancement | Effort | Impact | Priority |
|-------------|--------|--------|----------|
| Temporal context header | Low | High | P1 |
| Structured JSON schema | Low | High | P1 |
| Two-pass analysis | Medium | High | P2 |
| Confidence thresholds | Low | Medium | P2 |

## References

- [MachineLearningMastery - Prompt Engineering for Time Series](https://machinelearningmastery.com/prompt-engineering-for-time-series-analysis/)
- [Towards Data Science - LLM-Powered Time Series](https://towardsdatascience.com/llm-powered-time-series-analysis/)
- [Time-LLM GitHub (ICLR 2024)](https://github.com/KimMeen/Time-LLM)
- [arXiv - Time Series Forecasting with LLMs](https://arxiv.org/html/2402.10835v1)
