#!/usr/bin/env python3
"""
Daily VOO DCA (Dollar Cost Averaging) Script

Automatically buys fractional shares of VOO with available cash in brokerage account.
Designed to run daily after $25 deposits.

Strategy: Phil Town Rule #1 aligned
- VOO = Vanguard S&P 500 ETF (broad market exposure)
- DCA = Dollar Cost Averaging (reduces timing risk)
- Fractional shares = Use every dollar efficiently

Usage:
    python3 scripts/daily_voo_dca.py
    python3 scripts/daily_voo_dca.py --dry-run
    python3 scripts/daily_voo_dca.py --amount 25
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.alpaca_client import get_account_info, get_brokerage_client

Path("logs").mkdir(exist_ok=True)
Path("data").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/voo_dca_{datetime.now().strftime('%Y%m%d')}.log"),
    ],
)
logger = logging.getLogger(__name__)

SYMBOL = "VOO"
MIN_PURCHASE = 1.00  # Minimum $1 to avoid tiny orders


def get_voo_price(client) -> float:
    """Get current VOO price using Alpaca market data."""
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        from src.utils.alpaca_client import get_brokerage_credentials

        api_key, secret_key = get_brokerage_credentials()
        data_client = StockHistoricalDataClient(api_key, secret_key)
        request = StockLatestQuoteRequest(symbol_or_symbols=[SYMBOL])
        quotes = data_client.get_stock_latest_quote(request)

        if SYMBOL in quotes:
            return float(quotes[SYMBOL].ask_price)
    except Exception as e:
        logger.warning(f"Failed to get quote via Alpaca: {e}")

    # Fallback: try yfinance
    try:
        import yfinance as yf

        ticker = yf.Ticker(SYMBOL)
        data = ticker.history(period="1d")
        if not data.empty:
            return float(data["Close"].iloc[-1])
    except Exception as e:
        logger.warning(f"Failed to get quote via yfinance: {e}")

    raise ValueError(f"Could not get {SYMBOL} price from any source")


def buy_fractional_voo(client, amount: float, dry_run: bool = False) -> dict:
    """
    Buy fractional shares of VOO with specified dollar amount.

    Args:
        client: Alpaca TradingClient (brokerage)
        amount: Dollar amount to invest
        dry_run: If True, don't execute order

    Returns:
        Dict with order result
    """
    try:
        price = get_voo_price(client)
        shares = round(amount / price, 6)  # 6 decimal places for fractional

        logger.info(f"VOO Price: ${price:.2f}")
        logger.info(f"Amount: ${amount:.2f}")
        logger.info(f"Shares: {shares:.6f}")

        if amount < MIN_PURCHASE:
            return {
                "status": "SKIP",
                "reason": f"Amount ${amount:.2f} below minimum ${MIN_PURCHASE}",
            }

        if dry_run:
            logger.info("DRY RUN - No order placed")
            return {
                "status": "DRY_RUN",
                "symbol": SYMBOL,
                "amount": amount,
                "shares": shares,
                "price": price,
            }

        # Submit fractional order (notional = dollar amount)
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        order_request = MarketOrderRequest(
            symbol=SYMBOL,
            notional=round(amount, 2),  # Dollar amount
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )

        order = client.submit_order(order_request)

        logger.info(f"ORDER SUBMITTED: {order.id}")
        logger.info(f"  Symbol: {SYMBOL}")
        logger.info(f"  Amount: ${amount:.2f}")
        logger.info(f"  Status: {order.status}")

        return {
            "status": "SUBMITTED",
            "order_id": str(order.id),
            "symbol": SYMBOL,
            "amount": amount,
            "shares_approx": shares,
            "price_at_order": price,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Order failed: {e}")
        return {"status": "ERROR", "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Daily VOO DCA purchase")
    parser.add_argument(
        "--amount",
        type=float,
        default=0,
        help="Dollar amount to invest (0 = use all available cash)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulate without placing order")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("VOO DCA - Daily Investment")
    logger.info("=" * 60)

    # Get brokerage client (live account)
    client = get_brokerage_client()
    if not client:
        logger.error("Failed to connect to brokerage account")
        return 1

    # Get account info
    account = get_account_info(client)
    if not account:
        logger.error("Failed to get account info")
        return 1

    logger.info(f"Account Equity: ${account['equity']:.2f}")
    logger.info(f"Available Cash: ${account['cash']:.2f}")
    logger.info(f"Buying Power: ${account['buying_power']:.2f}")

    # Determine purchase amount
    if args.amount > 0:
        purchase_amount = min(args.amount, account["cash"])
    else:
        # Use all available cash (typical for DCA after deposit)
        purchase_amount = account["cash"]

    if purchase_amount < MIN_PURCHASE:
        logger.warning(f"Insufficient cash: ${purchase_amount:.2f} < ${MIN_PURCHASE}")
        return 0

    logger.info(f"Purchase Amount: ${purchase_amount:.2f}")

    # Execute purchase
    result = buy_fractional_voo(client, purchase_amount, args.dry_run)

    # Log result
    logger.info("\n" + "=" * 60)
    logger.info("RESULT")
    logger.info("=" * 60)
    logger.info(json.dumps(result, indent=2))

    # Save to log file
    log_file = Path("data") / "voo_dca_log.json"
    history = []
    if log_file.exists():
        with open(log_file) as f:
            history = json.load(f)

    history.append(
        {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "account_equity": account["equity"],
            "account_cash": account["cash"],
            "purchase_amount": purchase_amount,
            "result": result,
        }
    )

    with open(log_file, "w") as f:
        json.dump(history, f, indent=2)

    logger.info(f"\nSaved to {log_file}")

    return 0 if result.get("status") in ["SUBMITTED", "DRY_RUN", "SKIP"] else 1


if __name__ == "__main__":
    sys.exit(main())
