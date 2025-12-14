#!/usr/bin/env python3
"""
Fuzz testing for promotion gate to verify non-degenerate behavior.

Randomly samples metrics within realistic ranges (50 trials) and verifies:
1. Gate doesn't accept everything (acceptance rate 5-60%)
2. Gate doesn't reject everything (rejection rate 20-90%)
3. Distribution of decisions is reasonable

This catches degenerate gate configurations where:
- Thresholds are too loose (accepts >60% of random configs)
- Thresholds are too strict (rejects >90% of random configs)
- Gate logic is broken (accepts/rejects everything)
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

# Import gate evaluation logic
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.enforce_promotion_gate import evaluate_gate


def generate_random_metrics() -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Generate random but realistic trading metrics.

    Ranges based on real-world trading systems:
    - Win rate: 30-80% (below 30% = broken, above 80% = suspicious)
    - Sharpe: -1.0 to 3.0 (most systems fall in this range)
    - Drawdown: 0-30% (above 30% = catastrophic)
    - Trades: 50-500 (statistical significance range)
    - Profitable streak: 10-60 days (realistic backtesting range)
    """
    win_rate = random.uniform(30.0, 80.0)
    sharpe = random.uniform(-1.0, 3.0)
    drawdown = random.uniform(0.0, 30.0)
    total_trades = random.randint(50, 500)
    profitable_streak = random.randint(10, 60)

    # Add some correlation: good win rates tend to have better Sharpe/lower drawdown
    # But add noise to keep it realistic
    if random.random() < 0.3:  # 30% chance of correlated "good" metrics
        win_rate = random.uniform(55.0, 75.0)
        sharpe = random.uniform(1.0, 2.5)
        drawdown = random.uniform(2.0, 12.0)
        profitable_streak = random.randint(25, 50)
    elif random.random() < 0.3:  # 30% chance of correlated "bad" metrics
        win_rate = random.uniform(30.0, 50.0)
        sharpe = random.uniform(-0.8, 0.8)
        drawdown = random.uniform(15.0, 28.0)
        profitable_streak = random.randint(10, 20)

    # Create synthetic system_state
    system_state = {
        "meta": {"last_updated": "2025-12-11T10:00:00Z"},
        "performance": {
            "win_rate": win_rate,
            "total_trades": total_trades,
        },
        "heuristics": {
            "win_rate": win_rate,
            "sharpe_ratio": sharpe,
            "max_drawdown": -abs(drawdown),
        },
    }

    # Create synthetic backtest summary with slight variations
    # (backtest metrics often differ slightly from paper trading)
    backtest_win_rate = win_rate + random.uniform(-5.0, 5.0)
    backtest_sharpe = sharpe + random.uniform(-0.3, 0.3)
    backtest_drawdown = drawdown + random.uniform(-2.0, 2.0)

    backtest_summary = {
        "aggregate_metrics": {
            "min_win_rate": max(0.0, backtest_win_rate),
            "min_sharpe_ratio": backtest_sharpe,
            "max_drawdown": max(0.0, backtest_drawdown),
            "min_profitable_streak": profitable_streak,
            "total_trades": total_trades,
        },
    }

    return system_state, backtest_summary


