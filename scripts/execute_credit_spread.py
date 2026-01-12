#!/usr/bin/env python3
"""
Execute Credit Spread - Bull Put Spread for Capital-Efficient Options

PROBLEM SOLVED: Cash-secured puts require full collateral (strike × 100).
With $100k account but 19 positions, options buying power can be <$200.

SOLUTION: Bull Put Spreads require only (spread width × 100) collateral!
- Sell $25 put, buy $23 put = $200 max loss (vs $2,500 for naked CSP)
- 10x more capital efficient
- Still collect premium (though less than CSP)

Target Parameters:
- Spread Width: $2-5 depending on underlying price
- Delta (short leg): 0.20-0.30
- DTE: 30-45 days
- Min Premium: >$0.30 for the spread

Usage:
    python3 scripts/execute_credit_spread.py --symbol SOFI
    python3 scripts/execute_credit_spread.py --symbol F --width 1
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.rag.lessons_learned_rag import LessonsLearnedRAG

Path("logs").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/credit_spread_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
    ],
)
logger = logging.getLogger(__name__)


def get_alpaca_clients():
    """Initialize Alpaca trading and options clients."""
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.trading.client import TradingClient
    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret_key = get_alpaca_credentials()
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"

    if not api_key or not secret_key:
        raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")

    trading_client = TradingClient(api_key, secret_key, paper=paper)
    options_client = OptionHistoricalDataClient(api_key, secret_key)

    return trading_client, options_client


def get_underlying_price(symbol: str) -> float:
    """Get current price of underlying symbol."""
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    data = ticker.history(period="1d")
    if data.empty:
        raise ValueError(f"Could not get price for {symbol}")
    return float(data["Close"].iloc[-1])


def get_iv_percentile(symbol: str) -> dict:
    """Calculate IV Percentile - same as execute_options_trade.py"""
    import numpy as np
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y")
        if len(hist) < 20:
            return {"iv_percentile": 50, "recommendation": "NEUTRAL"}

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
            recommendation = "AVOID_SELLING"

        return {"iv_percentile": round(iv_percentile, 1), "recommendation": recommendation}
    except Exception as e:
        logger.error(f"IV calculation failed: {e}")
        return {"iv_percentile": 50, "recommendation": "NEUTRAL"}


def get_trend_filter(symbol: str) -> dict:
    """Check trend filter - same as execute_options_trade.py"""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2mo")
        if len(hist) < 20:
            return {"trend": "NEUTRAL", "recommendation": "PROCEED"}

        ma_20 = hist["Close"].rolling(window=20).mean()
        recent_ma = ma_20.iloc[-5:]
        slope = (recent_ma.iloc[-1] - recent_ma.iloc[0]) / recent_ma.iloc[0] * 100 / 5
        current_price = hist["Close"].iloc[-1]
        ma_current = ma_20.iloc[-1]
        price_vs_ma = (current_price - ma_current) / ma_current * 100

        if slope < -0.5 and price_vs_ma < -5:
            return {"trend": "STRONG_DOWNTREND", "slope": slope, "recommendation": "AVOID_PUTS"}
        elif slope < -0.3:
            return {"trend": "MODERATE_DOWNTREND", "slope": slope, "recommendation": "CAUTION"}
        else:
            return {"trend": "UPTREND_OR_SIDEWAYS", "slope": slope, "recommendation": "PROCEED"}
    except Exception as e:
        logger.error(f"Trend filter failed: {e}")
        return {"trend": "UNKNOWN", "recommendation": "PROCEED"}


def find_bull_put_spread(
    options_client,
    symbol: str,
    spread_width: float = 2.0,
    target_delta: float = 0.25,
    min_dte: int = 20,
    max_dte: int = 60,
):
    """
    Find optimal bull put spread (sell higher strike put, buy lower strike put).

    Collateral required = spread_width × 100 (NOT full strike × 100!)
    Example: $2 wide spread = $200 collateral (vs $2,500 for $25 CSP)
    """
    from alpaca.data.requests import OptionChainRequest

    logger.info(f"🔍 Scanning for bull put spread on {symbol}...")
    logger.info(f"   Spread width: ${spread_width}")

    current_price = get_underlying_price(symbol)
    logger.info(f"   Current {symbol} price: ${current_price:.2f}")

    req = OptionChainRequest(underlying_symbol=symbol)
    chain = options_client.get_option_chain(req)

    # Group puts by expiration
    puts_by_exp = {}
    for option_symbol, snapshot in chain.items():
        if not snapshot.greeks or snapshot.greeks.delta is None:
            continue

        try:
            base_len = len(symbol)
            exp_str = option_symbol[base_len : base_len + 6]
            option_type = option_symbol[base_len + 6]
            strike_str = option_symbol[base_len + 7 :]

            if option_type != "P":
                continue

            exp_date = datetime.strptime(exp_str, "%y%m%d").date()
            strike = float(strike_str) / 1000
            dte = (exp_date - date.today()).days

            if dte < min_dte or dte > max_dte:
                continue
            if strike >= current_price:  # Only OTM puts
                continue

            bid = snapshot.latest_quote.bid_price if snapshot.latest_quote else 0
            ask = snapshot.latest_quote.ask_price if snapshot.latest_quote else 0
            mid = (bid + ask) / 2 if bid and ask else 0

            if exp_date not in puts_by_exp:
                puts_by_exp[exp_date] = []

            puts_by_exp[exp_date].append(
                {
                    "symbol": option_symbol,
                    "strike": strike,
                    "expiration": exp_date,
                    "dte": dte,
                    "delta": snapshot.greeks.delta,
                    "mid": mid,
                    "bid": bid,
                    "ask": ask,
                }
            )
        except (ValueError, IndexError):
            continue

    # Find best spread
    best_spread = None
    best_score = -float("inf")

    for exp_date, puts in puts_by_exp.items():
        puts.sort(key=lambda x: x["strike"], reverse=True)  # High to low

        for i, short_put in enumerate(puts):
            # Find long put (lower strike) approximately spread_width away
            for long_put in puts[i + 1 :]:
                actual_width = short_put["strike"] - long_put["strike"]

                # Allow some tolerance on spread width
                if actual_width < spread_width * 0.8 or actual_width > spread_width * 1.5:
                    continue

                # Skip if delta is outside target range
                if short_put["delta"] > -0.10 or short_put["delta"] < -0.50:
                    continue

                # Calculate net credit (sell short - buy long)
                net_credit = short_put["mid"] - long_put["mid"]
                if net_credit <= 0.10:  # Need meaningful credit
                    continue

                # Score based on: credit, delta closeness to target, DTE
                delta_score = 1 - abs(abs(short_put["delta"]) - target_delta)
                credit_score = net_credit / actual_width  # Credit as % of max loss
                score = delta_score * 0.3 + credit_score * 0.7

                if score > best_score:
                    best_score = score
                    best_spread = {
                        "short_put": short_put,
                        "long_put": long_put,
                        "spread_width": actual_width,
                        "net_credit": net_credit,
                        "max_loss": actual_width - net_credit,
                        "collateral_required": actual_width * 100,
                        "credit_received": net_credit * 100,
                        "expiration": exp_date,
                        "dte": short_put["dte"],
                    }
                break  # Only check first valid long put per short put

    if not best_spread:
        logger.warning(f"❌ No suitable bull put spread found for {symbol}")
        return None

    logger.info("✅ Found optimal bull put spread:")
    logger.info(
        f"   SELL: {best_spread['short_put']['symbol']} @ ${best_spread['short_put']['mid']:.2f}"
    )
    logger.info(
        f"   BUY:  {best_spread['long_put']['symbol']} @ ${best_spread['long_put']['mid']:.2f}"
    )
    logger.info(f"   Width: ${best_spread['spread_width']:.2f}")
    logger.info(f"   Net Credit: ${best_spread['credit_received']:.2f}")
    logger.info(f"   Max Loss: ${best_spread['max_loss'] * 100:.2f}")
    logger.info(f"   Collateral: ${best_spread['collateral_required']:.2f}")
    logger.info(f"   Expiration: {best_spread['expiration']} ({best_spread['dte']} DTE)")

    return best_spread


def execute_bull_put_spread(
    trading_client, options_client, symbol: str, spread_width: float = 2.0, dry_run: bool = False
):
    """
    Execute a bull put spread.

    Much more capital efficient than cash-secured puts!
    Collateral = spread width × 100 (NOT full strike price)
    """
    # Query RAG for lessons before trading
    logger.info("Checking RAG lessons before execution...")
    rag = LessonsLearnedRAG()

    # Check for strategy-specific failures
    strategy_lessons = rag.search("credit spread bull put spread failures losses", top_k=3)
    for lesson, score in strategy_lessons:
        if lesson.severity == "CRITICAL":
            logger.error(f"BLOCKED by RAG: {lesson.title} (severity: {lesson.severity})")
            logger.error(f"Prevention: {lesson.prevention}")
            return {
                "status": "BLOCKED_BY_RAG",
                "reason": f"Critical lesson: {lesson.title}",
                "lesson_id": lesson.id,
            }

    # Check for ticker-specific failures
    ticker_lessons = rag.search(f"{symbol} trading failures options losses", top_k=3)
    for lesson, score in ticker_lessons:
        if lesson.severity == "CRITICAL":
            logger.error(f"BLOCKED by RAG: {lesson.title} (severity: {lesson.severity})")
            logger.error(f"Prevention: {lesson.prevention}")
            return {
                "status": "BLOCKED_BY_RAG",
                "reason": f"Critical lesson for {symbol}: {lesson.title}",
                "lesson_id": lesson.id,
            }

    logger.info("RAG checks passed - proceeding with execution")

    logger.info("=" * 60)
    logger.info("📊 BULL PUT SPREAD STRATEGY")
    logger.info("=" * 60)
    logger.info(f"Symbol: {symbol}, Spread Width: ${spread_width}")

    # Check IV
    iv_data = get_iv_percentile(symbol)
    if iv_data["recommendation"] == "AVOID_SELLING":
        logger.warning(f"❌ IV Percentile {iv_data['iv_percentile']}% - unfavorable")
        return {"status": "NO_TRADE", "reason": f"IV too low ({iv_data['iv_percentile']}%)"}
    logger.info(f"✅ IV Check: {iv_data['iv_percentile']}%")

    # Check trend
    trend_data = get_trend_filter(symbol)
    if trend_data["recommendation"] == "AVOID_PUTS":
        logger.warning(f"❌ Trend: {trend_data['trend']}")
        return {"status": "NO_TRADE", "reason": f"Trend blocked: {trend_data['trend']}"}
    logger.info(f"✅ Trend: {trend_data['trend']}")

    # Get account info
    account = trading_client.get_account()
    options_bp = float(getattr(account, "options_buying_power", account.buying_power))
    logger.info(f"Options Buying Power: ${options_bp:,.2f}")

    # Find spread
    spread = find_bull_put_spread(options_client, symbol, spread_width)
    if not spread:
        return {"status": "NO_TRADE", "reason": "No suitable spread found"}

    # Check if we have enough buying power
    if options_bp < spread["collateral_required"]:
        logger.error("❌ Insufficient options buying power!")
        logger.error(f"   Need: ${spread['collateral_required']:.2f}")
        logger.error(f"   Have: ${options_bp:.2f}")
        return {
            "status": "INSUFFICIENT_CAPITAL",
            "reason": f"Need ${spread['collateral_required']:.2f}, have ${options_bp:.2f}",
            "spread": spread,
        }

    if dry_run:
        logger.info("\n🔶 DRY RUN - No actual trade")
        return {"status": "DRY_RUN", "spread": spread}

    # Execute the spread (2-leg order)
    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest

        # SELL the higher strike put (short leg)
        short_order = LimitOrderRequest(
            symbol=spread["short_put"]["symbol"],
            qty=1,
            side=OrderSide.SELL,
            type="limit",
            limit_price=round(spread["short_put"]["mid"], 2),
            time_in_force=TimeInForce.DAY,
        )

        # BUY the lower strike put (long leg)
        long_order = LimitOrderRequest(
            symbol=spread["long_put"]["symbol"],
            qty=1,
            side=OrderSide.BUY,
            type="limit",
            limit_price=round(spread["long_put"]["mid"], 2),
            time_in_force=TimeInForce.DAY,
        )

        # Submit orders
        short_result = trading_client.submit_order(short_order)
        long_result = trading_client.submit_order(long_order)

        logger.info("\n✅ SPREAD ORDER SUBMITTED!")
        logger.info(f"   Short Leg: {short_result.id}")
        logger.info(f"   Long Leg: {long_result.id}")
        logger.info(f"   Net Credit: ${spread['credit_received']:.2f}")
        logger.info(f"   Max Loss: ${spread['max_loss'] * 100:.2f}")
        logger.info(f"   Collateral Used: ${spread['collateral_required']:.2f}")

        return {
            "status": "ORDER_SUBMITTED",
            "short_order_id": str(short_result.id),
            "long_order_id": str(long_result.id),
            "spread": spread,
        }

    except Exception as e:
        logger.error(f"❌ Order failed: {e}")
        return {"status": "ERROR", "error": str(e), "spread": spread}


def main():
    parser = argparse.ArgumentParser(description="Execute bull put spread")
    parser.add_argument("--symbol", default="SOFI", help="Underlying symbol")
    parser.add_argument("--width", type=float, default=2.0, help="Spread width in $")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    args = parser.parse_args()

    logger.info("🚀 Credit Spread Execution")
    logger.info(f"   Symbol: {args.symbol}")
    logger.info(f"   Width: ${args.width}")
    logger.info("")

    try:
        trading_client, options_client = get_alpaca_clients()
        result = execute_bull_put_spread(
            trading_client, options_client, args.symbol, args.width, args.dry_run
        )

        logger.info("\n" + "=" * 60)
        logger.info("📊 RESULT")
        logger.info("=" * 60)
        logger.info(json.dumps(result, indent=2, default=str))

        # Save result
        result_file = Path("data") / f"credit_spreads_{datetime.now().strftime('%Y%m%d')}.json"
        trades = []
        if result_file.exists():
            with open(result_file) as f:
                trades = json.load(f)
        trades.append(
            {
                "timestamp": datetime.now().isoformat(),
                "symbol": args.symbol,
                "width": args.width,
                "result": result,
            }
        )
        with open(result_file, "w") as f:
            json.dump(trades, f, indent=2, default=str)

        logger.info(f"\n💾 Saved to {result_file}")

        return 0 if result.get("status") in ["ORDER_SUBMITTED", "DRY_RUN", "NO_TRADE"] else 1

    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
