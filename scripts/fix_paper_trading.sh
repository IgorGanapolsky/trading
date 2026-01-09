#!/bin/bash
# Fix Paper Trading - Run this locally or in GitHub Codespace
#
# CEO: Run this script to diagnose and fix paper trading
# Date: Jan 9, 2026
#
# What this does:
# 1. Tests if Alpaca credentials work
# 2. Shows account status
# 3. Places a test trade if desired

set -e

echo "========================================"
echo "PAPER TRADING FIX SCRIPT"
echo "========================================"
echo ""

# Paper trading credentials (provided by CEO)
export ALPACA_API_KEY="PKMSWXVRXU6CYXOAIVVJVCMSWL"
export ALPACA_SECRET_KEY="4KsCY4Qbb7RXILb459MXCuTi43iWkERBr3jgarkqudRx"
export ALPACA_API_BASE_URL="https://paper-api.alpaca.markets"

echo "Step 1: Testing credentials..."
RESPONSE=$(curl -s -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
     -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" \
     "https://paper-api.alpaca.markets/v2/account")

if echo "$RESPONSE" | grep -q "equity"; then
    echo "SUCCESS: Credentials are valid!"
    echo ""
    echo "$RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Account Status: {data.get(\"status\")}')
print(f'Equity: \${float(data.get(\"equity\", 0)):,.2f}')
print(f'Cash: \${float(data.get(\"cash\", 0)):,.2f}')
print(f'Buying Power: \${float(data.get(\"buying_power\", 0)):,.2f}')
"
else
    echo "FAILED: Credentials invalid!"
    echo "Response: $RESPONSE"
    exit 1
fi

echo ""
echo "Step 2: Checking open positions..."
curl -s -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
     -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" \
     "https://paper-api.alpaca.markets/v2/positions" | python3 -c "
import json, sys
positions = json.load(sys.stdin)
if not positions:
    print('No open positions')
else:
    print(f'{len(positions)} open positions:')
    for p in positions:
        print(f'  {p[\"symbol\"]}: {p[\"qty\"]} @ \${float(p[\"current_price\"]):,.2f}')
"

echo ""
echo "Step 3: Checking recent orders..."
curl -s -H "APCA-API-KEY-ID: $ALPACA_API_KEY" \
     -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY" \
     "https://paper-api.alpaca.markets/v2/orders?status=all&limit=5" | python3 -c "
import json, sys
orders = json.load(sys.stdin)
if not orders:
    print('No recent orders')
else:
    print(f'{len(orders)} recent orders:')
    for o in orders[:5]:
        print(f'  {o[\"symbol\"]} {o[\"side\"]} {o[\"qty\"]} - {o[\"status\"]} ({o[\"created_at\"][:10]})')
"

echo ""
echo "========================================"
echo "NEXT STEPS:"
echo "========================================"
echo ""
echo "1. Go to: https://github.com/IgorGanapolsky/trading/settings/secrets/actions"
echo ""
echo "2. Add these secrets if they don't exist:"
echo "   ALPACA_PAPER_TRADING_5K_API_KEY = PKMSWXVRXU6CYXOAIVVJVCMSWL"
echo "   ALPACA_PAPER_TRADING_5K_API_SECRET = 4KsCY4Qbb7RXILb459MXCuTi43iWkERBr3jgarkqudRx"
echo ""
echo "3. Go to: https://github.com/IgorGanapolsky/trading/actions/workflows/daily-trading.yml"
echo "4. Click 'Run workflow' -> trading_mode: paper -> force_trade: true"
echo ""
