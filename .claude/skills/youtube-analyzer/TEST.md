# YouTube Analyzer - Test Plan

## Test 1: Installation Verification

```bash
# 1. Check if dependencies are installed
python3 -c "import yt_dlp; import youtube_transcript_api" && echo "✓ Dependencies installed" || echo "✗ Missing dependencies"

# 2. Verify script syntax
python3 -m py_compile analyze_youtube.py && echo "✓ Script syntax valid"

# 3. Check help text
python3 analyze_youtube.py --help | grep -q "YouTube" && echo "✓ Help text working"
```

## Test 2: Basic Functionality (Mock Mode)

```bash
# Test with a known working video (example: popular trading video)
# Note: Replace VIDEO_ID with actual video ID

python3 analyze_youtube.py \
  --url "https://youtube.com/watch?v=dQw4w9WgXcQ" \
  --output /tmp/youtube_test/

# Expected: Creates markdown report with metadata and transcript
# Check: /tmp/youtube_test/youtube_*.md exists
```

## Test 3: AI Analysis (Optional)

```bash
# Requires OPENROUTER_API_KEY in .env

python3 analyze_youtube.py \
  --url "https://youtube.com/watch?v=VIDEO_ID" \
  --analyze \
  --output /tmp/youtube_test/

# Expected: Report includes AI analysis section with trading insights
# Check: Report contains "## AI Analysis" section
```

## Test 4: Error Handling

### Test 4.1: Invalid URL
```bash
python3 analyze_youtube.py --url "https://invalid.com/video"
# Expected: Error message about invalid video ID
```

### Test 4.2: Private Video
```bash
python3 analyze_youtube.py --url "https://youtube.com/watch?v=PRIVATE_VIDEO_ID"
# Expected: Error about video unavailable
```

### Test 4.3: No Transcript
```bash
python3 analyze_youtube.py --url "https://youtube.com/watch?v=NO_TRANSCRIPT_VIDEO"
# Expected: Error about no transcript available
```

## Test 5: Integration Test

```bash
# Full workflow test

# 1. Create output directory
mkdir -p docs/youtube_analysis/test/

# 2. Analyze a trading video
python3 analyze_youtube.py \
  --url "https://youtube.com/watch?v=TRADING_VIDEO_ID" \
  --analyze \
  --output docs/youtube_analysis/test/

# 3. Verify report structure
latest_report=$(ls -t docs/youtube_analysis/test/youtube_*.md | head -1)

# Check required sections
grep -q "## Video Metadata" "$latest_report" && echo "✓ Metadata section present"
grep -q "## AI Analysis" "$latest_report" && echo "✓ AI section present"
grep -q "## Full Transcript" "$latest_report" && echo "✓ Transcript section present"

# 4. Cleanup
rm -rf docs/youtube_analysis/test/
```

## Test 6: Performance Test

```bash
# Test batch processing speed

time python3 analyze_youtube.py \
  --url "https://youtube.com/watch?v=SHORT_VIDEO" \
  --output /tmp/youtube_test/

# Expected: < 30 seconds for typical video
# Check: Time is reasonable
```

## Test 7: Example Script Test

```bash
# Run example script
bash example.sh 2>&1 | tee /tmp/example_test.log

# Verify examples ran
grep -q "✓" /tmp/example_test.log && echo "✓ Examples completed"
```

## Test Checklist

Before releasing skill:

- [ ] All Python imports work
- [ ] Script help text displays correctly
- [ ] Basic analysis (no AI) completes successfully
- [ ] AI analysis (with OpenRouter) works
- [ ] Error handling works for invalid inputs
- [ ] Output files are properly formatted markdown
- [ ] Reports contain all required sections
- [ ] Example script runs without errors
- [ ] README.md is complete and accurate
- [ ] Installation instructions are clear

## Manual Testing Recommendations

1. **Test with Real Trading Video**
   - Find popular trading analysis video on YouTube
   - Run analyzer with and without AI
   - Review output for accuracy and completeness

2. **Verify Trading Insights**
   - Check if stock tickers are correctly extracted
   - Verify sentiment analysis makes sense
   - Confirm recommendations are actionable

3. **Integration with Trading System**
   - Feed transcript into Multi-LLM Analyzer
   - Compare YouTube sentiment with system sentiment
   - Test watchlist integration workflow

4. **Performance Validation**
   - Test with various video lengths (5min, 30min, 1hr)
   - Measure time and cost for AI analysis
   - Verify memory usage is reasonable

## Known Limitations

1. **Transcript Availability**: Not all videos have transcripts
2. **Language Support**: Currently English only (can be extended)
3. **AI Cost**: OpenRouter charges per analysis (~$0.01-0.05 per video)
4. **Rate Limits**: YouTube/OpenRouter may rate limit requests
5. **Long Videos**: Transcripts >10k chars are truncated for AI analysis

## Future Test Additions

- [ ] Unit tests for video ID extraction
- [ ] Unit tests for transcript formatting
- [ ] Integration tests with Multi-LLM Analyzer
- [ ] Performance benchmarks for different video lengths
- [ ] Automated accuracy testing (compare predictions vs reality)
- [ ] Stress testing (100+ videos in batch)