def run_fuzz_test(
    num_trials: int = 50,
    min_accept_rate: float = 0.05,
    max_accept_rate: float = 0.60,
    min_reject_rate: float = 0.20,
    max_reject_rate: float = 0.90,
    verbose: bool = False,
    seed: int | None = None,
) -> dict[str, Any]:
    """
    Run fuzzing test on promotion gate.

    Args:
        num_trials: Number of random configurations to test
        min_accept_rate: Minimum fraction of accepts (gate not too strict)
        max_accept_rate: Maximum fraction of accepts (gate not too loose)
        min_reject_rate: Minimum fraction of rejects (gate has standards)
        max_reject_rate: Maximum fraction of rejects (gate not impossible to pass)
        verbose: Print detailed results
        seed: Random seed for reproducibility

    Returns:
        Dictionary with test results and statistics
    """
    if seed is not None:
        random.seed(seed)

    # Default gate thresholds
    args = argparse.Namespace(
        required_win_rate=55.0,
        required_sharpe=1.2,
        max_drawdown=10.0,
        min_profitable_days=30,
        min_trades=100,
        override_env="ALLOW_PROMOTION_OVERRIDE",
        stale_threshold_hours=48.0,
        json=False,
        json_output=None,
    )

    accepts = 0
    rejects = 0
    trial_results = []

    for trial in range(num_trials):
        system_state, backtest_summary = generate_random_metrics()
        deficits = evaluate_gate(system_state, backtest_summary, args)

        passed = len(deficits) == 0
        if passed:
            accepts += 1
        else:
            rejects += 1

        trial_result = {
            "trial": trial + 1,
            "passed": passed,
            "num_deficits": len(deficits),
            "metrics": {
                "win_rate": system_state["performance"]["win_rate"],
                "sharpe": system_state["heuristics"]["sharpe_ratio"],
                "drawdown": abs(system_state["heuristics"]["max_drawdown"]),
                "trades": system_state["performance"]["total_trades"],
                "streak": backtest_summary["aggregate_metrics"]["min_profitable_streak"],
            },
        }
        trial_results.append(trial_result)

        if verbose:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(
                f"Trial {trial + 1:3d}: {status} | "
                f"WR={trial_result['metrics']['win_rate']:.1f}% "
                f"Sharpe={trial_result['metrics']['sharpe']:.2f} "
                f"DD={trial_result['metrics']['drawdown']:.1f}% "
                f"Trades={trial_result['metrics']['trades']} "
                f"Streak={trial_result['metrics']['streak']}d | "
                f"Deficits={len(deficits)}"
            )

    accept_rate = accepts / num_trials
    reject_rate = rejects / num_trials

    results = {
        "num_trials": num_trials,
        "accepts": accepts,
        "rejects": rejects,
        "accept_rate": accept_rate,
        "reject_rate": reject_rate,
        "thresholds": {
            "min_accept_rate": min_accept_rate,
            "max_accept_rate": max_accept_rate,
            "min_reject_rate": min_reject_rate,
            "max_reject_rate": max_reject_rate,
        },
        "passed_checks": True,
        "failures": [],
    }

    # Check if acceptance rate is within bounds
    if accept_rate < min_accept_rate:
        results["passed_checks"] = False
        results["failures"].append(
            f"Acceptance rate {accept_rate:.1%} is below minimum {min_accept_rate:.1%} "
            f"(gate is too strict - rejects nearly everything)"
        )

    if accept_rate > max_accept_rate:
        results["passed_checks"] = False
        results["failures"].append(
            f"Acceptance rate {accept_rate:.1%} exceeds maximum {max_accept_rate:.1%} "
            f"(gate is too loose - accepts too many bad configs)"
        )

    # Check if rejection rate is within bounds
    if reject_rate < min_reject_rate:
        results["passed_checks"] = False
        results["failures"].append(
            f"Rejection rate {reject_rate:.1%} is below minimum {min_reject_rate:.1%} "
            f"(gate lacks standards - accepts almost everything)"
        )

    if reject_rate > max_reject_rate:
        results["passed_checks"] = False
        results["failures"].append(
            f"Rejection rate {reject_rate:.1%} exceeds maximum {max_reject_rate:.1%} "
            f"(gate is too strict - rejects nearly everything)"
        )

    # Add trial details if verbose
    if verbose:
        results["trials"] = trial_results

    return results


def main() -> None:
    """Run fuzzing test and report results."""
    parser = argparse.ArgumentParser(
        description="Fuzz test the promotion gate to verify non-degenerate behavior."
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=50,
        help="Number of random configurations to test (default: 50)",
    )
    parser.add_argument(
        "--min-accept-rate",
        type=float,
        default=0.05,
        help="Minimum acceptable acceptance rate (default: 0.05 = 5%%)",
    )
    parser.add_argument(
        "--max-accept-rate",
        type=float,
        default=0.60,
        help="Maximum acceptable acceptance rate (default: 0.60 = 60%%)",
    )
    parser.add_argument(
        "--min-reject-rate",
        type=float,
        default=0.20,
        help="Minimum acceptable rejection rate (default: 0.20 = 20%%)",
    )
    parser.add_argument(
        "--max-reject-rate",
        type=float,
        default=0.90,
        help="Maximum acceptable rejection rate (default: 0.90 = 90%%)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed trial-by-trial results",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )

    args = parser.parse_args()

    if not args.json:
        print("🔬 Fuzzing promotion gate with random configurations...")
        print(f"   Trials: {args.trials}")
        print(f"   Accept rate bounds: {args.min_accept_rate:.1%} - {args.max_accept_rate:.1%}")
        print(f"   Reject rate bounds: {args.min_reject_rate:.1%} - {args.max_reject_rate:.1%}")
        if args.seed is not None:
            print(f"   Seed: {args.seed}")
        print()

    results = run_fuzz_test(
        num_trials=args.trials,
        min_accept_rate=args.min_accept_rate,
        max_accept_rate=args.max_accept_rate,
        min_reject_rate=args.min_reject_rate,
        max_reject_rate=args.max_reject_rate,
        verbose=args.verbose,
        seed=args.seed,
    )

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n" + "=" * 70)
        print("FUZZING RESULTS")
        print("=" * 70)
        print(f"Total trials:     {results['num_trials']}")
        print(f"Accepted:         {results['accepts']} ({results['accept_rate']:.1%})")
        print(f"Rejected:         {results['rejects']} ({results['reject_rate']:.1%})")
        print()

        if results["passed_checks"]:
            print("✅ Gate behavior is HEALTHY (not degenerate)")
            print("   - Accept rate within bounds")
            print("   - Reject rate within bounds")
            print("   - Gate has appropriate selectivity")
        else:
            print("❌ Gate behavior is DEGENERATE")
            for failure in results["failures"]:
                print(f"   - {failure}")

    sys.exit(0 if results["passed_checks"] else 1)


if __name__ == "__main__":
    main()
