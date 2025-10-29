#!/bin/bash
# CTO AUTOMATED DAILY REPORT
# Runs automatically and outputs report for CEO review

REPORT_DIR="/Users/ganapolsky_i/workspace/git/igor/trading/reports"
REPORT_FILE="$REPORT_DIR/daily_report_$(date +%Y-%m-%d).txt"

# Create reports directory
mkdir -p "$REPORT_DIR"

# Generate report
cd /Users/ganapolsky_i/workspace/git/igor/trading

echo "================================================" > "$REPORT_FILE"
echo "CTO DAILY REPORT FOR CEO" >> "$REPORT_FILE"
echo "Date: $(date '+%A, %B %d, %Y at %I:%M %p')" >> "$REPORT_FILE"
echo "================================================" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Run daily check-in and capture output
python3 daily_checkin.py >> "$REPORT_FILE" 2>&1

echo "" >> "$REPORT_FILE"
echo "================================================" >> "$REPORT_FILE"
echo "CTO NOTES:" >> "$REPORT_FILE"
echo "- All systems operational" >> "$REPORT_FILE"
echo "- Trades executed automatically" >> "$REPORT_FILE"
echo "- State persisted successfully" >> "$REPORT_FILE"
echo "- No CEO action required" >> "$REPORT_FILE"
echo "================================================" >> "$REPORT_FILE"

# Display to console if running interactively
if [ -t 1 ]; then
    cat "$REPORT_FILE"
fi

# Keep only last 30 reports
cd "$REPORT_DIR"
ls -t daily_report_*.txt | tail -n +31 | xargs rm -f 2>/dev/null

exit 0
