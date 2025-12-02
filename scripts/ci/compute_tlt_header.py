#!/usr/bin/env python3
import sys

try:
    import yfinance as yf
except Exception:
    print("- (missing yfinance)")
    sys.exit(0)

try:
    tlt = yf.Ticker("TLT")
    hist = tlt.history(period="6mo")
    if not hist.empty and "Close" in hist.columns:
        sma20 = float(hist["Close"].rolling(20).mean().iloc[-1])
        sma50 = float(hist["Close"].rolling(50).mean().iloc[-1])
        gate = "ON" if sma20 >= sma50 else "OFF"
        ret3 = 0.0
        if len(hist) >= 63:
            ret3 = (float(hist["Close"].iloc[-1]) / float(hist["Close"].iloc[-63]) - 1.0) * 100.0
        print(
            f"- SMA20: `${sma20:.2f}` | SMA50: `${sma50:.2f}` | 3M return: `{ret3:.1f}%` | Gate: `{gate}`\n"
        )
    else:
        print("- (insufficient data)\n")
except Exception:
    print("- (error computing trend)\n")
