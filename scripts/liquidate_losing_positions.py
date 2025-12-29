#!/usr/bin/env python3
"""
Liquidate losing REIT and bond positions.

CEO Directive (Dec 29, 2025):
- Options strategy works (75% win rate, +$779 profit)
- REITs and bonds are DRAGGING performance
- LIQUIDATE all non-options positions except SPY

This script runs at market open to sell all losing positions.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Positions to LIQUIDATE (REITs, bonds, metals)
LIQUIDATE_SYMBOLS = {
    # REITs - all losing
    'AMT', 'PSA', 'CCI', 'DLR', 'EQIX', 'PLD',
    'O', 'VICI', 'WELL', 'AVB', 'EQR', 'INVH',
    # Bond ETFs - not Phil Town strategy
    'BIL', 'SHY', 'IEF', 'TLT',
    # Metals - not Phil Town strategy
    'GLD', 'SLV',
}

# Positions to KEEP
KEEP_SYMBOLS = {
    'SPY',  # Core holding - collateral for options
}


def main():
    """Liquidate losing positions."""
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
    except ImportError:
        logger.error("alpaca-py not installed. Run: pip install alpaca-py")
        sys.exit(1)

    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    paper = os.getenv('PAPER_TRADING', 'true').lower() == 'true'

    if not api_key or not secret_key:
        logger.error("ALPACA_API_KEY and ALPACA_SECRET_KEY required")
        sys.exit(1)

    client = TradingClient(api_key, secret_key, paper=paper)

    # Get current positions
    positions = client.get_all_positions()

    logger.info("=" * 60)
    logger.info("LIQUIDATION EXECUTION - %s", datetime.now().isoformat())
    logger.info("=" * 60)

    liquidated = []
    kept = []
    errors = []

    for pos in positions:
        symbol = pos.symbol
        qty = float(pos.qty)
        unrealized_pl = float(pos.unrealized_pl)
        market_value = float(pos.market_value)

        # Skip options (they have longer symbols like SPY260123P00660000)
        if len(symbol) > 10:
            logger.info("KEEP (option): %s - P/L=$%.2f", symbol, unrealized_pl)
            kept.append({'symbol': symbol, 'pl': unrealized_pl, 'reason': 'option'})
            continue

        if symbol in KEEP_SYMBOLS:
            logger.info("KEEP: %s - qty=%.4f, P/L=$%.2f", symbol, qty, unrealized_pl)
            kept.append({'symbol': symbol, 'pl': unrealized_pl, 'reason': 'keep_list'})
            continue

        if symbol in LIQUIDATE_SYMBOLS or symbol not in KEEP_SYMBOLS:
            logger.info("LIQUIDATE: %s - qty=%.4f, P/L=$%.2f, value=$%.2f",
                       symbol, qty, unrealized_pl, market_value)

            if qty > 0:
                try:
                    order = MarketOrderRequest(
                        symbol=symbol,
                        qty=qty,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY
                    )
                    result = client.submit_order(order)
                    logger.info("  ✅ SOLD %s: Order %s submitted", symbol, result.id)
                    liquidated.append({
                        'symbol': symbol,
                        'qty': qty,
                        'pl': unrealized_pl,
                        'order_id': str(result.id)
                    })
                except Exception as e:
                    logger.error("  ❌ FAILED %s: %s", symbol, e)
                    errors.append({'symbol': symbol, 'error': str(e)})

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("LIQUIDATION SUMMARY")
    logger.info("=" * 60)
    logger.info("Positions liquidated: %d", len(liquidated))
    logger.info("Positions kept: %d", len(kept))
    logger.info("Errors: %d", len(errors))

    total_pl_liquidated = sum(p['pl'] for p in liquidated)
    logger.info("Total P/L liquidated: $%.2f", total_pl_liquidated)

    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'liquidated': liquidated,
        'kept': kept,
        'errors': errors,
        'total_pl_liquidated': total_pl_liquidated
    }

    output_file = Path('data') / f"liquidation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved to: %s", output_file)

    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
