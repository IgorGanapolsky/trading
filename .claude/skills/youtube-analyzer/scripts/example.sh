#!/bin/bash
#
# YouTube Analyzer - Example Usage
#
# This script demonstrates how to use the YouTube analyzer skill
# to extract and analyze trading content from YouTube videos.

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}YouTube Analyzer - Example Usage${NC}\n"

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Example 1: Basic analysis (no AI)
echo -e "\n${GREEN}Example 1: Basic transcript extraction${NC}"
echo "Extracting transcript without AI analysis..."

python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
  --url "https://youtube.com/watch?v=zIiTLWLEym4" \
  --output docs/youtube_analysis/

echo -e "${GREEN}✓ Basic analysis complete${NC}"

# Example 2: AI-powered analysis
echo -e "\n${GREEN}Example 2: AI-powered trading analysis${NC}"
echo "Analyzing with AI for trading insights..."

python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
  --url "https://youtube.com/watch?v=zIiTLWLEym4" \
  --analyze \
  --output docs/youtube_analysis/

echo -e "${GREEN}✓ AI analysis complete${NC}"

# Example 3: Using video ID directly
echo -e "\n${GREEN}Example 3: Using video ID${NC}"
echo "Analyzing by video ID..."

python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
  --video-id "zIiTLWLEym4" \
  --output docs/youtube_analysis/

echo -e "${GREEN}✓ Video ID analysis complete${NC}"

# Example 4: Batch analysis of multiple videos
echo -e "\n${GREEN}Example 4: Batch analysis${NC}"
echo "Analyzing multiple videos..."

# Example video IDs (replace with actual trading video IDs)
videos=(
  "https://youtube.com/watch?v=VIDEO_ID_1"
  "https://youtube.com/watch?v=VIDEO_ID_2"
  "https://youtube.com/watch?v=VIDEO_ID_3"
)

for video in "${videos[@]}"; do
  echo "Analyzing: $video"
  python3 .claude/skills/youtube_analyzer/analyze_youtube.py \
    --url "$video" \
    --output docs/youtube_analysis/ || echo "Failed to analyze: $video"
done

echo -e "${GREEN}✓ Batch analysis complete${NC}"

# Show results
echo -e "\n${BLUE}Analysis Results:${NC}"
ls -lh docs/youtube_analysis/youtube_*.md | tail -5

echo -e "\n${YELLOW}View latest analysis:${NC}"
echo "cat docs/youtube_analysis/\$(ls -t docs/youtube_analysis/youtube_*.md | head -1)"

echo -e "\n${GREEN}All examples completed!${NC}"
echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Review generated reports in docs/youtube_analysis/"
echo "2. Extract stock picks and add to watchlist"
echo "3. Compare AI predictions with market performance"
echo "4. Integrate insights into trading strategy"

echo -e "\n${BLUE}Tips:${NC}"
echo "- Use --analyze for AI-powered trading insights (costs ~\$0.01-0.05 per video)"
echo "- Without --analyze flag, only extracts metadata and transcript (free)"
echo "- Reports saved in markdown format for easy reading"
echo "- Transcripts can be searched for specific tickers or strategies"
