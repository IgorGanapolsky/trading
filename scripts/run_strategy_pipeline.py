#!/usr/bin/env python3
"""
Unified entrypoint for running strategy pipelines defined in config/strategies.yaml.

Examples:
    # List registered strategies
    python3 scripts/run_strategy_pipeline.py --list

    # Run the 'plan' stage for the options theta strategy
    python3 scripts/run_strategy_pipeline.py --strategy options_theta --stage plan

    # Run every stage for the weekend proxy flow
    python3 scripts/run_strategy_pipeline.py --strategy weekend_proxy_dca
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from src.pipeline.strategy_registry import StageConfig, StrategyRegistry


def _print_stage(stage: StageConfig) -> None:
    print(f"  - {stage.name}: {stage.command}")
    if stage.description:
        print(f"      {stage.description}")


def list_strategies(registry: StrategyRegistry) -> None:
    print("Registered strategies:\n")
    for strategy in registry.list_strategies():
        print(f"* {strategy.strategy_id} - {strategy.label}")
        if strategy.description:
            print(f"    {strategy.description}")
        if strategy.stages:
            print("    Stages:")
            for stage in strategy.stages.values():
                _print_stage(stage)
        print()


def execute_stage(stage: StageConfig, *, dry_run: bool) -> None:
    print(f"\n>>> Running stage '{stage.name}'")
    print(f"Command : {stage.command}")
    if stage.description:
        print(f"Details : {stage.description}")
    if dry_run:
        print("Dry run enabled - command not executed.")
        return
    subprocess.run(stage.command, shell=True, check=True)


def run_pipeline(
    strategy_id: str, stages: Iterable[str] | None, *, dry_run: bool, registry: StrategyRegistry
) -> None:
    strategy = registry.get(strategy_id)
    ordered_stages = strategy.stages
    if not ordered_stages:
        raise ValueError(f"Strategy '{strategy_id}' has no stages configured.")

    target_stage_names = list(stages) if stages else list(ordered_stages.keys())
    for stage_name in target_stage_names:
        try:
            stage_cfg = ordered_stages[stage_name]
        except KeyError as exc:
            available = ", ".join(ordered_stages.keys())
            raise KeyError(
                f"Stage '{stage_name}' not defined for {strategy_id}. Available: {available}"
            ) from exc
        execute_stage(stage_cfg, dry_run=dry_run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run strategy pipelines.")
    parser.add_argument("--strategy", help="Strategy identifier defined in config/strategies.yaml")
    parser.add_argument(
        "--stage", nargs="*", help="Stage(s) to run. Default: all stages for the strategy."
    )
    parser.add_argument(
        "--registry", default="config/strategies.yaml", help="Path to strategy registry YAML."
    )
    parser.add_argument("--list", action="store_true", help="List available strategies and exit.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print commands without executing them."
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    registry = StrategyRegistry(args.registry)

    if args.list:
        list_strategies(registry)
        return

    if not args.strategy:
        parser.error("--strategy is required unless --list is provided")

    run_pipeline(
        strategy_id=args.strategy,
        stages=args.stage,
        dry_run=args.dry_run,
        registry=registry,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
