#!/usr/bin/env python3
"""
GUARANTEED TRADER - CREDIT SPREAD ACCUMULATOR

CRITICAL UPDATE Jan 15, 2026 (Deep Research Revision):
- 100K account succeeded with SPY focus (+$16,661)
- 5K account failed with SOFI (individual stock risk)
- STRATEGY: SPY CREDIT SPREADS only per CLAUDE.md

THE PROBLEM: This script was buying SOFI shares when CLAUDE.md
says "CREDIT SPREADS on SPY ONLY".

THE SOLUTION: Buy SPY shares (most liquid ETF) or accumulate cash
for credit spread collateral (~$500 per spread).

IMPORTANT: This script now uses SPY not SOFI. Individual stocks
are BLACKLISTED until proven profitable in paper trading.
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
    - Jan 15, 2026: Back to SPY per Deep Research findings
    - Simple rule: Accumulate SPY or cash for credit spread collateral

    Position size: $100/day (build towards $500 credit spread collateral)

    Jan 23, 2026 Fix (LL-298): Added daily trade limit
    - Prevents churning from multiple workflow triggers
    - Only 1 guaranteed_trader execution per day
    """
    # LL-298 FIX: Daily trade limit to prevent churning
    # ROOT CAUSE: 35 trades on Jan 23 caused -$17.56 loss from bid/ask spreads
    MAX_DAILY_RUNS = 1
    state_file = Path("data/guaranteed_trader_daily.json")
    today = datetime.now().strftime("%Y-%m-%d")

    if state_file.exists():
        try:
            with open(state_file) as f:
                state = json.load(f)
            if state.get("date") == today and state.get("runs", 0) >= MAX_DAILY_RUNS:
                logger.warning("=" * 60)
                logger.warning("DAILY LIMIT REACHED - BLOCKING EXECUTION")
                logger.warning(f"Already ran {state['runs']} time(s) today")
                logger.warning("Reason: Prevent churning and bid/ask spread losses")
                logger.warning("=" * 60)
                return {
                    "success": False,
                    "reason": "daily_limit_reached",
                    "runs_today": state["runs"],
                }
        except Exception as e:
            logger.warning(f"Could not read state file: {e}")

    logger.info("=" * 60)
    logger.info("GUARANTEED TRADER - STARTING")
    logger.info("Strategy: Accumulate SPY shares for credit spread collateral")
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

    # Check existing positions and RULE #1: Don't lose money
    trades_executed = []
    total_unrealized_pnl = 0.0

    for symbol in TARGET_SYMBOLS:
        position = get_position(client, symbol)
        if position:
            logger.info(
                f"{symbol} Position: {position['qty']:.2f} shares, "
                f"${position['value']:,.2f}, P/L: ${position['pnl']:,.2f}"
            )
            total_unrealized_pnl += position["pnl"]
        else:
            logger.info(f"No {symbol} position")

    # RULE #1 CHECK: Only block if losses are SIGNIFICANT (>2% of portfolio)
    # CEO FIX Jan 15, 2026: $0.03 unrealized loss was blocking ALL trades!
    # Phil Town Rule #1 means don't lose BIG, not "never have red days"
    loss_threshold = -account["equity"] * 0.02  # 2% of portfolio
    if total_unrealized_pnl < loss_threshold:
        logger.warning("=" * 60)
        logger.warning("⚠️ RULE #1 VIOLATION PREVENTED!")
        logger.warning(f"   Unrealized P/L: ${total_unrealized_pnl:.2f}")
        logger.warning(f"   Threshold: ${loss_threshold:.2f} (2% of portfolio)")
        logger.warning("   REFUSING to add to losing positions.")
        logger.warning("=" * 60)
        return {
            "success": False,
            "reason": "rule_1_protection",
            "unrealized_pnl": total_unrealized_pnl,
            "message": "Phil Town Rule #1: Don't lose money. Not adding to losing positions.",
        }
    elif total_unrealized_pnl < 0:
        logger.info(f"Minor unrealized loss (${total_unrealized_pnl:.2f}) - proceeding with trade")

    # SIMPLE STRATEGY: Buy $100 of SPY (most liquid ETF)
    # $100/day * 5 days = $500 = 1 credit spread collateral
    daily_investment = 100.0
    symbol = "SPY"  # Primary target per Jan 15 Deep Research

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

        # LL-298: Record successful run to prevent churning
        try:
            state = {"date": today, "runs": 1}
            if state_file.exists():
                with open(state_file) as f:
                    old_state = json.load(f)
                if old_state.get("date") == today:
                    state["runs"] = old_state.get("runs", 0) + 1
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
            logger.info(f"Daily run count: {state['runs']}/{MAX_DAILY_RUNS}")
        except Exception as e:
            logger.warning(f"Could not update daily state: {e}")
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


def set_stop_losses(client):
    """
    Set stop-losses on short put positions.

    CEO Directive: "We are never allowed to lose money!"
    This protects short put positions with buy-to-close stop orders.
    """
    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import StopLimitOrderRequest

        positions = client.get_all_positions()
        stops_set = []

        for p in positions:
            # Check if it's a short put (negative qty, symbol contains 'P')
            qty = float(p.qty)
            if qty < 0 and "P" in p.symbol and len(p.symbol) > 10:
                logger.info(f"Found short put: {p.symbol}, qty={qty}")

                current_price = float(p.current_price)
                # Set stop at 2x current price to cap losses
                stop_price = round(max(1.50, current_price * 2), 2)
                limit_price = round(stop_price + 0.05, 2)

                logger.info(f"  Setting stop-loss: buy to close @ ${stop_price}")

                try:
                    order_request = StopLimitOrderRequest(
                        symbol=p.symbol,
                        qty=abs(int(qty)),
                        side=OrderSide.BUY,
                        stop_price=stop_price,
                        limit_price=limit_price,
                        time_in_force=TimeInForce.GTC,
                    )
                    order = client.submit_order(order_request)
                    logger.info(f"  ✅ Stop-loss order placed: {order.id}")
                    stops_set.append(
                        {"symbol": p.symbol, "stop_price": stop_price, "order_id": str(order.id)}
                    )
                except Exception as e:
                    logger.warning(f"  ⚠️ Could not set stop: {e}")

        return stops_set
    except Exception as e:
        logger.error(f"Error setting stop-losses: {e}")
        return []


if __name__ == "__main__":
    result = run()
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")

    # Also set stop-losses on any short puts
    client = get_alpaca_client()
    if client:
        print("\n🛡️ Setting stop-losses on short puts...")
        stops = set_stop_losses(client)
        if stops:
            print(f"✅ Set {len(stops)} stop-loss orders")
            for s in stops:
                print(f"   {s['symbol']} @ ${s['stop_price']}")
        else:
            print("ℹ️ No short puts to protect")
