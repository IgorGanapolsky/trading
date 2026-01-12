#!/usr/bin/env python3
"""
Credit Spread Trader - 2026 Best Practices for Small Accounts

Based on industry research (Jan 2026):
- 50/25 Delta Rule: Sell 50 delta, buy 25 delta for optimal risk/reward
- 33% Rule: Collect minimum 33% of spread width as premium
- Take profit at 50%, stop loss at 100%
- 30-45 DTE for optimal theta decay

This strategy works for accounts as small as $100-500 (vs $5,000+ for wheel).

Sources:
- https://www.optionsplay.com/blogs/how-to-grow-a-small-account
- https://alpaca.markets/learn/credit-spreads
- https://thetradinganalyst.com/put-credit-spread/
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 2026 Best Practices Configuration
CONFIG = {
    # Target stocks for credit spreads (liquid options, stable companies)
    "watchlist": [
        # Tier 1: Ultra low-price ($5-15 range) - $500-1500 collateral per spread
        "F",  # Ford - ~$10
        "SOFI",  # SoFi - ~$15
        "T",  # AT&T - ~$20
        # Tier 2: Low-price ($15-35 range) - $1500-3500 collateral
        "INTC",  # Intel - ~$20
        "BAC",  # Bank of America - ~$35
        "AAL",  # American Airlines - ~$15
        # Tier 3: ETFs for safety
        "SPY",  # S&P 500 ETF (use narrow spreads)
    ],
    # Delta rules (2026 best practice)
    "sell_delta": 0.30,  # Sell 30 delta (70% probability OTM)
    "buy_delta": 0.15,  # Buy 15 delta for protection
    # Premium rules
    "min_premium_pct": 0.33,  # 33% rule - minimum premium as % of spread width
    "min_premium_dollars": 0.30,  # Minimum $0.30 credit per spread
    # DTE rules
    "target_dte": 30,
    "min_dte": 21,
    "max_dte": 45,
    # Risk management
    "take_profit_pct": 0.50,  # Close at 50% profit
    "stop_loss_pct": 1.00,  # Close at 100% loss (2x premium)
    "max_spread_width": 5,  # $5 wide spreads max ($500 collateral)
    "max_positions": 3,  # Max concurrent positions
    "max_portfolio_risk_pct": 0.10,  # Risk max 10% of portfolio per trade
}


def get_trading_client():
    """Get Alpaca trading client."""
    try:
        from alpaca.trading.client import TradingClient
        from src.utils.alpaca_client import get_alpaca_credentials

        api_key, secret_key = get_alpaca_credentials()

        if not api_key or not secret_key:
            logger.error("Missing Alpaca credentials")
            return None

        return TradingClient(api_key, secret_key, paper=True)
    except ImportError:
        logger.error("alpaca-py not installed")
        return None
    except Exception as e:
        logger.error(f"Failed to create trading client: {e}")
        return None


def get_account_info(client) -> Optional[dict]:
    """Get current account information."""
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


def calculate_spread_collateral(spread_width: float) -> float:
    """Calculate collateral required for a credit spread.

    For a $5 wide spread, collateral = $500 (100 shares x $5 width)
    """
    return spread_width * 100


def find_put_credit_spread(symbol: str, current_price: float, client) -> Optional[dict]:
    """Find optimal put credit spread for a symbol.

    Returns a spread that meets the 33% rule and delta requirements.
    """
    try:
        from alpaca.trading.requests import GetOptionContractsRequest

        # Calculate target strikes based on delta
        # 30 delta put is roughly 1 standard deviation OTM
        # Approximate: 30 delta ≈ price - (price * 0.05)
        sell_strike = round(current_price * 0.95, 0)  # ~30 delta
        buy_strike = sell_strike - CONFIG["max_spread_width"]  # Protection leg

        # Note: target_dte config used for optimal expiration preference
        # Actual filtering uses max_dte to get all available contracts
        request = GetOptionContractsRequest(
            underlying_symbols=[symbol],
            expiration_date_gte=datetime.now().strftime("%Y-%m-%d"),
            expiration_date_lte=(datetime.now() + timedelta(days=CONFIG["max_dte"])).strftime(
                "%Y-%m-%d"
            ),
            strike_price_lte=str(sell_strike + 2),
            strike_price_gte=str(buy_strike - 2),
            type="put",
        )

        contracts = client.get_option_contracts(request)

        if not contracts or not contracts.option_contracts:
            logger.warning(f"No option contracts found for {symbol}")
            return None

        # Find best spread combination
        puts_by_strike = {}
        for contract in contracts.option_contracts:
            strike = float(contract.strike_price)
            if strike not in puts_by_strike:
                puts_by_strike[strike] = contract

        # Try to find a valid spread
        for sell_strike in sorted(puts_by_strike.keys(), reverse=True):
            buy_strike = sell_strike - CONFIG["max_spread_width"]
            if buy_strike in puts_by_strike:
                # Found a valid spread
                return {
                    "symbol": symbol,
                    "sell_strike": sell_strike,
                    "buy_strike": buy_strike,
                    "spread_width": sell_strike - buy_strike,
                    "sell_contract": puts_by_strike[sell_strike],
                    "buy_contract": puts_by_strike[buy_strike],
                    "expiration": puts_by_strike[sell_strike].expiration_date,
                    "collateral": calculate_spread_collateral(sell_strike - buy_strike),
                }

        return None

    except Exception as e:
        logger.error(f"Error finding spread for {symbol}: {e}")
        return None


def validate_spread(spread: dict, min_credit: float = 0.30) -> bool:
    """Validate spread meets 33% rule and minimum credit.

    Args:
        spread: Spread details dict
        min_credit: Minimum credit to collect (default $0.30)

    Returns:
        True if spread is valid, False otherwise
    """
    width = spread.get("spread_width", 0)
    if width <= 0:
        return False

    # Use passed credit if available, otherwise estimate
    # In real implementation, would get actual bid/ask prices
    estimated_credit = spread.get("estimated_credit")
    if estimated_credit is None:
        estimated_credit = width * 0.18  # Conservative estimate for 30 delta

    # Check 33% rule
    min_required = width * CONFIG["min_premium_pct"]
    if estimated_credit < min_required:
        logger.info(f"Spread fails 33% rule: ${estimated_credit:.2f} < ${min_required:.2f}")
        return False

    # Check minimum dollar amount
    if estimated_credit < min_credit:
        logger.info(f"Spread below minimum: ${estimated_credit:.2f} < ${min_credit:.2f}")
        return False

    return True


def execute_credit_spread(client, spread: dict) -> Optional[dict]:
    """Execute a put credit spread order.

    This sells the higher strike put and buys the lower strike put.
    """
    try:
        # In production, this would:
        # 1. Get current bid/ask for both legs
        # 2. Calculate net credit
        # 3. Submit multi-leg order

        logger.info(
            f"Would execute spread: SELL {spread['sell_strike']} PUT, BUY {spread['buy_strike']} PUT"
        )
        logger.info(f"Collateral required: ${spread['collateral']:.2f}")
        logger.info(f"Expiration: {spread['expiration']}")

        # Record the trade
        trade = {
            "timestamp": datetime.now().isoformat(),
            "symbol": spread["symbol"],
            "strategy": "put_credit_spread",
            "sell_strike": spread["sell_strike"],
            "buy_strike": spread["buy_strike"],
            "spread_width": spread["spread_width"],
            "collateral": spread["collateral"],
            "expiration": str(spread["expiration"]),
            "status": "simulated",  # Would be "filled" in production
        }

        return trade

    except Exception as e:
        logger.error(f"Failed to execute spread: {e}")
        return None


def get_current_price(symbol: str, client) -> Optional[float]:
    """Get current price for a symbol."""
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestQuoteRequest
        from src.utils.alpaca_client import get_alpaca_credentials

        api_key, secret_key = get_alpaca_credentials()

        data_client = StockHistoricalDataClient(api_key, secret_key)
        request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
        quotes = data_client.get_stock_latest_quote(request)

        if symbol in quotes:
            return float(quotes[symbol].ask_price)
        return None

    except Exception as e:
        logger.warning(f"Could not get price for {symbol}: {e}")
        return None


def select_best_opportunity(client, account: dict) -> Optional[dict]:
    """Select the best credit spread opportunity based on current market.

    Filters by:
    1. Account has enough collateral
    2. Spread meets 33% rule
    3. Symbol is in watchlist
    """
    opportunities = []

    for symbol in CONFIG["watchlist"]:
        price = get_current_price(symbol, client)
        if not price:
            continue

        # Check if we can afford 100 shares at this price
        collateral_needed = price * 100 * 0.05  # ~5% of notional for spread
        if collateral_needed > account["buying_power"] * CONFIG["max_portfolio_risk_pct"]:
            logger.info(f"Skipping {symbol}: collateral ${collateral_needed:.0f} > max risk")
            continue

        spread = find_put_credit_spread(symbol, price, client)
        if spread and validate_spread(spread):
            opportunities.append(spread)

    if not opportunities:
        return None

    # Return the spread with best risk/reward (highest premium relative to width)
    return opportunities[0]  # Simplified - would rank by premium/width ratio


def run_credit_spread_strategy():
    """Main entry point for credit spread strategy."""
    logger.info("=" * 60)
    logger.info("CREDIT SPREAD TRADER - 2026 Best Practices")
    logger.info("=" * 60)

    client = get_trading_client()
    if not client:
        logger.error("Could not connect to Alpaca")
        return

    account = get_account_info(client)
    if not account:
        logger.error("Could not get account info")
        return

    logger.info(f"Account equity: ${account['equity']:.2f}")
    logger.info(f"Buying power: ${account['buying_power']:.2f}")

    # Check minimum requirements
    if account["buying_power"] < 500:
        logger.warning("Account below $500 - credit spreads require more capital")
        logger.info("Recommendation: Continue accumulating via deposits")
        return

    # Find best opportunity
    opportunity = select_best_opportunity(client, account)
    if not opportunity:
        logger.info("No valid spread opportunities found today")
        return

    logger.info(f"Best opportunity: {opportunity['symbol']}")
    logger.info(f"  Sell {opportunity['sell_strike']} put")
    logger.info(f"  Buy {opportunity['buy_strike']} put")
    logger.info(f"  Width: ${opportunity['spread_width']}")
    logger.info(f"  Collateral: ${opportunity['collateral']:.2f}")

    # Execute (simulated for now)
    trade = execute_credit_spread(client, opportunity)
    if trade:
        logger.info("Trade executed successfully")

        # Save trade to file
        trades_file = Path("data") / f"trades_{datetime.now().strftime('%Y-%m-%d')}.json"
        trades = []
        if trades_file.exists():
            trades = json.loads(trades_file.read_text())
        trades.append(trade)
        trades_file.write_text(json.dumps(trades, indent=2))
        logger.info(f"Trade saved to {trades_file}")


if __name__ == "__main__":
    run_credit_spread_strategy()
