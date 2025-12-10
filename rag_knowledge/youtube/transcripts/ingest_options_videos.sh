#!/bin/bash
# Ingest options trading video transcripts
# Run when network access is available

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="/home/user/trading"
ANALYZER_SCRIPT="$PROJECT_ROOT/.claude/skills/youtube-analyzer/scripts/analyze_youtube.py"
OUTPUT_DIR="$PROJECT_ROOT/rag_knowledge/youtube/transcripts"

echo "Options Trading YouTube Transcript Ingestion"
echo "============================================="
echo ""

# Check if YouTube access is available
if ! bash "$SCRIPT_DIR/test_youtube_access.sh" >/dev/null 2>&1; then
    echo "❌ Error: YouTube access is blocked"
    echo "Cannot ingest transcripts. Exiting."
    exit 1
fi

echo "✅ YouTube access available"
echo ""

# Target video URLs for options trading education
# Populate these with actual URLs when found
declare -A VIDEOS=(
    # TastyTrade covered calls
    # ["tastytrade_covered_calls"]="YOUTUBE_URL_HERE"

    # Options Alpha iron condors
    # ["options_alpha_iron_condor"]="YOUTUBE_URL_HERE"

    # InTheMoney wheel strategy
    # ["inthemoney_wheel_strategy"]="YOUTUBE_URL_HERE"

    # ProjectFinance covered calls
    # ["projectfinance_covered_calls"]="YOUTUBE_URL_HERE"

    # Sky View Trading credit spreads
    # ["skyview_credit_spreads"]="YOUTUBE_URL_HERE"
)

# Example URLs (uncomment and replace with real URLs)
# VIDEOS["inthemoney_wheel"]="https://youtube.com/watch?v=VIDEO_ID_1"
# VIDEOS["tastytrade_cc"]="https://youtube.com/watch?v=VIDEO_ID_2"
# VIDEOS["optionalpha_ic"]="https://youtube.com/watch?v=VIDEO_ID_3"

if [ ${#VIDEOS[@]} -eq 0 ]; then
    echo "⚠️  Warning: No video URLs configured"
    echo ""
    echo "To add videos, edit this script and add URLs to the VIDEOS array:"
    echo "  VIDEOS[\"description\"]=\"https://youtube.com/watch?v=VIDEO_ID\""
    echo ""
    echo "Recommended videos to add:"
    echo "  - TastyTrade: Covered Call Setup and Management"
    echo "  - Options Alpha: Iron Condor Strategy 101"
    echo "  - InTheMoney: The Wheel Strategy Explained"
    echo "  - ProjectFinance: Options Greeks Explained"
    echo "  - Sky View Trading: Credit Spreads for Income"
    echo ""
    exit 0
fi

echo "Videos to ingest: ${#VIDEOS[@]}"
echo ""

SUCCESS=0
FAILED=0

for name in "${!VIDEOS[@]}"; do
    url="${VIDEOS[$name]}"
    echo "Processing: $name"
    echo "  URL: $url"

    if python3 "$ANALYZER_SCRIPT" \
        --url "$url" \
        --output "$OUTPUT_DIR" \
        --analyze \
        --verbose; then
        echo "  ✅ Success"
        ((SUCCESS++))
    else
        echo "  ❌ Failed"
        ((FAILED++))
    fi
    echo ""
done

echo "============================================="
echo "Summary:"
echo "  Success: $SUCCESS"
echo "  Failed: $FAILED"
echo "  Output: $OUTPUT_DIR"
echo ""

if [ $SUCCESS -gt 0 ]; then
    echo "✅ Transcript ingestion complete"
    echo ""
    echo "Next steps:"
    echo "  1. Review transcripts in: $OUTPUT_DIR"
    echo "  2. Check insights in: $PROJECT_ROOT/rag_knowledge/youtube/insights/"
    echo "  3. Verify processed_videos.json updated"
else
    echo "❌ No transcripts successfully ingested"
    exit 1
fi
