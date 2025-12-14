#!/usr/bin/env python3
"""
System Simplicity Verification Framework

Prevents over-engineering by enforcing complexity budgets and validation requirements.
Run as part of CI/CD or pre-commit to catch complexity creep early.

Based on Lesson Learned: December 11, 2025
- Problem: Built 50,000+ line system with 0% win rate
- Solution: Enforce complexity budgets and validation gates

Usage:
    python scripts/verify_system_simplicity.py           # Full check
    python scripts/verify_system_simplicity.py --quick   # Quick check (no code scan)
    python scripts/verify_system_simplicity.py --fix     # Auto-generate report with recommendations

Author: Trading System CTO
Created: 2025-12-11
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# COMPLEXITY BUDGETS (from lessons learned)
# =============================================================================

COMPLEXITY_BUDGETS = {
    "proof_of_concept": {
        "max_entry_gates": 1,
        "max_frameworks": 0,
        "max_lines": 500,
        "min_trade_frequency": 5,  # trades per week
        "min_gate_pass_rate": 0.5,  # 50% of signals should pass
    },
    "basic_validation": {
        "max_entry_gates": 2,
        "max_frameworks": 0,
        "max_lines": 1000,
        "min_trade_frequency": 5,
        "min_gate_pass_rate": 0.3,
    },
    "validated_edge": {
        "max_entry_gates": 3,
        "max_frameworks": 1,
        "max_lines": 5000,
        "min_trade_frequency": 3,
        "min_gate_pass_rate": 0.2,
    },
    "scaled_system": {
        "max_entry_gates": 5,
        "max_frameworks": 2,
        "max_lines": 20000,
        "min_trade_frequency": 3,
        "min_gate_pass_rate": 0.2,
    },
}

# Current stage (should be updated as system matures)
CURRENT_STAGE = "proof_of_concept"


@dataclass
class ComplexityMetrics:
    """System complexity metrics."""

    entry_gates: int
    active_frameworks: int
    trading_logic_lines: int
    total_python_lines: int
    agent_framework_count: int
    rl_model_count: int
    circuit_breaker_count: int


@dataclass
class ValidationStatus:
    """Component validation status."""

    component_name: str
    trades_validated: int
    win_rate: float | None
    sharpe_ratio: float | None
    is_validated: bool


@dataclass
class VerificationResult:
    """Overall verification result."""

    passed: bool
    stage: str
    complexity: ComplexityMetrics
    validations: list[ValidationStatus]
    violations: list[str]
    warnings: list[str]
    recommendations: list[str]
    timestamp: datetime


# =============================================================================
# COMPLEXITY SCANNING
# =============================================================================


def count_entry_gates() -> int:
    """Count entry gates in trading logic."""
    gate_patterns = [
        r"if.*confidence.*<",  # Confidence thresholds
        r"if.*volume.*<",  # Volume filters
        r"if.*spread.*>",  # Spread gates
        r"if.*vix.*>",  # VIX circuit breakers
        r"if.*macd.*<",  # MACD filters
        r"if.*rsi.*[<>]",  # RSI filters
        r"if.*circuit.*breaker",  # Circuit breakers
        r"validate_.*\(",  # Validation functions
        r"check_.*gate",  # Gate checks
        r"\.filter\(",  # Filter operations
    ]

    gate_count = 0
    src_path = Path(__file__).parent.parent / "src"

    for py_file in src_path.rglob("*.py"):
        if "test" in str(py_file).lower():
            continue
        try:
            content = py_file.read_text()
            for pattern in gate_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                gate_count += len(matches)
        except Exception:
            continue

    # Normalize: actual gates are roughly 1/10 of pattern matches
    return max(1, gate_count // 10)


def count_active_frameworks() -> tuple[int, list[str]]:
    """Count active agent/ML frameworks."""
    framework_patterns = {
        "langchain": r"from langchain|import langchain",
        "deepagents": r"from deepagents|import deepagents|DeepAgent",
        "adk": r"from adk|import adk|ADK",
        "discorl": r"DiscoRL|disco_rl|DiscoDQN",
        "stable_baselines": r"from stable_baselines|import stable_baselines|SB3",
        "transformers": r"TransformerRL|transformer_policy",
        "gymnasium": r"from gymnasium|import gymnasium",
        "ray_rllib": r"from ray.rllib|import rllib",
    }

    active = []
    src_path = Path(__file__).parent.parent / "src"

    for py_file in src_path.rglob("*.py"):
        try:
            content = py_file.read_text()
            for name, pattern in framework_patterns.items():
                if re.search(pattern, content) and name not in active:
                    active.append(name)
        except Exception:
            continue

    return len(active), active


def count_trading_logic_lines() -> int:
    """Count lines of trading logic (not tests, not utils)."""
    trading_dirs = ["strategies", "orchestrator", "agents", "ml", "risk"]
    total_lines = 0
    src_path = Path(__file__).parent.parent / "src"

    for trading_dir in trading_dirs:
        dir_path = src_path / trading_dir
        if dir_path.exists():
            for py_file in dir_path.rglob("*.py"):
                if "test" in str(py_file).lower():
                    continue
                try:
                    lines = len(py_file.read_text().splitlines())
                    total_lines += lines
                except Exception:
                    continue

    return total_lines


def count_total_python_lines() -> int:
    """Count total Python lines in src."""
    total = 0
    src_path = Path(__file__).parent.parent / "src"

    for py_file in src_path.rglob("*.py"):
        try:
            total += len(py_file.read_text().splitlines())
        except Exception:
            continue

    return total


def count_rl_models() -> int:
    """Count RL model implementations."""
    rl_patterns = [
        r"class.*DQN",
        r"class.*PPO",
        r"class.*A2C",
        r"class.*SAC",
        r"class.*RLAgent",
        r"class.*RLFilter",
    ]

    count = 0
    src_path = Path(__file__).parent.parent / "src"

    for py_file in src_path.rglob("*.py"):
        try:
            content = py_file.read_text()
            for pattern in rl_patterns:
                matches = re.findall(pattern, content)
                count += len(matches)
        except Exception:
            continue

    return count


def count_circuit_breakers() -> int:
    """Count circuit breaker implementations."""
    cb_patterns = [
        r"circuit.*breaker",
        r"kill.*switch",
        r"emergency.*stop",
        r"daily.*loss.*limit",
        r"max.*drawdown",
    ]

    count = 0
    src_path = Path(__file__).parent.parent / "src"

    for py_file in src_path.rglob("*.py"):
        try:
            content = py_file.read_text().lower()
            for pattern in cb_patterns:
                matches = re.findall(pattern, content)
                count += len(matches)
        except Exception:
            continue

    # Normalize
    return max(1, count // 5)


def get_complexity_metrics() -> ComplexityMetrics:
    """Collect all complexity metrics."""
    framework_count, _ = count_active_frameworks()

    return ComplexityMetrics(
        entry_gates=count_entry_gates(),
        active_frameworks=framework_count,
        trading_logic_lines=count_trading_logic_lines(),
        total_python_lines=count_total_python_lines(),
        agent_framework_count=framework_count,
        rl_model_count=count_rl_models(),
        circuit_breaker_count=count_circuit_breakers(),
    )


# =============================================================================
# VALIDATION CHECKING
# =============================================================================


def check_component_validation() -> list[ValidationStatus]:
    """Check if active components have validation data."""
    validations = []

    # Check for validation files/data
    validation_path = Path(__file__).parent.parent / "data" / "validation"
    if not validation_path.exists():
        validation_path.mkdir(parents=True, exist_ok=True)

    # Check each major component
    components = [
        "minimal_trader",
        "core_strategy",
        "momentum_strategy",
        "treasury_strategy",
    ]

    for component in components:
        val_file = validation_path / f"{component}_validation.json"
        if val_file.exists():
            try:
                data = json.loads(val_file.read_text())
                validations.append(
                    ValidationStatus(
                        component_name=component,
                        trades_validated=data.get("trades", 0),
                        win_rate=data.get("win_rate"),
                        sharpe_ratio=data.get("sharpe"),
                        is_validated=data.get("trades", 0) >= 20 and data.get("sharpe", -1) > 0,
                    )
                )
            except Exception:
                validations.append(
                    ValidationStatus(
                        component_name=component,
                        trades_validated=0,
                        win_rate=None,
                        sharpe_ratio=None,
                        is_validated=False,
                    )
                )
        else:
            validations.append(
                ValidationStatus(
                    component_name=component,
                    trades_validated=0,
                    win_rate=None,
                    sharpe_ratio=None,
                    is_validated=False,
                )
            )

    return validations


# =============================================================================
# VERIFICATION
# =============================================================================


def verify_system(stage: str = CURRENT_STAGE) -> VerificationResult:
    """Run full system verification."""
    logger.info(f"Running verification for stage: {stage}")

    budget = COMPLEXITY_BUDGETS[stage]
    metrics = get_complexity_metrics()
    validations = check_component_validation()

    violations = []
    warnings = []
    recommendations = []

    # Check entry gates
    if metrics.entry_gates > budget["max_entry_gates"]:
        violations.append(
            f"Entry gates ({metrics.entry_gates}) exceeds budget ({budget['max_entry_gates']})"
        )
        recommendations.append(
            f"Remove {metrics.entry_gates - budget['max_entry_gates']} entry gates"
        )

    # Check frameworks
    if metrics.active_frameworks > budget["max_frameworks"]:
        violations.append(
            f"Active frameworks ({metrics.active_frameworks}) exceeds budget ({budget['max_frameworks']})"
        )
        _, frameworks = count_active_frameworks()
        recommendations.append(f"Remove frameworks: {', '.join(frameworks)}")

    # Check lines
    if metrics.trading_logic_lines > budget["max_lines"]:
        violations.append(
            f"Trading logic lines ({metrics.trading_logic_lines}) exceeds budget ({budget['max_lines']})"
        )
        recommendations.append("Simplify trading logic - consider minimal_trader.py approach")

    # Check RL models
    if metrics.rl_model_count > 1:
        warnings.append(f"Multiple RL models ({metrics.rl_model_count}) increases complexity")
        recommendations.append("Consolidate to single RL model after validation")

    # Check circuit breakers
    if metrics.circuit_breaker_count > 3:
        warnings.append(f"Many circuit breakers ({metrics.circuit_breaker_count}) may over-filter")

    # Check validations
    unvalidated = [v for v in validations if not v.is_validated]
    if unvalidated:
        for v in unvalidated:
            warnings.append(
                f"Component '{v.component_name}' not validated (trades: {v.trades_validated})"
            )
        recommendations.append("Run 20+ trades through each component before adding more")

    passed = len(violations) == 0

    return VerificationResult(
        passed=passed,
        stage=stage,
        complexity=metrics,
        validations=validations,
        violations=violations,
        warnings=warnings,
        recommendations=recommendations,
        timestamp=datetime.now(),
    )


def print_report(result: VerificationResult) -> None:
    """Print verification report."""
    print("\n" + "=" * 70)
    print("SYSTEM SIMPLICITY VERIFICATION REPORT")
    print("=" * 70)
    print(f"Stage: {result.stage.upper()}")
    print(f"Timestamp: {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Status: {'PASSED' if result.passed else 'FAILED'}")
    print("-" * 70)

    print("\nCOMPLEXITY METRICS:")
    print(f"  Entry Gates: {result.complexity.entry_gates}")
    print(f"  Active Frameworks: {result.complexity.active_frameworks}")
    print(f"  Trading Logic Lines: {result.complexity.trading_logic_lines:,}")
    print(f"  Total Python Lines: {result.complexity.total_python_lines:,}")
    print(f"  RL Models: {result.complexity.rl_model_count}")
    print(f"  Circuit Breakers: {result.complexity.circuit_breaker_count}")

    budget = COMPLEXITY_BUDGETS[result.stage]
    print("\nBUDGET COMPARISON:")
    print(f"  Entry Gates: {result.complexity.entry_gates} / {budget['max_entry_gates']}")
    print(f"  Frameworks: {result.complexity.active_frameworks} / {budget['max_frameworks']}")
    print(f"  Lines: {result.complexity.trading_logic_lines:,} / {budget['max_lines']:,}")

    if result.violations:
        print("\nVIOLATIONS:")
        for v in result.violations:
            print(f"  - {v}")

    if result.warnings:
        print("\nWARNINGS:")
        for w in result.warnings:
            print(f"  - {w}")

    if result.recommendations:
        print("\nRECOMMENDATIONS:")
        for r in result.recommendations:
            print(f"  - {r}")

    print("\nVALIDATION STATUS:")
    for v in result.validations:
        status = "VALIDATED" if v.is_validated else "NOT VALIDATED"
        print(f"  {v.component_name}: {status} ({v.trades_validated} trades)")

    print("=" * 70)

    if not result.passed:
        print("\nACTION REQUIRED: Fix violations before adding more complexity!")
        print("See: rag_knowledge/lessons_learned/over_engineering_trading_system.md")

    print()


def save_report(result: VerificationResult, output_path: Path) -> None:
    """Save report to JSON file."""
    report_dict = {
        "passed": result.passed,
        "stage": result.stage,
        "timestamp": result.timestamp.isoformat(),
        "complexity": {
            "entry_gates": result.complexity.entry_gates,
            "active_frameworks": result.complexity.active_frameworks,
            "trading_logic_lines": result.complexity.trading_logic_lines,
            "total_python_lines": result.complexity.total_python_lines,
            "rl_model_count": result.complexity.rl_model_count,
            "circuit_breaker_count": result.complexity.circuit_breaker_count,
        },
        "validations": [
            {
                "component": v.component_name,
                "trades": v.trades_validated,
                "win_rate": v.win_rate,
                "sharpe": v.sharpe_ratio,
                "is_validated": v.is_validated,
            }
            for v in result.validations
        ],
        "violations": result.violations,
        "warnings": result.warnings,
        "recommendations": result.recommendations,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report_dict, f, indent=2)

    logger.info(f"Report saved to {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="System Simplicity Verification")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick check (skip detailed code scan)",
    )
    parser.add_argument(
        "--stage",
        type=str,
        default=CURRENT_STAGE,
        choices=list(COMPLEXITY_BUDGETS.keys()),
        help="Development stage for budget comparison",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/verification/simplicity_report.json",
        help="Output path for JSON report",
    )

    args = parser.parse_args()

    try:
        result = verify_system(stage=args.stage)
        print_report(result)
        save_report(result, Path(args.output))

        sys.exit(0 if result.passed else 1)

    except Exception as e:
        logger.error(f"Verification failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
