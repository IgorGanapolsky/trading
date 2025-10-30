# YouTube Analysis Quick Start Guide

## Overview
Add YouTube video analysis to your trading system in 30 minutes.

## Installation (5 minutes)

```bash
# Run the automated setup
./setup_youtube_analysis.sh

# Or manually install
pip install youtube-transcript-api yt-dlp
```

## Basic Usage

### 1. Extract Video Metadata
```python
from src.core.youtube_analyzer import YouTubeAnalyzer

analyzer = YouTubeAnalyzer()
metadata = analyzer.get_metadata("https://www.youtube.com/watch?v=VIDEO_ID")

print(f"Title: {metadata.title}")
print(f"Channel: {metadata.channel}")
print(f"Views: {metadata.view_count:,}")
```

### 2. Get Transcript with Timestamps
```python
transcript = analyzer.get_transcript("https://www.youtube.com/watch?v=VIDEO_ID")

for entry in transcript[:5]:
    print(f"[{entry.start:.0f}s] {entry.text}")
```

### 3. Analyze for Trading Insights
```python
from src.core.multi_llm_analysis import MultiLLMAnalyzer
import asyncio

async def analyze():
    llm_analyzer = MultiLLMAnalyzer()

    analysis = await analyzer.analyze_video_for_trading(
        "https://www.youtube.com/watch?v=VIDEO_ID",
        llm_analyzer
    )

    print(f"Sentiment: {analysis['sentiment_score']:.2f}")
    print(f"Key Strategies: {analysis['key_strategies']}")
    print(f"Recommended Stocks: {analysis['recommended_stocks']}")
    print(f"Risk Factors: {analysis['risk_factors']}")

asyncio.run(analyze())
```

### 4. Generate Trading Signals
```python
from src.strategies.youtube_strategy import YouTubeStrategy
import os

async def get_signals():
    strategy = YouTubeStrategy(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        sentiment_threshold=0.6,
        confidence_threshold=0.7
    )

    videos = [
        "https://www.youtube.com/watch?v=VIDEO_ID_1",
        "https://www.youtube.com/watch?v=VIDEO_ID_2",
    ]

    results = await strategy.analyze_video_list(videos)

    for signal in results['aggregated_signals']:
        if signal['confidence'] >= 0.8:
            print(f"{signal['symbol']}: {signal['action']} "
                  f"(confidence: {signal['confidence']:.2f})")

asyncio.run(get_signals())
```

## MCP Server Setup (Optional - for Claude Desktop)

```bash
# Install MCP server for Claude Code
claude mcp add-json "youtube-transcript" '{"command":"uvx","args":["--from","git+https://github.com/jkawamoto/mcp-youtube-transcript","mcp-youtube-transcript"]}'

# Restart Claude Code/Desktop
```

Then in Claude:
- "Get the transcript from https://youtube.com/watch?v=VIDEO_ID"
- "Analyze this trading video for key insights: [URL]"

## Integration with Your Trading System

### Add to Daily Check-in
```python
# In daily_checkin.py

from src.strategies.youtube_strategy import YouTubeStrategy

async def check_youtube_signals():
    strategy = YouTubeStrategy(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY")
    )

    # Monitor specific videos
    videos = [
        # Add daily market analysis videos here
    ]

    results = await strategy.analyze_video_list(videos)

    return {
        'high_confidence_signals': [
            s for s in results['aggregated_signals']
            if s['confidence'] >= 0.8
        ]
    }
```

### Add to Trading Decision Engine
```python
# In your main trading loop

youtube_signals = await check_youtube_signals()

for signal in youtube_signals['high_confidence_signals']:
    if signal['action'] == 'BUY' and signal['confidence'] > 0.8:
        # Validate with your other strategies
        # Execute trade if consensus reached
        pass
```

## Configuration

Edit `data/youtube_monitor_config.json`:

```json
{
  "watched_videos": [
    "https://www.youtube.com/watch?v=EXAMPLE_1",
    "https://www.youtube.com/watch?v=EXAMPLE_2"
  ],
  "sentiment_threshold": 0.6,
  "confidence_threshold": 0.7,
  "keywords": ["stock", "trade", "buy", "sell", "market"]
}
```

## Key Features

### Extract from Videos:
- Title, description, channel, views, likes
- Full transcript with timestamps
- Key moments (mentions of buy/sell/risk)

### AI Analysis Provides:
- Sentiment score (-1.0 to 1.0)
- Trading insights and strategies
- Recommended stocks/tickers
- Actionable items
- Risk factors
- Confidence score

### Trading Integration:
- Generate buy/sell signals
- Aggregate signals from multiple videos
- Filter by confidence threshold
- Cross-validate with other strategies

## Best Practices

1. **High Confidence Only**: Only act on signals with confidence > 0.8
2. **Cross-Validation**: Never trade solely on YouTube analysis
3. **Rate Limiting**: Add delays between video requests
4. **Recent Content**: Prioritize recent videos (< 48 hours old)
5. **Reputable Sources**: Focus on established trading channels
6. **Timestamp Review**: Save key moments for manual verification

## Popular Trading Channels to Monitor

- Bloomberg Television
- CNBC Television
- Yahoo Finance
- Meet Kevin (Real Estate/Stocks)
- Graham Stephan (Personal Finance)
- Financial Education (Growth Stocks)

## Common Use Cases

### 1. Morning Market Analysis
```python
# Analyze overnight market commentary
morning_videos = ["URL1", "URL2"]
signals = await strategy.analyze_video_list(morning_videos)
```

### 2. Earnings Analysis
```python
# Find mentions of specific stock
transcript = analyzer.get_transcript(video_url)
keywords = ["AAPL", "earnings", "revenue"]
mentions = analyzer.extract_key_timestamps(transcript, keywords)
```

### 3. Strategy Discovery
```python
# Extract trading strategies from educational content
analysis = await analyzer.analyze_video_for_trading(video_url, llm_analyzer)
for strategy in analysis['key_strategies']:
    print(f"Strategy: {strategy}")
```

### 4. Risk Assessment
```python
# Identify risk factors mentioned
analysis = await analyzer.analyze_video_for_trading(video_url, llm_analyzer)
print(f"Risk Factors: {analysis['risk_factors']}")
```

## Troubleshooting

### "No transcript available"
- Video may not have captions enabled
- Try different language codes: ['en', 'en-US', 'en-GB']

### "Rate limit exceeded"
- Add delays: `time.sleep(2)` between requests
- Reduce batch size

### "Low confidence scores"
- Video content may not be trading-focused
- Try different videos or adjust threshold

## Next Steps

1. Read full implementation guide: `YOUTUBE_ANALYSIS_IMPLEMENTATION.md`
2. Copy code examples to your system
3. Test with sample videos
4. Add to daily trading routine
5. Monitor performance and adjust thresholds

## Performance Tracking

```python
# Track signal accuracy
results = {
    'video_id': video_id,
    'signals': signals,
    'actual_outcomes': [],  # Fill in after trades execute
    'accuracy': 0.0
}

# Save for analysis
with open('data/youtube_performance.json', 'a') as f:
    json.dump(results, f)
```

## Support

For issues or questions:
1. Check the main implementation guide
2. Review code examples in the guide
3. Test with known working video URLs
4. Verify API keys are set correctly

---

**Estimated Setup Time**: 30 minutes
**Implementation Time**: 2-4 hours for full integration
**Expected Value**: High-quality trading insights from professional analysts
