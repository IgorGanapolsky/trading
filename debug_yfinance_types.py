import pandas as pd
import yfinance as yf

print(f"yfinance version: {yf.__version__}")
print(f"pandas version: {pd.__version__}")

symbol = "SPY"
data = yf.download(symbol, period="1mo", progress=False, auto_adjust=False, threads=False)

print(f"\nData type: {type(data)}")
print(f"Data shape: {data.shape}")
print(f"Columns: {data.columns}")

close = data["Close"]
print(f"\nClose type: {type(close)}")
if isinstance(close, pd.DataFrame):
    print(f"Close shape: {close.shape}")
    print(f"Close columns: {close.columns}")

# Mimic MACD calculation
ema_fast = close.ewm(span=12, adjust=False).mean()
print(f"\nEMA type: {type(ema_fast)}")

last = ema_fast.iloc[-1]
print(f"Last EMA value type: {type(last)}")
print(f"Last EMA value: {last}")

if isinstance(last, pd.Series):
    print("Last EMA is a Series. iloc[0]:", last.iloc[0], type(last.iloc[0]))


def get_scalar(val):
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    return float(val) if not pd.isna(val) else 0.0


try:
    scalar = get_scalar(last)
    print(f"Scalar: {scalar}, Type: {type(scalar)}")
    print(f"Formatted: {scalar:.3f}")
except Exception as e:
    print(f"Failed: {e}")
