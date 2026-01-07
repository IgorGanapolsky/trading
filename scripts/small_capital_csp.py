#!/usr/bin/env python3
"""
Small Capital CSP (Cash-Secured Put) Strategy

PURPOSE: Execute Phil Town CSPs with limited capital ($500-$5000)
TARGET: First trade when capital reaches $500 (not $200 - math doesn't work)

CRITICAL MATH:
- CSP requires 100 x strike price in collateral
- $200 capital → Max $2 strike → Almost no liquid options exist
- $500 capital → Max $5 strike → F, SOFI, cheap stocks possible
- $1000 capital → Max $10 strike → INTC, BAC accessible

Created: January 6, 2026
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Capital tier configuration
CAPITAL_TIERS = {
    500: {
        "max_strike": 5.0,
        "watchlist": ["F", "SOFI"],
        "daily_target": 1.50,  # $1.50/day realistic
        "strategy": "Single CSP on cheap stock",
    },
    1000: {
        "max_strike": 10.0,
        "watchlist": ["F", "SOFI", "INTC", "PLTR"],
        "daily_target": 3.00,
        "strategy": "Single CSP or 2x on cheap stocks",
    },
    2000: {
        "max_strike": 20.0,
        "watchlist": ["F", "SOFI", "INTC", "BAC", "T"],
        "daily_target": 6.00,
        "strategy": "Multiple CSPs possible",
    },
    5000: {
        "max_strike": 50.0,
        "watchlist": ["AAPL", "MSFT", "V", "MA", "COST", "BAC", "INTC"],
        "daily_target": 15.00,
        "strategy": "Full Phil Town universe",
    },
}


def get_current_capital() -> float:
    """Get current capital from system state."""
    try:
        state_path = Path("data/system_state.json")
        if state_path.exists():
            with open(state_path) as f:
                state = json.load(f)
            # Check paper account for testing
            paper_equity = state.get("paper_account", {}).get("cash", 0)
            live_equity = state.get("account", {}).get("current_equity", 0)
            return max(paper_equity, live_equity)
    except Exception as e:
        logger.warning(f"Could not read system state: {e}")
    return 0


def get_tier_for_capital(capital: float) -> dict:
    """Get the appropriate tier configuration for given capital."""
    sorted_tiers = sorted(CAPITAL_TIERS.keys())

    for tier_capital in reversed(sorted_tiers):
        if capital >= tier_capital:
            return {
                "tier_capital": tier_capital,
                **CAPITAL_TIERS[tier_capital]
            }

    return {
        "tier_capital": 0,
        "max_strike": 0,
        "watchlist": [],
        "daily_target": 0,
        "strategy": "INSUFFICIENT CAPITAL - Cannot trade CSPs yet",
    }


def calculate_sticker_price(symbol: str) -> Optional[dict]:
    """
    Calculate Phil Town Sticker Price and MOS for a symbol.

    Returns dict with sticker_price, mos_price, current_price, recommendation
    """
    try:
        # Try yfinance first
        try:
            from src.utils import yfinance_wrapper as yf
            ticker = yf.Ticker(symbol)
            info = ticker.info

            current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
            eps = info.get("trailingEps", 0)
            growth = info.get("earningsGrowth", 0.10) or 0.10

            if eps <= 0:
                logger.warning(f"{symbol}: No positive EPS, using price-based estimate")
                # Estimate based on historical patterns
                eps = current_price / 15  # Assume P/E of 15

            # Phil Town formula
            growth = min(max(growth, 0.05), 0.25)  # Cap between 5% and 25%
            future_eps = eps * ((1 + growth) ** 10)
            future_pe = min(growth * 100 * 2, 50)
            future_pe = max(future_pe, 8)
            future_price = future_eps * future_pe
            sticker_price = future_price / ((1.15) ** 10)  # 15% MARR
            mos_price = sticker_price * 0.50  # 50% margin of safety

            return {
                "symbol": symbol,
                "current_price": round(current_price, 2),
                "sticker_price": round(sticker_price, 2),
                "mos_price": round(mos_price, 2),
                "growth_rate": round(growth * 100, 1),
                "eps": round(eps, 2),
                "recommendation": get_recommendation(current_price, sticker_price, mos_price),
            }

        except ImportError:
            logger.warning("yfinance not available, using fallback estimates")
            return None

    except Exception as e:
        logger.error(f"Error calculating sticker price for {symbol}: {e}")
        return None


def get_recommendation(current: float, sticker: float, mos: float) -> str:
    """Get Phil Town recommendation based on prices."""
    if current <= mos:
        return "STRONG BUY - Below MOS (Sell CSP)"
    elif current <= sticker:
        return "BUY - Below Sticker"
    elif current <= sticker * 1.2:
        return "HOLD - Near Fair Value"
    else:
        return "OVERVALUED - Avoid"


def find_csp_opportunity(symbol: str, mos_price: float, max_strike: float, capital: float) -> Optional[dict]:
    """
    Find a CSP opportunity for the given symbol.

    Args:
        symbol: Stock ticker
        mos_price: Phil Town Margin of Safety price
        max_strike: Maximum strike based on capital
        capital: Available capital

    Returns:
        dict with option details or None
    """
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOptionContractsRequest

        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            logger.warning("No Alpaca credentials")
            return None

        client = TradingClient(api_key, secret_key, paper=True)

        # Target strike is the lower of MOS and max affordable
        target_strike = min(mos_price, max_strike)

        request = GetOptionContractsRequest(
            underlying_symbols=[symbol],
            expiration_date_gte=datetime.now().strftime("%Y-%m-%d"),
            expiration_date_lte=(datetime.now() + timedelta(days=45)).strftime("%Y-%m-%d"),
            strike_price_gte=str(target_strike * 0.90),
            strike_price_lte=str(target_strike * 1.10),
            type="put",
        )

        contracts = client.get_option_contracts(request)

        if contracts and contracts.option_contracts:
            # Find best contract (closest to target strike, 30-45 DTE)
            best = None
            best_score = float("inf")

            for contract in contracts.option_contracts:
                strike = float(contract.strike_price)

                # Check if we can afford this
                collateral_needed = strike * 100
                if collateral_needed > capital:
                    continue

                exp_date = datetime.strptime(str(contract.expiration_date), "%Y-%m-%d")
                dte = (exp_date - datetime.now()).days

                # Score: prefer closer to 30 DTE and target strike
                strike_diff = abs(strike - target_strike)
                dte_diff = abs(dte - 30)
                score = strike_diff + dte_diff * 0.3

                if score < best_score:
                    best_score = score
                    best = {
                        "symbol": contract.symbol,
                        "underlying": symbol,
                        "strike": strike,
                        "expiration": str(contract.expiration_date),
                        "dte": dte,
                        "collateral": collateral_needed,
                    }

            return best

    except ImportError:
        logger.warning("Alpaca not available - dry run mode")
        return {
            "symbol": f"{symbol}260207P00{int(mos_price):05d}00",
            "underlying": symbol,
            "strike": mos_price,
            "expiration": "2026-02-07",
            "dte": 32,
            "collateral": mos_price * 100,
            "dry_run": True,
        }
    except Exception as e:
        logger.error(f"Error finding CSP for {symbol}: {e}")
        return None


def execute_csp(option: dict, capital: float) -> dict:
    """
    Execute (or simulate) a CSP trade.

    Returns trade result dict.
    """
    if option.get("dry_run"):
        logger.info(f"DRY RUN: Would sell {option['symbol']} CSP")
        return {
            "success": True,
            "dry_run": True,
            "option": option,
            "estimated_premium": option["strike"] * 0.02,  # ~2% estimate
        }

    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest

        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        client = TradingClient(api_key, secret_key, paper=True)

        # Estimate premium (2% of strike as starting point)
        estimated_premium = round(option["strike"] * 0.02, 2)

        order = LimitOrderRequest(
            symbol=option["symbol"],
            qty=1,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            limit_price=estimated_premium,
        )

        result = client.submit_order(order)

        return {
            "success": True,
            "order_id": str(result.id),
            "option": option,
            "limit_price": estimated_premium,
        }

    except Exception as e:
        logger.error(f"Trade execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "option": option,
        }


def run_small_capital_csp():
    """Main entry point for small capital CSP strategy."""
    logger.info("=" * 60)
    logger.info("SMALL CAPITAL CSP STRATEGY")
    logger.info("Phil Town Rule #1 for Limited Capital")
    logger.info("=" * 60)

    # Get current capital
    capital = get_current_capital()
    logger.info(f"\nCurrent Capital: ${capital:,.2f}")

    # Get tier
    tier = get_tier_for_capital(capital)
    logger.info(f"Capital Tier: ${tier['tier_capital']}")
    logger.info(f"Max Strike: ${tier['max_strike']:.2f}")
    logger.info(f"Daily Target: ${tier['daily_target']:.2f}")
    logger.info(f"Strategy: {tier['strategy']}")
    logger.info(f"Watchlist: {tier['watchlist']}")

    if tier["tier_capital"] == 0:
        logger.warning("\n⚠️  INSUFFICIENT CAPITAL FOR CSPs")
        logger.warning("Need minimum $500 to sell cash-secured puts on cheap stocks")
        logger.warning("Current plan: Continue depositing $10/day until $500 reached")

        days_to_500 = max(0, (500 - capital) / 10)
        logger.info(f"Days until first CSP possible: ~{days_to_500:.0f}")

        return {
            "success": False,
            "reason": "insufficient_capital",
            "capital": capital,
            "needed": 500,
            "days_to_trade": days_to_500,
        }

    # Analyze watchlist
    opportunities = []

    for symbol in tier["watchlist"]:
        logger.info(f"\n--- Analyzing {symbol} ---")

        valuation = calculate_sticker_price(symbol)
        if not valuation:
            logger.warning(f"  Could not value {symbol}")
            continue

        logger.info(f"  Current: ${valuation['current_price']:.2f}")
        logger.info(f"  Sticker: ${valuation['sticker_price']:.2f}")
        logger.info(f"  MOS: ${valuation['mos_price']:.2f}")
        logger.info(f"  Recommendation: {valuation['recommendation']}")

        # Check if MOS price is within our capital constraint
        mos_collateral = valuation["mos_price"] * 100
        if mos_collateral > capital:
            logger.info(f"  ⚠️  MOS requires ${mos_collateral:.0f} collateral (have ${capital:.0f})")
            continue

        # Find CSP opportunity
        if "BUY" in valuation["recommendation"] or "STRONG" in valuation["recommendation"]:
            option = find_csp_opportunity(
                symbol,
                valuation["mos_price"],
                tier["max_strike"],
                capital
            )

            if option:
                opportunities.append({
                    "valuation": valuation,
                    "option": option,
                })
                logger.info(f"  ✅ Found CSP: {option['symbol']} @ ${option['strike']:.2f}")

    logger.info(f"\n{'=' * 60}")
    logger.info(f"SUMMARY: Found {len(opportunities)} CSP opportunities")

    # Execute best opportunity (if any)
    trades = []
    for opp in opportunities[:1]:  # Only execute 1 trade at a time
        logger.info(f"\nExecuting CSP on {opp['option']['underlying']}...")
        result = execute_csp(opp["option"], capital)
        trades.append(result)

        if result.get("success"):
            logger.info("  ✅ Trade submitted")
        else:
            logger.warning(f"  ❌ Trade failed: {result.get('error')}")

    return {
        "success": True,
        "capital": capital,
        "tier": tier["tier_capital"],
        "opportunities": len(opportunities),
        "trades": trades,
    }


if __name__ == "__main__":
    result = run_small_capital_csp()
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
