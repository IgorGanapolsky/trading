"""
Iterative Eval Improvement Loop — CLI for continuous eval refinement.

Workflow:
  1. Trace Mining: Fetch recent traces (local + LangSmith)
  2. Proposal: Generate eval proposals from traces + repo inspection
  3. Build: Convert approved proposals into Harbor-format evals
  4. Run: Execute evals and collect results
  5. Inspect: Check for reward hacking in trajectories
  6. Report: Generate improvement report with recommendations
  7. Iterate: Loop until convergence or user break

Inspired by LangChain's "trace → eval → improve" feedback loop.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.eval.eval_engineering_skill import (
    EvalProposal,
    EvalProposalEngine,
    EvalTask,
    EvalTaskBuilder,
)
from src.eval.harbor_runner import HarborRunner, HarborRunReport
from src.eval.verifier_trajectory_inspector import TrajectoryInspector

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class ImprovementRound:
    """State for a single improvement iteration."""
    round_number: int
    proposals: list[EvalProposal]
    approved_proposals: list[EvalProposal]
    built_tasks: list[EvalTask]
    run_report: HarborRunReport | None = None
    convergence_score: float = 0.0
    improvement_delta: float = 0.0
    recommendations: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0


@dataclass
class ImprovementReport:
    """Full improvement session report."""
    session_id: str
    rounds: list[ImprovementRound]
    total_rounds: int
    final_score: float
    score_trajectory: list[float]
    converged: bool
    total_duration_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class EvalImprovementLoop:
    """Iterative trace → eval → improve loop.

    Usage
    -----
    >>> loop = EvalImprovementLoop()
    >>> report = loop.run(max_rounds=3)
    >>> print(report.converged, report.final_score)
    """

    def __init__(
        self,
        max_proposals_per_round: int = 5,
        convergence_threshold: float = 0.05,
    ):
        self.max_proposals_per_round = max_proposals_per_round
        self.convergence_threshold = convergence_threshold
        self.engine = EvalProposalEngine()
        self.builder = EvalTaskBuilder()
        self.runner = HarborRunner()
        self.inspector = TrajectoryInspector()

    def run(
        self,
        max_rounds: int = 5,
        auto_approve: bool = False,
        verbose: bool = True,
    ) -> ImprovementReport:
        """Run the full improvement loop."""
        session_id = f"improve-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        start = time.time()
        rounds: list[ImprovementRound] = []
        previous_score = 0.0
        converged = False

        for round_num in range(1, max_rounds + 1):
            if verbose:
                print(f"\n{'='*60}")
                print(f"  Improvement Round {round_num}/{max_rounds}")
                print(f"{'='*60}")

            round_start = time.time()
            round_result = self._run_round(round_num, auto_approve, verbose)
            round_result.duration_seconds = time.time() - round_start

            # Track convergence
            if round_result.run_report:
                current_score = round_result.run_report.overall_score
                round_result.improvement_delta = current_score - previous_score
                previous_score = current_score
                round_result.convergence_score = abs(round_result.improvement_delta)

                if round_result.convergence_score < self.convergence_threshold and round_num > 1:
                    converged = True
                    if verbose:
                        print(f"\n  ✓ Converged after {round_num} rounds (Δ={round_result.convergence_score:.4f})")
            else:
                current_score = 0.0
                round_result.convergence_score = 1.0  # Not converged

            # Generate recommendations
            round_result.recommendations = self._generate_recommendations(round_result)
            rounds.append(round_result)

            if converged:
                break

        total_time = time.time() - start
        score_trajectory = [
            r.run_report.overall_score for r in rounds if r.run_report and r.run_report.overall_score > 0
        ]
        final_score = score_trajectory[-1] if score_trajectory else 0.0

        return ImprovementReport(
            session_id=session_id,
            rounds=rounds,
            total_rounds=len(rounds),
            final_score=final_score,
            score_trajectory=score_trajectory,
            converged=converged,
            total_duration_seconds=total_time,
        )

    def _run_round(
        self,
        round_num: int,
        auto_approve: bool,
        verbose: bool,
    ) -> ImprovementRound:
        """Execute a single improvement round."""
        # 1. Generate proposals
        proposals = self.engine.generate_proposals()
        proposals = proposals[:self.max_proposals_per_round]

        if verbose:
            print(f"\n  📋 Generated {len(proposals)} proposals:")
            for p in proposals:
                print(f"     - [{p.priority_score:.2f}] {p.title} ({p.suggested_verifier_type})")

        # 2. Approve proposals
        approved = []
        for p in proposals:
            if auto_approve or p.priority_score >= 0.8:
                approved.append(p)
                if verbose:
                    print(f"     ✓ Approved: {p.title}")

        # 3. Build tasks
        built_tasks = []
        for p in approved:
            try:
                task = self.builder.build_task(p)
                built_tasks.append(task)
            except Exception as exc:
                logger.warning("Failed to build task for '%s': %s", p.title, exc)

        if verbose:
            print(f"\n  🔨 Built {len(built_tasks)} eval tasks")

        # 4. Run evals
        run_report = None
        if built_tasks:
            try:
                run_report = self.runner.run_native()
                if verbose:
                    print(f"\n  🏃 Ran {run_report.total} evals: "
                          f"{run_report.passed} passed, {run_report.failed} failed "
                          f"(score: {run_report.overall_score:.2%})")
            except Exception as exc:
                logger.warning("Eval run failed: %s", exc)

        return ImprovementRound(
            round_number=round_num,
            proposals=proposals,
            approved_proposals=approved,
            built_tasks=built_tasks,
            run_report=run_report,
        )

    def _generate_recommendations(self, round_result: ImprovementRound) -> list[str]:
        """Generate human-readable improvement recommendations."""
        recommendations = []

        if round_result.run_report:
            if round_result.run_report.overall_score < 0.5:
                recommendations.append("Overall score is low. Consider revising verifier logic or test cases.")
            if round_result.run_report.failed > round_result.run_report.passed:
                recommendations.append("More failures than passes. Review agent behavior and eval criteria.")

        # Check for reward hacking
        if round_result.run_report:
            for r in round_result.run_report.results:
                if r.inspection_report and r.inspection_report.get("signals"):
                    recommendations.append(
                        f"Reward hacking detected in '{r.name}': "
                        f"{len(r.inspection_report['signals'])} signal(s) "
                        f"({r.inspection_report['verdict']})"
                    )

        if not round_result.built_tasks:
            recommendations.append("No tasks were built. Check proposal priorities and verifier type compatibility.")

        return recommendations


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    """CLI for the iterative eval improvement loop."""
    import argparse

    parser = argparse.ArgumentParser(description="Iterative Eval Improvement Loop")
    parser.add_argument("--rounds", "-r", type=int, default=5, help="Maximum improvement rounds")
    parser.add_argument("--auto-approve", "-a", action="store_true", help="Auto-approve all proposals")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output JSON report path")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress verbose output")

    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO, format="%(levelname)s %(message)s")

    loop = EvalImprovementLoop()
    report = loop.run(max_rounds=args.rounds, auto_approve=args.auto_approve, verbose=not args.quiet)

    # Print final summary
    print(f"\n{'='*60}")
    print("  Improvement Loop Complete")
    print(f"{'='*60}")
    print(f"  Session:      {report.session_id}")
    print(f"  Rounds:       {report.total_rounds}")
    print(f"  Final score:  {report.final_score:.2%}")
    print(f"  Converged:    {report.converged}")
    print(f"  Time:         {report.total_duration_seconds:.1f}s")
    print(f"  Score trend:  {', '.join(f'{s:.1%}' for s in report.score_trajectory)}")
    print()

    for r in report.rounds:
        print(f"  Round {r.round_number}: {len(r.built_tasks)} tasks, "
              f"score={r.run_report.overall_score:.2% if r.run_report else 'N/A'}, "
              f"Δ={r.improvement_delta:+.2%}")
        for rec in r.recommendations[:3]:
            print(f"     → {rec}")

    if args.output:
        report_dict = {
            "session_id": report.session_id,
            "total_rounds": report.total_rounds,
            "final_score": report.final_score,
            "score_trajectory": report.score_trajectory,
            "converged": report.converged,
            "total_duration_seconds": report.total_duration_seconds,
            "rounds": [
                {
                    "round_number": r.round_number,
                    "num_proposals": len(r.proposals),
                    "num_approved": len(r.approved_proposals),
                    "num_built": len(r.built_tasks),
                    "score": r.run_report.overall_score if r.run_report else None,
                    "improvement_delta": r.improvement_delta,
                    "recommendations": r.recommendations,
                }
                for r in report.rounds
            ],
        }
        Path(args.output).write_text(json.dumps(report_dict, indent=2, default=str), encoding="utf-8")
        print(f"\nReport written to {args.output}")

    return 0


if __name__ == "__main__":
    exit(main())
