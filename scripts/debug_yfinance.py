import pandas as pd
import yfinance as yf


def test_yfinance():
    symbol = "GOOGL"
    print(f"Fetching data for {symbol}...")
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="3mo")

    print("Columns:", hist.columns)
    print("Shape:", hist.shape)
    print("Head:\n", hist.head())

    closes = hist["Close"]
    print("Closes type:", type(closes))
    print("Closes shape:", closes.shape)

    last_close = closes.iloc[-1]
    print("Last close:", last_close)
    print("Last close type:", type(last_close))

    # Check MACD calculation logic
    try:
        ema_fast = closes.ewm(span=12, adjust=False).mean()
        ema_slow = closes.ewm(span=26, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        last_hist = histogram.iloc[-1]
        print("Last histogram:", last_hist)
        print("Last histogram type:", type(last_hist))

        if pd.isna(last_hist):
            print("Is NA")
        else:
            print("Not NA")

    except Exception as e:
        print(f"Error in MACD logic: {e}")


if __name__ == "__main__":
    test_yfinance()
