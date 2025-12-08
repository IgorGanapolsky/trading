# YouTube Analyzer - Complete Guide

## Overview

The YouTube Analyzer skill enables extraction and analysis of financial content from YouTube videos. It fetches video metadata, extracts transcripts, and optionally uses AI to analyze content for trading insights.

## Installation

### 1. Install Dependencies

```bash
# Navigate to project root
cd /Users/igorganapolsky/workspace/git/apps/trading

# Activate virtual environment
source venv/bin/activate

# Install required packages
pip install yt-dlp youtube-transcript-api
```

### 2. Verify Installation

```bash
python3 -c "import yt_dlp; import youtube_transcript_api; print('Installation successful!')"
```

## Usage

### Basic Analysis (No AI)

Extract video metadata and transcript only:

```bash
python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
  --url "https://youtube.com/watch?v=zIiTLWLEym4"
```

### AI-Powered Analysis

Include AI analysis for trading insights (requires OpenRouter API key in .env):

```bash
python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
  --url "https://youtube.com/watch?v=zIiTLWLEym4" \
  --analyze
```

### Custom Output Directory

Save results to specific location:

```bash
python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
  --url "https://youtube.com/watch?v=zIiTLWLEym4" \
  --output docs/youtube_analysis/
```

### Analyze Multiple Videos

```bash
# Create a list of videos
videos=(
  "https://youtube.com/watch?v=VIDEO_ID_1"
  "https://youtube.com/watch?v=VIDEO_ID_2"
  "https://youtube.com/watch?v=VIDEO_ID_3"
)

# Analyze each
for video in "${videos[@]}"; do
  python3 .claude/skills/youtube_analyzer/analyze_youtube.py --url "$video"
done
```

## Command-Line Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--url` | Yes* | Full YouTube URL |
| `--video-id` | Yes* | YouTube video ID (alternative to --url) |
| `--output` | No | Output directory (default: docs/youtube_analysis/) |
| `--analyze` | No | Enable AI analysis (requires OpenRouter API) |
| `--verbose` | No | Enable detailed logging |

*One of --url or --video-id is required

## Output Structure

### File Naming

Files are saved with format: `youtube_TITLE_TIMESTAMP.md`

Example: `youtube_best_stocks_2025_20251105_123456.md`

### Report Sections

1. **Video Metadata**
   - Title
   - Channel name
   - Upload date
   - Duration
   - View count
   - Video URL

2. **Executive Summary** (if --analyze used)
   - Key takeaways (3-5 bullet points)
   - Overall sentiment (Bullish/Bearish/Neutral)

3. **Stock Picks** (if --analyze used)
   - Ticker symbols mentioned
   - Bullish or Bearish sentiment
   - Confidence scores
   - Reasoning

4. **Trading Strategies** (if --analyze used)
   - Specific approaches discussed
   - Entry/exit criteria
   - Risk management tactics

5. **Risk Factors** (if --analyze used)
   - Warnings and cautions
   - Market conditions to watch
   - Potential pitfalls

6. **Actionable Recommendations** (if --analyze used)
   - What to do next
   - Specific actions to take
   - Timeline for action

7. **Key Timestamps** (if --analyze used)
   - Important sections with timestamps
   - Quick navigation to key insights

8. **Full Transcript**
   - Complete video transcript
   - Timestamped text
   - Searchable content

## Integration with Trading System

### 1. Manual Integration

After analyzing a video:

```bash
# Review the analysis
cat docs/youtube_analysis/youtube_VIDEO_TITLE_*.md

# If stock picks are compelling, add to watchlist
python3 scripts/add_to_watchlist.py --ticker AAPL --source "YouTube: Video Title"
```

### 2. Feed into Multi-LLM Analyzer

Use transcript as additional sentiment data:

```python
from src.core.multi_llm_analysis import MultiLLMAnalyzer

analyzer = MultiLLMAnalyzer()

# Load transcript from analysis
with open('docs/youtube_analysis/youtube_VIDEO_*.md', 'r') as f:
    transcript = f.read()

# Analyze sentiment
sentiment = analyzer.analyze_text_sentiment(transcript)
print(f"YouTube sentiment: {sentiment}")
```

### 3. Track Analysis Accuracy

Compare video predictions with actual performance:

```python
# After 30 days, compare stock picks from video with actual returns
python3 scripts/validate_youtube_picks.py \
  --analysis-file docs/youtube_analysis/youtube_VIDEO_*.md \
  --period 30
```

## Example Workflows

### Workflow 1: Daily Market Analysis

```bash
#!/bin/bash
# Daily routine: Analyze top market commentary videos

# Popular financial YouTube channels (video IDs change daily)
channels=(
  "CHANNEL_ID_1/videos"
  "CHANNEL_ID_2/videos"
)

# Fetch latest videos from each channel
# Analyze top 1-2 videos
# Generate daily market sentiment report

python3 .claude/skills/youtube_analyzer/daily_analysis.sh
```

### Workflow 2: Earnings Call Reviews

```bash
# When company announces earnings, find YouTube analysis
# Example: NVDA earnings

python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
  --url "https://youtube.com/watch?v=NVDA_EARNINGS_VIDEO" \
  --analyze \
  --output docs/youtube_analysis/earnings/
```

