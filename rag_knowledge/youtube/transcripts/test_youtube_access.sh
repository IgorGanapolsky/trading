#!/bin/bash
# Test if YouTube access is available
# Exit 0 if available, 1 if blocked

echo "Testing YouTube access..."
echo "========================"

# Test 1: Try yt-dlp with a known video
echo "Test 1: yt-dlp access check..."
if timeout 10 yt-dlp --get-title "https://youtube.com/watch?v=dQw4w9WgXcQ" >/dev/null 2>&1; then
    echo "✅ yt-dlp: YouTube access available"
    YT_DLP_OK=1
else
    echo "❌ yt-dlp: YouTube access blocked"
    YT_DLP_OK=0
fi

# Test 2: Try youtube-transcript-api
echo ""
echo "Test 2: youtube-transcript-api check..."
if timeout 10 python3 -c "from youtube_transcript_api import YouTubeTranscriptApi; YouTubeTranscriptApi.get_transcript('dQw4w9WgXcQ')" >/dev/null 2>&1; then
    echo "✅ youtube-transcript-api: Access available"
    TRANSCRIPT_API_OK=1
else
    echo "❌ youtube-transcript-api: Access blocked"
    TRANSCRIPT_API_OK=0
fi

# Test 3: Try curl to youtube.com
echo ""
echo "Test 3: Direct HTTP access check..."
if timeout 5 curl -s -o /dev/null -w "%{http_code}" "https://www.youtube.com" | grep -q "200"; then
    echo "✅ HTTP: YouTube accessible"
    HTTP_OK=1
else
    echo "❌ HTTP: YouTube blocked"
    HTTP_OK=0
fi

echo ""
echo "========================"
echo "Summary:"
echo "  yt-dlp: $([[ $YT_DLP_OK -eq 1 ]] && echo '✅ Working' || echo '❌ Blocked')"
echo "  youtube-transcript-api: $([[ $TRANSCRIPT_API_OK -eq 1 ]] && echo '✅ Working' || echo '❌ Blocked')"
echo "  HTTP: $([[ $HTTP_OK -eq 1 ]] && echo '✅ Working' || echo '❌ Blocked')"
echo ""

if [[ $YT_DLP_OK -eq 1 ]] || [[ $TRANSCRIPT_API_OK -eq 1 ]]; then
    echo "✅ YouTube access available - can ingest transcripts"
    exit 0
else
    echo "❌ YouTube access blocked - cannot ingest transcripts"
    echo "    Use curated knowledge in rag_knowledge/youtube/insights/options_education_sources.json"
    exit 1
fi
