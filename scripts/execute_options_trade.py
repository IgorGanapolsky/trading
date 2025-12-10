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
    from alpaca.data.requests import OptionChainRequest
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"

    # Debug: show if keys are present (without revealing them)
    logger.info(f"   API Key present: {bool(api_key)} (length: {len(api_key) if api_key else 0})")
    logger.info(f"   Secret Key present: {bool(secret_key)} (length: {len(secret_key) if secret_key else 0})")
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
        logger.info(f"   Options trading approved: {getattr(account, 'options_trading_level', 'unknown')}")
        logger.info(f"   Options approved level: {getattr(account, 'options_approved_level', 'unknown')}")
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
        "options_buying_power": float(getattr(account, "options_buying_power", account.buying_power)),
    }


def get_underlying_price(symbol: str) -> float:
    """Get current price of underlying symbol."""
    import yfinance as yf

    ticker = yf.Ticker(symbol)
    data = ticker.history(period="1d")
    if data.empty:
        raise ValueError(f"Could not get price for {symbol}")
    return float(data["Close"].iloc[-1])


def find_optimal_put(options_client, symbol: str, target_delta: float = 0.25, min_dte: int = 30, max_dte: int = 45):
    """
    Find optimal put option for cash-secured put strategy.

    Criteria (from McMillan/TastyTrade):
    - OTM put (strike below current price)
    - Delta between -0.20 and -0.35
    - DTE between 30-45 days
    - Decent premium (>0.5% of underlying)
    """
    from alpaca.data.requests import OptionChainRequest

    logger.info(f"🔍 Scanning option chain for {symbol}...")

    current_price = get_underlying_price(symbol)
    logger.info(f"   Current {symbol} price: ${current_price:.2f}")

    # Calculate target expiration range
    min_exp = date.today() + timedelta(days=min_dte)
    max_exp = date.today() + timedelta(days=max_dte)

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

        # Check delta (puts have negative delta)
        delta = snapshot.greeks.delta
        if delta > -0.15 or delta < -0.40:  # Want delta between -0.15 and -0.40
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

        # Skip if premium too low
        if premium_pct < 0.5:
            continue

        candidates.append({
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
        })

    if not candidates:
        logger.warning(f"❌ No suitable put options found for {symbol}")
        return None

    # Sort by delta closest to target
    candidates.sort(key=lambda x: abs(abs(x["delta"]) - target_delta))

    best = candidates[0]
    logger.info(f"✅ Found optimal put:")
    logger.info(f"   Symbol: {best['symbol']}")
    logger.info(f"   Strike: ${best['strike']:.2f} ({((current_price - best['strike']) / current_price * 100):.1f}% OTM)")
    logger.info(f"   Expiration: {best['expiration']} ({best['dte']} DTE)")
    logger.info(f"   Delta: {best['delta']:.3f}")
    logger.info(f"   Premium: ${best['mid']:.2f} ({best['premium_pct']:.2f}%)")
    logger.info(f"   IV: {best['iv']:.1%}" if best['iv'] else "   IV: N/A")

    return best


def execute_cash_secured_put(trading_client, options_client, symbol: str, dry_run: bool = False):
    """
    Execute a cash-secured put trade.

    Strategy:
    1. Find optimal OTM put (delta ~0.25, 30-45 DTE)
    2. Verify we have enough cash to cover assignment
    3. Sell 1 put contract
    """
    logger.info("=" * 60)
    logger.info("💰 CASH-SECURED PUT STRATEGY")
    logger.info("=" * 60)

    # Get account info
    account = get_account_info(trading_client)
    logger.info(f"Account cash: ${account['cash']:,.2f}")
    logger.info(f"Options buying power: ${account['options_buying_power']:,.2f}")

    # Find optimal put
    put_option = find_optimal_put(options_client, symbol)
    if not put_option:
        return {"status": "NO_TRADE", "reason": "No suitable options found"}

    # Calculate cash required for assignment (strike * 100 shares)
    cash_required = put_option["strike"] * 100
    logger.info(f"\n💵 Cash required for assignment: ${cash_required:,.2f}")

    if account["cash"] < cash_required:
        logger.warning(f"❌ Insufficient cash! Need ${cash_required:,.2f}, have ${account['cash']:,.2f}")
        return {"status": "NO_TRADE", "reason": "Insufficient cash"}

    # Execute trade
    if dry_run:
        logger.info("\n🔶 DRY RUN - No actual trade executed")
        return {
            "status": "DRY_RUN",
            "option": put_option,
            "cash_required": cash_required,
            "potential_premium": put_option["mid"] * 100,
        }

    # Place the order
    try:
        from alpaca.trading.requests import LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        # Sell to open (write) the put
        order_request = LimitOrderRequest(
            symbol=put_option["symbol"],
            qty=1,
            side=OrderSide.SELL,
            type="limit",
            limit_price=put_option["bid"],  # Sell at bid for faster fill
            time_in_force=TimeInForce.DAY,
        )

        order = trading_client.submit_order(order_request)
        logger.info(f"\n✅ ORDER SUBMITTED!")
        logger.info(f"   Order ID: {order.id}")
        logger.info(f"   Symbol: {put_option['symbol']}")
        logger.info(f"   Side: SELL TO OPEN")
        logger.info(f"   Qty: 1 contract")
        logger.info(f"   Limit Price: ${put_option['bid']:.2f}")
        logger.info(f"   Premium: ${put_option['bid'] * 100:.2f} (1 contract)")

        return {
            "status": "ORDER_SUBMITTED",
            "order_id": str(order.id),
            "option": put_option,
            "premium": put_option["bid"] * 100,
        }

    except Exception as e:
        logger.error(f"❌ Order failed: {e}")
        return {"status": "ERROR", "error": str(e)}


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
            result = execute_covered_call(
                trading_client, options_client, args.symbol, args.dry_run
            )
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

        trades.append({
            "timestamp": datetime.now().isoformat(),
            "strategy": args.strategy,
            "symbol": args.symbol,
            "result": result,
        })

        with open(result_file, "w") as f:
            json.dump(trades, f, indent=2, default=str)

        logger.info(f"\n💾 Results saved to {result_file}")

        return 0 if result.get("status") in ["ORDER_SUBMITTED", "DRY_RUN", "NO_TRADE"] else 1

    except Exception as e:
        logger.exception(f"❌ Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
