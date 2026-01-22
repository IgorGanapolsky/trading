#!/usr/bin/env python3
"""
Ralph Loop - Iterative AI Coding for Self-Healing CI

Implements the Ralph Wiggum methodology:
1. Send prompt to Claude API
2. Claude analyzes codebase and generates fixes
3. Apply fixes, run tests
4. If tests fail, loop with failure context
5. Repeat until success or max iterations

Usage:
    python scripts/ralph_loop.py --max-iterations 10 --task "fix_tests"
    python scripts/ralph_loop.py --task "improve_code" --target src/
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Try to import anthropic, handle gracefully if not available
try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class StruggleDetector:
    """Detect when AI is stuck in a loop to prevent wasted API costs.

    Detects:
    1. Repetitive responses (hash-based similarity)
    2. No file changes for multiple iterations
    3. Same test failures persisting
    4. API cost budget exceeded
    """

    def __init__(
        self,
        max_no_change_iterations: int = 3,
        max_same_error_iterations: int = 3,
        max_api_cost_usd: float = 5.0,
    ):
        self.max_no_change = max_no_change_iterations
        self.max_same_error = max_same_error_iterations
        self.max_cost = max_api_cost_usd
        self.response_hashes: list[str] = []
        self.no_change_count = 0
        self.error_hashes: list[str] = []
        self.api_calls = 0
        self.estimated_cost = 0.0
        # Approximate costs (Claude Sonnet)
        self.cost_per_1k_input = 0.003
        self.cost_per_1k_output = 0.015

    def _hash_text(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()[:16]

    def record_api_call(self, input_tokens: int = 2000, output_tokens: int = 1000):
        self.api_calls += 1
        self.estimated_cost += (input_tokens / 1000) * self.cost_per_1k_input
        self.estimated_cost += (output_tokens / 1000) * self.cost_per_1k_output

    def check_response_repetition(self, response: str) -> tuple[bool, str]:
        response_hash = self._hash_text(response)
        if response_hash in self.response_hashes[-2:]:
            return True, "repetitive_response"
        self.response_hashes.append(response_hash)
        self.response_hashes = self.response_hashes[-5:]
        return False, ""

    def check_no_progress(self, files_changed: int) -> tuple[bool, str]:
        if files_changed == 0:
            self.no_change_count += 1
            if self.no_change_count >= self.max_no_change:
                return True, f"no_changes_for_{self.no_change_count}_iterations"
        else:
            self.no_change_count = 0
        return False, ""

    def check_same_error(self, error_output: str) -> tuple[bool, str]:
        error_hash = self._hash_text(error_output[:500])
        if self.error_hashes and error_hash == self.error_hashes[-1]:
            consecutive = sum(1 for h in reversed(self.error_hashes) if h == error_hash)
            if consecutive >= self.max_same_error:
                return True, f"same_error_for_{consecutive}_iterations"
        self.error_hashes.append(error_hash)
        self.error_hashes = self.error_hashes[-5:]
        return False, ""

    def check_cost_budget(self) -> tuple[bool, str]:
        if self.estimated_cost >= self.max_cost:
            return True, f"cost_budget_exceeded_${self.estimated_cost:.2f}"
        return False, ""

    def is_stuck(
        self, response: str | None = None, files_changed: int = 0, error_output: str = ""
    ) -> tuple[bool, str]:
        stuck, reason = self.check_cost_budget()
        if stuck:
            return True, reason
        if response:
            stuck, reason = self.check_response_repetition(response)
            if stuck:
                return True, reason
        stuck, reason = self.check_no_progress(files_changed)
        if stuck:
            return True, reason
        if error_output:
            stuck, reason = self.check_same_error(error_output)
            if stuck:
                return True, reason
        return False, ""

    def get_status(self) -> dict:
        return {
            "api_calls": self.api_calls,
            "estimated_cost_usd": round(self.estimated_cost, 3),
            "no_change_streak": self.no_change_count,
            "budget_remaining_usd": round(self.max_cost - self.estimated_cost, 3),
        }


def log(message: str, level: str = "INFO"):
    """Log with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def run_command(cmd: str, timeout: int = 300) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def run_tests() -> tuple[bool, str]:
    """Run pytest and return success status and output."""
    log("Running pytest...")
    exit_code, stdout, stderr = run_command("pytest tests/ -q --tb=short 2>&1", timeout=300)
    output = stdout + stderr

    # Check for success patterns
    success = exit_code == 0 or "passed" in output.lower()

    # Extract summary line
    for line in output.split("\n"):
        if "passed" in line or "failed" in line or "error" in line:
            log(f"Test result: {line.strip()}")
            break

    return success, output


