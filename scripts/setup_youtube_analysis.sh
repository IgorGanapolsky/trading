#!/bin/bash

# YouTube Analysis Setup Script for Trading System
# This script sets up the YouTube video analysis capability

set -e

echo "=========================================="
echo "YouTube Analysis Setup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running from correct directory
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Error: Please run this script from the trading system root directory${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Installing Python dependencies...${NC}"
pip install youtube-transcript-api==0.6.2 yt-dlp==2024.10.7

echo ""
echo -e "${YELLOW}Step 2: Updating requirements.txt...${NC}"
if ! grep -q "youtube-transcript-api" requirements.txt; then
    echo "youtube-transcript-api==0.6.2" >> requirements.txt
    echo -e "${GREEN}Added youtube-transcript-api to requirements.txt${NC}"
fi

if ! grep -q "yt-dlp" requirements.txt; then
    echo "yt-dlp==2024.10.7" >> requirements.txt
    echo -e "${GREEN}Added yt-dlp to requirements.txt${NC}"
fi

echo ""
echo -e "${YELLOW}Step 3: Creating directory structure...${NC}"
mkdir -p data/youtube_analysis
mkdir -p src/strategies

echo ""
echo -e "${YELLOW}Step 4: Creating YouTube monitor configuration...${NC}"
cat > data/youtube_monitor_config.json << 'EOF'
{
  "watched_channels": [
    "Bloomberg Television",
    "CNBC Television",
    "Yahoo Finance",
    "Meet Kevin",
    "Graham Stephan"
  ],
  "watched_videos": [
  ],
  "keywords": [
    "stock",
    "trade",
    "buy",
    "sell",
    "market",
    "analysis",
    "bullish",
    "bearish",
    "IPO",
    "earnings"
  ],
  "sentiment_threshold": 0.6,
  "confidence_threshold": 0.7,
  "check_interval_hours": 24
}
EOF

echo -e "${GREEN}Created data/youtube_monitor_config.json${NC}"

echo ""
echo -e "${YELLOW}Step 5: Testing installation...${NC}"
python3 << 'PYTHON_TEST'
import sys

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    print("✓ youtube-transcript-api installed successfully")
except ImportError as e:
    print(f"✗ Error importing youtube-transcript-api: {e}")
    sys.exit(1)

try:
    import yt_dlp
    print("✓ yt-dlp installed successfully")
except ImportError as e:
    print(f"✗ Error importing yt-dlp: {e}")
    sys.exit(1)

print("\nAll dependencies installed successfully!")
PYTHON_TEST

echo ""
echo -e "${GREEN}=========================================="
echo "Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Review the implementation guide:"
echo "   cat YOUTUBE_ANALYSIS_IMPLEMENTATION.md"
echo ""
echo "2. Copy code examples to your system:"
echo "   - src/core/youtube_analyzer.py"
echo "   - src/strategies/youtube_strategy.py"
echo "   - youtube_monitor.py"
echo ""
echo "3. (Optional) Setup MCP server for Claude Desktop:"
echo "   claude mcp add-json \"youtube-transcript\" '{\"command\":\"uvx\",\"args\":[\"--from\",\"git+https://github.com/jkawamoto/mcp-youtube-transcript\",\"mcp-youtube-transcript\"]}'"
echo ""
echo "4. Test with a sample video:"
echo "   python3 -c 'from src.core.youtube_analyzer import YouTubeAnalyzer; analyzer = YouTubeAnalyzer(); print(analyzer.get_metadata(\"https://www.youtube.com/watch?v=dQw4w9WgXcQ\"))'"
echo ""
echo "5. Add video URLs to monitor in:"
echo "   data/youtube_monitor_config.json"
echo ""
echo -e "${YELLOW}Happy trading!${NC}"
