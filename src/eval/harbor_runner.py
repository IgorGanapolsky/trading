"""
Harbor Runner — Container-aware eval execution with LangSmith upload.

Runs evals in a "Harbor‑compatible" way:
- Discovers eval configs in evals/<task-id>/ directories
- Runs verifier against agent trajectories
- Uploads results and trajectories to LangSmith as datasets + feedback
- Supports the existing `tests/evals/harbor_configs/` format

No Harbor package is required; this module implements the same on‑disk
layout (task.toml / instruction.md / environment/Dockerfile / tests/)
and can be extended to a real containerised runner later.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess  # nosec
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.eval.eval_harness import EvalHarness, EvalResult
from src.eval.verifier_trajectory_inspector import TrajectoryInspector

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]

try:
    from langsmith import Client as LangSmithClient
    HAS_LANGSMITH = True
except ImportError:
    HAS_LANGSMITH = False


# ── Data models ──────────────────────────────────────────────────────────────

@dataclass
class HarborEvalResult:
    """Result from running a single Harbor-format eval."""
    task_id: str
    name: str
    passed: bool
    score: float
    details: str
    trajectory: dict[str, Any] | None = None
    inspection_report: dict[str, Any] | None = None
    langsmith_run_id: str | None = None
    duration_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class HarborRunReport:
    """Aggregate report from a Harbor eval run."""
    run_id: str
    results: list[HarborEvalResult]
    total: int
    passed: int
    failed: int
    overall_score: float
    duration_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    langsmith_dataset_id: str | None = None


# ── Harbor Runner ────────────────────────────────────────────────────────────

class HarborRunner:
    """Runs evals and uploads results to LangSmith.

    Two modes:
      1. **Native** — runs existing Python eval modules directly.
      2. **Docker** — builds and runs a Docker container (requires Docker).
    """

    def __init__(self, langsmith_project: str | None = None, use_docker: bool = False):
        self.root = ROOT
        self.use_docker = use_docker
        self.langsmith_project = langsmith_project or os.getenv("LANGSMITH_PROJECT", "trading-agent")
        self._langsmith_client: Any = None
        self.inspector = TrajectoryInspector()

    # ── LangSmith helpers ─────────────────────────────────────────────────

    def _get_langsmith(self) -> Any:
        if self._langsmith_client is None and HAS_LANGSMITH:
            api_key = os.getenv("LANGSMITH_API_KEY")
            if api_key:
                self._langsmith_client = LangSmithClient(api_key=api_key)
        return self._langsmith_client

    def _upload_to_langsmith(self, result: HarborEvalResult) -> str | None:
        """Upload a trajectory and eval result to LangSmith as feedback."""
        client = self._get_langsmith()
        if client is None:
            return None

        try:
            # If we have a trajectory, create a run
            if result.trajectory and result.trajectory.get("tool_calls"):
                run_data = {
                    "name": result.name,
                    "run_type": "chain",
                    "inputs": result.trajectory.get("inputs", {}),
                    "outputs": result.trajectory.get("outputs", {}),
                    "error": None if result.passed else result.details,
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat(),
                }

                # Use LangSmith client to create feedback
                if hasattr(client, "create_run"):
                    run_id = client.create_run(
                        project_name=self.langsmith_project,
                        **run_data,
                    )
                    # Add feedback
                    client.create_feedback(
                        run_id=run_id,
                        key="eval_result",
                        score=result.score,
                        comment=result.details,
                    )
                    if result.inspection_report:
                        client.create_feedback(
                            run_id=run_id,
                            key="reward_hacking",
                            score=1.0 - result.inspection_report.get("overall_score_penalty", 0),
                            comment=result.inspection_report.get("inspector_notes", ""),
                        )
                    return str(run_id)

            # Simpler: create feedback directly on a dataset
            if hasattr(client, "create_feedback"):
                client.create_feedback(
                    run_id=f"eval-{result.task_id}-{int(time.time())}",
                    key="harbor_eval",
                    score=result.score,
                    comment=result.details,
                )

        except Exception as exc:
            logger.warning("Failed to upload to LangSmith: %s", exc)
        return None

    def _create_langsmith_dataset(self, results: list[HarborEvalResult]) -> str | None:
        """Create a LangSmith dataset from eval results."""
        client = self._get_langsmith()
        if client is None:
            return None

        try:
            dataset_name = f"harbor-eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            if hasattr(client, "create_dataset"):
                dataset = client.create_dataset(
                    dataset_name=dataset_name,
                    description=f"Harbor eval run with {len(results)} tasks",
                )
                dataset_id = str(dataset.id) if hasattr(dataset, "id") else dataset_name
                for r in results:
                    if r.trajectory:
                        client.create_example(
                            dataset_id=dataset_id,
                            inputs=r.trajectory.get("inputs", {}),
                            outputs=r.trajectory.get("outputs", {"_result": {"passed": r.passed, "score": r.score}}),
                        )
                return dataset_id
        except Exception as exc:
            logger.warning("Failed to create LangSmith dataset: %s", exc)
        return None

    # ── Native eval execution ─────────────────────────────────────────────

    def run_native(self, task_dir: Path | None = None) -> HarborRunReport:
        """Run evals natively (no Docker) using the existing EvalHarness."""
        run_id = f"harbor-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        start = time.time()
        results: list[HarborEvalResult] = []
        harness = EvalHarness()

        if task_dir:
            # Run a single task
            result = self._run_single_task(task_dir, harness)
            results.append(result)
        else:
            # Run all discovered Harbor tasks
            for evals_dir in [self.root / "evals", self.root / "tests" / "evals"]:
                if evals_dir.exists():
                    for task_cfg in evals_dir.iterdir():
                        if task_cfg.is_dir() and (task_cfg / "task.toml").exists():
                            result = self._run_single_task(task_cfg, harness)
                            results.append(result)

        # If nothing found, run the default eval harness
        if not results:
            logger.info("No Harbor tasks found; running default eval harness")
            report = harness.run()
            for er in report.results:
                h_result = self._convert_eval_result(er)
                results.append(h_result)

        duration = time.time() - start
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        overall = sum(r.score for r in results) / max(len(results), 1)

        # Upload to LangSmith
        dataset_id = self._create_langsmith_dataset(results)

        return HarborRunReport(
            run_id=run_id,
            results=results,
            total=len(results),
            passed=passed,
            failed=failed,
            overall_score=overall,
            duration_seconds=duration,
            langsmith_dataset_id=dataset_id,
        )

    def _run_single_task(self, task_dir: Path, harness: EvalHarness) -> HarborEvalResult:
        """Run a single Harbor-format eval task."""
        task_name = task_dir.name
        verifier_path = task_dir / "verifier.py"

        logger.info("Running task: %s", task_name)
        start = time.time()

        trajectory = {
            "task_id": task_name,
            "tool_calls": [],
            "inputs": {},
            "outputs": {},
            "errors": [],
        }

        # Run the verifier if it exists
        passed = False
        score = 0.0
        details = "No verifier executed"

        if verifier_path.exists():
            try:
                # Import the verifier module dynamically
                import importlib.util
                spec = importlib.util.spec_from_file_location("verifier", verifier_path)
                if spec and spec.loader:
                    verifier_mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(verifier_mod)
                    if hasattr(verifier_mod, "Verifier"):
                        verifier = verifier_mod.Verifier()
                        verdict = verifier.verify(trajectory)
                        passed = verdict.passed
                        score = verdict.score
                        details = verdict.details
            except Exception as exc:
                details = f"Verifier error: {exc}"
                logger.warning(details)
        else:
            # Run eval harness check
            try:
                report = harness.run()
                for r in report.results:
                    if task_name in r.name:
                        passed = r.passed
                        score = r.score
                        details = r.details
                        trajectory = {
                            "tool_calls": [],
                            "inputs": {"category": r.category},
                            "outputs": {"passed": r.passed, "score": r.score},
                            "errors": [] if r.passed else [r.details],
                        }
                        break
            except Exception as exc:
                details = f"Harness error: {exc}"

        # Run trajectory inspector for reward hacking
        inspection = self.inspector.inspect(trajectory)

        duration = time.time() - start
        result = HarborEvalResult(
            task_id=task_name,
            name=task_name,
            passed=passed,
            score=score,
            details=details,
            trajectory=trajectory,
            inspection_report={
                "verdict": inspection.verdict,
                "confidence": inspection.confidence,
                "overall_score_penalty": inspection.overall_score_penalty,
                "inspector_notes": inspection.inspector_notes,
                "signals": [asdict(s) for s in inspection.signals],
            },
            duration_seconds=duration,
        )

        # Upload to LangSmith
        run_id = self._upload_to_langsmith(result)
        result.langsmith_run_id = run_id

        return result

    def _convert_eval_result(self, er: EvalResult) -> HarborEvalResult:
        """Convert an existing EvalResult to HarborEvalResult."""
        return HarborEvalResult(
            task_id=er.name.lower().replace(" ", "_"),
            name=er.name,
            passed=er.passed,
            score=er.score,
            details=er.details,
            trajectory={
                "tool_calls": [],
                "inputs": {"category": er.category},
                "outputs": {"passed": er.passed, "score": er.score, "details": er.details},
                "errors": [] if er.passed else [er.details],
            },
            duration_seconds=0.0,
        )

    # ── Docker execution (optional) ───────────────────────────────────────

    def run_docker(self, task_dir: Path) -> HarborEvalResult:
        """Build and run a Docker container for the eval task."""
        task_name = task_dir.name
        start = time.time()

        # Build Docker image
        build_cmd = ["docker", "build", "-t", f"harbor-eval-{task_name}", str(task_dir)]
        result = subprocess.run(build_cmd, capture_output=True, text=True)  # nosec
        if result.returncode != 0:
            return HarborEvalResult(
                task_id=task_name,
                name=task_name,
                passed=False,
                score=0.0,
                details=f"Docker build failed: {result.stderr[:200]}",
                duration_seconds=time.time() - start,
            )

        # Run Docker container
        run_cmd = ["docker", "run", "--rm", f"harbor-eval-{task_name}"]
        result = subprocess.run(run_cmd, capture_output=True, text=True, timeout=120)  # nosec
        duration = time.time() - start

        # Parse pytest exit code
        passed = result.returncode == 0
        return HarborEvalResult(
            task_id=task_name,
            name=task_name,
            passed=passed,
            score=1.0 if passed else 0.0,
            details=f"Exit code: {result.returncode}\n{result.stdout[:500]}\n{result.stderr[:500]}",
            duration_seconds=duration,
        )


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    """CLI entry point for running Harbor evals."""
    import argparse

    parser = argparse.ArgumentParser(description="Harbor Runner — eval execution with LangSmith upload")
    parser.add_argument("--task-dir", "-t", type=str, default=None, help="Path to specific task directory")
    parser.add_argument("--docker", action="store_true", help="Use Docker for execution")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output JSON report path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    runner = HarborRunner(use_docker=args.docker)
    task_dir = Path(args.task_dir) if args.task_dir else None

    if args.docker and task_dir:
        result = runner.run_docker(task_dir)
        report = HarborRunReport(
            run_id=f"harbor-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            results=[result],
            total=1,
            passed=1 if result.passed else 0,
            failed=0 if result.passed else 1,
            overall_score=result.score,
            duration_seconds=result.duration_seconds,
        )
    else:
        report = runner.run_native(task_dir)

    # Print summary
    print(f"\n{'='*60}")
    print(f"Harbor Run: {report.run_id}")
    print(f"{'='*60}")
    print(f"  Total:  {report.total}")
    print(f"  Passed: {report.passed}")
    print(f"  Failed: {report.failed}")
    print(f"  Score:  {report.overall_score:.2%}")
    print(f"  Time:   {report.duration_seconds:.1f}s")
    if report.langsmith_dataset_id:
        print(f"  LangSmith Dataset: {report.langsmith_dataset_id}")
    print()

    for r in report.results:
        status = "✓" if r.passed else "✗"
        print(f"  {status} {r.name}: {r.score:.2%} ({r.duration_seconds:.1f}s)")
        saw_inspection = r.inspection_report
        if saw_inspection and saw_inspection.get("signals"):
            n_sig = len(saw_inspection["signals"])
            print(f"      Reward hacking signals: {n_sig} ({saw_inspection['verdict']})")

    # Write output
    if args.output:
        report_path = Path(args.output)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_dict = {
            "run_id": report.run_id,
            "results": [
                {
                    "task_id": r.task_id,
                    "name": r.name,
                    "passed": r.passed,
                    "score": r.score,
                    "details": r.details,
                    "duration_seconds": r.duration_seconds,
                    "langsmith_run_id": r.langsmith_run_id,
                }
                for r in report.results
            ],
            "total": report.total,
            "passed": report.passed,
            "failed": report.failed,
            "overall_score": report.overall_score,
            "duration_seconds": report.duration_seconds,
            "langsmith_dataset_id": report.langsmith_dataset_id,
        }
        report_path.write_text(json.dumps(report_dict, indent=2, default=str), encoding="utf-8")
        print(f"\nReport written to {report_path}")

    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    exit(main())