def run_lint() -> tuple[bool, str]:
    """Run ruff lint and return success status and output."""
    log("Running ruff lint...")
    exit_code, stdout, stderr = run_command("ruff check src/ scripts/ --select=E,F,W 2>&1")
    output = stdout + stderr
    success = exit_code == 0 or "All checks passed" in output
    return success, output


def get_git_diff() -> str:
    """Get git diff to show recent changes."""
    _, stdout, _ = run_command("git diff --stat HEAD~1 2>/dev/null || echo 'No previous commit'")
    return stdout[:2000]  # Limit size


def get_failing_test_details(test_output: str) -> str:
    """Extract relevant failure details from test output."""
    lines = test_output.split("\n")
    relevant_lines = []
    capture = False

    for line in lines:
        if "FAILED" in line or "ERROR" in line or "assert" in line.lower():
            capture = True
        if capture:
            relevant_lines.append(line)
            if len(relevant_lines) > 50:  # Limit context
                break

    return "\n".join(relevant_lines) if relevant_lines else test_output[:2000]


def call_claude_api(prompt: str, system_prompt: str) -> str | None:
    """Call Claude API and return the response."""
    if not ANTHROPIC_AVAILABLE:
        log("Anthropic SDK not available", "ERROR")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log("ANTHROPIC_API_KEY not set", "ERROR")
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        return message.content[0].text
    except Exception as e:
        log(f"Claude API error: {e}", "ERROR")
        return None


def parse_code_changes(response: str) -> list[dict]:
    """Parse Claude's response for file changes.

    Expected format in response:
    ```file:path/to/file.py
    <file contents>
    ```
    """
    changes = []
    lines = response.split("\n")
    current_file = None
    current_content = []

    for line in lines:
        if line.startswith("```file:"):
            if current_file and current_content:
                changes.append({"file": current_file, "content": "\n".join(current_content)})
            current_file = line[8:].strip()
            current_content = []
        elif line == "```" and current_file:
            changes.append({"file": current_file, "content": "\n".join(current_content)})
            current_file = None
            current_content = []
        elif current_file:
            current_content.append(line)

    return changes


def apply_changes(changes: list[dict]) -> int:
    """Apply code changes to files. Returns number of files changed."""
    applied = 0
    for change in changes:
        file_path = change["file"]
        content = change["content"]

        try:
            # Ensure directory exists
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

            # Write file
            with open(file_path, "w") as f:
                f.write(content)

            log(f"Updated: {file_path}")
            applied += 1
        except Exception as e:
            log(f"Failed to update {file_path}: {e}", "ERROR")

    return applied


def commit_changes(iteration: int, task: str) -> bool:
    """Commit changes if any."""
    # Check for changes
    exit_code, stdout, _ = run_command("git status --porcelain")
    if not stdout.strip():
        log("No changes to commit")
        return False

    # Stage and commit
    run_command("git add -A")
    commit_msg = f"fix(ralph): Iteration {iteration} - {task}"
    exit_code, _, _ = run_command(f'git commit -m "{commit_msg}"')

    if exit_code == 0:
        log(f"Committed: {commit_msg}")
        return True
    return False


