#!/usr/bin/env python3
"""
DAILY CHECK-IN REPORT
Shows you exactly how profitable you are
Run this every day to track progress
"""
import os
import json
from datetime import datetime, date, timedelta
from pathlib import Path
import alpaca_trade_api as tradeapi

DATA_DIR = Path("data")
STARTING_BALANCE = 100000.0

api = tradeapi.REST(
    os.getenv("ALPACA_API_KEY", "PKSGVK5JNGYIFPTW53EAKCNBP5"),
    os.getenv("ALPACA_SECRET_KEY", "9DCF1pY2wgTTY3TBasjAHUWWLXiDTyrAhMJ4ZD6nVWaG"),
    "https://paper-api.alpaca.markets",
)


def get_fibonacci_investment(day):
    """Get Fibonacci investment amount for given day"""
    fibonacci_sequence = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]

    if day <= 0:
        return 0
    if day <= len(fibonacci_sequence):
        return float(fibonacci_sequence[day - 1])

    # If beyond sequence, keep using last value
    return float(fibonacci_sequence[-1])


def get_challenge_day():
    """Calculate which day of 30-day challenge"""
    challenge_file = DATA_DIR / "challenge_start.json"

    if not challenge_file.exists():
        # First day!
        start_data = {
            "start_date": date.today().isoformat(),
            "starting_balance": STARTING_BALANCE,
        }
        with open(challenge_file, "w") as f:
            json.dump(start_data, f, indent=2)
        return 1

    with open(challenge_file, "r") as f:
        data = json.load(f)

    start_date = datetime.fromisoformat(data["start_date"]).date()
    today = date.today()
    days = (today - start_date).days + 1

    return days


def get_total_fibonacci_investment(current_day):
    """Calculate total investment from Day 1 to current_day using Fibonacci"""
    total = 0
    for day in range(1, current_day + 1):
        total += get_fibonacci_investment(day)
    return total


def get_account_data():
    """Get current account status"""
    account = api.get_account()

    return {
        "equity": float(account.equity),
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "pl": float(account.equity) - STARTING_BALANCE,
        "pl_pct": ((float(account.equity) - STARTING_BALANCE) / STARTING_BALANCE) * 100,
        "positions_value": float(account.equity) - float(account.cash),
    }


def get_positions_summary():
    """Get all current positions"""
    positions = api.list_positions()

    summary = []
    for pos in positions:
        summary.append(
            {
                "symbol": pos.symbol,
                "qty": float(pos.qty),
                "value": float(pos.market_value),
                "pl": float(pos.unrealized_pl),
                "pl_pct": float(pos.unrealized_plpc) * 100,
                "entry": float(pos.avg_entry_price),
                "current": float(pos.current_price),
            }
        )

    return summary


def get_todays_trades():
    """Get today's executed trades"""
    today_file = DATA_DIR / f"trades_{date.today().isoformat()}.json"

    if today_file.exists():
        with open(today_file, "r") as f:
            return json.load(f)
    return []


def get_manual_reserves():
    """Get manual investment reserves"""
    tracking_file = DATA_DIR / "manual_investments.json"

    if tracking_file.exists():
        with open(tracking_file, "r") as f:
            return json.load(f)

    return {"ipo_reserve": 0, "crowdfunding_reserve": 0}


def calculate_daily_return():
    """Calculate today's return"""
    perf_file = DATA_DIR / "performance_log.json"

    if not perf_file.exists():
        return 0, 0

    with open(perf_file, "r") as f:
        data = json.load(f)

    if len(data) < 2:
        return 0, 0

    yesterday = data[-2]["equity"]
    today = data[-1]["equity"]

    daily_return = today - yesterday
    daily_return_pct = (daily_return / yesterday) * 100

    return daily_return, daily_return_pct