### Workflow 3: Strategy Deep Dive

```bash
# Analyze in-depth strategy videos for new trading ideas
python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
  --url "https://youtube.com/watch?v=STRATEGY_VIDEO" \
  --analyze

# Review detailed analysis
cat docs/youtube_analysis/youtube_STRATEGY_*.md

# If strategy is promising, backtest it
python3 scripts/backtest_strategy.py --config docs/youtube_analysis/youtube_STRATEGY_*.md
```

## Supported Video Types

### Best Results
- Trading strategy explanations
- Stock picking videos with specific tickers
- Market analysis with clear buy/sell recommendations
- Technical analysis walkthroughs
- Earnings call reviews

### Moderate Results
- General market commentary
- Economic news analysis
- Investment philosophy discussions
- Portfolio reviews

### Limited Results
- Pure entertainment content
- Live streams (transcripts may be incomplete)
- Non-English videos (requires language parameter)
- Videos without transcripts/captions

## Troubleshooting

### Issue: "No transcript available"

**Cause**: Video doesn't have captions/transcript

**Solution**:
```bash
# Check if transcript exists
youtube-dl --list-subs "VIDEO_URL"

# Try different transcript language
python3 analyze_youtube.py --url "VIDEO_URL" --language "en"
```

### Issue: "API quota exceeded"

**Cause**: Too many OpenRouter API calls (if --analyze used)

**Solution**:
- Reduce analysis frequency
- Cache results for repeated analysis
- Use free tier models (Gemini 2.0 Flash)

### Issue: "yt-dlp download failed"

**Cause**: Network issues or YouTube blocking

**Solution**:
```bash
# Update yt-dlp
pip install --upgrade yt-dlp

# Test directly
yt-dlp --get-title "VIDEO_URL"

# Use different user agent
export YT_DLP_USER_AGENT="Mozilla/5.0..."
```

### Issue: "AI analysis is empty"

**Cause**: Transcript too long or irrelevant content

**Solution**:
- Check transcript length
- Try shorter videos
- Adjust AI prompt for better extraction

## Advanced Features

### Custom AI Prompts

Edit analyze_youtube.py to customize AI analysis:

```python
# Custom prompt for specific analysis focus
ANALYSIS_PROMPT = """
Analyze this trading video transcript focusing on:
1. Short-term trades (< 1 week)
2. Options strategies mentioned
3. Technical levels and chart patterns

Extract specific entry/exit prices if mentioned.
"""
```

### Batch Analysis

Analyze multiple videos in parallel:

```bash
# Create video list
cat > videos.txt << EOF
https://youtube.com/watch?v=VIDEO_1
https://youtube.com/watch?v=VIDEO_2
https://youtube.com/watch?v=VIDEO_3
EOF

# Analyze all in parallel
cat videos.txt | xargs -P 3 -I {} python3 analyze_youtube.py --url {}
```

### Scheduled Analysis

Add to crontab for daily analysis:

```bash
# Analyze top market videos every morning at 8 AM
0 8 * * 1-5 cd /path/to/trading && python3 .claude/skills/youtube_analyzer/daily_market_analysis.sh
```

## Cost Considerations

### Without AI Analysis (--analyze flag not used)
- **Cost**: $0 (free)
- **Speed**: Fast (~10-30 seconds per video)
- **Output**: Metadata + transcript only

### With AI Analysis (--analyze flag used)
- **Cost**: ~$0.01-0.05 per video (depends on length and model)
- **Speed**: Slower (~30-60 seconds per video)
- **Output**: Full analysis with trading insights

### Recommendations
- Start without AI analysis to build transcript library
- Use AI analysis selectively on high-value videos
- Cache AI results to avoid repeated analysis
- Use cheaper models (Gemini 2.0 Flash) for initial pass

## Best Practices

1. **Verify Information**: Never blindly trust video recommendations
2. **Cross-Reference**: Compare with other sources and analysis
3. **Track Accuracy**: Log predictions and validate later
4. **Time-Sensitive**: Market conditions change - timestamp all analysis
5. **Context Matters**: Consider video upload date vs current market
6. **Creator Bias**: Be aware of potential conflicts of interest
7. **Diversify Sources**: Don't rely on single content creator

## Future Enhancements

- [ ] Automatic channel monitoring (fetch latest videos)
- [ ] Sentiment trend tracking across time
- [ ] Integration with Alpaca alerts
- [ ] AI-powered timestamp generation
- [ ] Multi-language support
- [ ] Playlist analysis
- [ ] Performance tracking dashboard
- [ ] Automated watchlist updates

## Support

For issues or questions:
1. Check logs in analyze_youtube.py output
2. Verify dependencies: `pip list | grep -E "yt-dlp|youtube-transcript"`
3. Test with known working video URL
4. Review error messages for specific guidance

## License

Part of the AI Trading System project. See main README for license details.

## Changelog

### Version 1.0.0 (2025-11-05)
- Initial release
- Basic transcript extraction
- AI-powered analysis support
- Markdown report generation
- Integration with trading system