def ralph_loop(
    task: str = "fix_tests",
    target: str = "",
    max_iterations: int = 10,
    auto_commit: bool = True,
    max_cost_usd: float = 5.0,
) -> dict:
    """
    Main Ralph loop - iterative AI coding until success.

    Args:
        task: Type of task (fix_tests, improve_code, fix_lint)
        target: Specific file or directory to focus on
        max_iterations: Maximum number of iterations
        auto_commit: Whether to auto-commit successful changes
        max_cost_usd: Maximum API cost budget in USD

    Returns:
        dict with success status and iteration details
    """
    log(f"Starting Ralph Loop: task={task}, max_iterations={max_iterations}, budget=${max_cost_usd}")

    # Initialize struggle detector to prevent infinite loops
    struggle_detector = StruggleDetector(
        max_no_change_iterations=3,
        max_same_error_iterations=3,
        max_api_cost_usd=max_cost_usd,
    )

    results = {
        "success": False,
        "iterations": 0,
        "task": task,
        "changes_made": 0,
        "final_test_status": False,
        "final_lint_status": False,
        "history": [],
        "struggle_status": {},
        "termination_reason": None,
    }

    # System prompt for Claude
    system_prompt = """You are an expert Python developer fixing code in an AI trading system.

RULES:
1. Analyze the error/failure carefully
2. Make MINIMAL changes to fix the issue
3. Output file changes in this EXACT format:
   ```file:path/to/file.py
   <complete file contents>
   ```
4. Only output files that need changes
5. Do NOT add unnecessary comments or documentation
6. Focus on the specific error - don't over-engineer

If tests are passing and no issues found, respond with:
<promise>MISSION_COMPLETE</promise>"""

    for iteration in range(1, max_iterations + 1):
        log(f"=== Iteration {iteration}/{max_iterations} ===")
        results["iterations"] = iteration

        # Run tests first
        tests_pass, test_output = run_tests()
        lint_pass, lint_output = run_lint()

        results["final_test_status"] = tests_pass
        results["final_lint_status"] = lint_pass

        # Check if we're done
        if tests_pass and lint_pass:
            log("All tests and lint passing!")
            results["success"] = True
            results["history"].append(
                {
                    "iteration": iteration,
                    "status": "complete",
                    "tests_pass": True,
                    "lint_pass": True,
                }
            )
            break

        # Build prompt based on task and failures
        if task == "fix_tests" and not tests_pass:
            failure_details = get_failing_test_details(test_output)
            prompt = f"""Fix the failing tests in this Python project.

TEST OUTPUT:
{failure_details}

RECENT CHANGES:
{get_git_diff()}

Analyze the failures and provide fixes. Output ONLY the files that need changes."""

        elif task == "fix_lint" and not lint_pass:
            prompt = f"""Fix the lint errors in this Python project.

LINT OUTPUT:
{lint_output[:3000]}

Provide fixes for the lint errors. Output ONLY the files that need changes."""

        elif task == "improve_code":
            prompt = f"""Improve code quality in {target or "src/"}.

Current test status: {"PASSING" if tests_pass else "FAILING"}
Current lint status: {"PASSING" if lint_pass else "FAILING"}

{f"TEST FAILURES: {get_failing_test_details(test_output)}" if not tests_pass else ""}
{f"LINT ERRORS: {lint_output[:2000]}" if not lint_pass else ""}

Make improvements while ensuring tests continue to pass."""

        else:
            # Default: fix whatever is broken
            prompt = f"""Fix issues in this Python project.

TEST STATUS: {"PASSING" if tests_pass else "FAILING"}
LINT STATUS: {"PASSING" if lint_pass else "FAILING"}

{f"TEST OUTPUT: {get_failing_test_details(test_output)}" if not tests_pass else ""}
{f"LINT OUTPUT: {lint_output[:2000]}" if not lint_pass else ""}

Fix the issues. Output ONLY files that need changes."""

        # Check if stuck before making API call (save costs)
        error_context = test_output if not tests_pass else lint_output
        stuck, reason = struggle_detector.is_stuck(error_output=error_context)
        if stuck:
            log(f"STRUGGLE DETECTED: {reason} - terminating early to save costs", "WARN")
            results["termination_reason"] = f"struggle_detected:{reason}"
            results["struggle_status"] = struggle_detector.get_status()
            break

        # Call Claude API
        log("Calling Claude API for fixes...")
        response = call_claude_api(prompt, system_prompt)

        # Record API call for cost tracking
        struggle_detector.record_api_call(input_tokens=2500, output_tokens=1500)

        if not response:
            log("No response from Claude API", "ERROR")
            results["history"].append(
                {
                    "iteration": iteration,
                    "status": "api_error",
                    "tests_pass": tests_pass,
                    "lint_pass": lint_pass,
                }
            )
            continue

        # Check for repetitive responses (struggle detection)
        stuck, reason = struggle_detector.is_stuck(response=response)
        if stuck:
            log(f"STRUGGLE DETECTED: {reason} - AI giving same responses", "WARN")
            results["termination_reason"] = f"struggle_detected:{reason}"
            results["struggle_status"] = struggle_detector.get_status()
            break

        # Check for completion signal
        if "<promise>MISSION_COMPLETE</promise>" in response:
            log("Claude indicates mission complete")
            results["success"] = True
            results["termination_reason"] = "mission_complete"
            break

        # Parse and apply changes
        changes = parse_code_changes(response)
        files_changed = 0
        if changes:
            applied = apply_changes(changes)
            files_changed = applied
            results["changes_made"] += applied
            log(f"Applied {applied} file changes")

            if auto_commit and applied > 0:
                commit_changes(iteration, task)
        else:
            log("No code changes parsed from response")

        # Check for no progress (struggle detection)
        stuck, reason = struggle_detector.is_stuck(files_changed=files_changed)
        if stuck:
            log(f"STRUGGLE DETECTED: {reason} - no progress being made", "WARN")
            results["termination_reason"] = f"struggle_detected:{reason}"
            results["struggle_status"] = struggle_detector.get_status()
            break

        results["history"].append(
            {
                "iteration": iteration,
                "status": "changes_applied" if changes else "no_changes",
                "tests_pass": tests_pass,
                "lint_pass": lint_pass,
                "files_changed": len(changes),
                "api_cost_so_far": struggle_detector.estimated_cost,
            }
        )

    # Final status
    results["struggle_status"] = struggle_detector.get_status()

    if results["success"]:
        log(f"Ralph Loop COMPLETE after {results['iterations']} iterations")
        log(f"Total estimated cost: ${struggle_detector.estimated_cost:.3f}")
    elif results.get("termination_reason") and "struggle" in str(results["termination_reason"]):
        log(f"Ralph Loop STOPPED due to struggle: {results['termination_reason']}", "WARN")
        log("Saved money by detecting stuck state early!")
    else:
        log("Ralph Loop reached max iterations without full success", "WARN")
        results["termination_reason"] = "max_iterations_reached"

    log(f"Final cost: ${struggle_detector.estimated_cost:.3f} / ${max_cost_usd:.2f} budget")
    return results


