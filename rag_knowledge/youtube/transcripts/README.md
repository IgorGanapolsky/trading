# YouTube Transcript Storage

This directory stores YouTube video transcripts for options trading education content.

## Directory Structure

```
transcripts/
├── README.md                    # This file
├── test_youtube_access.sh       # Test if YouTube access available
├── ingest_options_videos.sh     # Bulk transcript ingestion
└── [transcript files]           # Generated transcript files
```

## Quick Start

### 1. Test YouTube Access

```bash
bash test_youtube_access.sh
```

**Expected Output (when blocked)**:
```
❌ YouTube access blocked - cannot ingest transcripts
   Use curated knowledge in rag_knowledge/youtube/insights/options_education_sources.json
```

**Expected Output (when available)**:
```
✅ YouTube access available - can ingest transcripts
```

### 2. Ingest Options Trading Videos

When YouTube access is available:

```bash
# Method 1: Use bulk ingestion script (after adding URLs)
bash ingest_options_videos.sh

# Method 2: Ingest individual videos
python3 ../../.claude/skills/youtube-analyzer/scripts/analyze_youtube.py \
    --url "https://youtube.com/watch?v=VIDEO_ID" \
    --output . \
    --analyze
```

## Current Status

- **Network Access**: ❌ BLOCKED (Proxy 403 Error)
- **Workaround**: Use curated knowledge in `../insights/options_education_sources.json`

## Curated Knowledge Already Available

The system has **expertly curated insights** from major options educators:

### Covered in `options_education_sources.json`:
- ✅ **tastytrade** - IV Rank strategies, 50% profit targets, 21 DTE closes
- ✅ **Option Alpha** - Probability trading, portfolio allocation
- ✅ **InTheMoney** - Wheel strategy, covered calls, cash-secured puts
- ✅ **Sky View Trading** - Iron condors, credit spreads, position sizing
- ✅ **ProjectFinance** - Options Greeks, theta decay, backtesting
- ✅ **Adam Khoo** - Technical analysis with options

### Key Insights Available:
- Wheel strategy mechanics and best practices
- Iron condor setup and adjustments
- Covered call management at 50% profit
- Credit spread position sizing
- Greeks explanation (theta, gamma, vega)
- IV Rank and volatility strategies
- Risk management rules

## Priority Videos to Ingest (When Network Available)

### TastyTrade
- "Covered Call Setup and Management"
- "Managing Winners at 50% of Max Profit"
- "Understanding IV Rank and IV Percentile"

### Options Alpha
- "Iron Condor Strategy 101"
- "Iron Condor Adjustments"
- "Probability Trading Explained"

### InTheMoney
- "The Wheel Strategy Explained"
- "Selling Cash-Secured Puts"
- "Covered Calls for Income"

### ProjectFinance
- "Options Greeks Explained"
- "Theta Decay Visualization"
- "Backtesting Options Strategies"

### Sky View Trading
- "Credit Spreads for Monthly Income"
- "Iron Condor Risk Management"
- "Position Sizing Rules"

## Workflow When Network Becomes Available

### Step 1: Verify Access
```bash
cd /home/user/trading/rag_knowledge/youtube/transcripts
bash test_youtube_access.sh
```

### Step 2: Find Specific Video URLs
Use web search or direct browsing to find YouTube URLs for target videos.

### Step 3: Update Ingestion Script
Edit `ingest_options_videos.sh` and add URLs:
```bash
VIDEOS["inthemoney_wheel"]="https://youtube.com/watch?v=VIDEO_ID_1"
VIDEOS["tastytrade_cc"]="https://youtube.com/watch?v=VIDEO_ID_2"
VIDEOS["optionalpha_ic"]="https://youtube.com/watch?v=VIDEO_ID_3"
```

### Step 4: Run Ingestion
```bash
bash ingest_options_videos.sh
```

### Step 5: Verify Results
```bash
# Check transcripts
ls -lh *.txt

# Check insights
ls -lh ../insights/*.json

# Check processed videos log
cat /home/user/trading/data/youtube_cache/processed_videos.json
```

## Output Format

### Transcript Files
- Format: `VIDEO_ID_transcript.txt`
- Content: Full video transcript with timestamps
- Location: This directory

### Insight Files
- Format: `VIDEO_ID.json`
- Content: Structured insights, trading signals, key takeaways
- Location: `../insights/`

### Processed Videos Log
- Format: `processed_videos.json`
- Content: Metadata and processing status
- Location: `/home/user/trading/data/youtube_cache/`

## MCP vs YouTube Analyzer

### YouTube Transcript MCP
- **Config**: `.claude/mcp_config.json`
- **Package**: `@sinco-lab/mcp-youtube-transcript`
- **Usage**: MCP-aware tools (when available)
- **Status**: Configured, network blocked

### YouTube Analyzer Skill (Recommended)
- **Location**: `.claude/skills/youtube-analyzer/`
- **Script**: `scripts/analyze_youtube.py`
- **Advantages**:
  - Direct command-line usage
  - AI-powered analysis with OpenRouter
  - Structured output (markdown reports)
  - RAG integration built-in
- **Status**: Fully functional when network available

## Troubleshooting

### Error: "Proxy 403 Forbidden"
**Cause**: Network blocks YouTube access
**Solution**: Use curated knowledge in `options_education_sources.json`

### Error: "No transcript available"
**Cause**: Video doesn't have captions
**Solution**: Find alternative videos with captions

### Error: "ModuleNotFoundError: yt_dlp"
**Cause**: Dependencies not installed
**Solution**: `pip install yt-dlp youtube-transcript-api`

## Related Documentation

- YouTube Analyzer Skill: `.claude/skills/youtube-analyzer/SKILL.md`
- MCP Setup: `.claude/MCP_SETUP_INSTRUCTIONS.md`
- RAG Storage: `src/evaluation/rag_storage.py`
- System State: `data/youtube_cache/processed_videos.json`

## Contact

For issues or questions about YouTube transcript ingestion, check:
1. Test report: `TEST_REPORT_youtube_transcript_mcp.md`
2. YouTube Analyzer docs: `.claude/skills/youtube-analyzer/README.md`
3. Network access logs
