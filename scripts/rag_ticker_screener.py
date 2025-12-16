#!/usr/bin/env python3
"""
RAG-Based Ticker Screener for Options Trading

This script uses RAG knowledge to intelligently select tickers for options trading
instead of using a hardcoded list.

Screening Criteria (from McMillan/TastyTrade RAG knowledge):
1. IV Percentile > 50% (favorable for selling premium)
2. No earnings within 7 days (avoid IV crush or gap risk)
3. Bullish/Neutral sentiment from RAG (for cash-secured puts)
4. Collateral within buying power (position sizing)
5. Trend filter (avoid strong downtrends)

Usage:
    python3 scripts/rag_ticker_screener.py --buying-power 10000
    python3 scripts/rag_ticker_screener.py --max-tickers 5 --output json
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Default universe of tickers to screen (options-tradeable with decent liquidity)
DEFAULT_UNIVERSE = [
    # Large-cap ETFs (high liquidity, lower collateral relative to stock price)
    "SPY",   # S&P 500 - ~$600, needs ~$60k collateral
    "QQQ",   # Nasdaq - ~$530, needs ~$53k collateral
    "IWM",   # Russell 2000 - ~$230, needs ~$23k collateral
    # Tech stocks with options
    "AAPL",  # Apple - ~$250, needs ~$25k collateral
    "NVDA",  # NVIDIA - ~$140, needs ~$14k collateral
    "AMD",   # AMD - ~$140, needs ~$14k collateral
    "MSFT",  # Microsoft - ~$430, needs ~$43k collateral
    "GOOGL", # Google - ~$190, needs ~$19k collateral
    "AMZN",  # Amazon - ~$230, needs ~$23k collateral
    "META",  # Meta - ~$610, needs ~$61k collateral
    # Lower-priced stocks (accessible with small accounts)
    "PLTR",  # Palantir - ~$75, needs ~$7.5k collateral
    "SOFI",  # SoFi - ~$17, needs ~$1.7k collateral
    "F",     # Ford - ~$10, needs ~$1k collateral
    "BAC",   # Bank of America - ~$47, needs ~$4.7k collateral
    "T",     # AT&T - ~$23, needs ~$2.3k collateral
    "INTC",  # Intel - ~$20, needs ~$2k collateral
]


def get_rag_sentiment(ticker: str) -> dict:
    """
    Query RAG for sentiment on a ticker.

    Uses lightweight_rag to search for recent news/analysis.
    Returns bullish/bearish/neutral sentiment.
    """
    try:
        from src.rag.lightweight_rag import get_singleton_rag

        rag = get_singleton_rag()

        # Query for recent sentiment
        results = rag.query(
            query_text=f"{ticker} stock outlook sentiment bullish bearish",
            n_results=5,
            where={"ticker": ticker} if ticker else None,
        )

        if not results.get("documents"):
            return {"sentiment": "NEUTRAL", "confidence": 0.0, "reason": "No RAG data"}

        # Simple sentiment analysis from document content
        docs = " ".join(results.get("documents", [])).lower()

        bullish_words = ["bullish", "buy", "upgrade", "strong", "growth", "beat", "positive"]
        bearish_words = ["bearish", "sell", "downgrade", "weak", "decline", "miss", "negative"]

        bullish_count = sum(1 for w in bullish_words if w in docs)
        bearish_count = sum(1 for w in bearish_words if w in docs)

        total = bullish_count + bearish_count
        if total == 0:
            return {"sentiment": "NEUTRAL", "confidence": 0.0, "reason": "No clear sentiment"}

        if bullish_count > bearish_count:
            confidence = bullish_count / total
            return {"sentiment": "BULLISH", "confidence": confidence, "reason": f"{bullish_count} bullish signals"}
        elif bearish_count > bullish_count:
            confidence = bearish_count / total
            return {"sentiment": "BEARISH", "confidence": confidence, "reason": f"{bearish_count} bearish signals"}
        else:
            return {"sentiment": "NEUTRAL", "confidence": 0.5, "reason": "Mixed signals"}

    except Exception as e:
        logger.warning(f"RAG query failed for {ticker}: {e}")
        return {"sentiment": "NEUTRAL", "confidence": 0.0, "reason": f"Error: {e}"}


def get_iv_percentile(symbol: str) -> dict:
    """
    Calculate IV Percentile using historical volatility as proxy.

    Returns dict with iv_percentile, recommendation (SELL_PREMIUM/NEUTRAL/AVOID)
    """
    try:
        import numpy as np
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y")

        if len(hist) < 20:
            return {"iv_percentile": 50, "recommendation": "NEUTRAL", "error": "Insufficient data"}

        returns = np.log(hist["Close"] / hist["Close"].shift(1))
        rolling_vol = returns.rolling(window=20).std() * np.sqrt(252) * 100

        current_hv = rolling_vol.iloc[-1]
        valid_vols = rolling_vol.dropna()
        iv_percentile = (valid_vols < current_hv).sum() / len(valid_vols) * 100

        if iv_percentile >= 50:
            recommendation = "SELL_PREMIUM"
        elif iv_percentile >= 30:
            recommendation = "NEUTRAL"
        else:
            recommendation = "AVOID"

        return {
            "iv_percentile": round(iv_percentile, 1),
            "current_hv": round(current_hv, 2),
            "recommendation": recommendation,
        }

    except Exception as e:
        logger.warning(f"IV calculation failed for {symbol}: {e}")
        return {"iv_percentile": 50, "recommendation": "NEUTRAL", "error": str(e)}


def get_current_price(symbol: str) -> float:
    """Get current price of a symbol."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if data.empty:
            return 0.0
        return float(data["Close"].iloc[-1])
    except Exception:
        return 0.0


