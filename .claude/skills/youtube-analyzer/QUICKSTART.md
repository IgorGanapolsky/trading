# YouTube Analyzer - Quick Start Guide

## 30-Second Setup

```bash
cd /Users/igorganapolsky/workspace/git/apps/trading
source venv/bin/activate
pip install yt-dlp youtube-transcript-api
```

## 60-Second First Analysis

```bash
# Replace VIDEO_ID with actual YouTube video ID
python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
  --url "https://youtube.com/watch?v=VIDEO_ID"

# View result
cat docs/youtube_analysis/youtube_*.md | tail -50
```

## Common Commands

```bash
# Basic analysis (free)
python3 .claude/skills/youtube_analyzer/analyze_youtube.py --url "URL"

# With AI insights (costs ~$0.01-0.05)
python3 .claude/skills/youtube_analyzer/analyze_youtube.py --url "URL" --analyze

# Analyze multiple videos
for url in "URL1" "URL2" "URL3"; do
  python3 .claude/skills/youtube_analyzer/analyze_youtube.py --url "$url"
done
```

## What You Get

**Without AI** (free):
- Video metadata (title, channel, views, date)
- Complete timestamped transcript
- Searchable text for manual analysis

**With AI** (~$0.01-0.05 per video):
- All of the above, plus:
- Stock picks with tickers
- Trading strategies mentioned
- Risk factors identified
- Actionable recommendations
- Key timestamps highlighted

## Output Location

Reports saved to: `docs/youtube_analysis/youtube_TITLE_TIMESTAMP.md`

## Troubleshooting

**Error: "No module named 'yt_dlp'"**
```bash
pip install yt-dlp youtube-transcript-api
```

**Error: "No transcript available"**
- Video doesn't have captions
- Try a different video

**Error: "OPENROUTER_API_KEY not found"**
- Only needed for --analyze flag
- Skip AI analysis or add key to .env

## Next Steps

1. ✓ Analyze your first video
2. 📖 Read [README.md](README.md) for detailed guide
3. 🎯 Try [example.sh](example.sh) for sample workflows
4. 🔧 Integrate with trading system

## Support

- Full documentation: [README.md](README.md)
- Installation help: [INSTALL.md](INSTALL.md)
- Testing guide: [TEST.md](TEST.md)
- Integration: [skill.md](skill.md)

---

**Pro Tip**: Start without --analyze to build a transcript library, then use AI selectively on high-value videos to control costs.
