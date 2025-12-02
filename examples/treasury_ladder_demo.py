#!/usr/bin/env python3
"""
Treasury Ladder Strategy - Integration Demo

This script demonstrates how to use the TreasuryLadderStrategy
to build a stable income ladder using treasury ETFs (SHY, IEF, TLT).

Usage:
    # Dry run (analysis only, no trades)
    python3 examples/treasury_ladder_demo.py --dry-run

    # Execute daily investment
    python3 examples/treasury_ladder_demo.py --execute --amount 10.0

    # Check and execute rebalancing
    python3 examples/treasury_ladder_demo.py --rebalance

    # Get performance summary
    python3 examples/treasury_ladder_demo.py --summary

Requirements:
    - ALPACA_API_KEY and ALPACA_SECRET_KEY in .env
    - FRED_API_KEY in .env (optional, for yield curve data)

Author: Trading System
Created: 2025-12-02
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.treasury_ladder_strategy import TreasuryLadderStrategy


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Treasury Ladder Strategy Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze yield curve only
  python3 examples/treasury_ladder_demo.py --dry-run

  # Execute daily $10 investment
  python3 examples/treasury_ladder_demo.py --execute --amount 10.0

  # Check and rebalance if needed
  python3 examples/treasury_ladder_demo.py --rebalance

  # Get performance summary
  python3 examples/treasury_ladder_demo.py --summary
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze only, don't execute trades",
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute daily investment",
    )

    parser.add_argument(
        "--amount",
        type=float,
        default=10.0,
        help="Daily investment amount (default: $10)",
    )

    parser.add_argument(
        "--rebalance",
        action="store_true",
        help="Check and execute rebalancing if needed",
    )

    parser.add_argument(
        "--summary",
        action="store_true",
        help="Display performance summary",
    )

    parser.add_argument(
        "--paper",
        action="store_true",
        default=True,
        help="Use paper trading (default: True)",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Use LIVE trading (use with caution!)",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Determine paper vs live
    paper = not args.live

    if not paper:
        logger.warning("⚠️  LIVE TRADING MODE ENABLED ⚠️")
        response = input("Are you sure you want to trade with real money? (yes/no): ")
        if response.lower() != "yes":
            logger.info("Aborting live trading")
            return

    # Initialize strategy
    logger.info("Initializing Treasury Ladder Strategy...")
    strategy = TreasuryLadderStrategy(
        daily_allocation=args.amount,
        rebalance_threshold=0.05,  # 5% drift threshold
        paper=paper,
    )

    print("\n" + "=" * 80)
    print("TREASURY LADDER STRATEGY")
    print("=" * 80)

    # Dry run: analyze only
    if args.dry_run or not (args.execute or args.rebalance or args.summary):
        print("\n📊 YIELD CURVE ANALYSIS")
        print("-" * 80)
        regime, spread, rationale = strategy.analyze_yield_curve()
        print(f"Regime:    {regime.value.upper()}")
        print(f"Spread:    {spread:.2f}% (10yr - 2yr)")
        print(f"Rationale: {rationale}")

        print("\n📈 OPTIMAL ALLOCATION")
        print("-" * 80)
        allocation = strategy.get_optimal_allocation()
        print(f"SHY (1-3yr):   {allocation.shy_pct*100:>5.1f}%")
        print(f"IEF (7-10yr):  {allocation.ief_pct*100:>5.1f}%")
        print(f"TLT (20+yr):   {allocation.tlt_pct*100:>5.1f}%")
        print(f"Total:         {(allocation.shy_pct + allocation.ief_pct + allocation.tlt_pct)*100:>5.1f}%")

        if args.amount:
            print(f"\n💰 INVESTMENT BREAKDOWN (${args.amount:.2f})")
            print("-" * 80)
            print(f"SHY: ${args.amount * allocation.shy_pct:>7.2f}")
            print(f"IEF: ${args.amount * allocation.ief_pct:>7.2f}")
            print(f"TLT: ${args.amount * allocation.tlt_pct:>7.2f}")

    # Execute daily investment
    if args.execute:
        print(f"\n💸 EXECUTING DAILY INVESTMENT (${args.amount:.2f})")
        print("-" * 80)

        if paper:
            print("Mode: PAPER TRADING")
        else:
            print("⚠️  Mode: LIVE TRADING ⚠️")

        result = strategy.execute_daily(amount=args.amount)

        if result["success"]:
            print(f"✅ Success: {len(result['orders'])} orders executed")
            print(f"   Total invested: ${result['total_invested']:.2f}")

            for order in result["orders"]:
                print(f"   - {order['symbol']}: ${order['notional']:.2f}")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")

    # Check rebalancing
    if args.rebalance:
        print("\n⚖️  REBALANCING CHECK")
        print("-" * 80)

        decision = strategy.rebalance_if_needed()

        if decision:
            if decision.should_rebalance:
                print(f"✅ REBALANCED: {decision.reason}")
                print(f"   Max drift: {decision.max_drift*100:.1f}%")

                print("\n   Current → Target:")
                for symbol in ["SHY", "IEF", "TLT"]:
                    curr = decision.current_allocation[symbol]
                    targ = decision.target_allocation[symbol]
                    drift = decision.drift_pct[symbol]
                    print(f"   {symbol}: {curr*100:>5.1f}% → {targ*100:>5.1f}% (drift: {drift*100:>4.1f}%)")
            else:
                print(f"ℹ️  No rebalancing needed: {decision.reason}")
                print(f"   Max drift: {decision.max_drift*100:.1f}% (threshold: {strategy.rebalance_threshold*100:.1f}%)")
        else:
            print("⚠️  Could not check rebalancing (insufficient data or too soon)")

    # Performance summary
    if args.summary:
        print("\n📈 PERFORMANCE SUMMARY")
        print("-" * 80)

        summary = strategy.get_performance_summary()

        if "error" in summary:
            print(f"❌ Error: {summary['error']}")
        else:
            print(f"Total invested:       ${summary['total_invested']:.2f}")
            print(f"Market value:         ${summary['total_market_value']:.2f}")
            print(f"Cost basis:           ${summary['total_cost_basis']:.2f}")
            print(f"Unrealized P/L:       ${summary['total_unrealized_pl']:.2f}")
            print(f"Return:               {summary['return_pct']:.2f}%")
            print(f"Current regime:       {summary['current_regime']}")
            print(f"Last rebalance:       {summary['last_rebalance'] or 'Never'}")
            print(f"Rebalance count:      {summary['rebalance_count']}")

            if summary['positions']:
                print("\nPositions:")
                for pos in summary['positions']:
                    print(f"  {pos['symbol']:>4}: {pos['qty']:>8.4f} shares @ ${pos['avg_entry_price']:>8.2f} = ${pos['market_value']:>8.2f}")

    print("\n" + "=" * 80)
    print("Demo complete!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
