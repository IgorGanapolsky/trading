# Unified Sentiment Synthesizer

## Overview

The Unified Sentiment Synthesizer (`src/utils/unified_sentiment.py`) aggregates sentiment from ALL available sources with appropriate weighting to provide a single, reliable sentiment signal for trading decisions.

## Architecture

### Source Weights

The system uses a weighted aggregation model where each source contributes based on reliability and signal quality:

| Source | Weight | Rationale |
|--------|--------|-----------|
| News | 40% | Most reliable - professional analysts, financial news outlets |
| Reddit | 35% | High volume retail sentiment, meme stock detection |
| YouTube | 25% | Expert analysis from financial content creators |

**Total**: 100%

When sources are unavailable, weights are automatically normalized across active sources.

### Integration Points

#### News Sentiment (40%)
- **Module**: `src/utils/news_sentiment.py`
- **Sources**: Yahoo Finance, Stocktwits, Alpha Vantage, Grok/Twitter
- **Updates**: Real-time via API calls
- **Cache**: 24 hours

#### Reddit Sentiment (35%)
- **Module**: `src/utils/reddit_sentiment.py`
- **Sources**: r/wallstreetbets, r/stocks, r/investing, r/options
- **Updates**: Daily pre-market (9:00 AM ET)
- **Cache**: 24 hours

#### YouTube Sentiment (25%)
- **Module**: `scripts/youtube_monitor.py`
- **Sources**: Financial YouTube channels (configurable)
- **Updates**: Daily at 8:00 AM ET
- **Cache**: 7 days (rolling window)

## API Reference

### Class: `UnifiedSentiment`

Main class for unified sentiment analysis.

#### Initialization

```python
from src.utils.unified_sentiment import UnifiedSentiment

analyzer = UnifiedSentiment(
    cache_dir="data/sentiment",
    enable_news=True,
    enable_reddit=True,
    enable_youtube=True
)
```

#### Methods

##### `get_ticker_sentiment(symbol: str, use_cache: bool = True) -> Dict`

Get aggregated sentiment for a single ticker.

**Returns**:
```python
{
    "symbol": "SPY",
    "overall_score": 0.45,      # -1.0 to 1.0
    "confidence": 0.75,         # 0.0 to 1.0
    "signal": "BULLISH",        # "BULLISH", "BEARISH", "NEUTRAL"
    "recommendation": "BUY_SIGNAL",  # "BUY_SIGNAL", "SELL_SIGNAL", "HOLD"
    "sources": {
        "news": {...},
        "reddit": {...},
        "youtube": {...}
    },
    "timestamp": "2025-11-29T10:30:00",
    "cache_hit": False
}
```

**Signal Thresholds**:
- `BULLISH`: score > 0.20
- `BEARISH`: score < -0.20
- `NEUTRAL`: -0.20 ≤ score ≤ 0.20

**Recommendation Thresholds** (more conservative):
- `BUY_SIGNAL`: score > 0.40 AND confidence ≥ 0.60
- `SELL_SIGNAL`: score < -0.40 AND confidence ≥ 0.60
- `HOLD`: All other cases

##### `get_batch_sentiment(symbols: List[str], use_cache: bool = True) -> Dict[str, Dict]`

Get sentiment for multiple tickers in batch.

```python
results = analyzer.get_batch_sentiment(['SPY', 'QQQ', 'NVDA'])

for symbol, data in results.items():
    print(f"{symbol}: {data['signal']} ({data['overall_score']:.2f})")
```

##### `print_sentiment_summary(symbol: str)`

Print formatted sentiment summary to console.

```python
analyzer.print_sentiment_summary('SPY')
```

Output:
```
================================================================================
UNIFIED SENTIMENT ANALYSIS: SPY
================================================================================
Overall Score: +0.45 (-1.0 to +1.0)
Confidence: 75.0%
Signal: BULLISH
Recommendation: BUY_SIGNAL
...
```

## Usage Examples

### Basic Usage

```python
from src.utils.unified_sentiment import UnifiedSentiment

# Initialize
analyzer = UnifiedSentiment()

# Get sentiment for a ticker
result = analyzer.get_ticker_sentiment('SPY')

print(f"Signal: {result['signal']}")
print(f"Score: {result['overall_score']:.2f}")
print(f"Recommendation: {result['recommendation']}")
```

### Integration with Trading Strategy

