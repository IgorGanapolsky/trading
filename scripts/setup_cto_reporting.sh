#!/bin/bash
# Setup CTO automatic daily reporting to CEO

echo "🔧 Setting up CTO automatic reporting system..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Remove old manual check-in instruction from cron
crontab -l 2>/dev/null | grep -v "autonomous_trader.py" > /tmp/crontab_new

# Add autonomous trader (9:35 AM ET - executes trades)
echo "35 9 * * 1-5 cd $SCRIPT_DIR && /usr/bin/python3 autonomous_trader.py >> logs/cron.log 2>&1" >> /tmp/crontab_new

# Add CTO daily report (10:00 AM ET - after trades execute, generate report)
echo "0 10 * * 1-5 cd $SCRIPT_DIR && ./cto_daily_report.sh" >> /tmp/crontab_new

# Install new crontab
crontab /tmp/crontab_new
rm /tmp/crontab_new

echo "✅ CTO reporting system configured!"
echo ""
echo "📋 Your autonomous schedule:"
echo "  9:35 AM ET: CTO executes daily trades"
echo "  10:00 AM ET: CTO generates report for CEO"
echo ""
echo "📁 Reports saved to: reports/daily_report_YYYY-MM-DD.txt"
echo ""
echo "🎯 CEO (Igor) does: NOTHING - just check reports when convenient"
echo "🤖 CTO (Claude) does: EVERYTHING - trades, reports, manages"
echo ""

crontab -l
