#!/usr/bin/env python3
"""
Simple ETF Accumulator - The Bogleheads Way

CTO/CFO Decision (Dec 10, 2025):
- Options strategy backtest: Sharpe -7 to -72 (LOSING MONEY)
- 31 days, $17.49 profit, 0% win rate
- PIVOT: Simple ETF accumulation that actually works

Strategy:
- Buy $10/day of SPY (or configurable amount)
- Market order for guaranteed fill
- Hold forever
- No timing, no options, no complexity
- Historically ~10% annual return

"The stock market is a device for transferring money from the impatient to the patient."
- Warren Buffett
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_alpaca_client():
    """Initialize Alpaca trading client."""
    try:
        from alpaca.trading.client import TradingClient

        api_key = os.environ.get("ALPACA_API_KEY")
        secret_key = os.environ.get("ALPACA_SECRET_KEY")
        paper = os.environ.get("PAPER_TRADING", "true").lower() == "true"

        if not api_key or not secret_key:
            logger.error("❌ ALPACA_API_KEY and ALPACA_SECRET_KEY required")
            return None

        return TradingClient(api_key, secret_key, paper=paper)
    except Exception as e:
        logger.error(f"❌ Failed to initialize Alpaca client: {e}")
        return None


def get_current_price(symbol: str) -> float:
    """Get current price for symbol."""
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except Exception as e:
        logger.warning(f"yfinance failed: {e}")

    # Fallback to Alpaca
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest

        api_key = os.environ.get("ALPACA_API_KEY")
        secret_key = os.environ.get("ALPACA_SECRET_KEY")

        client = StockHistoricalDataClient(api_key, secret_key)
        request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quotes = client.get_stock_latest_quote(request)

        if symbol in quotes:
            return float(quotes[symbol].ask_price)
    except Exception as e:
        logger.warning(f"Alpaca quote failed: {e}")

    return 0.0


def execute_etf_buy(symbol: str = "SPY", amount: float = 10.0, dry_run: bool = False) -> dict:
    """
    Execute simple ETF buy order.

    Args:
        symbol: ETF to buy (default SPY)
        amount: Dollar amount to invest
        dry_run: If True, don't actually execute

    Returns:
        Result dict with order details
    """
    logger.info("=" * 60)
    logger.info("📈 SIMPLE ETF ACCUMULATOR")
    logger.info("=" * 60)
    logger.info(f"   Symbol: {symbol}")
    logger.info(f"   Amount: ${amount:.2f}")
    logger.info(f"   Strategy: Buy and Hold (Bogleheads)")
    logger.info("")

    # Get current price
    current_price = get_current_price(symbol)
    if current_price <= 0:
        logger.error(f"❌ Could not get price for {symbol}")
        return {"status": "ERROR", "error": "Could not get price"}

    logger.info(f"📊 Current {symbol} price: ${current_price:.2f}")

    # Calculate shares (fractional allowed on Alpaca)
    shares = amount / current_price
    logger.info(f"   Shares to buy: {shares:.6f}")
    logger.info(f"   Notional value: ${amount:.2f}")

    if dry_run:
        logger.info("\n🔶 DRY RUN - No actual trade executed")
        return {
            "status": "DRY_RUN",
            "symbol": symbol,
            "shares": shares,
            "price": current_price,
            "amount": amount,
        }

    # Initialize client
    client = get_alpaca_client()
    if not client:
        return {"status": "ERROR", "error": "Could not initialize Alpaca client"}

    # Check account
    try:
        account = client.get_account()
        buying_power = float(account.buying_power)
        logger.info(f"💰 Account buying power: ${buying_power:,.2f}")

        if buying_power < amount:
            logger.error(f"❌ Insufficient buying power! Need ${amount}, have ${buying_power}")
            return {"status": "NO_TRADE", "reason": "Insufficient buying power"}
    except Exception as e:
        logger.error(f"❌ Failed to get account: {e}")
        return {"status": "ERROR", "error": str(e)}

    # Submit market order (notional for exact dollar amount)
    try:
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        order_request = MarketOrderRequest(
            symbol=symbol,
            notional=amount,  # Dollar amount, not shares
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )

        order = client.submit_order(order_request)

        logger.info("\n✅ ORDER SUBMITTED!")
        logger.info(f"   Order ID: {order.id}")
        logger.info(f"   Symbol: {symbol}")
        logger.info(f"   Side: BUY")
        logger.info(f"   Amount: ${amount:.2f}")
        logger.info(f"   Type: MARKET (guaranteed fill)")
        logger.info(f"   Status: {order.status}")

        # Record trade
        trade_record = {
            "timestamp": datetime.now().isoformat(),
            "symbol": symbol,
            "side": "BUY",
            "amount": amount,
            "price": current_price,
            "shares": shares,
            "order_id": str(order.id),
            "status": str(order.status),
            "strategy": "simple_etf_accumulator",
        }

        # Save to trades file
        trades_file = Path("data") / f"etf_trades_{datetime.now().strftime('%Y-%m-%d')}.json"
        trades_file.parent.mkdir(exist_ok=True)

        existing_trades = []
        if trades_file.exists():
            try:
                existing_trades = json.loads(trades_file.read_text())
            except:
                pass

        existing_trades.append(trade_record)
        trades_file.write_text(json.dumps(existing_trades, indent=2))
        logger.info(f"   Trade logged to: {trades_file}")

        return {
            "status": "ORDER_SUBMITTED",
            "order_id": str(order.id),
            "symbol": symbol,
            "shares": shares,
            "price": current_price,
            "amount": amount,
        }

    except Exception as e:
        logger.error(f"❌ Order failed: {e}")
        return {"status": "ERROR", "error": str(e)}


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Simple ETF Accumulator")
    parser.add_argument("--symbol", default="SPY", help="ETF symbol (default: SPY)")
    parser.add_argument("--amount", type=float, default=10.0, help="Dollar amount (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Don't execute, just simulate")

    args = parser.parse_args()

    result = execute_etf_buy(
        symbol=args.symbol,
        amount=args.amount,
        dry_run=args.dry_run,
    )

    # Exit with appropriate code
    if result.get("status") in ["ORDER_SUBMITTED", "DRY_RUN"]:
        logger.info("\n✅ ETF accumulation complete!")
        sys.exit(0)
    else:
        logger.error(f"\n❌ ETF accumulation failed: {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()
