import os
from datetime import datetime, timedelta

import alpaca_trade_api as tradeapi
import requests
from dotenv import load_dotenv

# Load env
load_dotenv()


def test_alpaca():
    print("\nTesting Alpaca API...")
    key = os.getenv("ALPACA_API_KEY")
    secret = os.getenv("ALPACA_SECRET_KEY")

    if not key or not secret:
        print("❌ ALPACA_API_KEY or ALPACA_SECRET_KEY missing")
        return

    try:
        api = tradeapi.REST(key, secret, "https://paper-api.alpaca.markets")
        account = api.get_account()
        print(f"✅ Alpaca Connection Successful. Status: {account.status}")

        # Try fetching bars
        symbol = "AMZN"
        start = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")
        print(f"   Fetching {symbol} bars from {start} to {end}...")

        bars = api.get_bars(symbol, "1Day", start=start, end=end).df
        if not bars.empty:
            print(f"✅ Fetched {len(bars)} bars for {symbol}")
            print(bars.head())
        else:
            print(f"⚠️  Fetched 0 bars for {symbol}")

    except Exception as e:
        print(f"❌ Alpaca Error: {e}")


def test_polygon():
    print("\nTesting Polygon.io API...")
    key = os.getenv("POLYGON_API_KEY")
    if not key:
        print("❌ POLYGON_API_KEY missing")
        return

    symbol = "AMZN"
    start = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")

    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}?adjusted=true&sort=asc&limit=120&apiKey={key}"

    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("resultsCount", 0) > 0:
                print(f"✅ Polygon Connection Successful. Fetched {data['resultsCount']} bars.")
            else:
                print(f"⚠️  Polygon returned 0 results. Response: {data}")
        else:
            print(f"❌ Polygon Error: HTTP {resp.status_code}")
            print(resp.text)
    except Exception as e:
        print(f"❌ Polygon Exception: {e}")


if __name__ == "__main__":
    test_alpaca()
    test_polygon()