```python
from src.utils.unified_sentiment import UnifiedSentiment

class MyStrategy:
    def __init__(self):
        self.sentiment = UnifiedSentiment()

    def should_enter_position(self, symbol: str) -> bool:
        """Check if sentiment supports entering position"""
        result = self.sentiment.get_ticker_sentiment(symbol)

        # Only enter if BULLISH with BUY_SIGNAL
        if result['recommendation'] == 'BUY_SIGNAL':
            print(f"✅ {symbol}: Sentiment supports entry")
            print(f"   Score: {result['overall_score']:.2f}")
            print(f"   Confidence: {result['confidence']:.1%}")
            return True

        return False

    def get_position_boost(self, symbol: str, base_amount: float) -> float:
        """Boost position size based on sentiment strength"""
        result = self.sentiment.get_ticker_sentiment(symbol)

        # Apply 20% boost if strong bullish sentiment
        if result['overall_score'] > 0.60 and result['confidence'] > 0.70:
            return base_amount * 1.20

        return base_amount
```

### Batch Analysis

```python
from src.utils.unified_sentiment import UnifiedSentiment

analyzer = UnifiedSentiment()

# Analyze multiple tickers
watchlist = ['SPY', 'QQQ', 'NVDA', 'GOOGL', 'AMZN']
results = analyzer.get_batch_sentiment(watchlist)

# Filter for buy signals
buy_candidates = [
    (symbol, data)
    for symbol, data in results.items()
    if data['recommendation'] == 'BUY_SIGNAL'
]

print(f"Buy Candidates: {len(buy_candidates)}")
for symbol, data in buy_candidates:
    print(f"  {symbol}: {data['overall_score']:.2f} (confidence: {data['confidence']:.1%})")
```

### CLI Usage

```bash
# Analyze single ticker
python3 src/utils/unified_sentiment.py SPY

# Analyze multiple tickers
python3 src/utils/unified_sentiment.py SPY,QQQ,NVDA

# Disable specific sources
python3 src/utils/unified_sentiment.py SPY --disable-reddit --disable-youtube

# Force fresh data (bypass cache)
python3 src/utils/unified_sentiment.py SPY --no-cache
```

## Caching

### Cache Strategy

- **TTL**: 1 hour (3600 seconds)
- **Location**: `data/sentiment/unified_{SYMBOL}_{YYYYMMDD_HH}.json`
- **Key**: `unified_{symbol}_{date}_{hour}`
- **Invalidation**: Automatic after TTL expires

### Cache Benefits

1. **Performance**: Avoid redundant API calls
2. **Cost Reduction**: Minimize API usage (especially for paid services)
3. **Rate Limiting**: Stay within API limits
4. **Consistency**: Same data across multiple strategy evaluations

### Disabling Cache

```python
# Programmatic
result = analyzer.get_ticker_sentiment('SPY', use_cache=False)

# CLI
python3 src/utils/unified_sentiment.py SPY --no-cache
```

## Source-Specific Details

### News Sentiment

**Raw Data Fields**:
- `yahoo`: Yahoo Finance sentiment
- `stocktwits`: Stocktwits social sentiment
- `alphavantage`: Alpha Vantage AI sentiment
- `grok_twitter`: Grok/X.ai Twitter sentiment

**Score Range**: -100 to +100 (normalized to -1.0 to +1.0)

### Reddit Sentiment

**Raw Data Fields**:
- `mentions`: Number of mentions across subreddits
- `bullish_keywords`: Count of bullish keywords
- `bearish_keywords`: Count of bearish keywords
- `total_upvotes`: Total upvotes across all posts

**Score Calculation**: Weighted by mentions, upvotes, and engagement

### YouTube Sentiment

**Raw Data Fields**:
- `analyses_found`: Number of recent video analyses mentioning ticker
- `bullish_keywords`: Count of bullish keywords in transcripts
- `bearish_keywords`: Count of bearish keywords in transcripts

**Lookback Window**: 7 days

## Configuration

### Environment Variables

Required for full functionality:

```bash
# News Sources
ALPHA_VANTAGE_API_KEY=your_key_here
GROK_API_KEY=your_key_here

# Reddit
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT="TradingBot/1.0"
```

### Customizing Weights

To adjust source weights, modify `SOURCE_WEIGHTS` in `unified_sentiment.py`:

```python
SOURCE_WEIGHTS = {
    "news": 0.50,      # Increase news weight
    "reddit": 0.30,    # Decrease Reddit weight
    "youtube": 0.20,
}
```

**Note**: Weights must sum to 1.0, or use auto-normalization.

## Integration with Existing Systems

### Sentiment Loader

The unified sentiment synthesizer complements the existing `sentiment_loader.py`:

