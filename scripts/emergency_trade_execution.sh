#!/bin/bash
# Emergency Trading Execution Script
# Use this when GitHub Actions workflow hangs or fails
# Last Updated: 2025-12-16

set -e

echo "🚨 EMERGENCY TRADING EXECUTION"
echo "=============================="
echo ""
echo "This script bypasses the hung GitHub Actions workflow"
echo "and executes trading directly."
echo ""

# Check if we're in the right directory
if [ ! -f "scripts/autonomous_trader.py" ]; then
    echo "❌ Error: Must run from repository root"
    exit 1
fi

# Check environment variables
if [ -z "$ALPACA_API_KEY" ] || [ -z "$ALPACA_SECRET_KEY" ]; then
    echo "❌ Error: Alpaca credentials not set"
    echo "   Please export ALPACA_API_KEY and ALPACA_SECRET_KEY"
    exit 1
fi

echo "✅ Environment validated"
echo ""

# Check current time (market hours)
HOUR=$(date +%H)
if [ $HOUR -lt 9 ] || [ $HOUR -ge 16 ]; then
    echo "⚠️  WARNING: Outside market hours (9:30 AM - 4:00 PM ET)"
    echo "   Current time: $(date)"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📊 Executing daily trading strategy..."
echo ""

# Run the main trading script
PYTHONPATH=. python3 scripts/autonomous_trader.py

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Trading execution completed successfully"
    echo ""
    echo "📈 Next steps:"
    echo "   1. Check data/trades_$(date +%Y-%m-%d).json for executed trades"
    echo "   2. Verify positions: python3 scripts/verify_positions.py"
    echo "   3. Update dashboard: python3 scripts/generate_progress_dashboard.py"
else
    echo "❌ Trading execution failed with exit code $EXIT_CODE"
    echo ""
    echo "🔍 Troubleshooting:"
    echo "   1. Check logs/trading_*.log"
    echo "   2. Verify Alpaca API status"
    echo "   3. Check network connectivity"
    exit $EXIT_CODE
fi

# Run options harvesting
echo ""
echo "💰 Harvesting theta (options income)..."
python3 scripts/options_profit_planner.py --target-daily 10 || echo "⚠️  Options planning skipped"

# Execute wheel on high-priority tickers
for SYMBOL in SPY QQQ PLTR SOFI AMD; do
    echo "   Executing wheel on $SYMBOL..."
    python3 scripts/execute_options_trade.py --strategy wheel --symbol $SYMBOL || echo "   ⚠️  $SYMBOL skipped"
done

echo ""
echo "✅ Emergency trading execution complete"
echo ""
echo "📊 Summary:"
python3 -c "
import json
from datetime import datetime
trade_file = f'data/trades_{datetime.now().strftime(\"%Y-%m-%d\")}.json'
try:
    with open(trade_file) as f:
        trades = json.load(f)
    print(f'   Trades executed: {len(trades)}')
    for t in trades[-5:]:
        symbol = t.get('symbol', 'N/A')
        action = t.get('action', 'N/A')
        status = t.get('status', 'N/A')
        print(f'   - {symbol}: {action} ({status})')
except:
    print('   No trades file found')
"
