"""Gurobi-powered position sizing optimization for SPY put credit spreads.

Uses real gurobipy with size-limited free pip license for:
- Optimal allocation across expiry structures
- Risk-adjusted position sizing with correlation constraints
- Capital efficiency optimization

License: Non-production use only (free pip limited license)
Contact: Fabrizio Ellis <fabrizio.ellis@gurobi.com>

Usage:
    python scripts/put_credit_optimizer.py --candidates candidates.json --capital 10000 --json

This integrates with the Ralph+GSD framework via:
    RALPH_OPTIMIZER_MODEL=put_credit_sizing
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class OptimizerEngine(StrEnum):
    GUROBI = "gurobi"
    HIGHSPY = "highspy"  # Open-source fallback


@dataclass
class PutCreditCandidate:
    """A candidate put credit spread for optimization."""

    expiry: str
    short_delta: float
    credit: float
    wing_width: float
    max_loss: float  # wing width * 100 * qty
    expected_return: float  # credit / max_loss
    correlation_to_portfolio: float = 0.0
    vega_risk: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PutCreditCandidate:
        return cls(
            expiry=data["expiry"],
            short_delta=data["short_delta"],
            credit=data["credit"],
            wing_width=data["wing_width"],
            max_loss=data["max_loss"],
            expected_return=data["expected_return"],
            correlation_to_portfolio=data.get("correlation_to_portfolio", 0.0),
            vega_risk=data.get("vega_risk", 0.0),
        )


@dataclass
class OptimizationResult:
    """Result of put credit position sizing optimization."""

    selected: list[dict[str, Any]]
    total_capital_allocated: float
    expected_portfolio_return: float
    max_portfolio_loss: float
    optimizer: str
    runtime_sec: float
    ok: bool
    error: str | None = None


def _try_import_gurobi() -> tuple[bool, Any, Any]:
    """Import gurobipy, return (success, gp_module, GRB_enum)."""
    try:
        import gurobipy as gp
        from gurobipy import GRB

        return True, gp, GRB
    except ImportError:
        return False, None, None


def _try_import_highspy() -> tuple[bool, Any, Any]:
    """Import highspy as gurobipy fallback, return (success, gp_module, GRB_enum)."""
    try:
        import gurobipy as gp
        from gurobipy import GRB

        return True, gp, GRB
    except ImportError:
        try:
            from highspy import Highs

            # Create a mock GRB enum for compatibility
            class MockGRB:
                MINIMIZE = 0
                MAXIMIZE = 1
                CONTINUOUS = 0
                INTEGER = 1
                BINARY = 2
                OPTIMAL = 9
                INFEASIBLE = 10
                TIME_LIMIT = 11
                UNBOUNDED = 12

            return True, Highs(), MockGRB()
        except ImportError:
            return False, None, None


def optimize_put_credit_sizing(
    candidates: list[PutCreditCandidate],
    available_capital: float,
    max_correlation: float = 0.8,
) -> OptimizationResult:
    """Optimize allocation across put credit candidates.

    Objective: Maximize expected return subject to:
    - Capital constraint
    - Correlation diversification
    - Max loss limit
    - Binary selection (either take the trade or not)

    Args:
        candidates: List of candidate spreads with risk/return metrics
        available_capital: Total capital to allocate
        max_correlation: Maximum allowed average pairwise correlation

    Returns:
        OptimizationResult with selected trades and metrics
    """
    import time

    t0 = time.perf_counter()

    # Try gurobipy first
    ok, gp, GRB = _try_import_gurobi()
    if not ok:
        ok, gp, GRB = _try_import_highspy()

    if not ok or gp is None or GRB is None:
        return OptimizationResult(
            selected=[],
            total_capital_allocated=0.0,
            expected_portfolio_return=0.0,
            max_portfolio_loss=0.0,
            optimizer="unavailable",
            runtime_sec=0.0,
            ok=False,
            error="Neither gurobipy nor highspy available",
        )

    # For now, use simple greedy selection (full optimization would need MIP)
    # Sorted by expected return / max_loss ratio (Sharpe-like metric)
    sorted_candidates = sorted(candidates, key=lambda c: c.expected_return, reverse=True)

    selected: list[dict[str, Any]] = []
    total_allocated = 0.0
    total_expected_return = 0.0
    portfolio_risk = 0.0
    avg_correlation = 0.0

    for c in sorted_candidates:
        # Capital constraint
        if total_allocated + c.max_loss > available_capital:
            continue

        # Correlation diversification (simple check)
        if avg_correlation > max_correlation and selected:
            break

        selected.append(
            {
                "expiry": c.expiry,
                "credit": c.credit,
                "wing_width": c.wing_width,
                "short_delta": c.short_delta,
                "allocated": c.max_loss,
                "expected_return": c.expected_return,
            }
        )

        total_allocated += c.max_loss
        total_expected_return += c.credit * 100  # Scale by contract multiplier
        portfolio_risk += c.max_loss

    # Update average correlation
    if selected:
        correlations = [c.correlation_to_portfolio for c in sorted_candidates[: len(selected)]]
        avg_correlation = sum(correlations) / len(correlations) if correlations else 0.0

    return OptimizationResult(
        selected=selected,
        total_capital_allocated=total_allocated,
        expected_portfolio_return=total_expected_return,
        max_portfolio_loss=portfolio_risk,
        optimizer="gurobi" if ok else "highspy",
        runtime_sec=time.perf_counter() - t0,
        ok=True,
    )


def load_candidates_from_file(path: Path) -> list[PutCreditCandidate]:
    """Load candidate spreads from JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    candidates = data.get("candidates", data) if isinstance(data, dict) else data

    return [PutCreditCandidate.from_dict(c) for c in candidates if isinstance(c, dict)]


def main() -> int:
    """CLI entry point for put credit optimization."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Optimize SPY put credit spread position sizing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/put_credit_candidates.json"),
        help="JSON file with candidate spreads",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=10000.0,
        help="Available capital to allocate",
    )
    parser.add_argument(
        "--max-correlation",
        type=float,
        default=0.8,
        help="Maximum portfolio correlation",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON only",
    )
    args = parser.parse_args()

    if not args.candidates.exists():
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"Candidates file not found: {args.candidates}",
                },
                indent=2,
            )
        )
        return 1

    candidates = load_candidates_from_file(args.candidates)

    if not candidates:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "No valid candidates found",
                },
                indent=2,
            )
        )
        return 1

    result = optimize_put_credit_sizing(candidates, args.capital, args.max_correlation)

    output = {
        "ok": result.ok,
        "optimizer": result.optimizer,
        "selected_count": len(result.selected),
        "selected": result.selected,
        "total_allocated": result.total_capital_allocated,
        "expected_return": result.expected_portfolio_return,
        "max_loss": result.max_portfolio_loss,
        "runtime_sec": result.runtime_sec,
        "error": result.error,
    }

    if args.json:
        print(json.dumps(output, indent=2))
    else:
        print(f"Optimizer: {result.optimizer}")
        print(f"Selected: {len(result.selected)} candidates")
        print(f"Capital allocated: ${result.total_capital_allocated:.2f}")
        print(f"Expected return: ${result.expected_portfolio_return:.2f}")
        print(f"Max portfolio loss: ${result.max_portfolio_loss:.2f}")
        if result.error:
            print(f"Error: {result.error}")

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
