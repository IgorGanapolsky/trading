#!/bin/bash
# Setup cron job for autonomous daily trading

echo "🔧 Setting up autonomous trading cron job..."

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create cron job entry
# Runs every weekday at 9:35 AM ET
CRON_JOB="35 9 * * 1-5 cd $SCRIPT_DIR && /usr/bin/python3 autonomous_trader.py >> logs/cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "autonomous_trader.py"; then
    echo "⚠️  Cron job already exists!"
    echo "Current crontab:"
    crontab -l | grep autonomous_trader
else
    # Add to crontab
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✅ Cron job added!"
    echo "📅 Will run every weekday at 9:35 AM ET"
fi

echo ""
echo "📋 Current cron jobs:"
crontab -l | grep autonomous_trader || echo "No jobs found"

echo ""
echo "🎯 Your system is now FULLY AUTONOMOUS!"
echo ""
echo "To check status:"
echo "  python3 daily_checkin.py"
echo ""
echo "To view logs:"
echo "  tail -f logs/cron.log"
echo ""
echo "To remove cron job:"
echo "  crontab -e"
echo ""
