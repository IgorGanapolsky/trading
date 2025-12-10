# YouTube Analyzer - Installation Guide

## Quick Install

```bash
# Navigate to project root
cd /Users/igorganapolsky/workspace/git/apps/trading

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install yt-dlp youtube-transcript-api
```

## Verify Installation

```bash
# Test imports
python3 -c "import yt_dlp; import youtube_transcript_api; print('✓ Installation successful!')"

# Test script help
python3 .claude/skills/youtube_analyzer/analyze_youtube.py --help
```

## Optional: AI Analysis Support

AI analysis is **optional** and requires OpenRouter API access.

If you want AI-powered trading insights:

```bash
# Ensure these are in your .env file (already should be)
# OPENROUTER_API_KEY=your_key_here

# Test AI availability
python3 -c "import openai; from dotenv import load_dotenv; print('✓ AI support available')"
```

## Usage After Installation

```bash
# Basic analysis (no AI)
python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
  --url "https://youtube.com/watch?v=VIDEO_ID"

# With AI analysis
python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
  --url "https://youtube.com/watch?v=VIDEO_ID" \
  --analyze
```

## Troubleshooting

### Issue: "No module named 'yt_dlp'"

**Solution**: Ensure virtual environment is activated
```bash
source venv/bin/activate
pip install yt-dlp youtube-transcript-api
```

### Issue: "No module named 'openai'"

**Solution**: AI analysis is optional - either skip --analyze flag or install:
```bash
pip install openai python-dotenv
```

### Issue: "OPENROUTER_API_KEY not found"

**Solution**: Add to .env file
```bash
echo "OPENROUTER_API_KEY=your_key_here" >> .env
```

## Complete Installation Script

```bash
#!/bin/bash
# Complete installation in one go

cd /Users/igorganapolsky/workspace/git/apps/trading
source venv/bin/activate
pip install yt-dlp youtube-transcript-api

# Verify
python3 -c "import yt_dlp; import youtube_transcript_api; print('✓ YouTube Analyzer installed successfully!')"

echo "Ready to analyze videos!"
echo "Run: python3 .claude/skills/youtube_analyzer/analyze_youtube.py --url 'VIDEO_URL'"
```

## Updating Dependencies

```bash
# Update to latest versions
pip install --upgrade yt-dlp youtube-transcript-api

# Check versions
pip show yt-dlp youtube-transcript-api
```

## Next Steps

After installation:

1. Read [README.md](README.md) for usage examples
2. Try [example.sh](example.sh) for sample workflows
3. Review [skill.md](skill.md) for integration guide
4. Start analyzing trading videos!