def main():
    parser = argparse.ArgumentParser(description="Ralph Loop - Iterative AI Coding")
    parser.add_argument(
        "--task",
        default="fix_tests",
        choices=["fix_tests", "fix_lint", "improve_code", "auto"],
        help="Type of task to perform",
    )
    parser.add_argument("--target", default="", help="Specific file/directory to focus on")
    parser.add_argument(
        "--max-iterations", type=int, default=10, help="Maximum iterations (default: 10)"
    )
    parser.add_argument("--no-commit", action="store_true", help="Don't auto-commit changes")
    parser.add_argument(
        "--max-cost", type=float, default=5.0, help="Maximum API cost budget in USD (default: $5.00)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Run tests/lint only, don't call AI")

    args = parser.parse_args()

    if args.dry_run:
        log("Dry run mode - checking current status")
        tests_pass, test_output = run_tests()
        lint_pass, lint_output = run_lint()
        print(f"\nTests: {'PASS' if tests_pass else 'FAIL'}")
        print(f"Lint: {'PASS' if lint_pass else 'FAIL'}")
        sys.exit(0 if tests_pass and lint_pass else 1)

    if not ANTHROPIC_AVAILABLE:
        log("anthropic package not installed. Add to requirements.txt for CI.", "ERROR")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        log("ANTHROPIC_API_KEY environment variable not set", "ERROR")
        sys.exit(1)

    results = ralph_loop(
        task=args.task,
        target=args.target,
        max_iterations=args.max_iterations,
        auto_commit=not args.no_commit,
        max_cost_usd=args.max_cost,
    )

    # Output results as JSON for CI parsing
    print("\n" + "=" * 50)
    print("RALPH LOOP RESULTS:")
    print(json.dumps(results, indent=2))

    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