def main():
    """Generate daily check-in report"""

    # Header
    print("\n" + "=" * 70)
    print("📊 DAILY CHECK-IN REPORT")
    print(f"📅 {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
    print("=" * 70)

    # Challenge Progress
    day = get_challenge_day()
    days_remaining = 30 - day
    progress = (day / 30) * 100

    print(f"\n🎯 30-DAY CHALLENGE PROGRESS")
    print("-" * 70)
    print(f"Day {day} of 30 ({progress:.0f}% complete)")
    print(f"Days Remaining: {days_remaining}")
    print(f"Progress: {'█' * (day // 2)}{'░' * (15 - day // 2)}")

    # Account Performance
    account = get_account_data()

    print(f"\n💰 ACCOUNT SUMMARY")
    print("-" * 70)
    print(f"Total Equity:     ${account['equity']:>12,.2f}")
    print(f"Cash:             ${account['cash']:>12,.2f}")
    print(f"Positions Value:  ${account['positions_value']:>12,.2f}")
    print(f"Buying Power:     ${account['buying_power']:>12,.2f}")

    print(f"\n📈 PROFIT/LOSS")
    print("-" * 70)
    print(f"Total P/L:        ${account['pl']:>12,.2f}")
    print(f"Return:           {account['pl_pct']:>12,.2f}%")

    # Daily Performance
    daily_return, daily_pct = calculate_daily_return()

    if daily_return != 0:
        print(f"\n📊 TODAY'S PERFORMANCE")
        print("-" * 70)
        print(f"Daily Return:     ${daily_return:>12,.2f}")
        print(f"Daily Change:     {daily_pct:>12,.2f}%")

    # Current Positions
    positions = get_positions_summary()

    if positions:
        print(f"\n📍 CURRENT POSITIONS ({len(positions)})")
        print("-" * 70)
        for pos in positions:
            pl_symbol = "📈" if pos["pl"] > 0 else "📉" if pos["pl"] < 0 else "➡️"
            print(
                f"{pl_symbol} {pos['symbol']:5s} | Qty: {pos['qty']:>8.4f} | "
                f"Value: ${pos['value']:>8,.2f} | "
                f"P/L: ${pos['pl']:>7,.2f} ({pos['pl_pct']:>+6.2f}%)"
            )
    else:
        print(f"\n📍 CURRENT POSITIONS")
        print("-" * 70)
        print("No positions yet")

    # Today's Trades
    trades = get_todays_trades()

    if trades:
        print(f"\n🔄 TODAY'S TRADES ({len(trades)})")
        print("-" * 70)
        for trade in trades:
            print(
                f"✅ {trade['tier']:10s} | {trade['symbol']:5s} | ${trade['amount']:.2f}"
            )
    else:
        print(f"\n🔄 TODAY'S TRADES")
        print("-" * 70)
        print("No trades executed today")

    # Manual Reserves
    reserves = get_manual_reserves()

    print(f"\n💼 MANUAL INVESTMENT RESERVES")
    print("-" * 70)
    print(f"IPO Reserve:           ${reserves.get('ipo_reserve', 0):>10,.2f}")
    print(f"Crowdfunding Reserve:  ${reserves.get('crowdfunding_reserve', 0):>10,.2f}")

    # Investment Breakdown using Fibonacci
    total_invested = get_total_fibonacci_investment(day)
    tier1_invested = total_invested * 0.60
    tier2_invested = total_invested * 0.20

    print(f"\n💸 TOTAL INVESTED (Since Day 1 - Fibonacci Strategy)")
    print("-" * 70)
    print(f"Tier 1 (Core):         ${tier1_invested:>10,.2f} (60%)")
    print(f"Tier 2 (Growth):       ${tier2_invested:>10,.2f} (20%) - NVDA/GOOGL")
    print(f"Tier 3 (IPO):          ${reserves.get('ipo_reserve', 0):>10,.2f} (10%)")
    print(
        f"Tier 4 (Crowdfunding): ${reserves.get('crowdfunding_reserve', 0):>10,.2f} (10%)"
    )
    print(f"{'─'*70}")
    print(f"TOTAL:                 ${total_invested:>10,.2f}")
    print(f"Today's Investment:    ${get_fibonacci_investment(day):.2f}")

    # Goals & Targets
    target_30day = total_invested * 1.10  # 10% return target
    current_value = account["equity"]
    to_target = target_30day - current_value

    print(f"\n🎯 30-DAY GOALS")
    print("-" * 70)
    print(f"Target Equity (10% return):  ${target_30day:>12,.2f}")
    print(f"Current Equity:              ${current_value:>12,.2f}")
    print(f"To Target:                   ${to_target:>12,.2f}")

    if account["pl"] > 0:
        print(f"\n🎉 You're PROFITABLE! Up ${account['pl']:.2f}!")
    elif account["pl"] < 0:
        print(f"\n💪 Down ${abs(account['pl']):.2f} - Stay disciplined!")
    else:
        print(f"\n➡️  Break-even - Building momentum!")

    # Footer
    print("\n" + "=" * 70)
    print("📝 NEXT ACTIONS")
    print("=" * 70)
    print("1. Review positions - any need adjusting?")
    print("2. Check for IPO opportunities on SoFi")
    print("3. Research crowdfunding deals")
    print("4. System auto-runs tomorrow 9:35 AM ET")
    print("\n💡 Stay patient. Compound interest takes time!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