def check_earnings(symbol: str) -> dict:
    """
    Check if there's an earnings announcement within 7 days.

    Per RAG knowledge: Avoid selling options before earnings due to:
    - IV crush after announcement
    - Gap risk
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        calendar = ticker.calendar

        if calendar is None or calendar.empty:
            return {"has_earnings_soon": False, "earnings_date": None, "days_to_earnings": None}

        # Get next earnings date
        earnings_date = None
        if "Earnings Date" in calendar.columns:
            earnings_dates = calendar["Earnings Date"]
            if len(earnings_dates) > 0:
                earnings_date = earnings_dates.iloc[0]

        if earnings_date is None:
            return {"has_earnings_soon": False, "earnings_date": None, "days_to_earnings": None}

        # Calculate days to earnings
        today = datetime.now().date()
        if hasattr(earnings_date, "date"):
            earnings_date = earnings_date.date()

        days_to_earnings = (earnings_date - today).days

        return {
            "has_earnings_soon": 0 <= days_to_earnings <= 7,
            "earnings_date": str(earnings_date),
            "days_to_earnings": days_to_earnings,
        }

    except Exception as e:
        logger.warning(f"Earnings check failed for {symbol}: {e}")
        return {"has_earnings_soon": False, "earnings_date": None, "error": str(e)}


def get_trend(symbol: str) -> dict:
    """
    Check market trend using 20-day MA slope.

    Per RAG knowledge (backtest results):
    - All 5 losses came from entering in strong downtrends
    - Avoid selling puts when slope < -0.5% per day AND price < -5% below MA
    """
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2mo")

        if len(hist) < 20:
            return {"trend": "NEUTRAL", "slope": 0, "recommendation": "PROCEED"}

        ma_20 = hist["Close"].rolling(window=20).mean()
        recent_ma = ma_20.iloc[-5:]
        slope = (recent_ma.iloc[-1] - recent_ma.iloc[0]) / recent_ma.iloc[0] * 100 / 5

        current_price = hist["Close"].iloc[-1]
        ma_current = ma_20.iloc[-1]
        price_vs_ma = (current_price - ma_current) / ma_current * 100

        if slope < -0.5 and price_vs_ma < -5:
            trend = "STRONG_DOWNTREND"
            recommendation = "AVOID"
        elif slope < -0.3:
            trend = "MODERATE_DOWNTREND"
            recommendation = "CAUTION"
        else:
            trend = "UPTREND_OR_SIDEWAYS"
            recommendation = "PROCEED"

        return {
            "trend": trend,
            "slope": round(slope, 4),
            "price_vs_ma": round(price_vs_ma, 2),
            "recommendation": recommendation,
        }

    except Exception as e:
        logger.warning(f"Trend check failed for {symbol}: {e}")
        return {"trend": "UNKNOWN", "slope": 0, "recommendation": "PROCEED", "error": str(e)}


def get_options_book_recommendation(iv_percentile: float) -> dict:
    """
    Get strategy recommendation from McMillan options knowledge.

    Uses OptionsBookRetriever for IV-based guidance.
    """
    try:
        from src.rag.options_book_retriever import get_options_book_retriever

        retriever = get_options_book_retriever()
        regime = retriever.get_iv_regime(iv_percentile)

        return {
            "regime": regime.get("regime"),
            "guidance": regime.get("guidance"),
            "allowed_strategies": regime.get("allowed_strategies", []),
        }

    except Exception as e:
        logger.warning(f"Options book retrieval failed: {e}")
        return {"regime": "unknown", "guidance": "Error", "error": str(e)}


def screen_tickers(
    universe: list[str] = None,
    buying_power: float = 10000,
    max_tickers: int = 5,
) -> list[dict]:
    """
    Screen tickers using RAG knowledge and market data.

    Args:
        universe: List of tickers to screen (default: DEFAULT_UNIVERSE)
        buying_power: Available buying power for collateral
        max_tickers: Maximum tickers to return

    Returns:
        List of ticker dicts with screening results, sorted by score
    """
    if universe is None:
        universe = DEFAULT_UNIVERSE

    logger.info(f"🔍 Screening {len(universe)} tickers with buying power ${buying_power:,.2f}")
    logger.info("=" * 60)

    candidates = []

    for ticker in universe:
        logger.info(f"\n📊 Screening {ticker}...")

        # 1. Get current price and check collateral
        price = get_current_price(ticker)
        if price <= 0:
            logger.warning(f"   ❌ Could not get price for {ticker}")
            continue

        collateral_required = price * 100  # 100 shares for CSP

        if collateral_required > buying_power:
            logger.info(f"   ⚠️ Skipping: Collateral ${collateral_required:,.0f} > buying power ${buying_power:,.0f}")
            continue

        logger.info(f"   💵 Price: ${price:.2f}, Collateral: ${collateral_required:,.0f}")

        # 2. Check IV percentile
        iv_data = get_iv_percentile(ticker)
        iv_pct = iv_data.get("iv_percentile", 50)
        logger.info(f"   📈 IV Percentile: {iv_pct:.1f}% ({iv_data.get('recommendation', 'NEUTRAL')})")

        if iv_data.get("recommendation") == "AVOID":
            logger.info(f"   ⚠️ Low IV ({iv_pct:.1f}%) - less favorable for selling premium")
            # Don't skip, just lower score

        # 3. Check earnings
        earnings = check_earnings(ticker)
        if earnings.get("has_earnings_soon"):
            logger.warning(f"   ❌ Skipping: Earnings in {earnings.get('days_to_earnings')} days")
            continue

        # 4. Check trend
        trend = get_trend(ticker)
        if trend.get("recommendation") == "AVOID":
            logger.warning(f"   ❌ Skipping: Strong downtrend (slope: {trend.get('slope')}%/day)")
            continue

        logger.info(f"   📉 Trend: {trend.get('trend')} (slope: {trend.get('slope'):.3f}%/day)")

        # 5. Get RAG sentiment
        sentiment = get_rag_sentiment(ticker)
        logger.info(f"   🎯 Sentiment: {sentiment.get('sentiment')} ({sentiment.get('reason')})")

        if sentiment.get("sentiment") == "BEARISH" and sentiment.get("confidence", 0) > 0.7:
            logger.info(f"   ⚠️ Strong bearish sentiment - proceeding with caution")
            # Don't skip for cash-secured puts (we want to buy the stock), just note it

        # 6. Get McMillan recommendation
        book_rec = get_options_book_recommendation(iv_pct)

        # Calculate composite score
        score = 0

        # IV score (0-40 points): Higher IV = better for selling
        iv_score = min(iv_pct, 100) * 0.4
        score += iv_score

        # Trend score (0-30 points): Better trend = more points
        if trend.get("recommendation") == "PROCEED":
            trend_score = 30
        elif trend.get("recommendation") == "CAUTION":
            trend_score = 15
        else:
            trend_score = 0
        score += trend_score

        # Sentiment score (0-20 points)
        sent = sentiment.get("sentiment", "NEUTRAL")
        conf = sentiment.get("confidence", 0)
        if sent == "BULLISH":
            sentiment_score = 20 * conf
        elif sent == "NEUTRAL":
            sentiment_score = 10
        else:  # BEARISH - still OK for CSPs (we want to own the stock)
            sentiment_score = 5 * (1 - conf)
        score += sentiment_score

        # Collateral efficiency (0-10 points): Lower relative to buying power = better
        collateral_pct = collateral_required / buying_power
        collateral_score = max(0, 10 * (1 - collateral_pct))
        score += collateral_score

        logger.info(f"   ✅ Score: {score:.1f}/100 (IV:{iv_score:.0f}, Trend:{trend_score:.0f}, Sent:{sentiment_score:.0f}, Coll:{collateral_score:.0f})")

        candidates.append({
            "ticker": ticker,
            "price": round(price, 2),
            "collateral": round(collateral_required, 0),
            "iv_percentile": iv_pct,
            "iv_recommendation": iv_data.get("recommendation"),
            "trend": trend.get("trend"),
            "trend_slope": trend.get("slope"),
            "sentiment": sentiment.get("sentiment"),
            "sentiment_confidence": sentiment.get("confidence"),
            "mcmillan_regime": book_rec.get("regime"),
            "score": round(score, 1),
        })

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Return top N
    selected = candidates[:max_tickers]

    logger.info("\n" + "=" * 60)
    logger.info(f"🏆 TOP {len(selected)} TICKERS FOR OPTIONS TRADING")
    logger.info("=" * 60)
    for i, c in enumerate(selected, 1):
        logger.info(f"   {i}. {c['ticker']} - Score: {c['score']:.1f}/100")
        logger.info(f"      IV: {c['iv_percentile']:.1f}%, Trend: {c['trend']}, Sentiment: {c['sentiment']}")

    return selected


def main():
    parser = argparse.ArgumentParser(description="RAG-based ticker screener for options")
    parser.add_argument("--buying-power", type=float, default=10000, help="Available buying power")
    parser.add_argument("--max-tickers", type=int, default=5, help="Max tickers to return")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--universe", type=str, help="Comma-separated ticker list (overrides default)")
    args = parser.parse_args()

    universe = None
    if args.universe:
        universe = [t.strip().upper() for t in args.universe.split(",")]

    results = screen_tickers(
        universe=universe,
        buying_power=args.buying_power,
        max_tickers=args.max_tickers,
    )

    if args.output == "json":
        print(json.dumps(results, indent=2))
    else:
        # Text output - just the tickers for shell scripting
        tickers = ",".join(r["ticker"] for r in results)
        print(f"\n📋 Selected tickers: {tickers}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
