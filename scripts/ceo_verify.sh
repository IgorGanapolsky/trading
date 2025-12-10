#!/bin/bash
# CEO VERIFICATION SCRIPT
# Use this to verify EVERYTHING the CTO claims
# Trust nothing. Verify everything.

echo "========================================================================"
echo "CEO VERIFICATION TOOL"
echo "Trust Nothing. Verify Everything."
echo "========================================================================"
echo ""

# Get script directory and navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "1. CHECKING SYSTEM STATE STALENESS"
echo "------------------------------------------------------------------------"
python3 -c "
import json
from datetime import datetime

state = json.load(open('data/system_state.json'))
last_update = datetime.fromisoformat(state['meta']['last_updated'])
now = datetime.now()
hours_old = (now - last_update).total_seconds() / 3600

print(f'Last Updated: {last_update.strftime(\"%Y-%m-%d %H:%M:%S\")}')
print(f'Current Time: {now.strftime(\"%Y-%m-%d %H:%M:%S\")}')
print(f'Hours Old: {hours_old:.1f}')
print(f'Status: {state[\"meta\"].get(\"staleness_status\", \"UNKNOWN\")}')

if hours_old > 24:
    print('⚠️  WARNING: State is more than 24 hours old!')
if hours_old > 72:
    print('🚨 CRITICAL: State is EXPIRED (>3 days old)')
"
echo ""

echo "2. CHECKING REAL ALPACA ACCOUNT BALANCE"
echo "------------------------------------------------------------------------"
python3 -c "
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()

try:
    client = TradingClient(
        os.getenv('ALPACA_API_KEY'),
        os.getenv('ALPACA_SECRET_KEY'),
        paper=True
    )

    account = client.get_account()
    equity = float(account.equity)
    cash = float(account.cash)
    pl = equity - 100000

    print(f'Real Equity: \${equity:,.2f}')
    print(f'Real Cash: \${cash:,.2f}')
    print(f'Real P/L: \${pl:,.2f} ({pl/1000:.2f}%)')

    if pl < 0:
        print(f'⚠️  Currently losing money')
    else:
        print(f'✅ Currently profitable')

except Exception as e:
    print(f'❌ ERROR connecting to Alpaca: {e}')
" 2>&1
echo ""

echo "3. CHECKING CURRENT POSITIONS"
echo "------------------------------------------------------------------------"
python3 -c "
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()

try:
    client = TradingClient(
        os.getenv('ALPACA_API_KEY'),
        os.getenv('ALPACA_SECRET_KEY'),
        paper=True
    )

    positions = client.get_all_positions()

    if len(positions) == 0:
        print('No open positions')
    else:
        print(f'Open Positions: {len(positions)}')
        print('')
        for p in positions:
            pl = float(p.unrealized_pl)
            plpc = float(p.unrealized_plpc) * 100
            mv = float(p.market_value)
            qty = float(p.qty)

            status = '✅' if pl >= 0 else '❌'
            print(f'{status} {p.symbol}:')
            print(f'   Qty: {qty:.4f} shares')
            print(f'   Value: \${mv:.2f}')
            print(f'   P/L: \${pl:.2f} ({plpc:+.2f}%)')
            print('')

except Exception as e:
    print(f'❌ ERROR: {e}')
" 2>&1
echo ""

echo "4. CHECKING CRON JOB CONFIGURATION"
echo "------------------------------------------------------------------------"
if crontab -l 2>/dev/null | grep -q "trading"; then
    echo "✅ Cron job configured:"
    crontab -l | grep trading
else
    echo "❌ NO cron job found for trading system"
fi
echo ""

echo "5. CHECKING LAST EXECUTION LOG"
echo "------------------------------------------------------------------------"
if [ -f "logs/cron_trading.log" ]; then
    echo "Last 20 lines of execution log:"
    tail -20 logs/cron_trading.log
else
    echo "❌ No execution log found"
fi
echo ""

echo "6. CHECKING TODAY'S TRADES"
echo "------------------------------------------------------------------------"
TODAY=$(date +%Y-%m-%d)
if [ -f "data/trades_${TODAY}.json" ]; then
    echo "✅ Trades executed today:"
    cat "data/trades_${TODAY}.json" | python3 -m json.tool
else
    echo "⚠️  No trades executed today (or log not created yet)"
fi
echo ""

echo "7. COMPARING CTO REPORT VS REALITY"
echo "------------------------------------------------------------------------"
echo "CTO's Reported State (from system_state.json):"
python3 -c "
import json
state = json.load(open('data/system_state.json'))
print(f'  Equity: \${state[\"account\"][\"current_equity\"]:,.2f}')
print(f'  P/L: \${state[\"account\"][\"total_pl\"]:,.2f}')
print(f'  Day: {state[\"challenge\"][\"current_day\"]}')
"
echo ""
echo "Alpaca's Reality (from API):"
python3 -c "
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()
client = TradingClient(
    os.getenv('ALPACA_API_KEY'),
    os.getenv('ALPACA_SECRET_KEY'),
    paper=True
)

account = client.get_account()
equity = float(account.equity)
pl = equity - 100000

print(f'  Equity: \${equity:,.2f}')
print(f'  P/L: \${pl:,.2f}')
" 2>&1
echo ""

echo "========================================================================"
echo "VERIFICATION COMPLETE"
echo "========================================================================"
echo ""
echo "If CTO's report doesn't match Alpaca's reality → CTO is LYING"
echo "If state is >24 hours old → CTO is using STALE DATA"
echo "If cron not configured → CTO's automation claims are FALSE"
echo ""
echo "Trust nothing. Verify everything."
echo "========================================================================"
