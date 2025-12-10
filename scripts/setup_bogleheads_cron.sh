#!/bin/bash
# Setup autonomous Bogleheads forum collection cron job
# Runs daily at 2:00 AM ET (off-peak hours to avoid forum overload)

echo "🔧 Setting up autonomous Bogleheads forum collection..."

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create cron job entry
# Runs every day at 2:00 AM ET (7:00 UTC)
# Note: Adjust UTC time based on EST/EDT (EST: UTC-5, EDT: UTC-4)
# EST: 2:00 AM ET = 7:00 UTC
# EDT: 2:00 AM ET = 6:00 UTC
# Using 6:00 UTC to cover EDT (will run at 2:00 AM EDT or 1:00 AM EST)
CRON_JOB="0 6,7 * * * bash $SCRIPT_DIR/cron_bogleheads_ingest.sh"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "cron_bogleheads_ingest.sh"; then
    echo "⚠️  Bogleheads collection cron job already exists!"
    echo "Current crontab:"
    crontab -l | grep cron_bogleheads_ingest
else
    # Add to crontab
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✅ Bogleheads collection cron job added!"
    echo "📅 Will run daily at 2:00 AM ET (off-peak hours)"
fi

echo ""
echo "📋 Current Bogleheads collection cron job:"
crontab -l | grep cron_bogleheads_ingest || echo "No job found"

echo ""
echo "🎯 Bogleheads forum collection is now FULLY AUTONOMOUS!"
echo ""
echo "To test manually:"
echo "  bash scripts/cron_bogleheads_ingest.sh"
echo ""
echo "To run ingestion directly:"
echo "  python3 scripts/bogleheads_ingest_once.py"
echo ""
echo "To view logs:"
echo "  tail -f logs/cron_bogleheads.log"
echo ""
echo "To check RAG database:"
echo "  python3 scripts/query_sentiment_rag.py --ticker MARKET --source bogleheads_forum"
echo ""
echo "To remove cron job:"
echo "  crontab -e"
echo ""
echo "Output files:"
echo "  - RAG store: data/rag/sentiment_rag.db"
echo "  - Fallback JSON: data/rag/bogleheads_latest.json"
echo "  - Logs: logs/cron_bogleheads.log"
echo ""