```python
from src.utils.sentiment_loader import load_latest_sentiment
from src.utils.unified_sentiment import UnifiedSentiment

# Option 1: Use sentiment loader (Reddit + News from cache)
sentiment_data = load_latest_sentiment()
score, confidence, regime = get_ticker_sentiment('SPY', sentiment_data)

# Option 2: Use unified sentiment (all sources, weighted)
analyzer = UnifiedSentiment()
result = analyzer.get_ticker_sentiment('SPY')
```

**When to use each**:
- **Sentiment Loader**: Fast, cache-only, good for batch operations
- **Unified Sentiment**: Real-time, multi-source, better for individual trades

### Sentiment Boost

The unified sentiment can replace or complement `sentiment_boost.py`:

```python
from src.utils.unified_sentiment import UnifiedSentiment

def calculate_sentiment_boost(symbol: str, base_amount: float) -> tuple:
    analyzer = UnifiedSentiment()
    result = analyzer.get_ticker_sentiment(symbol)

    # Apply boost if strong buy signal
    if result['recommendation'] == 'BUY_SIGNAL':
        boost_multiplier = 1.0 + (result['overall_score'] * 0.5)  # Up to 50% boost
        adjusted_amount = base_amount * boost_multiplier

        return adjusted_amount, {
            'boost_applied': True,
            'sentiment_score': result['overall_score'],
            'confidence': result['confidence'],
            'multiplier': boost_multiplier
        }

    return base_amount, {'boost_applied': False}
```

## Logging

The module uses Python's standard logging framework:

```python
import logging

# Enable debug logging
logging.getLogger('src.utils.unified_sentiment').setLevel(logging.DEBUG)

# Example output
# INFO: UnifiedSentiment initialized. Active sources: ['news', 'reddit', 'youtube']
# INFO: Fetching unified sentiment for SPY...
# DEBUG: news: score=0.35, confidence=0.80, weight=0.30
# DEBUG: reddit: score=0.45, confidence=0.70, weight=0.25
# INFO: SPY: score=0.42, confidence=0.75, signal=BULLISH, recommendation=BUY_SIGNAL, sources=news,reddit,youtube
```

## Error Handling

The synthesizer gracefully handles source failures:

```python
# If a source fails, it's marked as unavailable
result = analyzer.get_ticker_sentiment('SPY')

for source_name, source_data in result['sources'].items():
    if not source_data['available']:
        print(f"{source_name}: {source_data['error']}")
```

**Failure Modes**:
1. **API Rate Limit**: Source marked unavailable, weights normalized
2. **Missing Data**: Source returns neutral score (0.0)
3. **Network Error**: Source skipped, error logged
4. **Invalid Ticker**: All sources return neutral

## Performance

### Benchmarks

| Operation | Time | API Calls |
|-----------|------|-----------|
| Single ticker (cache hit) | ~10ms | 0 |
| Single ticker (cache miss) | ~2-5s | 3-5 |
| Batch 10 tickers (cache hit) | ~100ms | 0 |
| Batch 10 tickers (cache miss) | ~20-50s | 30-50 |

### Optimization Tips

1. **Use Cache**: Enable caching for repeated queries
2. **Batch Queries**: Use `get_batch_sentiment()` for multiple tickers
3. **Disable Unused Sources**: Disable sources you don't need
4. **Pre-warm Cache**: Run analysis during off-hours

## Future Enhancements

### Planned Features

1. **Advanced Weighting**
   - Dynamic weights based on source reliability
   - Time-decay for stale data
   - Adaptive weighting based on historical accuracy

4. **Machine Learning**
   - Train model to optimize source weights
   - Predict sentiment momentum
   - Anomaly detection for unusual sentiment shifts

5. **Real-Time Streaming**
   - WebSocket connections to sentiment sources
   - Live sentiment updates
   - Alert system for significant sentiment changes

## Troubleshooting

### No Sentiment Sources Available

**Problem**: All sources return "unavailable"

**Solutions**:
1. Check API credentials in `.env`
2. Verify sentiment data files exist in `data/sentiment/`
3. Run sentiment collectors:
   ```bash
   python3 src/utils/news_sentiment.py
   python3 src/utils/reddit_sentiment.py
   ```

### Low Confidence Scores

**Problem**: Confidence consistently < 0.50

**Solutions**:
1. Increase number of active sources
2. Check source data quality
3. Verify tickers are widely covered

### Cache Not Working

**Problem**: `cache_hit` always `False`

**Solutions**:
1. Check write permissions on `data/sentiment/`
2. Verify cache TTL settings
3. Check disk space

## Support

For issues or questions:
1. Check logs: `logs/unified_sentiment.log`
2. Review source module documentation
3. File issue in GitHub repo

---

**Last Updated**: 2025-11-29
**Version**: 1.0.0
**Maintainer**: Trading System CTO
