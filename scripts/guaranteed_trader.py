#!/usr/bin/env python3
"""
GUARANTEED TRADER - WILL EXECUTE TRADES

Jan 12, 2026 FIX: Changed from SPY to SOFI
- SPY @ $580/share was wrong for $5K account
- SOFI @ $15/share allows real position building
- Strategy from CLAUDE.md: F/SOFI at $5 strike for CSPs

THE PROBLEM: 74 days, $0 profit, complex gates blocked everything.
THE SOLUTION: Buy SOFI shares. Simple. No gates.

This is NOT about being smart. It's about EXECUTING.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.utils.error_monitoring import init_sentry

load_dotenv()
init_sentry()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_alpaca_client():
    """Get Alpaca client."""
    from src.utils.alpaca_client import get_alpaca_client as _get_client

    return _get_client(paper=True)


def get_stock_price(symbol: str) -> float:
    """Get current stock price. Returns 0 if unavailable."""
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        if len(hist) > 0:
            return float(hist["Close"].iloc[-1])
        return 0.0
    except Exception as e:
        logger.warning(f"Price fetch failed for {symbol}: {e}")
        return 0.0


# Target symbols for CSP strategy (from centralized constants)
from src.constants.trading_thresholds import SYMBOLS

TARGET_SYMBOLS = SYMBOLS.CSP_WATCHLIST


def get_account(client) -> Optional[dict]:
    """Get account info."""
    try:
        acc = client.get_account()
        return {
            "equity": float(acc.equity),
            "cash": float(acc.cash),
            "buying_power": float(acc.buying_power),
        }
    except Exception as e:
        logger.error(f"Account error: {e}")
        return None


def get_position(client, symbol: str) -> Optional[dict]:
    """Get current position for a symbol."""
    try:
        positions = client.get_all_positions()
        for p in positions:
            if p.symbol == symbol:
                return {
                    "symbol": symbol,
                    "qty": float(p.qty),
                    "value": float(p.market_value),
                    "pnl": float(p.unrealized_pl),
                }
        return None
    except Exception as e:
        logger.error(f"Position error for {symbol}: {e}")
        return None


def buy_stock(client, symbol: str, dollars: float) -> Optional[dict]:
    """Buy stock with dollar amount."""
    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        request = MarketOrderRequest(
            symbol=symbol,
            notional=dollars,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        order = client.submit_order(request)
        logger.info(f"BUY ORDER SUBMITTED: ${dollars:.2f} of {symbol}")
        return {
            "id": str(order.id),
            "symbol": symbol,
            "side": "buy",
            "notional": dollars,
            "status": str(order.status),
        }
    except Exception as e:
        logger.error(f"Buy error for {symbol}: {e}")
        return None


def sell_stock(client, symbol: str, qty: float) -> Optional[dict]:
    """Sell stock shares."""
    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        order = client.submit_order(request)
        logger.info(f"SELL ORDER SUBMITTED: {qty} shares of {symbol}")
        return {
            "id": str(order.id),
            "symbol": symbol,
            "side": "sell",
            "qty": qty,
            "status": str(order.status),
        }
    except Exception as e:
        logger.error(f"Sell error for {symbol}: {e}")
        return None


def record_trade(trade: dict):
    """Save trade to file."""
    trades_file = Path(f"data/trades_{datetime.now().strftime('%Y-%m-%d')}.json")
    trades_file.parent.mkdir(parents=True, exist_ok=True)

    trades = []
    if trades_file.exists():
        try:
            with open(trades_file) as f:
                trades = json.load(f)
        except Exception:
            pass

    trade["timestamp"] = datetime.now().isoformat()
    trades.append(trade)

    with open(trades_file, "w") as f:
        json.dump(trades, f, indent=2)

    logger.info(f"Trade recorded: {trade}")


def run():
    """
    GUARANTEED EXECUTION - NO GATES, NO EXCUSES.

    Jan 12, 2026 Fix:
    - Removed RSI logic (was blocking trades)
    - Removed RAG checks (was blocking trades)
    - Changed from SPY to SOFI/F (cheaper, matches strategy)
    - Simple rule: Buy $100 of SOFI every day

    Position size: $100/day (build towards CSP collateral)
    """
    logger.info("=" * 60)
    logger.info("GUARANTEED TRADER - STARTING")
    logger.info("Strategy: Accumulate SOFI shares for CSP collateral")
    logger.info("=" * 60)

    client = get_alpaca_client()
    if not client:
        return {"success": False, "reason": "no_client"}

    account = get_account(client)
    if not account:
        return {"success": False, "reason": "no_account"}

    logger.info(f"Equity: ${account['equity']:,.2f}")
    logger.info(f"Cash: ${account['cash']:,.2f}")
    logger.info(f"Buying Power: ${account['buying_power']:,.2f}")

    # Check existing positions
    trades_executed = []
    for symbol in TARGET_SYMBOLS:
        position = get_position(client, symbol)
        if position:
            logger.info(
                f"{symbol} Position: {position['qty']:.2f} shares, "
                f"${position['value']:,.2f}, P/L: ${position['pnl']:,.2f}"
            )
        else:
            logger.info(f"No {symbol} position")

    # SIMPLE STRATEGY: Buy $100 of SOFI (primary target)
    # $100/day * 5 days = $500 = 1 CSP contract collateral
    daily_investment = 100.0
    symbol = "SOFI"  # Primary target from CLAUDE.md

    # Check we have enough cash
    if account["cash"] < daily_investment:
        logger.warning(
            f"Insufficient cash (${account['cash']:.2f}) for ${daily_investment} investment"
        )
        # Try smaller amount
        daily_investment = min(50.0, account["cash"] * 0.9)
        if daily_investment < 10:
            logger.error("Not enough cash to trade")
            return {"success": False, "reason": "insufficient_cash", "cash": account["cash"]}

    # Get current price for logging
    price = get_stock_price(symbol)
    if price > 0:
        shares_estimate = daily_investment / price
        logger.info(
            f"{symbol} price: ${price:.2f} (est. {shares_estimate:.2f} shares for ${daily_investment})"
        )

    # EXECUTE THE TRADE - NO GATES
    logger.info(f"EXECUTING: Buy ${daily_investment:.2f} of {symbol}")
    trade = buy_stock(client, symbol, daily_investment)

    if trade:
        trade["reason"] = "Daily accumulation for CSP collateral"
        trade["strategy"] = "guaranteed_trader_v2"
        record_trade(trade)
        trades_executed.append(trade)
        logger.info(f"SUCCESS: Order {trade['id']} submitted")
    else:
        logger.error(f"FAILED to submit order for {symbol}")

    # Summary
    logger.info("=" * 60)
    logger.info(f"Trades executed: {len(trades_executed)}")
    for t in trades_executed:
        logger.info(f"  - {t['symbol']}: ${t['notional']:.2f} ({t['status']})")
    logger.info("=" * 60)

    return {
        "success": len(trades_executed) > 0,
        "trades": trades_executed,
        "equity": account["equity"],
        "cash_remaining": account["cash"] - sum(t.get("notional", 0) for t in trades_executed),
    }


if __name__ == "__main__":
    result = run()
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
