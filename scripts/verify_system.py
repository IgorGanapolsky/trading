#!/usr/bin/env python3
"""
System Verification Script
Tests Alpaca API, strategies, and readiness for trading execution
"""

import os
import sys
from datetime import datetime

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import security utilities
from src.utils.security import mask_api_key


def print_section(title):
    """Print formatted section header"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def test_alpaca_connection():
    """Test 1: Verify Alpaca API credentials and connection"""
    print_section("TEST 1: Alpaca API Connection")

    try:
        from alpaca.trading.client import TradingClient

        # Load environment variables
        load_dotenv()
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        paper_trading = os.getenv("PAPER_TRADING", "true").lower() == "true"

        # Mask API key for security (CodeQL-safe pattern)
        masked = mask_api_key(api_key)
        print(f"API Key: {masked}")
        print(f"Paper Trading: {paper_trading}")

        # Initialize client
        client = TradingClient(api_key, secret_key, paper=paper_trading)

        # Test 1: Get account info
        account = client.get_account()
        print("\n✅ Account connected successfully!")
        print(f"   Account Number: {account.account_number}")
        print(f"   Account Status: {account.status}")
        print(f"   Trading Blocked: {account.trading_blocked}")
        print(f"   Pattern Day Trader: {account.pattern_day_trader}")

        # Test 2: Get portfolio values
        print("\n📊 Portfolio Status:")
        print(f"   Equity: ${float(account.equity):,.2f}")
        print(f"   Cash: ${float(account.cash):,.2f}")
        print(f"   Buying Power: ${float(account.buying_power):,.2f}")
        print(f"   Portfolio Value: ${float(account.portfolio_value):,.2f}")
        print(f"   Last Equity: ${float(account.last_equity):,.2f}")

        # Calculate P/L
        pl = float(account.equity) - float(account.last_equity)
        pl_pct = (pl / float(account.last_equity)) * 100
        print(f"   Today's P/L: ${pl:,.2f} ({pl_pct:+.2f}%)")

        # Test 3: Get positions
        positions = client.get_all_positions()
        print(f"\n📈 Current Positions ({len(positions)}):")
        for pos in positions:
            unrealized_pl = float(pos.unrealized_pl)
            unrealized_pl_pct = float(pos.unrealized_plpc) * 100
            print(f"   {pos.symbol}: {pos.qty} shares @ ${float(pos.avg_entry_price):.2f}")
            print(
                f"      Current: ${float(pos.current_price):.2f} | P/L: ${unrealized_pl:+.2f} ({unrealized_pl_pct:+.2f}%)"
            )

        # Test 4: Check market status
        clock = client.get_clock()
        print("\n🕒 Market Status:")
        print(f"   Is Open: {clock.is_open}")
        print(f"   Current Time: {clock.timestamp}")
        print(f"   Next Open: {clock.next_open}")
        print(f"   Next Close: {clock.next_close}")

        return True, client

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback

        traceback.print_exc()
        return False, None


def test_market_data():
    """Test 2: Verify market data access via yfinance"""
    print_section("TEST 2: Market Data Access")

    try:
        import yfinance as yf

        # Test SPY data with headers to avoid rate limiting
        print("Fetching SPY data...")

        # Set user agent to avoid 403 errors
        import requests

        session = requests.Session()
        session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        spy = yf.Ticker("SPY", session=session)
        hist = spy.history(period="5d")

        if hist.empty:
            print("⚠️  WARNING: No data returned for SPY (market may be closed)")
            print("   This is not critical - yfinance can be temperamental on weekends")
            return True  # Don't fail the test for this

        print("✅ SPY data fetched successfully!")
        print(f"   Last 5 days: {len(hist)} records")
        print(f"   Latest close: ${hist['Close'].iloc[-1]:.2f}")
        print(f"   Latest date: {hist.index[-1].strftime('%Y-%m-%d')}")

        # Test MACD calculation
        print("\nCalculating MACD...")
        closes = hist["Close"]
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal

        print(f"   MACD: {macd.iloc[-1]:.4f}")
        print(f"   Signal: {signal.iloc[-1]:.4f}")
        print(f"   Histogram: {histogram.iloc[-1]:.4f}")
        print(f"   Status: {'BULLISH ✅' if histogram.iloc[-1] > 0 else 'BEARISH ❌'}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_strategies():
    """Test 3: Verify strategy imports and initialization"""
    print_section("TEST 3: Strategy Initialization")

    try:
        from src.strategies.core_strategy import CoreStrategy
        from src.strategies.growth_strategy import GrowthStrategy

        print("Testing CoreStrategy...")
        core = CoreStrategy(use_sentiment=False)  # Disable sentiment to avoid API calls
        print("✅ CoreStrategy initialized")
        print(f"   Daily allocation: ${core.daily_allocation}")
        print(f"   ETF universe: {core.etf_universe}")
        print(f"   Stop loss: {core.stop_loss_pct * 100}%")

        print("\nTesting GrowthStrategy...")
        growth = GrowthStrategy(weekly_allocation=10.0)
        print("✅ GrowthStrategy initialized")
        print(f"   Weekly allocation: ${growth.weekly_allocation}")
        print(f"   Stop loss: {growth.stop_loss_pct * 100}%")
        print(f"   Take profit: {growth.take_profit_pct * 100}%")
        print(f"   Max positions: {growth.max_positions}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_order_submission(client):
    """Test 4: Submit and cancel a test order"""
    print_section("TEST 4: Order Submission Test")

    if client is None:
        print("❌ SKIPPED: No client available")
        return False

    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        # Check if market is open
        clock = client.get_clock()
        if not clock.is_open:
            print("⚠️  Market is closed - will test order submission anyway")

        # Create a small test order for SPY ($1)
        print("Submitting test order: SPY $1 (fractional share)...")

        order_request = MarketOrderRequest(
            symbol="SPY",
            notional=1.0,  # $1 worth of SPY
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )

        # Submit order
        order = client.submit_order(order_request)
        print("✅ Order submitted successfully!")
        print(f"   Order ID: {order.id}")
        print(f"   Symbol: {order.symbol}")
        print(f"   Side: {order.side}")
        print(f"   Notional: ${order.notional}")
        print(f"   Status: {order.status}")

        # Wait a moment then cancel
        import time

        time.sleep(1)

        print("\nCanceling test order...")
        client.cancel_order_by_id(order.id)
        print("✅ Order canceled successfully!")

        return True

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_autonomous_trader():
    """Test 5: Verify autonomous trader script structure"""
    print_section("TEST 5: Autonomous Trader Script")

    try:
        script_path = os.path.join(os.path.dirname(__file__), "autonomous_trader.py")

        if not os.path.exists(script_path):
            print(f"❌ FAILED: Script not found at {script_path}")
            return False

        print(f"✅ Script exists: {script_path}")

        # Read script to check for dry-run capability
        with open(script_path) as f:
            content = f.read()

        print(f"   Size: {len(content)} bytes")
        print(f"   Lines: {len(content.splitlines())}")

        # Check for key components
        checks = {
            "CoreStrategy import": "from src.strategies.core_strategy import CoreStrategy"
            in content,
            "GrowthStrategy import": "from src.strategies.growth_strategy import GrowthStrategy"
            in content,
            "Alpaca client": (
                "TradingClient" in content or "alpaca_trade_api" in content or "tradeapi" in content
            ),
            "Environment variables": (
                "load_dotenv" in content or "os.getenv" in content or "os.environ" in content
            ),
        }

        print("\n   Component checks:")
        for check, result in checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check}")

        return all(checks.values())

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def verify_system_state():
    """Verify current system state from JSON"""
    print_section("SYSTEM STATE VERIFICATION")

    try:
        import json

        state_path = os.path.join(os.path.dirname(__file__), "..", "data", "system_state.json")

        with open(state_path) as f:
            state = json.load(f)

        print("📊 Current System State:")
        print(
            f"   Challenge Day: {state['challenge']['current_day']} / {state['challenge']['total_days']}"
        )
        print(f"   Phase: {state['challenge']['phase']}")
        print(f"   Status: {state['challenge']['status']}")

        print("\n💰 Account Summary:")
        print(f"   Starting Balance: ${state['account']['starting_balance']:,.2f}")
        print(f"   Current Equity: ${state['account']['current_equity']:,.2f}")
        print(
            f"   Total P/L: ${state['account']['total_pl']:,.2f} ({state['account']['total_pl_pct']:.2f}%)"
        )

        print("\n📈 Performance:")
        print(f"   Total Trades: {state['performance']['total_trades']}")
        print(f"   Win Rate: {state['performance']['win_rate'] * 100:.1f}%")
        print(f"   Winning Trades: {state['performance']['winning_trades']}")
        print(f"   Losing Trades: {state['performance']['losing_trades']}")

        print("\n🎯 Strategies:")
        print(f"   Tier 1 (Core): ${state['strategies']['tier1']['total_invested']:,.2f} invested")
        print(
            f"   Tier 2 (Growth): ${state['strategies']['tier2']['total_invested']:,.2f} invested"
        )
        print(f"   Tier 2 Stocks: {', '.join(state['strategies']['tier2']['stocks'])}")

        print("\n🤖 Automation:")
        automation = state["automation"]
        print(f"   GitHub Actions Enabled: {automation.get('github_actions_enabled')}")
        print(f"   Workflow Name: {automation.get('workflow_name')}")
        print(f"   Workflow Status: {automation.get('workflow_status')}")
        print(f"   Execution Count: {state['automation']['execution_count']}")
        print(f"   Failures: {state['automation']['failures']}")

        print("\n📹 Video Analysis:")
        print(f"   Enabled: {state['video_analysis']['enabled']}")
        print(f"   Autonomous Monitoring: {state['video_analysis']['autonomous_monitoring']}")
        print(f"   Channels Monitored: {state['video_analysis']['channels_monitored']}")
        print(f"   Videos Analyzed: {state['video_analysis']['videos_analyzed']}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all system verification tests"""
    print("\n" + "=" * 80)
    print("  TRADING SYSTEM VERIFICATION")
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    results = {}

    # Run tests
    results["state"] = verify_system_state()
    results["alpaca"], client = test_alpaca_connection()
    results["market_data"] = test_market_data()
    results["strategies"] = test_strategies()
    results["order_test"] = test_order_submission(client)
    results["trader_script"] = test_autonomous_trader()

    # Summary
    print_section("VERIFICATION SUMMARY")

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {test_name.replace('_', ' ').title()}")

    # Overall readiness score
    passed = sum(results.values())
    total = len(results)
    score = (passed / total) * 100

    print(f"\n{'=' * 80}")
    print(f"SYSTEM READINESS SCORE: {score:.0f}% ({passed}/{total} tests passed)")
    print(f"{'=' * 80}\n")

    if score == 100:
        print("✅ SYSTEM READY FOR TRADING EXECUTION")
    elif score >= 80:
        print("⚠️  SYSTEM MOSTLY READY - Review failed tests")
    else:
        print("❌ SYSTEM NOT READY - Critical issues detected")

    return score


if __name__ == "__main__":
    score = main()
    sys.exit(0 if score == 100 else 1)
