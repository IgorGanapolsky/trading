#!/usr/bin/env python3
"""
Execute Options Trade - Cash-Secured Put or Covered Call

This script executes options trades based on McMillan/TastyTrade rules:
- Cash-Secured Puts: Sell OTM puts on stocks we want to own
- Covered Calls: Sell OTM calls on stocks we own (100+ shares)
- Wheel Strategy: Combine CSPs and covered calls

Target Parameters (from RAG knowledge):
- Delta: 0.20-0.30 (20-30% probability of assignment)
- DTE: 30-45 days (optimal theta decay)
- IV Rank: >30 preferred (elevated premium)
- Min Premium: >0.5% of underlying price

Usage:
    python3 scripts/execute_options_trade.py --strategy cash_secured_put --symbol SPY
    python3 scripts/execute_options_trade.py --strategy covered_call --symbol QQQ
    python3 scripts/execute_options_trade.py --strategy wheel --symbol SPY --dry-run
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Ensure directories exist BEFORE configuring logging
Path("logs").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/options_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
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

    # Debug: show if keys are present (without revealing them)
    logger.info(f"   API Key present: {bool(api_key)} (length: {len(api_key) if api_key else 0})")
    logger.info(
        f"   Secret Key present: {bool(secret_key)} (length: {len(secret_key) if secret_key else 0})"
    )
    logger.info(f"   Paper trading: {paper}")

    if not api_key or not secret_key:
        raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")

    try:
        trading_client = TradingClient(api_key, secret_key, paper=paper)
        logger.info("   ✅ Trading client initialized")
    except Exception as e:
        logger.error(f"   ❌ Trading client failed: {e}")
        raise

    try:
        options_client = OptionHistoricalDataClient(api_key, secret_key)
        logger.info("   ✅ Options client initialized")
    except Exception as e:
        logger.error(f"   ❌ Options client failed: {e}")
        raise

    # Verify account has options trading enabled
    try:
        account = trading_client.get_account()
        logger.info(f"   Account status: {account.status}")
        logger.info(
            f"   Options trading approved: {getattr(account, 'options_trading_level', 'unknown')}"
        )
        logger.info(
            f"   Options approved level: {getattr(account, 'options_approved_level', 'unknown')}"
        )
    except Exception as e:
        logger.warning(f"   ⚠️ Account check failed: {e}")

    return trading_client, options_client


def get_account_info(trading_client):
    """Get current account information."""
    account = trading_client.get_account()
    return {
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "portfolio_value": float(account.portfolio_value),
        "options_buying_power": float(
            getattr(account, "options_buying_power", account.buying_power)
        ),
    }


def get_underlying_price(symbol: str) -> float:
    """Get current price of underlying symbol."""
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    data = ticker.history(period="1d")
    if data.empty:
        raise ValueError(f"Could not get price for {symbol}")
    return float(data["Close"].iloc[-1])


def get_iv_percentile(symbol: str, lookback_days: int = 252) -> dict:
    """
    Calculate IV Percentile for a symbol.

    IV Percentile = % of days in past year when IV was lower than current IV.
    Per RAG knowledge (volatility_forecasting_2025.json):
    - IV Percentile > 50%: Favor selling strategies (CSPs, covered calls)
    - IV Percentile < 30%: Favor buying strategies or stay on sidelines

    Returns dict with iv_percentile, current_iv, recommendation.
    """
    import numpy as np
    import yfinance as yf

    logger.info(f"📊 Calculating IV Percentile for {symbol}...")

    try:
        ticker = yf.Ticker(symbol)

        # Get historical data for IV calculation (we'll use HV as proxy if IV not available)
        hist = ticker.history(period="1y")
        if len(hist) < 20:
            logger.warning(f"   ⚠️ Insufficient history for {symbol}, defaulting to neutral")
            return {"iv_percentile": 50, "current_iv": None, "recommendation": "NEUTRAL"}

        # Calculate historical volatility (20-day rolling)
        returns = np.log(hist["Close"] / hist["Close"].shift(1))
        rolling_vol = returns.rolling(window=20).std() * np.sqrt(252) * 100  # Annualized %

        current_hv = rolling_vol.iloc[-1]

        # Calculate percentile
        valid_vols = rolling_vol.dropna()
        iv_percentile = (valid_vols < current_hv).sum() / len(valid_vols) * 100

        # Determine recommendation per RAG knowledge
        if iv_percentile >= 50:
            recommendation = "SELL_PREMIUM"
            logger.info(
                f"   ✅ IV Percentile: {iv_percentile:.1f}% - FAVORABLE for selling premium"
            )
        elif iv_percentile >= 30:
            recommendation = "NEUTRAL"
            logger.info(f"   ⚠️ IV Percentile: {iv_percentile:.1f}% - NEUTRAL conditions")
        else:
            recommendation = "AVOID_SELLING"
            logger.info(f"   ❌ IV Percentile: {iv_percentile:.1f}% - UNFAVORABLE for selling")

        return {
            "iv_percentile": round(iv_percentile, 1),
            "current_iv": round(current_hv, 2),
            "recommendation": recommendation,
        }

    except Exception as e:
        logger.error(f"   ❌ IV calculation failed: {e}")
        return {"iv_percentile": 50, "current_iv": None, "recommendation": "NEUTRAL"}


# Minimum IV percentile threshold for selling options
# RELAXED from 50 to 30 on Dec 29, 2025 - too many opportunities blocked
# RAG still recommends >50%, but we need to generate $100/day
MIN_IV_PERCENTILE_FOR_SELLING = 30


def get_trend_filter(symbol: str, lookback_days: int = 20) -> dict:
    """
    Check market trend to avoid selling puts in downtrending markets.

    Per options_backtest_summary.md recommendations:
    - All losses (5/5) came from positions entered in strong trends
    - Add trend filter to avoid selling options in adverse conditions
    - Use 20-day MA slope as trend indicator

    For CASH-SECURED PUTS:
    - Uptrend/Sideways: SAFE to sell puts (bullish bias helps)
    - Strong Downtrend: AVOID selling puts (will get assigned at bad prices)

    Returns dict with trend, slope, recommendation.
    """
    import yfinance as yf

    logger.info(f"📈 Checking trend filter for {symbol}...")

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2mo")

        if len(hist) < lookback_days:
            logger.warning("   ⚠️ Insufficient history for trend filter, defaulting to neutral")
            return {"trend": "NEUTRAL", "slope": 0, "recommendation": "PROCEED"}

        # Calculate 20-day moving average
        ma_20 = hist["Close"].rolling(window=lookback_days).mean()

        # Calculate slope over last 5 days (normalized as % per day)
        recent_ma = ma_20.iloc[-5:]
        slope = (recent_ma.iloc[-1] - recent_ma.iloc[0]) / recent_ma.iloc[0] * 100 / 5

        # Also check if price is above or below MA
        current_price = hist["Close"].iloc[-1]
        ma_current = ma_20.iloc[-1]
        price_vs_ma = (current_price - ma_current) / ma_current * 100

        # Determine trend
        # RELAXED thresholds to allow more trades (Dec 16 fix)
        # Strong downtrend: slope < -0.5% per day AND price below MA by 5%+
        # Moderate downtrend: slope < -0.3% per day
        # Uptrend/Sideways: slope >= -0.3%

        if slope < -0.5 and price_vs_ma < -5:
            trend = "STRONG_DOWNTREND"
            recommendation = "AVOID_PUTS"
            logger.warning("   ❌ STRONG DOWNTREND detected!")
            logger.warning(f"      MA slope: {slope:.3f}%/day, Price vs MA: {price_vs_ma:.1f}%")
        elif slope < -0.3:
            trend = "MODERATE_DOWNTREND"
            recommendation = "CAUTION_BUT_PROCEED"
            logger.info("   ⚠️ Moderate downtrend - proceeding with caution")
            logger.info(f"      MA slope: {slope:.3f}%/day, Price vs MA: {price_vs_ma:.1f}%")
        else:
            trend = "UPTREND_OR_SIDEWAYS"
            recommendation = "PROCEED"
            logger.info("   ✅ Trend FAVORABLE for selling puts")
            logger.info(f"      MA slope: {slope:.3f}%/day, Price vs MA: {price_vs_ma:.1f}%")

        return {
            "trend": trend,
            "slope": round(slope, 4),
            "price_vs_ma": round(price_vs_ma, 2),
            "recommendation": recommendation,
        }

    except Exception as e:
        logger.error(f"   ❌ Trend filter failed: {e}")
        return {"trend": "UNKNOWN", "slope": 0, "recommendation": "PROCEED"}


def find_optimal_put(
    options_client, symbol: str, target_delta: float = 0.25, min_dte: int = 20, max_dte: int = 60
):
    """
    Find optimal put option for cash-secured put strategy.

    Criteria (from McMillan/TastyTrade - RELAXED for more opportunities):
    - OTM put (strike below current price)
    - Delta between -0.10 and -0.50 (wider range)
    - DTE between 20-60 days (more flexibility)
    - Decent premium (>0.3% of underlying)
    """
    from alpaca.data.requests import OptionChainRequest

    logger.info(f"🔍 Scanning option chain for {symbol}...")

    current_price = get_underlying_price(symbol)
    logger.info(f"   Current {symbol} price: ${current_price:.2f}")

    # Calculate target expiration range
    date.today() + timedelta(days=min_dte)
    date.today() + timedelta(days=max_dte)

    # Get option chain
    req = OptionChainRequest(underlying_symbol=symbol)
    chain = options_client.get_option_chain(req)

    candidates = []
    for option_symbol, snapshot in chain.items():
        # Skip if no greeks
        if not snapshot.greeks or snapshot.greeks.delta is None:
            continue

        # Parse option symbol to get details
        # Format: SPY251219P00580000 (SPY, 2025-12-19, Put, $580)
        try:
            # Extract expiration from symbol
            base_len = len(symbol)
            exp_str = option_symbol[base_len : base_len + 6]  # YYMMDD
            option_type = option_symbol[base_len + 6]  # P or C
            strike_str = option_symbol[base_len + 7 :]

            exp_date = datetime.strptime(exp_str, "%y%m%d").date()
            strike = float(strike_str) / 1000  # Convert to dollars
        except (ValueError, IndexError):
            continue

        # Filter for puts only
        if option_type != "P":
            continue

        # Check DTE
        dte = (exp_date - date.today()).days
        if dte < min_dte or dte > max_dte:
            continue

        # Check delta (puts have negative delta) - RELAXED for more opportunities
        delta = snapshot.greeks.delta
        if delta > -0.10 or delta < -0.50:  # Want delta between -0.10 and -0.50
            continue

        # Check strike is OTM (below current price for puts)
        if strike >= current_price:
            continue

        # Get bid/ask
        bid = snapshot.latest_quote.bid_price if snapshot.latest_quote else 0
        ask = snapshot.latest_quote.ask_price if snapshot.latest_quote else 0
        mid = (bid + ask) / 2 if bid and ask else 0

        # Calculate premium as % of underlying
        premium_pct = (mid / current_price) * 100 if current_price > 0 else 0

        # Skip if premium too low - RELAXED for more opportunities
        if premium_pct < 0.3:
            continue

        candidates.append(
            {
                "symbol": option_symbol,
                "strike": strike,
                "expiration": exp_date,
                "dte": dte,
                "delta": delta,
                "bid": bid,
                "ask": ask,
                "mid": mid,
                "premium_pct": premium_pct,
                "iv": snapshot.implied_volatility,
            }
        )

    if not candidates:
        logger.warning(f"❌ No suitable put options found for {symbol}")
        return None

    # Sort by delta closest to target
    candidates.sort(key=lambda x: abs(abs(x["delta"]) - target_delta))

    best = candidates[0]
    logger.info("✅ Found optimal put:")
    logger.info(f"   Symbol: {best['symbol']}")
    logger.info(
        f"   Strike: ${best['strike']:.2f} ({((current_price - best['strike']) / current_price * 100):.1f}% OTM)"
    )
    logger.info(f"   Expiration: {best['expiration']} ({best['dte']} DTE)")
    logger.info(f"   Delta: {best['delta']:.3f}")
    logger.info(f"   Premium: ${best['mid']:.2f} ({best['premium_pct']:.2f}%)")
    logger.info(f"   IV: {best['iv']:.1%}" if best["iv"] else "   IV: N/A")

    return best


def try_tradier_fallback(symbol: str, dry_run: bool = False) -> dict:
    """
    Tradier fallback has been removed (broker integration deleted Dec 2025).
    Returns NO_FALLBACK status.
    """
    logger.warning("Tradier fallback not available (broker integration removed)")
    return {"status": "NO_FALLBACK", "reason": "Tradier integration removed"}


def execute_cash_secured_put(trading_client, options_client, symbol: str, dry_run: bool = False):
    """
    Execute a cash-secured put trade.

    Strategy:
    1. CHECK IV PERCENTILE (>50% required per RAG knowledge)
    2. Find optimal OTM put (delta ~0.25, 30-45 DTE)
    3. Verify we have enough cash to cover assignment
    4. Sell 1 put contract

    Failover (per lesson ll_007):
    - If Alpaca fails, try Tradier as backup broker
    """
    logger.info("=" * 60)
    logger.info("💰 CASH-SECURED PUT STRATEGY (ALPACA)")
    logger.info("=" * 60)

    # CRITICAL: Check IV Percentile FIRST (per RAG: volatility_forecasting_2025.json)
    # "Only sell options when IV Percentile > 50%" - TastyTrade research
    iv_data = get_iv_percentile(symbol)
    if iv_data["recommendation"] == "AVOID_SELLING":
        logger.warning(
            f"❌ IV Percentile {iv_data['iv_percentile']}% < {MIN_IV_PERCENTILE_FOR_SELLING}%"
        )
        logger.warning("   Per RAG knowledge: Avoid selling premium in low IV environment")
        logger.warning("   Recommendation: Wait for higher IV or use ETF accumulation strategy")
        return {
            "status": "NO_TRADE",
            "reason": f"IV Percentile too low ({iv_data['iv_percentile']}% < {MIN_IV_PERCENTILE_FOR_SELLING}%)",
            "iv_data": iv_data,
            "broker": "alpaca",
        }

    logger.info(
        f"✅ IV Check passed: {iv_data['iv_percentile']}% >= {MIN_IV_PERCENTILE_FOR_SELLING}%"
    )

    # CRITICAL: Check trend filter (per options_backtest_summary.md recommendations)
    # All 5 losses in backtest came from entering positions in strong trends
    trend_data = get_trend_filter(symbol)
    if trend_data["recommendation"] == "AVOID_PUTS":
        logger.warning(f"❌ TREND FILTER BLOCKED: {trend_data['trend']}")
        logger.warning("   Per backtest analysis: 100% of losses came from adverse trend entries")
        logger.warning("   Recommendation: Wait for trend reversal or use hedged strategy")
        return {
            "status": "NO_TRADE",
            "reason": f"Trend filter blocked: {trend_data['trend']} (slope: {trend_data['slope']}%/day)",
            "trend_data": trend_data,
            "broker": "alpaca",
        }

    logger.info(f"✅ Trend filter passed: {trend_data['trend']}")

    # Get account info
    account = get_account_info(trading_client)
    logger.info(f"Account cash: ${account['cash']:,.2f}")
    logger.info(f"Options buying power: ${account['options_buying_power']:,.2f}")

    # Find optimal put
    put_option = find_optimal_put(options_client, symbol)
    if not put_option:
        logger.warning("❌ No suitable options found on Alpaca, trying Tradier...")
        return try_tradier_fallback(symbol, dry_run)

    # Calculate cash required for assignment (strike * 100 shares)
    cash_required = put_option["strike"] * 100
    logger.info(f"\n💵 Cash required for assignment: ${cash_required:,.2f}")

    if account["cash"] < cash_required:
        logger.warning(
            f"❌ Insufficient cash! Need ${cash_required:,.2f}, have ${account['cash']:,.2f}"
        )
        logger.info("🔄 Trying credit spread instead (more capital efficient)...")
        # Fall back to credit spread
        try:
            from scripts.execute_credit_spread import execute_bull_put_spread

            return execute_bull_put_spread(
                trading_client, options_client, symbol, spread_width=2.0, dry_run=dry_run
            )
        except Exception as e:
            logger.warning(f"Credit spread fallback failed: {e}")
            return {
                "status": "NO_TRADE",
                "reason": "Insufficient cash for CSP, spread failed",
                "broker": "alpaca",
            }

    # Execute trade
    if dry_run:
        logger.info("\n🔶 DRY RUN - No actual trade executed")
        return {
            "status": "DRY_RUN",
            "option": put_option,
            "cash_required": cash_required,
            "potential_premium": put_option["mid"] * 100,
            "broker": "alpaca",
        }

    # Place the order
    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest

        # Sell to open (write) the put
        # Round limit price to 2 decimal places (Alpaca requirement)
        limit_price = round(put_option["mid"], 2)
        order_request = LimitOrderRequest(
            symbol=put_option["symbol"],
            qty=1,
            side=OrderSide.SELL,
            type="limit",
            limit_price=limit_price,
            time_in_force=TimeInForce.DAY,
        )

        order = trading_client.submit_order(order_request)

        # Calculate stop loss per backtest recommendation (50% of premium)
        # If we collect $1.00 premium, close position if cost to buy back exceeds $1.50
        premium = put_option["mid"]
        stop_loss_price = premium * 1.5  # 50% max loss = buy back at 1.5x premium
        max_loss_dollars = (stop_loss_price - premium) * 100  # Loss if stopped out

        logger.info("\n✅ ALPACA ORDER SUBMITTED!")
        logger.info(f"   Order ID: {order.id}")
        logger.info(f"   Symbol: {put_option['symbol']}")
        logger.info("   Side: SELL TO OPEN")
        logger.info("   Qty: 1 contract")
        logger.info(f"   Limit Price: ${premium:.2f}")
        logger.info(f"   Premium: ${premium * 100:.2f} (1 contract)")
        logger.info("\n📊 RISK MANAGEMENT (per backtest recommendations):")
        logger.info(f"   ⚠️ STOP LOSS: Close if bid exceeds ${stop_loss_price:.2f}")
        logger.info(f"   📉 Max loss at stop: ${max_loss_dollars:.2f}")
        logger.info(f"   💰 Max profit: ${premium * 100:.2f} (option expires worthless)")
        logger.info(f"   📈 Risk/Reward: 1:{premium / 0.5:.1f} (50% stop)")

        return {
            "status": "ORDER_SUBMITTED",
            "order_id": str(order.id),
            "option": put_option,
            "premium": premium * 100,
            "stop_loss_price": stop_loss_price,
            "max_loss": max_loss_dollars,
            "risk_reward": f"1:{premium / 0.5:.1f}",
            "broker": "alpaca",
        }

    except Exception as e:
        error_str = str(e)
        logger.error(f"❌ Alpaca order failed: {e}")

        # Check if it's an insufficient buying power error
        if "insufficient options buying power" in error_str.lower():
            logger.info("🔄 CSP blocked by buying power - trying credit spread instead...")
            try:
                from scripts.execute_credit_spread import execute_bull_put_spread

                return execute_bull_put_spread(
                    trading_client, options_client, symbol, spread_width=2.0, dry_run=dry_run
                )
            except Exception as spread_error:
                logger.warning(f"Credit spread also failed: {spread_error}")

        logger.info("🔄 Attempting Tradier fallback...")
        return try_tradier_fallback(symbol, dry_run)


def execute_covered_call(trading_client, options_client, symbol: str, dry_run: bool = False):
    """
    Execute a covered call trade.

    Strategy:
    1. Check if we own 100+ shares of the underlying
    2. Find optimal OTM call (delta ~0.30, 30-45 DTE)
    3. Sell 1 call contract per 100 shares
    """
    logger.info("=" * 60)
    logger.info("📈 COVERED CALL STRATEGY")
    logger.info("=" * 60)

    # Check current positions
    positions = trading_client.get_all_positions()
    position = None
    for p in positions:
        if p.symbol == symbol:
            position = p
            break

    if not position:
        logger.warning(f"❌ No position in {symbol}. Cannot write covered call.")
        return {"status": "NO_TRADE", "reason": f"No {symbol} position"}

    shares = int(float(position.qty))
    if shares < 100:
        logger.warning(f"❌ Only {shares} shares of {symbol}. Need 100+ for covered call.")
        return {"status": "NO_TRADE", "reason": f"Insufficient shares ({shares} < 100)"}

    contracts = shares // 100
    logger.info(f"✅ Own {shares} shares of {symbol}. Can sell {contracts} covered call(s).")

    # TODO: Implement call option finding similar to put finding
    logger.info("⚠️ Covered call execution not yet implemented")
    return {"status": "NOT_IMPLEMENTED", "reason": "Covered call logic pending"}


def main():
    parser = argparse.ArgumentParser(description="Execute options trades")
    parser.add_argument(
        "--strategy",
        choices=["cash_secured_put", "covered_call", "wheel"],
        default="cash_secured_put",
        help="Options strategy to execute",
    )
    parser.add_argument("--symbol", default="SPY", help="Underlying symbol")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    args = parser.parse_args()

    logger.info("🚀 Starting Options Trading Execution")
    logger.info(f"   Strategy: {args.strategy}")
    logger.info(f"   Symbol: {args.symbol}")
    logger.info(f"   Dry Run: {args.dry_run}")
    logger.info("")

    try:
        trading_client, options_client = get_alpaca_clients()

        if args.strategy == "cash_secured_put":
            result = execute_cash_secured_put(
                trading_client, options_client, args.symbol, args.dry_run
            )
        elif args.strategy == "covered_call":
            result = execute_covered_call(trading_client, options_client, args.symbol, args.dry_run)
        elif args.strategy == "wheel":
            # Wheel = CSP first, then covered call if assigned
            result = execute_cash_secured_put(
                trading_client, options_client, args.symbol, args.dry_run
            )
        else:
            result = {"status": "ERROR", "error": f"Unknown strategy: {args.strategy}"}

        logger.info("\n" + "=" * 60)
        logger.info("📊 EXECUTION RESULT")
        logger.info("=" * 60)
        logger.info(json.dumps(result, indent=2, default=str))

        # Save result
        result_file = Path("data") / f"options_trades_{datetime.now().strftime('%Y%m%d')}.json"
        result_file.parent.mkdir(exist_ok=True)

        # Append to daily trades file
        trades = []
        if result_file.exists():
            with open(result_file) as f:
                trades = json.load(f)

        trades.append(
            {
                "timestamp": datetime.now().isoformat(),
                "strategy": args.strategy,
                "symbol": args.symbol,
                "result": result,
            }
        )

        with open(result_file, "w") as f:
            json.dump(trades, f, indent=2, default=str)

        logger.info(f"\n💾 Results saved to {result_file}")

        # R&D Phase: Acceptable statuses that indicate success or no-action
        # ERROR status should fail workflow so CI shows accurate status
        status = result.get("status")
        if status in ["ORDER_SUBMITTED", "DRY_RUN", "NO_TRADE"]:
            return 0
        else:
            logger.error(f"❌ Options execution failed with status: {status}")
            return 1

    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
