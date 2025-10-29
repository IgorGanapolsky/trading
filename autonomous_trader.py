#!/usr/bin/env python3
"""
AUTONOMOUS DAILY TRADER
Runs automatically every day at market open
Executes $10 daily investment across strategies
"""
import os
import sys
import json
from datetime import datetime, date
from pathlib import Path
import alpaca_trade_api as tradeapi

# Configuration
ALPACA_KEY = os.getenv('ALPACA_API_KEY', 'PKSGVK5JNGYIFPTW53EAKCNBP5')
ALPACA_SECRET = os.getenv('ALPACA_SECRET_KEY', '9DCF1pY2wgTTY3TBasjAHUWWLXiDTyrAhMJ4ZD6nVWaG')
DAILY_INVESTMENT = 10.0
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)

# Initialize Alpaca
api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, 'https://paper-api.alpaca.markets')

def log_trade(trade_data):
    """Log trade to daily record"""
    log_file = DATA_DIR / f"trades_{date.today().isoformat()}.json"

    trades = []
    if log_file.exists():
        with open(log_file, 'r') as f:
            trades = json.load(f)

    trades.append(trade_data)

    with open(log_file, 'w') as f:
        json.dump(trades, f, indent=2)

def get_momentum_score(symbol, days=20):
    """Calculate momentum score using latest trade data"""
    try:
        # Get latest price
        latest = api.get_latest_trade(symbol)
        current_price = latest.price

        # Simple momentum: use current price
        # In real scenario, would compare to historical average
        return current_price
    except:
        return 0

def execute_tier1():
    """Tier 1: Core ETF Strategy - $6/day"""
    print("\n" + "="*70)
    print("🎯 TIER 1: CORE ETF STRATEGY")
    print("="*70)

    etfs = ['SPY', 'QQQ', 'VOO']
    scores = {}

    # Analyze each ETF
    for symbol in etfs:
        score = get_momentum_score(symbol)
        scores[symbol] = score
        print(f"{symbol}: Score {score:.2f}")

    # Select best
    best = max(scores, key=scores.get)
    amount = 6.0

    print(f"\n✅ Selected: {best}")
    print(f"💰 Investment: ${amount}")

    try:
        # Place order
        order = api.submit_order(
            symbol=best,
            notional=amount,
            side='buy',
            type='market',
            time_in_force='day'
        )

        print(f"✅ Order placed: {order.id}")

        # Log trade
        log_trade({
            'timestamp': datetime.now().isoformat(),
            'tier': 'T1_CORE',
            'symbol': best,
            'amount': amount,
            'order_id': order.id,
            'status': order.status
        })

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def execute_tier2():
    """Tier 2: Growth Stock Strategy - $2/day"""
    print("\n" + "="*70)
    print("📈 TIER 2: GROWTH STOCK STRATEGY")
    print("="*70)

    # Simplified: rotate between AAPL, MSFT, GOOGL, NVDA
    stocks = ['AAPL', 'MSFT', 'GOOGL', 'NVDA']

    # Simple rotation based on day of week
    day_of_week = datetime.now().weekday()
    selected = stocks[day_of_week % len(stocks)]
    amount = 2.0

    print(f"✅ Selected: {selected}")
    print(f"💰 Investment: ${amount}")

    try:
        order = api.submit_order(
            symbol=selected,
            notional=amount,
            side='buy',
            type='market',
            time_in_force='day'
        )

        print(f"✅ Order placed: {order.id}")

        log_trade({
            'timestamp': datetime.now().isoformat(),
            'tier': 'T2_GROWTH',
            'symbol': selected,
            'amount': amount,
            'order_id': order.id,
            'status': order.status
        })

        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def track_daily_deposit():
    """Track $1/day for Tier 3 (IPO) and Tier 4 (Crowdfunding)"""
    print("\n" + "="*70)
    print("💰 TIER 3 & 4: MANUAL INVESTMENT TRACKING")
    print("="*70)

    tracking_file = DATA_DIR / 'manual_investments.json'

    data = {'ipo_reserve': 0, 'crowdfunding_reserve': 0, 'history': []}
    if tracking_file.exists():
        with open(tracking_file, 'r') as f:
            data = json.load(f)

    # Add $1 to each
    data['ipo_reserve'] += 1.0
    data['crowdfunding_reserve'] += 1.0
    data['history'].append({
        'date': date.today().isoformat(),
        'ipo_deposit': 1.0,
        'crowdfunding_deposit': 1.0
    })

    with open(tracking_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✅ IPO Reserve: ${data['ipo_reserve']:.2f}")
    print(f"✅ Crowdfunding Reserve: ${data['crowdfunding_reserve']:.2f}")
    print(f"💡 Manual investments ready when opportunities arise")

def get_account_summary():
    """Get current account performance"""
    account = api.get_account()

    return {
        'equity': float(account.equity),
        'cash': float(account.cash),
        'buying_power': float(account.buying_power),
        'pl': float(account.equity) - 100000.0,  # Starting balance
        'pl_pct': ((float(account.equity) - 100000.0) / 100000.0) * 100
    }

def update_performance_log():
    """Update daily performance log"""
    perf_file = DATA_DIR / 'performance_log.json'

    perf_data = []
    if perf_file.exists():
        with open(perf_file, 'r') as f:
            perf_data = json.load(f)

    summary = get_account_summary()
    summary['date'] = date.today().isoformat()
    summary['timestamp'] = datetime.now().isoformat()

    perf_data.append(summary)

    with open(perf_file, 'w') as f:
        json.dump(perf_data, f, indent=2)

    return summary

def main():
    """Main autonomous trading execution"""
    print("\n" + "="*70)
    print("🤖 AUTONOMOUS DAILY TRADER")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print("="*70)

    # Check if market is open
    clock = api.get_clock()
    if not clock.is_open:
        print("⚠️  Market is closed. Order will execute at next open.")

    # Execute strategies
    tier1_success = execute_tier1()
    tier2_success = execute_tier2()
    track_daily_deposit()

    # Update performance
    print("\n" + "="*70)
    print("📊 PERFORMANCE UPDATE")
    print("="*70)

    perf = update_performance_log()
    print(f"💰 Equity: ${perf['equity']:,.2f}")
    print(f"📈 P/L: ${perf['pl']:+,.2f} ({perf['pl_pct']:+.2f}%)")
    print(f"💵 Cash: ${perf['cash']:,.2f}")

    # Summary
    print("\n" + "="*70)
    print("✅ DAILY EXECUTION COMPLETE")
    print("="*70)
    print(f"Tier 1 (Core): {'✅' if tier1_success else '❌'}")
    print(f"Tier 2 (Growth): {'✅' if tier2_success else '❌'}")
    print(f"Tier 3 (IPO): ✅ Tracked")
    print(f"Tier 4 (Crowdfunding): ✅ Tracked")
    print(f"\n📁 Logs saved to: {DATA_DIR}")
    print(f"🎯 Next execution: Tomorrow 9:35 AM ET")
    print("="*70)

if __name__ == '__main__':
    main()
