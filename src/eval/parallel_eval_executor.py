"""
Parallel Eval Executor — runs evals across multiple agent configurations concurrently.

Uses concurrent.futures to run N evals in parallel, each with a different agent
config / model / prompt variant. Reports aggregate results and per-config breakdowns.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.eval.harbor_runner import HarborEvalResult, HarborRunner
from src.eval.verifier_trajectory_inspector import TrajectoryInspector

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class AgentConfig:
    """Configuration for an agent variant to evaluate."""
    name: str
    model: str = ""
    prompt_template: str = ""
    tool_set: list[str] = field(default_factory=list)
    env_overrides: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParallelEvalResult:
    """Result from running all evals for one agent config."""
    config_name: str
    config: AgentConfig
    results: list[HarborEvalResult]
    total: int
    passed: int
    failed: int
    overall_score: float
    duration_seconds: float
    error: str | None = None


@dataclass
class ParallelEvalReport:
    """Aggregate report across all agent configs."""
    run_id: str
    config_results: list[ParallelEvalResult]
    total_configs: int
    total_evals: int
    total_passed: int
    total_failed: int
    overall_score: float
    duration_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    best_config: str | None = None
    worst_config: str | None = None


class ParallelEvalExecutor:
    """Runs evals across multiple agent configs concurrently.

    Example
    -------
    >>> executor = ParallelEvalExecutor()
    >>> configs = [
    ...     AgentConfig(name="gpt-4o", model="gpt-4o"),
    ...     AgentConfig(name="gpt-4o-mini", model="gpt-4o-mini"),
    ... ]
    >>> report = executor.run(configs, max_workers=4)
    >>> print(report.best_config)
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.inspector = TrajectoryInspector()

    def run(
        self,
        configs: list[AgentConfig],
        eval_task_dir: Path | None = None,
        timeout_per_config: int = 300,
    ) -> ParallelEvalReport:
        """Run all agent configs in parallel."""
        run_id = f"parallel-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        start = time.time()

        config_results: list[ParallelEvalResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_config = {
                executor.submit(self._run_single_config, config, eval_task_dir, timeout_per_config): config
                for config in configs
            }
            for future in concurrent.futures.as_completed(future_to_config):
                config = future_to_config[future]
                try:
                    result = future.result()
                    config_results.append(result)
                except Exception as exc:
                    config_results.append(ParallelEvalResult(
                        config_name=config.name,
                        config=config,
                        results=[],
                        total=0,
                        passed=0,
                        failed=0,
                        overall_score=0.0,
                        duration_seconds=0.0,
                        error=str(exc),
                    ))

        duration = time.time() - start

        # Compute aggregates
        total_evals = sum(r.total for r in config_results)
        total_passed = sum(r.passed for r in config_results)
        total_failed = sum(r.failed for r in config_results)
        scores = [r.overall_score for r in config_results if r.overall_score > 0]
        overall = sum(scores) / max(len(scores), 1)

        # Best/worst
        scored_results = [(r.overall_score, r.config_name) for r in config_results]
        scored_results.sort(reverse=True)
        best = scored_results[0][1] if scored_results else None
        worst = scored_results[-1][1] if scored_results else None

        return ParallelEvalReport(
            run_id=run_id,
            config_results=config_results,
            total_configs=len(configs),
            total_evals=total_evals,
            total_passed=total_passed,
            total_failed=total_failed,
            overall_score=overall,
            duration_seconds=duration,
            best_config=best,
            worst_config=worst,
        )

    def _run_single_config(
        self,
        config: AgentConfig,
        eval_task_dir: Path | None,
        timeout: int,
    ) -> ParallelEvalResult:
        """Run the full eval suite for a single agent config."""
        config_start = time.time()
        logger.info("Starting config '%s' with model '%s'", config.name, config.model)

        # Apply environment overrides
        original_env = {}
        for k, v in config.env_overrides.items():
            original_env[k] = os.environ.get(k)
            os.environ[k] = v

        try:
            runner = HarborRunner()
            report = runner.run_native(eval_task_dir)
        except Exception as exc:
            logger.error("Config '%s' failed: %s", config.name, exc)
            return ParallelEvalResult(
                config_name=config.name,
                config=config,
                results=[],
                total=0,
                passed=0,
                failed=0,
                overall_score=0.0,
                duration_seconds=time.time() - config_start,
                error=str(exc),
            )
        finally:
            # Restore original env
            for k in config.env_overrides:
                if original_env.get(k) is not None:
                    os.environ[k] = original_env[k]
                elif k in os.environ:
                    del os.environ[k]

        duration = time.time() - config_start
        return ParallelEvalResult(
            config_name=config.name,
            config=config,
            results=report.results,
            total=report.total,
            passed=report.passed,
            failed=report.failed,
            overall_score=report.overall_score,
            duration_seconds=duration,
        )

    # ── Config builders ────────────────────────────────────────────────────

    @staticmethod
    def from_model_names(models: list[str]) -> list[AgentConfig]:
        """Create configs from a list of model names."""
        return [AgentConfig(name=name.replace("/", "-"), model=name) for name in models]

    @staticmethod
    def from_env_variants(variants: list[dict[str, str]]) -> list[AgentConfig]:
        """Create configs from environment variable overrides."""
        configs = []
        for i, env_vars in enumerate(variants):
            name = f"env-variant-{i}"
            for key in ("AGENT_NAME", "MODEL", "CONFIG"):
                if key in env_vars:
                    name = f"{env_vars[key]}".lower().replace(" ", "-")
                    break
            configs.append(AgentConfig(name=name, env_overrides=env_vars))
        return configs


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    """CLI entry point for parallel eval execution."""
    import argparse

    parser = argparse.ArgumentParser(description="Parallel Eval Executor — run evals across agent configs")
    parser.add_argument("--configs", "-c", type=str, nargs="+", help="Agent config names or models")
    parser.add_argument("--models", "-m", type=str, nargs="+", default=None, help="Model names (shorthand)")
    parser.add_argument("--task-dir", "-t", type=str, default=None, help="Specific eval task directory")
    parser.add_argument("--max-workers", "-w", type=int, default=4, help="Max parallel workers")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output JSON report path")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    configs: list[AgentConfig] = []

    if args.models:
        configs.extend(ParallelEvalExecutor.from_model_names(args.models))
    elif args.configs:
        configs.extend(AgentConfig(name=c) for c in args.configs)
    else:
        # Default: run with 3 model variants if models env is set
        default_models = os.getenv("EVAL_MODELS", "gpt-4o,gpt-4o-mini")
        model_list = [m.strip() for m in default_models.split(",")]
        configs.extend(ParallelEvalExecutor.from_model_names(model_list))

    executor = ParallelEvalExecutor(max_workers=args.max_workers)
    task_dir = Path(args.task_dir) if args.task_dir else None
    report = executor.run(configs, eval_task_dir=task_dir)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Parallel Eval Run: {report.run_id}")
    print(f"{'='*60}")
    print(f"  Configs:    {report.total_configs}")
    print(f"  Total evals: {report.total_evals}")
    print(f"  Passed:      {report.total_passed}")
    print(f"  Failed:      {report.total_failed}")
    print(f"  Overall:     {report.overall_score:.2%}")
    print(f"  Time:        {report.duration_seconds:.1f}s")
    print(f"  Best config: {report.best_config}")
    print(f"  Worst config: {report.worst_config}")
    print()

    for cr in report.config_results:
        status = "✓" if cr.overall_score >= 0.8 else "✗"
        print(f"  {status} {cr.config_name}: {cr.overall_score:.2%} ({cr.total} evals, {cr.duration_seconds:.1f}s)")
        if cr.error:
            print(f"      ERROR: {cr.error}")
        for r in cr.results[:5]:  # Show top 5
            print(f"      {'✓' if r.passed else '✗'}  {r.name}: {r.score:.2%}")

    if args.output:
        Path(args.output).write_text(json.dumps({
            "run_id": report.run_id,
            "config_results": [
                {
                    "config_name": cr.config_name,
                    "total": cr.total,
                    "passed": cr.passed,
                    "failed": cr.failed,
                    "overall_score": cr.overall_score,
                    "duration_seconds": cr.duration_seconds,
                    "error": cr.error,
                }
                for cr in report.config_results
            ],
            "total_configs": report.total_configs,
            "total_evals": report.total_evals,
            "total_passed": report.total_passed,
            "total_failed": report.total_failed,
            "overall_score": report.overall_score,
            "duration_seconds": report.duration_seconds,
            "best_config": report.best_config,
            "worst_config": report.worst_config,
        }, indent=2, default=str), encoding="utf-8")
        print(f"\nReport written to {args.output}")

    return 0 if report.total_failed == 0 else 1


if __name__ == "__main__":
    exit(main())
