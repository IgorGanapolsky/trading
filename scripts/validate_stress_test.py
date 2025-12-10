#!/usr/bin/env python3
"""
Pre-Deployment Stress Test Validator

Runs pessimistic backtest and validates that the strategy passes
minimum requirements before live deployment.

Validation Criteria:
1. Pessimistic Sharpe ratio >= 0.5
2. Maximum drawdown <= 25%
3. Strategy remains profitable under stress
4. Win rate doesn't drop more than 15 percentage points

Usage:
    python scripts/validate_stress_test.py --symbols SPY,QQQ
    python scripts/validate_stress_test.py --min-sharpe 0.5 --max-drawdown 25
    python scripts/validate_stress_test.py --period 180  # 180 days backtest

Exit Codes:
    0: Validation passed - safe to deploy
    1: Validation failed - DO NOT deploy
    2: Error during validation

Author: Trading System
Created: 2025-12-05
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the validator."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def run_backtest(
    symbols: list[str],
    start_date: str,
    end_date: str,
    pessimistic: bool = False,
    initial_capital: float = 100000.0,
) -> dict[str, Any]:
    """
    Run backtest with specified parameters.

    Args:
        symbols: List of symbols to trade
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        pessimistic: Whether to use pessimistic assumptions
        initial_capital: Starting capital

    Returns:
        Dict with backtest results
    """
    try:
        from src.backtesting.backtest_engine import BacktestEngine
        from src.strategies.core_strategy import CoreStrategy

        # Create strategy
        strategy = CoreStrategy(
            etf_universe=symbols,
            daily_allocation=10.0,
            use_sentiment=False,
        )

        # Configure slippage based on mode
        if pessimistic:
            # Double slippage for stress test
            slippage_bps = 10.0  # 2x normal
            enable_commissions = True
            logger.info("Running PESSIMISTIC backtest (2x slippage, commissions enabled)")
        else:
            slippage_bps = 5.0
            enable_commissions = True
            logger.info("Running NORMAL backtest")

        # Run backtest
        engine = BacktestEngine(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            enable_slippage=True,
            slippage_bps=slippage_bps,
            enable_commissions=enable_commissions,
        )

        results = engine.run()

        return {
            "total_pnl": results.final_capital - results.initial_capital,
            "total_return": results.total_return,
            "sharpe_ratio": results.sharpe_ratio,
            "max_drawdown": results.max_drawdown,
            "win_rate": results.win_rate,
            "total_trades": results.total_trades,
            "slippage_cost": results.total_slippage_cost,
            "commission_cost": results.total_commission_cost,
            "start_date": start_date,
            "end_date": end_date,
            "pessimistic_mode": pessimistic,
        }

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        return {"error": str(e)}


def validate_results(
    normal_results: dict[str, Any],
    pessimistic_results: dict[str, Any],
    min_sharpe: float = 0.5,
    max_drawdown: float = 25.0,
    max_win_rate_drop: float = 15.0,
) -> dict[str, Any]:
    """
    Validate stress test results against criteria.

    Args:
        normal_results: Results from normal backtest
        pessimistic_results: Results from pessimistic backtest
        min_sharpe: Minimum acceptable Sharpe ratio (pessimistic)
        max_drawdown: Maximum acceptable drawdown percentage
        max_win_rate_drop: Maximum acceptable win rate drop (percentage points)

    Returns:
        Validation report with pass/fail status
    """
    if "error" in pessimistic_results:
        return {
            "passes": False,
            "reason": f"Backtest error: {pessimistic_results['error']}",
        }

    # Extract metrics
    pess_sharpe = pessimistic_results.get("sharpe_ratio", 0)
    pess_drawdown = pessimistic_results.get("max_drawdown", 100)
    pess_pnl = pessimistic_results.get("total_pnl", 0)
    pess_win_rate = pessimistic_results.get("win_rate", 0)

    normal_win_rate = normal_results.get("win_rate", 0) if normal_results else pess_win_rate
    win_rate_drop = normal_win_rate - pess_win_rate

    # Check criteria
    criteria = {
        "sharpe_ratio": {
            "value": pess_sharpe,
            "threshold": min_sharpe,
            "operator": ">=",
            "passes": pess_sharpe >= min_sharpe,
            "message": f"Sharpe ratio {pess_sharpe:.2f} {'≥' if pess_sharpe >= min_sharpe else '<'} {min_sharpe}",
        },
        "max_drawdown": {
            "value": pess_drawdown,
            "threshold": max_drawdown,
            "operator": "<=",
            "passes": pess_drawdown <= max_drawdown,
            "message": f"Max drawdown {pess_drawdown:.1f}% {'≤' if pess_drawdown <= max_drawdown else '>'} {max_drawdown}%",
        },
        "profitability": {
            "value": pess_pnl,
            "threshold": 0,
            "operator": ">",
            "passes": pess_pnl > 0,
            "message": f"P/L ${pess_pnl:,.2f} {'>' if pess_pnl > 0 else '≤'} $0",
        },
        "win_rate_stability": {
            "value": win_rate_drop,
            "threshold": max_win_rate_drop,
            "operator": "<=",
            "passes": win_rate_drop <= max_win_rate_drop,
            "message": f"Win rate drop {win_rate_drop:.1f}pp {'≤' if win_rate_drop <= max_win_rate_drop else '>'} {max_win_rate_drop}pp",
        },
    }

    # Overall pass/fail
    all_pass = all(c["passes"] for c in criteria.values())

    # Build failure reasons
    failures = [c["message"] for c in criteria.values() if not c["passes"]]

    return {
        "passes": all_pass,
        "criteria": criteria,
        "failures": failures,
        "reason": "; ".join(failures) if failures else "All criteria passed",
        "metrics": {
            "pessimistic_sharpe": pess_sharpe,
            "pessimistic_drawdown": pess_drawdown,
            "pessimistic_pnl": pess_pnl,
            "pessimistic_win_rate": pess_win_rate,
            "normal_win_rate": normal_win_rate,
            "win_rate_drop": win_rate_drop,
        },
    }


def save_results(
    validation: dict[str, Any],
    normal_results: dict[str, Any],
    pessimistic_results: dict[str, Any],
    output_path: Optional[Path] = None,
) -> Path:
    """Save validation results to JSON file."""
    output_path = output_path or Path("data/stress_test_results.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "validation_date": datetime.now().isoformat(),
        "validation": validation,
        "normal_results": normal_results,
        "pessimistic_results": pessimistic_results,
    }

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"Results saved to {output_path}")
    return output_path


def print_report(
    validation: dict[str, Any],
    normal_results: dict[str, Any],
    pessimistic_results: dict[str, Any],
) -> None:
    """Print formatted validation report."""
    print("\n" + "=" * 70)
    print("PRE-DEPLOYMENT STRESS TEST REPORT")
    print("=" * 70)

    print(f"\nValidation Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backtest Period: {pessimistic_results.get('start_date', 'N/A')} to {pessimistic_results.get('end_date', 'N/A')}")

    print("\n" + "-" * 70)
    print("COMPARISON: Normal vs Pessimistic")
    print("-" * 70)

    # Format comparison table
    headers = ["Metric", "Normal", "Pessimistic", "Change"]
    rows = []

    if normal_results and "error" not in normal_results:
        normal_sharpe = normal_results.get("sharpe_ratio", 0)
        pess_sharpe = pessimistic_results.get("sharpe_ratio", 0)
        rows.append([
            "Sharpe Ratio",
            f"{normal_sharpe:.2f}",
            f"{pess_sharpe:.2f}",
            f"{pess_sharpe - normal_sharpe:+.2f}",
        ])

        normal_dd = normal_results.get("max_drawdown", 0)
        pess_dd = pessimistic_results.get("max_drawdown", 0)
        rows.append([
            "Max Drawdown",
            f"{normal_dd:.1f}%",
            f"{pess_dd:.1f}%",
            f"{pess_dd - normal_dd:+.1f}pp",
        ])

        normal_pnl = normal_results.get("total_pnl", 0)
        pess_pnl = pessimistic_results.get("total_pnl", 0)
        rows.append([
            "P/L",
            f"${normal_pnl:,.0f}",
            f"${pess_pnl:,.0f}",
            f"${pess_pnl - normal_pnl:,.0f}",
        ])

        normal_wr = normal_results.get("win_rate", 0)
        pess_wr = pessimistic_results.get("win_rate", 0)
        rows.append([
            "Win Rate",
            f"{normal_wr:.1f}%",
            f"{pess_wr:.1f}%",
            f"{pess_wr - normal_wr:+.1f}pp",
        ])

    # Print table
    col_widths = [20, 15, 15, 15]
    header_line = "  ".join(h.ljust(w) for h, w in zip(headers, col_widths))
    print(f"\n  {header_line}")
    print("  " + "-" * sum(col_widths))
    for row in rows:
        row_line = "  ".join(str(c).ljust(w) for c, w in zip(row, col_widths))
        print(f"  {row_line}")

    print("\n" + "-" * 70)
    print("VALIDATION CRITERIA")
    print("-" * 70)

    if "criteria" in validation:
        for name, criterion in validation["criteria"].items():
            status = "✅ PASS" if criterion["passes"] else "❌ FAIL"
            print(f"  {status}  {criterion['message']}")

    print("\n" + "=" * 70)
    status = "✅ VALIDATION PASSED" if validation["passes"] else "❌ VALIDATION FAILED"
    print(f"FINAL STATUS: {status}")
    print("=" * 70)

    if not validation["passes"]:
        print("\n⚠️  DO NOT DEPLOY - Strategy fails stress test requirements")
        print(f"Reason: {validation['reason']}")
    else:
        print("\n✅ Safe to deploy - Strategy survives stress test")

    print()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Pre-deployment stress test validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--symbols",
        type=str,
        default="SPY,QQQ,IWM",
        help="Comma-separated list of symbols (default: SPY,QQQ,IWM)",
    )
    parser.add_argument(
        "--period",
        type=int,
        default=180,
        help="Backtest period in days (default: 180)",
    )
    parser.add_argument(
        "--min-sharpe",
        type=float,
        default=0.5,
        help="Minimum acceptable Sharpe ratio (default: 0.5)",
    )
    parser.add_argument(
        "--max-drawdown",
        type=float,
        default=25.0,
        help="Maximum acceptable drawdown %% (default: 25)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100000.0,
        help="Initial capital for backtest (default: 100000)",
    )
    parser.add_argument(
        "--skip-normal",
        action="store_true",
        help="Skip normal backtest (only run pessimistic)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path for results JSON",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Output only JSON result (for CI integration)",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Parse symbols
    symbols = [s.strip().upper() for s in args.symbols.split(",")]

    # Calculate date range
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=args.period)).strftime("%Y-%m-%d")

    if not args.json_output:
        print(f"\n🔬 Running stress test validation...")
        print(f"   Symbols: {', '.join(symbols)}")
        print(f"   Period: {start_date} to {end_date} ({args.period} days)")
        print(f"   Capital: ${args.capital:,.0f}")
        print(f"   Min Sharpe: {args.min_sharpe}")
        print(f"   Max Drawdown: {args.max_drawdown}%")

    try:
        # Run normal backtest (optional)
        normal_results = {}
        if not args.skip_normal:
            if not args.json_output:
                print("\n📊 Running normal backtest...")
            normal_results = run_backtest(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                pessimistic=False,
                initial_capital=args.capital,
            )

        # Run pessimistic backtest
        if not args.json_output:
            print("\n🔴 Running pessimistic (stress) backtest...")
        pessimistic_results = run_backtest(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            pessimistic=True,
            initial_capital=args.capital,
        )

        # Validate results
        validation = validate_results(
            normal_results=normal_results,
            pessimistic_results=pessimistic_results,
            min_sharpe=args.min_sharpe,
            max_drawdown=args.max_drawdown,
        )

        # Save results
        output_path = Path(args.output) if args.output else None
        save_results(validation, normal_results, pessimistic_results, output_path)

        # Output
        if args.json_output:
            output = {
                "passes": validation["passes"],
                "reason": validation["reason"],
                "metrics": validation.get("metrics", {}),
            }
            print(json.dumps(output, indent=2))
        else:
            print_report(validation, normal_results, pessimistic_results)

        return 0 if validation["passes"] else 1

    except Exception as e:
        logger.error(f"Stress test failed: {e}", exc_info=True)
        if args.json_output:
            print(json.dumps({"passes": False, "error": str(e)}))
        else:
            print(f"\n❌ Error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
