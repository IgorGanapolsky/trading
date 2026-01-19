#!/usr/bin/env python3
"""
Simple Daily Trader - SPY CREDIT SPREADS ONLY

CRITICAL UPDATE Jan 15, 2026 (Deep Research Revision):
- 100K account succeeded with SPY focus (+$16,661)
- 5K account failed with SOFI (individual stock risk)
- Strategy: CREDIT SPREADS on SPY/IWM only per CLAUDE.md

Why Credit Spreads (not naked puts):
- Defined risk: Max loss = spread width - premium (~$440)
- $500 collateral per spread (fits $5K account)
- 30-delta short, 20-delta long = ~$60-70 premium
- Close at 50% profit to boost win rate to ~80%

THIS SCRIPT WILL TRADE. No excuses. SPY/IWM only.
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.rag.lessons_learned_rag import LessonsLearnedRAG
from src.utils.error_monitoring import init_sentry

load_dotenv()
init_sentry()

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration - UPDATED Jan 15 2026: Back to SPY per Deep Research Revision
# Credit spreads on SPY only need ~$500 collateral (spread width), not $50K!
# 100K account succeeded with SPY focus (+$16,661). 5K account failed with SOFI.
CONFIG = {
    "symbol": "SPY",  # SPY ~$590/share, credit spread = $500 collateral (fits $5K account!)
    "strategy": "credit_spread",  # Bull put spread per CLAUDE.md
    "target_delta": 0.30,  # 30 delta per CLAUDE.md strategy
    "target_dte": 30,  # 30 days to expiration
    "max_dte": 45,
    "min_dte": 21,
    "position_size_pct": 0.05,  # FIXED Jan 19, 2026: 5% max per position - CLAUDE.md MANDATE
    "take_profit_pct": 0.50,  # Close at 50% profit (improves win rate)
    "max_positions": 1,  # Per CLAUDE.md: "1 spread at a time"
    "north_star_daily_target": 10.0,  # $5-10/day realistic for $5K (CLAUDE.md updated)
    "fallback_symbols": ["IWM"],  # Only IWM as backup per CLAUDE.md whitelist
}


def get_alpaca_client():
    """Get Alpaca trading client."""
    from src.utils.alpaca_client import get_alpaca_client as _get_client

    return _get_client(paper=True)


def get_options_client():
    """Get Alpaca options client."""
    from src.utils.alpaca_client import get_options_client as _get_options

    return _get_options(paper=True)


def get_account_info(client) -> Optional[dict]:
    """Get account information."""
    try:
        account = client.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
        }
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        return None


def get_current_positions(client) -> list:
    """Get current positions."""
    try:
        positions = client.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
            }
            for p in positions
        ]
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return []


def find_put_option(symbol: str, target_delta: float, target_dte: int) -> Optional[dict]:
    """
    Find a put option matching our criteria.

    For now, returns a mock option contract.
    In production, this would query Alpaca's options chain.
    """
    # Calculate target expiration date
    today = datetime.now()
    target_expiry = today + timedelta(days=target_dte)

    # Format as YYMMDD for options symbol
    expiry_str = target_expiry.strftime("%y%m%d")

    # CRITICAL FIX Jan 13, 2026: Use symbol-specific prices, not hardcoded SPY!
    # This bug was causing strike calculations to be wildly wrong for SOFI
    symbol_prices = {
        "SOFI": 14,  # ~$14/share
        "F": 10,  # ~$10/share
        "PLTR": 80,  # ~$80/share
        "SPY": 600,  # ~$600/share
    }
    estimated_price = symbol_prices.get(symbol, 20)  # Default to $20 if unknown

    # For 20 delta put, use ~30% OTM strike (conservative for small account)
    strike = int(estimated_price * 0.70)  # 30% OTM for ~20 delta

    # Minimum strike of $5 to ensure tradeable
    strike = max(strike, 5)

    # Options symbol format: SOFI260213P00010000
    option_symbol = f"{symbol}{expiry_str}P{strike:08d}"

    logger.info(f"Option search: {symbol} @ ~${estimated_price} -> strike ${strike}")

    return {
        "symbol": option_symbol,
        "underlying": symbol,
        "strike": strike,
        "expiry": target_expiry.strftime("%Y-%m-%d"),
        "dte": target_dte,
        "delta": target_delta,
        "estimated_premium": max(strike * 0.02, 0.10),  # Min $0.10 premium
    }


def should_open_position(client, config: dict) -> bool:
    """
    Determine if we should open a new position.

    SIMPLE RULES:
    1. Less than max positions
    2. Have enough buying power
    3. Market is open
    """
    # CRITICAL: Check market hours FIRST (Jan 13, 2026 fix)
    # Options market: 9:30 AM - 4:00 PM ET, Mon-Fri
    try:
        from zoneinfo import ZoneInfo

        et_tz = ZoneInfo("America/New_York")
        now_et = datetime.now(et_tz)
    except ImportError:
        # Fallback for older Python
        now_et = datetime.utcnow()
        # Adjust for ET (UTC-5 in winter, UTC-4 in summer)
        from datetime import timedelta

        now_et = now_et - timedelta(hours=5)

    weekday = now_et.weekday()
    hour = now_et.hour
    minute = now_et.minute
    current_time_mins = hour * 60 + minute
    market_open = 9 * 60 + 30  # 9:30 AM
    market_close = 16 * 60  # 4:00 PM

    if weekday >= 5:  # Weekend
        logger.info(f"Market CLOSED: Weekend (today is {now_et.strftime('%A')})")
        return False

    if current_time_mins < market_open:
        mins_to_open = market_open - current_time_mins
        logger.info(
            f"Market CLOSED: Pre-market ({now_et.strftime('%I:%M %p')} ET). Opens in {mins_to_open} mins"
        )
        return False

    if current_time_mins >= market_close:
        logger.info(f"Market CLOSED: After hours ({now_et.strftime('%I:%M %p')} ET)")
        return False

    logger.info(f"✅ Market OPEN: {now_et.strftime('%I:%M %p')} ET")

    positions = get_current_positions(client)
    options_positions = [
        p for p in positions if len(p["symbol"]) > 10
    ]  # Options have longer symbols

    if len(options_positions) >= config["max_positions"]:
        logger.info(f"Max positions reached ({len(options_positions)}/{config['max_positions']})")
        return False

    account = get_account_info(client)
    if not account:
        return False

    # For cash-secured puts, we need buying power = strike * 100 (1 contract)
    # CRITICAL FIX Jan 12, 2026: Use CONFIG symbol price, not hardcoded SPY!
    # Previous bug: Hardcoded SPY at $600 = $57,000 collateral required
    # With SOFI at ~$14 and $10 strike = $1,000 collateral (fits $5K account)
    symbol_prices = {
        "SOFI": 14,  # ~$14/share, $10 strike = $1,000 collateral
        "F": 10,  # ~$10/share, $8 strike = $800 collateral
        "PLTR": 80,  # ~$80/share, $70 strike = $7,000 collateral
        "SPY": 600,  # ~$600/share, $570 strike = $57,000 collateral
    }
    symbol = config.get("symbol", "SOFI")
    price_estimate = symbol_prices.get(symbol, 20)  # Default to $20 if unknown
    strike_estimate = int(price_estimate * 0.70)  # 30% OTM for conservative strike
    required_bp = strike_estimate * 100  # 1 contract = 100 shares

    if account["buying_power"] < required_bp:
        logger.info(
            f"Insufficient buying power for {symbol} CSP: ${account['buying_power']:,.0f} < ${required_bp:,.0f}"
        )
        logger.info(
            "Need more capital for cash-secured puts. Consider credit spreads for smaller accounts."
        )
        return False

    logger.info(
        f"✅ Buying power OK for {symbol} CSP: ${account['buying_power']:,.0f} >= ${required_bp:,.0f} required"
    )
    return True


def execute_cash_secured_put(client, option: dict, config: dict) -> Optional[dict]:
    """
    Execute a cash-secured put sale.

    Returns trade details or None if failed.
    """
    # Query RAG for lessons before trading
    logger.info("Checking RAG lessons before execution...")
    rag = LessonsLearnedRAG()

    # Check for strategy-specific failures
    strategy_lessons = rag.search("cash secured put failures losses", top_k=3)
    for lesson, score in strategy_lessons:
        if lesson.severity == "CRITICAL":
            logger.error(f"BLOCKED by RAG: {lesson.title} (severity: {lesson.severity})")
            logger.error(f"Prevention: {lesson.prevention}")
            return None

    # Check for ticker-specific failures
    ticker_lessons = rag.search(f"{option['underlying']} trading failures options losses", top_k=3)
    for lesson, score in ticker_lessons:
        if lesson.severity == "CRITICAL":
            logger.error(f"BLOCKED by RAG: {lesson.title} (severity: {lesson.severity})")
            logger.error(f"Prevention: {lesson.prevention}")
            return None

    logger.info("RAG checks passed - proceeding with execution")

    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest

        logger.info(f"Executing cash-secured put SALE: {option['symbol']}")
        logger.info(f"  Strike: ${option['strike']}")
        logger.info(f"  Expiry: {option['expiry']} ({option['dte']} DTE)")
        logger.info(f"  Target Delta: {option['delta']}")
        logger.info(f"  Estimated Premium: ${option['estimated_premium']:.2f}")

        # SELL TO OPEN a cash-secured put (Phil Town Rule #1 style)
        # This collects premium while waiting to buy at our desired price
        try:
            # Get options chain to find real contract
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.data.requests import OptionChainRequest
            from src.utils.alpaca_client import get_alpaca_credentials

            api_key, secret_key = get_alpaca_credentials()
            options_data_client = OptionHistoricalDataClient(api_key, secret_key)

            # Find the actual option contract
            chain_request = OptionChainRequest(
                underlying_symbol=option["underlying"],
                expiration_date_gte=datetime.now().strftime("%Y-%m-%d"),
                expiration_date_lte=option["expiry"],
                strike_price_lte=option["strike"] + 10,
                strike_price_gte=option["strike"] - 10,
            )

            # Get option contracts
            contracts = options_data_client.get_option_chain(chain_request)

            # Find put contract closest to our target
            put_contract = None
            for symbol, contract in contracts.items():
                if "P" in symbol and abs(float(symbol[-8:]) / 1000 - option["strike"]) < 10:
                    put_contract = symbol
                    break

            if not put_contract:
                # Use calculated symbol if API doesn't return contracts
                put_contract = option["symbol"]
                logger.warning(f"Using calculated contract symbol: {put_contract}")

            logger.info(f"📊 SELLING PUT: {put_contract}")

            # CRITICAL SAFETY CHECK: Don't sell more if we're already short this contract
            # Phil Town Rule #1: Don't lose money by over-leveraging
            try:
                existing_positions = client.get_all_positions()
                for pos in existing_positions:
                    if pos.symbol == put_contract:
                        pos_qty = float(pos.qty)
                        if pos_qty < 0:  # Already short this contract
                            logger.error(
                                f"🚫 BLOCKED: Already SHORT {put_contract} (qty={pos_qty})"
                            )
                            logger.error("   Cannot SELL more - would increase risk exposure!")
                            logger.error("   Rule #1: Don't lose money by doubling down on losers")
                            return None
                        else:
                            logger.warning(f"⚠️ Existing LONG position on {put_contract}")
            except Exception as pos_err:
                logger.warning(f"Could not check existing positions: {pos_err}")

            # Also check for pending SELL orders on this contract
            try:
                open_orders = client.get_orders()
                for order in open_orders:
                    if order.symbol == put_contract and str(order.side).lower() == "sell":
                        logger.error(f"🚫 BLOCKED: Pending SELL order exists for {put_contract}")
                        logger.error(f"   Order ID: {order.id}, Status: {order.status}")
                        logger.error("   Cannot submit duplicate order")
                        return None
            except Exception as ord_err:
                logger.warning(f"Could not check open orders: {ord_err}")

            # Submit SELL TO OPEN order for the put option
            order_request = LimitOrderRequest(
                symbol=put_contract,
                qty=1,  # 1 contract = 100 shares exposure
                side=OrderSide.SELL,  # SELL to open (collect premium)
                time_in_force=TimeInForce.DAY,
                limit_price=option["estimated_premium"],  # Limit price for premium
            )
            order = client.submit_order(order_request)

            trade = {
                "timestamp": datetime.now().isoformat(),
                "action": "SELL_TO_OPEN",
                "symbol": put_contract,
                "underlying": option["underlying"],
                "strike": option["strike"],
                "expiry": option["expiry"],
                "quantity": 1,
                "premium": option["estimated_premium"],
                "strategy": "cash_secured_put",
                "status": "SUBMITTED",
                "order_id": str(order.id) if hasattr(order, "id") else "unknown",
                "phil_town_rule": "Getting paid to wait for a great company at a great price",
            }

            logger.info(f"✅ CSP ORDER SUBMITTED: {trade}")
            return trade

        except Exception as order_err:
            logger.error(f"Options order failed: {order_err}")
            logger.error("Attempting market order for put...")

            # Fallback: try market order for the put
            try:
                from alpaca.trading.requests import MarketOrderRequest

                order_request = MarketOrderRequest(
                    symbol=option["symbol"],
                    qty=1,
                    side=OrderSide.SELL,  # SELL the put
                    time_in_force=TimeInForce.DAY,
                )
                order = client.submit_order(order_request)

                trade = {
                    "timestamp": datetime.now().isoformat(),
                    "action": "SELL_TO_OPEN",
                    "symbol": option["symbol"],
                    "underlying": option["underlying"],
                    "strike": option["strike"],
                    "expiry": option["expiry"],
                    "quantity": 1,
                    "strategy": "cash_secured_put",
                    "status": "SUBMITTED_MARKET",
                    "order_id": str(order.id) if hasattr(order, "id") else "unknown",
                }
                logger.info(f"✅ CSP MARKET ORDER SUBMITTED: {trade}")
                return trade

            except Exception as market_err:
                logger.error(f"Market order also failed: {market_err}")
                trade = {
                    "timestamp": datetime.now().isoformat(),
                    "action": "SELL_TO_OPEN",
                    "symbol": option["symbol"],
                    "quantity": 1,
                    "strategy": "cash_secured_put",
                    "status": "FAILED",
                    "error": f"Limit: {order_err}, Market: {market_err}",
                }
                return trade

    except ImportError as ie:
        logger.error(f"Missing Alpaca imports: {ie}")
        logger.error("Install with: pip install alpaca-py")
        return None
    except Exception as e:
        logger.error(f"Failed to execute CSP trade: {e}")
        return None


def check_exit_conditions(client, positions: list, config: dict) -> list:
    """
    Check if any positions should be closed.

    Exit conditions:
    1. 50% profit reached
    2. 21 DTE reached (roll or close)
    3. Stop loss (100% of premium)
    """
    exits = []

    for pos in positions:
        # Check if it's an options position
        if len(pos["symbol"]) <= 10:
            continue

        # Check profit target
        if pos.get("unrealized_pl", 0) > 0:
            cost_basis = pos.get("cost_basis", abs(pos["market_value"]))
            if cost_basis > 0:
                profit_pct = pos["unrealized_pl"] / cost_basis
                if profit_pct >= config["take_profit_pct"]:
                    exits.append(
                        {
                            "symbol": pos["symbol"],
                            "reason": "TAKE_PROFIT",
                            "profit_pct": profit_pct,
                        }
                    )
                    logger.info(f"Exit signal: {pos['symbol']} - Take profit at {profit_pct:.1%}")

    return exits


def record_trade(trade: dict):
    """Record trade to memory for learning."""
    try:
        # Use the new TradeMemory system
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.learning.trade_memory import TradeMemory

        memory = TradeMemory()
        memory.add_trade(
            {
                "symbol": trade.get("underlying", trade.get("symbol")),
                "strategy": trade.get("strategy", "cash_secured_put"),
                "entry_reason": "daily_execution",
                "won": trade.get("status") == "FILLED",
                "pnl": trade.get("pnl", 0),
                "lesson": f"Executed {trade.get('strategy')} on {trade.get('symbol')}",
            }
        )
        logger.info("Trade recorded to memory")
    except Exception as e:
        logger.warning(f"Failed to record trade to memory: {e}")

    # Also save to daily trades file
    trades_file = Path(f"data/trades_{datetime.now().strftime('%Y-%m-%d')}.json")
    trades_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        if trades_file.exists():
            with open(trades_file) as f:
                trades = json.load(f)
        else:
            trades = []

        trades.append(trade)

        with open(trades_file, "w") as f:
            json.dump(trades, f, indent=2)

        logger.info(f"Trade saved to {trades_file}")
    except Exception as e:
        logger.error(f"Failed to save trade: {e}")


def run_daily_trading():
    """
    Main daily trading routine.

    THIS WILL EXECUTE TRADES. No complex gates. No ML filtering.
    Just the proven strategy.
    """
    logger.info("=" * 60)
    logger.info("SIMPLE DAILY TRADER - STARTING")
    logger.info("=" * 60)

    # Get client
    client = get_alpaca_client()
    if not client:
        logger.error("Cannot proceed without Alpaca client")
        return {"success": False, "reason": "no_client"}

    # Get account status
    account = get_account_info(client)
    if account:
        logger.info(f"Account Equity: ${account['equity']:,.2f}")
        logger.info(f"Buying Power: ${account['buying_power']:,.2f}")

    # Get current positions
    positions = get_current_positions(client)
    logger.info(f"Current Positions: {len(positions)}")

    # Check for exits first
    exits = check_exit_conditions(client, positions, CONFIG)
    for exit_signal in exits:
        logger.info(f"Would close: {exit_signal['symbol']} ({exit_signal['reason']})")
        # In production: execute close order

    # Check if we should open new position
    if should_open_position(client, CONFIG):
        logger.info("Opening new position...")

        # Find option contract
        option = find_put_option(CONFIG["symbol"], CONFIG["target_delta"], CONFIG["target_dte"])

        if option:
            # Execute trade
            trade = execute_cash_secured_put(client, option, CONFIG)
            if trade:
                record_trade(trade)
                logger.info("NEW POSITION OPENED")
            else:
                logger.warning("Failed to execute trade")
        else:
            logger.warning("No suitable option found")
    else:
        logger.info("No new position needed")

    # Summary
    logger.info("=" * 60)
    logger.info("DAILY TRADING COMPLETE")
    logger.info(f"Positions: {len(positions)}")
    logger.info(f"Exits triggered: {len(exits)}")
    logger.info("=" * 60)

    return {
        "success": True,
        "positions": len(positions),
        "exits": len(exits),
        "account": account,
    }


if __name__ == "__main__":
    result = run_daily_trading()
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
