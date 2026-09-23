#!/usr/bin/env python3
"""Ralph Loop Runner - Autonomous Test & Evidence-Driven Execution.

Implements the Ralph Loop / pstack execution protocol:
1. Verifies finish condition command
2. Runs struggle detection across iterations
3. Manages optional atomic rollback on test regressions
4. Records structured decision logs in data/audit/decision_log.tsv

Usage:
    python scripts/ralph_loop_runner.py --verify-cmd "pytest tests/test_skills_ralph_and_pstack.py" --max-iterations 5
    python scripts/ralph_loop_runner.py --check-only
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess  # nosec B404
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DECISION_LOG_PATH = REPO_ROOT / "data" / "audit" / "decision_log.tsv"


class StruggleDetector:
    """Detects cycles, repeated errors, and lack of forward progress."""

    def __init__(self, max_consecutive_errors: int = 3):
        self.max_consecutive_errors = max_consecutive_errors
        self.error_hashes: list[str] = []

    def hash_error(self, output: str) -> str:
        normalized = " ".join(output.strip().split())[:500]
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def record_and_check(self, output: str) -> tuple[bool, str]:
        h = self.hash_error(output)
        self.error_hashes.append(h)
        if len(self.error_hashes) >= self.max_consecutive_errors:
            recent = self.error_hashes[-self.max_consecutive_errors :]
            if all(x == recent[0] for x in recent):
                return (
                    True,
                    f"Identical failure detected {self.max_consecutive_errors} times consecutively.",
                )
        return False, ""


def append_decision_log(
    *,
    iteration: int,
    phase: str,
    hypothesis: str,
    action: str,
    evidence: str,
    result: str,
    log_path: Path = DECISION_LOG_PATH,
) -> None:
    """Append a structured row to the decision log TSV."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    header_needed = not log_path.exists() or log_path.stat().st_size == 0

    timestamp = datetime.now(UTC).isoformat()
    clean_hypothesis = hypothesis.replace("\t", " ").replace("\n", " ")
    clean_action = action.replace("\t", " ").replace("\n", " ")
    clean_evidence = evidence.replace("\t", " ").replace("\n", " ")
    clean_result = result.replace("\t", " ").replace("\n", " ")

    with open(log_path, "a", encoding="utf-8") as f:
        if header_needed:
            f.write("timestamp\titeration\tphase\thypothesis\taction\tevidence\tresult\n")
        f.write(
            f"{timestamp}\t{iteration}\t{phase}\t{clean_hypothesis}\t"
            f"{clean_action}\t{clean_evidence}\t{clean_result}\n"
        )


def run_verification(cmd: str, cwd: Path = REPO_ROOT) -> tuple[int, str]:
    """Execute verification command and capture exit code + combined output."""
    res = subprocess.run(  # nosec B602
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    output = (res.stdout + "\n" + res.stderr).strip()
    return res.returncode, output


def execute_ralph_cycle(
    verify_cmd: str,
    max_iterations: int = 5,
    auto_revert: bool = False,
    cwd: Path = REPO_ROOT,
) -> bool:
    """Execute the autonomous Ralph loop."""
    detector = StruggleDetector(max_consecutive_errors=3)
    print(f"[*] Starting Ralph Loop with target: {verify_cmd}")
    print(f"[*] Max iterations: {max_iterations} | Auto-revert: {auto_revert}")

    # Baseline check
    code, output = run_verification(verify_cmd, cwd=cwd)
    if code == 0:
        print("[+] Baseline verification ALREADY PASSING. Finish condition met.")
        append_decision_log(
            iteration=0,
            phase="BASELINE",
            hypothesis="Baseline check",
            action="Executed verification command",
            evidence=f"Exit code 0. {output[:120]}",
            result="SUCCESS",
        )
        return True

    print(f"[-] Baseline failed with code {code}. Commencing iterations.")
    append_decision_log(
        iteration=0,
        phase="BASELINE",
        hypothesis="Initial failure assessment",
        action="Captured baseline output",
        evidence=f"Exit code {code}. {output[:120]}",
        result="BASELINE_FAILED",
    )

    iteration = 1
    while iteration <= max_iterations:
        print(f"\n[=== Ralph Iteration {iteration}/{max_iterations} ===]")
        struggling, reason = detector.record_and_check(output)
        if struggling:
            print(f"[!] STRUGGLE DETECTOR TRIGGERED: {reason}")
            append_decision_log(
                iteration=iteration,
                phase="STRUGGLE",
                hypothesis="Struggle detection",
                action="Halt loop to avoid cycling",
                evidence=reason,
                result="HALTED",
            )
            return False

        code, output = run_verification(verify_cmd, cwd=cwd)
        if code == 0:
            print(f"[+] Finish condition SATISFIED on iteration {iteration}!")
            append_decision_log(
                iteration=iteration,
                phase="VERIFY",
                hypothesis="Verified working state",
                action=f"Ran {verify_cmd}",
                evidence=f"Exit code 0. {output[:120]}",
                result="SUCCESS",
            )
            return True

        print(f"[-] Iteration {iteration} verification failed (exit code {code}).")
        if auto_revert:
            print("[!] Auto-revert enabled: reverting working tree changes.")
            subprocess.run(["git", "restore", "."], cwd=cwd, check=False)  # nosec B603 B607
            append_decision_log(
                iteration=iteration,
                phase="ROLLBACK",
                hypothesis="Revert regressed change",
                action="git restore .",
                evidence=f"Exit code {code}",
                result="REVERTED",
            )
        else:
            append_decision_log(
                iteration=iteration,
                phase="FAILED_STEP",
                hypothesis="Candidate change failed verification",
                action="Evaluated candidate output",
                evidence=f"Exit code {code}. {output[:120]}",
                result="NEEDS_RETRY",
            )

        iteration += 1

    print(
        f"[!] Ralph Loop reached max iterations ({max_iterations}) without meeting exit criterion."
    )
    return False


from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ralph Loop Autonomous Runner")
    parser.add_argument(
        "--verify-cmd",
        type=str,
        default="pytest tests/test_repo_hygiene.py -q",
        help="Command to verify finish condition",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum allowed iterations",
    )
    parser.add_argument(
        "--auto-revert",
        action="store_true",
        help="Automatically revert git changes if verification fails",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run baseline verification once and exit",
    )
    args = parser.parse_args(argv)

    if args.check_only:
        code, out = run_verification(args.verify_cmd)
        print(f"Exit code: {code}\nOutput:\n{out}")
        return code

    success = execute_ralph_cycle(
        verify_cmd=args.verify_cmd,
        max_iterations=args.max_iterations,
        auto_revert=args.auto_revert,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
