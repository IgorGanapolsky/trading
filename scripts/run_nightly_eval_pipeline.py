#!/usr/bin/env python3
"""Nightly automated trace-to-eval pipeline.

Triggers the full eval engineering workflow:
  1. Fetch recent LangSmith traces (if configured)
  2. Mine local traces for failure patterns
  3. Generate eval proposals
  4. Build and run evals
  5. Inspect trajectories for reward hacking
  6. Upload results to LangSmith
  7. Generate summary report

Intended to be run via cron/launchd nightly.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Ensure we can import from src
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.eval.eval_engineering_skill import (  # noqa: E402
    EvalProposalEngine,
    EvalTaskBuilder,
    TraceAnalyzer,
)
from src.eval.eval_improvement_loop import EvalImprovementLoop  # noqa: E402
from src.eval.harbor_runner import HarborRunner  # noqa: E402
from src.eval.verifier_trajectory_inspector import TrajectoryInspector  # noqa: E402

logger = logging.getLogger(__name__)

REPORTS_DIR = PROJECT_ROOT / "data" / "eval" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class NightlyEvalPipeline:
    """Automated nightly eval pipeline."""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.analyzer = TraceAnalyzer()
        self.engine = EvalProposalEngine()
        self.builder = EvalTaskBuilder()
        self.runner = HarborRunner()
        self.loop = EvalImprovementLoop()
        self.inspector = TrajectoryInspector()

    def run(self) -> dict[str, Any]:
        """Execute the full nightly pipeline.

        Returns a dictionary with the full pipeline report.
        """
        pipeline_start = time.time()
        report: dict[str, Any] = {
            "pipeline_id": f"nightly-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "steps": {},
        }

        self._log("Starting nightly eval pipeline")

        # Step 1: Fetch LangSmith traces (if configured)
        self._log("Step 1/6: Fetching LangSmith traces...")
        langsmith_dataset = self.analyzer.fetch_traces_as_dataset(
            output_path=REPORTS_DIR / "langsmith_traces.jsonl",
            max_traces=100,
        )
        report["steps"]["fetch_langsmith"] = {
            "success": langsmith_dataset is not None,
            "path": str(langsmith_dataset) if langsmith_dataset else None,
        }

        # Step 2: Mine local traces for patterns
        self._log("Step 2/6: Mining local traces...")
        proposals_from_traces = self.analyzer.analyze_traces(max_traces=200)
        report["steps"]["mine_traces"] = {
            "success": True,
            "proposals_found": len(proposals_from_traces),
        }
        self._log(f"  Found {len(proposals_from_traces)} proposals from traces")

        # Step 3: Generate eval proposals (full engine)
        self._log("Step 3/6: Generating eval proposals...")
        all_proposals = self.engine.generate_proposals()
        report["steps"]["generate_proposals"] = {
            "success": True,
            "total_proposals": len(all_proposals),
            "high_priority": len([p for p in all_proposals if p.priority_score >= 0.8]),
        }
        self._log(f"  Generated {len(all_proposals)} proposals total")

        # Save proposals
        proposals_path = REPORTS_DIR / f"proposals_{datetime.now().strftime('%Y%m%d')}.json"
        proposals_path.write_text(
            json.dumps(
                [{
                    "proposal_id": p.proposal_id,
                    "title": p.title,
                    "category": p.category,
                    "source": p.source,
                    "priority_score": p.priority_score,
                    "suggested_verifier_type": p.suggested_verifier_type,
                } for p in all_proposals],
                indent=2,
            ),
            encoding="utf-8",
        )

        # Step 4: Build evals for high-priority proposals
        self._log("Step 4/6: Building eval tasks...")
        built_tasks = []
        for proposal in all_proposals:
            if proposal.priority_score >= 0.7:
                try:
                    task = self.builder.build_task(proposal)
                    built_tasks.append(task)
                except Exception as exc:
                    logger.warning("Failed to build task '%s': %s", proposal.title, exc)

        report["steps"]["build_evals"] = {
            "success": True,
            "tasks_built": len(built_tasks),
        }
        self._log(f"  Built {len(built_tasks)} eval tasks")

        # Step 5: Run evals + inspect trajectories
        self._log("Step 5/6: Running evals with trajectory inspection...")
        run_report = self.runner.run_native()
        report["steps"]["run_evals"] = {
            "success": True,
            "total": run_report.total,
            "passed": run_report.passed,
            "failed": run_report.failed,
            "overall_score": run_report.overall_score,
            "duration_seconds": run_report.duration_seconds,
            "langsmith_dataset_id": run_report.langsmith_dataset_id,
        }
        self._log(f"  Ran {run_report.total} evals: {run_report.passed} passed, {run_report.failed} failed")

        # Track reward hacking signals
        reward_hacking_count = 0
        for result in run_report.results:
            if result.inspection_report and result.inspection_report.get("signals"):
                reward_hacking_count += len(result.inspection_report["signals"])

        report["steps"]["run_evals"]["reward_hacking_signals"] = reward_hacking_count
        if reward_hacking_count > 0:
            self._log(f"  ⚠ Detected {reward_hacking_count} reward hacking signals")

        # Step 6: Save full report
        self._log("Step 6/6: Saving report and generating summary...")
        pipeline_duration = time.time() - pipeline_start
        report["duration_seconds"] = pipeline_duration
        report["status"] = "success" if run_report.failed == 0 else "partial_failure"

        report_path = REPORTS_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

        # Write summary markdown
        summary = self._generate_summary(report, run_report)
        summary_path = REPORTS_DIR / f"summary_{datetime.now().strftime('%Y%m%d')}.md"
        summary_path.write_text(summary, encoding="utf-8")

        self._log(f"\n{'='*60}")
        self._log(f"Pipeline complete in {pipeline_duration:.1f}s")
        self._log(f"Report: {report_path}")
        self._log(f"Summary: {summary_path}")
        self._log(f"{'='*60}")

        return report

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)
        logger.info(msg)

    def _generate_summary(self, report: dict, run_report: Any) -> str:
        """Generate a human-readable markdown summary."""
        lines = [
            "# Nightly Eval Pipeline Report",
            "",
            f"- **Pipeline ID**: {report['pipeline_id']}",
            f"- **Timestamp**: {report['timestamp']}",
            f"- **Duration**: {report.get('duration_seconds', 0):.1f}s",
            f"- **Status**: {report.get('status', 'unknown')}",
            "",
            "## Results",
            "",
            "| Metric | Value |",
            "|--------|-------|",
        ]
        run_info = report.get("steps", {}).get("run_evals", {})
        lines.append(f"| Total evals | {run_info.get('total', 'N/A')} |")
        lines.append(f"| Passed | {run_info.get('passed', 'N/A')} |")
        lines.append(f"| Failed | {run_info.get('failed', 'N/A')} |")
        lines.append(f"| Overall Score | {run_info.get('overall_score', 0):.2%} |")
        lines.append(f"| Reward Hacking Signals | {run_info.get('reward_hacking_signals', 0)} |")
        lines.append("")

        if run_report and hasattr(run_report, 'results'):
            lines.append("## Per-Task Results")
            lines.append("")
            lines.append("| Task | Status | Score | Details |")
            lines.append("|------|--------|-------|---------|")
            for r in run_report.results[:20]:
                status = "✅" if r.passed else "❌"
                lines.append(f"| {r.name} | {status} | {r.score:.2%} | {r.details[:60]} |")

        lines.append("")
        lines.append("## Proposals Generated")
        proposals_info = report.get("steps", {}).get("generate_proposals", {})
        lines.append(f"- Total: {proposals_info.get('total_proposals', 0)}")
        lines.append(f"- High-priority: {proposals_info.get('high_priority', 0)}")
        lines.append("")

        if report.get("steps", {}).get("fetch_langsmith", {}).get("success"):
            lines.append("## LangSmith Integration")
            lines.append("- Traces fetched and stored as local dataset")
            if run_info.get("langsmith_dataset_id"):
                lines.append(f"- Results uploaded to LangSmith dataset: {run_info['langsmith_dataset_id']}")

        lines.append("")
        lines.append("---")
        lines.append(f"*Generated by nightly eval pipeline at {datetime.now().isoformat()}*")

        return "\n".join(lines)


def main():
    """CLI entry point for the nightly eval pipeline."""
    import argparse

    parser = argparse.ArgumentParser(description="Nightly Eval Pipeline")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output report path")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress output")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    pipeline = NightlyEvalPipeline(verbose=not args.quiet)
    report = pipeline.run()

    # Print final result line for scripting
    status = report.get("status", "unknown")
    score = report.get("steps", {}).get("run_evals", {}).get("overall_score", 0)
    print(f"\nRESULT: status={status} score={score:.2%}")

    return 0


if __name__ == "__main__":
    exit(main())
