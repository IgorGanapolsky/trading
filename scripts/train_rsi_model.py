#!/usr/bin/env python3
"""
RSI Optimization Training Script


Usage:
    python scripts/train_rsi_model.py
    python scripts/train_rsi_model.py --symbols -USD -USD
    python scripts/train_rsi_model.py --lookback 180 --output data/rsi_results.json
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ml.rsi_optimizer import RSIOptimizer


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the script."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/rsi_optimization.log"),
        ],
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Optimize with default settings
  python scripts/train_rsi_model.py

  python scripts/train_rsi_model.py --symbols -USD -USD -USD

  # Use longer historical period
  python scripts/train_rsi_model.py --lookback 180

  # Custom thresholds
  python scripts/train_rsi_model.py --thresholds 35 40 45 50 55 60 65

  # Save to custom location
  python scripts/train_rsi_model.py --output data/custom_rsi_results.json
        """,
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        default=[-USD", -USD"],
    )

    parser.add_argument(
        "--lookback",
        type=int,
        default=90,
        help="Number of days of historical data (default: 90)",
    )

    parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=None,
        help="RSI thresholds to test (default: 40 45 50 55 60)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="data/rsi_optimization_results.json",
        help="Output JSON file path (default: data/rsi_optimization_results.json)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def optimize_symbol(
    symbol: str,
    lookback_days: int,
    thresholds: list[float] | None = None,
) -> dict:
    """
    Optimize RSI threshold for a single symbol.

    Args:
        lookback_days: Days of historical data
        thresholds: RSI thresholds to test

    Returns:
        Optimization results dictionary
    """
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info(f"Optimizing RSI threshold for {symbol}")
    logger.info("=" * 80)

    try:
        optimizer = RSIOptimizer(
            symbol=symbol,
            lookback_days=lookback_days,
            thresholds=thresholds,
        )

        results = optimizer.optimize()
        return results

    except Exception as e:
        logger.error(f"Failed to optimize {symbol}: {e}", exc_info=True)
        return {
            "symbol": symbol,
            "error": str(e),
            "optimization_date": datetime.now().isoformat(),
        }


def main():
    """Main execution function."""
    args = parse_args()

    # Setup logging
    Path("logs").mkdir(exist_ok=True)
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("RSI OPTIMIZATION TRAINING SCRIPT")
    logger.info("=" * 80)
    logger.info(f"Symbols: {', '.join(args.symbols)}")
    logger.info(f"Lookback: {args.lookback} days")
    logger.info(f"Thresholds: {args.thresholds or 'default (40, 45, 50, 55, 60)'}")
    logger.info(f"Output: {args.output}")
    logger.info("=" * 80)

    # Optimize each symbol
    all_results = {}
    for symbol in args.symbols:
        results = optimize_symbol(
            symbol=symbol,
            lookback_days=args.lookback,
            thresholds=args.thresholds,
        )
        all_results[symbol] = results

    # Compile summary
    summary = {
        "training_date": datetime.now().isoformat(),
        "lookback_days": args.lookback,
        "symbols_optimized": args.symbols,
        "results": all_results,
    }

    # Add comparison summary
    successful_results = {
        k: v for k, v in all_results.items() if "error" not in v
    }

    if successful_results:
        comparison = []
        for symbol, result in successful_results.items():
            comparison.append({
                "symbol": symbol,
                "best_threshold": result["best_threshold"],
                "sharpe_ratio": result["best_sharpe"],
                "win_rate": result["best_win_rate"],
                "total_return": result["best_total_return"],
            })

        # Sort by Sharpe ratio
        comparison.sort(key=lambda x: x["sharpe_ratio"], reverse=True)
        summary["comparison"] = comparison

        # Best overall
        best = comparison[0]
        summary["best_overall"] = {
            "symbol": best["symbol"],
            "threshold": best["best_threshold"],
            "sharpe": best["sharpe_ratio"],
            "reason": f"{best['symbol']} with RSI > {best['best_threshold']} has the highest Sharpe ratio ({best['sharpe_ratio']:.2f})",
        }

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("=" * 80)
    logger.info(f"Results saved to {output_path}")
    logger.info("=" * 80)

    # Print summary
    print("\n" + "=" * 80)
    print("RSI OPTIMIZATION COMPLETE")
    print("=" * 80)

    if successful_results:
        print("\nRESULTS BY SYMBOL:")
        print("-" * 80)
        for result in comparison:
            print(f"{result['symbol']:10s} | RSI > {result['best_threshold']:4.0f} | "
                  f"Sharpe: {result['sharpe_ratio']:6.3f} | "
                  f"Win Rate: {result['win_rate']:5.1f}% | "
                  f"Return: {result['total_return']:6.2f}%")

        print("\n" + "=" * 80)
        print("RECOMMENDATION (Best Risk-Adjusted Performance):")
        print("-" * 80)
        print(f"Symbol: {summary['best_overall']['symbol']}")
        print(f"Optimal RSI Threshold: {summary['best_overall']['threshold']}")
        print(f"Sharpe Ratio: {summary['best_overall']['sharpe']:.3f}")
        print(f"\n{summary['best_overall']['reason']}")
        print("=" * 80)
    else:
        print("\n❌ No successful optimizations. Check logs for errors.")

    # Print errors if any
    failed = [k for k, v in all_results.items() if "error" in v]
    if failed:
        print(f"\n⚠️  Failed to optimize: {', '.join(failed)}")
        print("   Check logs/rsi_optimization.log for details")

    print(f"\nFull results saved to: {output_path}")
    print("=" * 80 + "\n")

    # Exit with appropriate code
    sys.exit(0 if successful_results else 1)


if __name__ == "__main__":
    main()
