#!/usr/bin/env python3
"""
Rule #1 Options Trader - Phil Town Strategy

This script runs the Phil Town Rule #1 options strategy:
1. Calculate Sticker Price for quality stocks
2. Sell puts at 50% MOS (Margin of Safety) - "Getting Paid to Wait"
3. Sell covered calls at Sticker Price - "Getting Paid to Sell"

Based on: rag_knowledge/books/phil_town_rule_one.md

Target: $20-50/day additional income

CRITICAL: This script MUST execute trades, not just analyze!
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.utils.error_monitoring import init_sentry

load_dotenv()
init_sentry()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Phil Town Strategy Configuration
# CAPITAL-TIERED: With $5K, can only do CSPs on stocks with strike <= $50
CONFIG = {
    "watchlist": [
        # TIER 1: Affordable for $5K account (strike <= $50)
        "F",      # Ford - ~$10 strike
        "SOFI",   # SoFi - ~$15 strike
        "T",      # AT&T - ~$20 strike
        "INTC",   # Intel - ~$20 strike
        "BAC",    # Bank of America - ~$35 strike
        "VZ",     # Verizon - ~$40 strike
    ],
    "max_position_pct": 0.10,  # Max 10% of portfolio per position
    "target_dte": 30,  # 30 days to expiration for puts
    "min_dte": 21,
    "max_dte": 45,
    "north_star_target": 100.0,  # $100/day goal
}


def get_trading_client():
    """Get Alpaca trading client."""
    try:
        from alpaca.trading.client import TradingClient

        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            logger.error("Missing Alpaca credentials")
            return None

        return TradingClient(api_key, secret_key, paper=True)
    except Exception as e:
        logger.error(f"Failed to create trading client: {e}")
        return None


def find_put_option(symbol: str, target_strike: float, client) -> Optional[dict]:
    """Find a put option near the target strike (MOS price)."""
    try:
        from alpaca.trading.requests import GetOptionContractsRequest

        # Calculate target expiration (30 DTE)
        _target_date = datetime.now() + timedelta(days=CONFIG["target_dte"])  # noqa: F841

        request = GetOptionContractsRequest(
            underlying_symbols=[symbol],
            expiration_date_gte=datetime.now().strftime("%Y-%m-%d"),
            expiration_date_lte=(datetime.now() + timedelta(days=CONFIG["max_dte"])).strftime(
                "%Y-%m-%d"
            ),
            strike_price_lte=str(target_strike * 1.05),  # 5% buffer above target
            strike_price_gte=str(target_strike * 0.95),  # 5% buffer below target
            type="put",
        )

        contracts = client.get_option_contracts(request)

        if contracts and contracts.option_contracts:
            # Find contract closest to target strike and DTE
            best = None
            best_score = float("inf")

            for contract in contracts.option_contracts:
                strike_diff = abs(float(contract.strike_price) - target_strike)
                exp_date = datetime.strptime(str(contract.expiration_date), "%Y-%m-%d")
                dte = (exp_date - datetime.now()).days
                dte_diff = abs(dte - CONFIG["target_dte"])

                score = strike_diff + dte_diff * 0.5
                if score < best_score:
                    best_score = score
                    best = {
                        "symbol": contract.symbol,
                        "strike": float(contract.strike_price),
                        "expiration": str(contract.expiration_date),
                        "dte": dte,
                    }

            return best

        return None
    except Exception as e:
        logger.warning(f"Failed to find put option for {symbol}: {e}")
        return None


def execute_phil_town_csp(client, symbol: str, analysis: dict) -> Optional[dict]:
    """
    Execute Phil Town Cash-Secured Put trade.

    Sells a put at or below MOS price to "get paid to wait" for a wonderful company.
    """
    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

        mos_price = analysis.get("mos_price", 0)
        current_price = analysis.get("current_price", 0)

        if not mos_price or mos_price <= 0:
            logger.warning(f"{symbol}: Invalid MOS price")
            return None

        # Find put option at MOS price
        option = find_put_option(symbol, mos_price, client)

        if not option:
            logger.info(f"{symbol}: No suitable put option found near ${mos_price:.2f}")
            return None

        logger.info(
            f"  Found put: {option['symbol']} @ ${option['strike']:.2f} ({option['dte']} DTE)"
        )

        # Calculate premium (estimate based on strike distance)
        # In real implementation, fetch actual bid/ask
        distance_pct = (current_price - option["strike"]) / current_price
        estimated_premium = current_price * 0.02 * (1 + distance_pct)  # ~2% base premium

        logger.info(f"  Estimated premium: ${estimated_premium:.2f}/share")

        # Execute SELL TO OPEN
        try:
            order_request = LimitOrderRequest(
                symbol=option["symbol"],
                qty=1,  # 1 contract = 100 shares
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=round(estimated_premium, 2),
            )

            order = client.submit_order(order_request)

            trade_result = {
                "success": True,
                "symbol": symbol,
                "option_symbol": option["symbol"],
                "strategy": "phil_town_csp",
                "strike": option["strike"],
                "mos_price": mos_price,
                "premium": estimated_premium,
                "order_id": str(order.id) if hasattr(order, "id") else "unknown",
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"  ✅ TRADE EXECUTED: Sold {option['symbol']} for ~${estimated_premium:.2f}"
            )
            record_trade(trade_result)
            return trade_result

        except Exception as order_err:
            logger.warning(f"  Limit order failed: {order_err}, trying market order...")

            # Fallback to market order
            try:
                order_request = MarketOrderRequest(
                    symbol=option["symbol"],
                    qty=1,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )

                order = client.submit_order(order_request)

                trade_result = {
                    "success": True,
                    "symbol": symbol,
                    "option_symbol": option["symbol"],
                    "strategy": "phil_town_csp_market",
                    "strike": option["strike"],
                    "order_id": str(order.id) if hasattr(order, "id") else "unknown",
                    "timestamp": datetime.now().isoformat(),
                }

                logger.info(f"  ✅ MARKET ORDER: Sold {option['symbol']}")
                record_trade(trade_result)
                return trade_result

            except Exception as market_err:
                logger.error(f"  ❌ Market order also failed: {market_err}")
                return None

    except Exception as e:
        logger.error(f"Failed to execute Phil Town CSP for {symbol}: {e}")
        return None


def record_trade(trade: dict):
    """Record trade to file and RLHF storage."""
    try:
        # Save to daily trades file
        today = datetime.now().strftime("%Y-%m-%d")
        trades_file = Path(f"data/trades_{today}.json")
        trades_file.parent.mkdir(exist_ok=True)

        existing = []
        if trades_file.exists():
            with open(trades_file) as f:
                existing = json.load(f)

        existing.append(trade)

        with open(trades_file, "w") as f:
            json.dump(existing, f, indent=2, default=str)

        logger.info(f"  Trade recorded to {trades_file}")

        # Store RLHF trajectory
        try:
            from src.learning.rlhf_storage import store_trade_trajectory

            store_trade_trajectory(
                episode_id=trade.get("order_id", f"phil_town_{datetime.now().timestamp()}"),
                entry_state={"price": trade.get("strike", 0), "symbol": trade.get("symbol")},
                action=2,  # SELL action
                exit_state={},
                reward=trade.get("premium", 0),
                symbol=trade.get("symbol", "UNKNOWN"),
                policy_version="phil_town_1.0",
                metadata={"strategy": "phil_town_csp"},
            )
            logger.info("  RLHF trajectory stored")
        except Exception as rlhf_err:
            logger.warning(f"  RLHF storage failed: {rlhf_err}")

    except Exception as e:
        logger.warning(f"Failed to record trade: {e}")


def run_rule_one_strategy():
    """Execute Rule #1 options strategy - ANALYZES AND TRADES."""
    logger.info("=" * 60)
    logger.info("RULE #1 OPTIONS TRADER - PHIL TOWN STRATEGY")
    logger.info("=" * 60)

    try:
        from src.strategies.rule_one_options import RuleOneOptionsStrategy

        # Initialize strategy and client
        strategy = RuleOneOptionsStrategy()
        client = get_trading_client()

        if not client:
            return {"success": False, "reason": "no_trading_client"}

        # Run analysis on Rule #1 worthy stocks
        watchlist = CONFIG["watchlist"]

        analyses = []
        trades_executed = []

        for symbol in watchlist:
            try:
                logger.info(f"\n{'=' * 40}")
                logger.info(f"Analyzing {symbol}...")

                # Calculate sticker price and MOS
                analysis = strategy.analyze_stock(symbol)

                if not analysis:
                    logger.info(f"  No analysis available for {symbol}")
                    continue

                logger.info(f"  Sticker Price: ${analysis.get('sticker_price', 'N/A')}")
                logger.info(f"  MOS Price: ${analysis.get('mos_price', 'N/A')}")
                logger.info(f"  Current Price: ${analysis.get('current_price', 'N/A')}")
                logger.info(f"  Recommendation: {analysis.get('recommendation')}")

                analyses.append(analysis)

                # EXECUTE TRADE if recommendation is STRONG BUY
                recommendation = analysis.get("recommendation", "")
                if "STRONG BUY" in recommendation and "Below MOS" in recommendation:
                    logger.info(f"  🎯 ACTIONABLE: {symbol} is below MOS - Selling CSP")

                    trade = execute_phil_town_csp(client, symbol, analysis)
                    if trade:
                        trades_executed.append(trade)
                        logger.info(f"  ✅ Trade executed for {symbol}")
                    else:
                        logger.warning(f"  ⚠️ Trade execution failed for {symbol}")

                elif "BUY" in recommendation:
                    logger.info(f"  📊 {symbol} is below Sticker but above MOS - watching")

                elif "SELL" in recommendation:
                    logger.info(f"  📈 {symbol} overvalued - consider covered calls if holding")

            except Exception as e:
                logger.warning(f"  Failed to process {symbol}: {e}")

        logger.info("\n" + "=" * 60)
        logger.info(f"RULE #1 COMPLETE - {len(analyses)} analyzed, {len(trades_executed)} traded")
        logger.info("=" * 60)

        return {
            "success": True,
            "opportunities": len(analyses),
            "trades_executed": len(trades_executed),
            "analyses": analyses,
            "trades": trades_executed,
        }

    except ImportError as e:
        logger.error(f"CRITICAL: Rule #1 strategy import failed: {e}")
        logger.error("This indicates missing dependencies - FIX REQUIRED")
        return {"success": False, "reason": f"import_error: {e}"}
    except AttributeError as e:
        logger.error(f"CRITICAL: Strategy implementation error: {e}")
        logger.error("Missing method in RuleOneOptionsStrategy - FIX REQUIRED")
        return {"success": False, "reason": f"implementation_error: {e}"}
    except Exception as e:
        logger.error(f"Rule #1 strategy error: {e}")
        return {"success": False, "reason": str(e)}


def main():
    """Main entry point."""
    result = run_rule_one_strategy()
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
    return result


if __name__ == "__main__":
    main()
