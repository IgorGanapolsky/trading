#!/usr/bin/env python3
"""
Pre-Commit Hygiene Orchestrator - Implementation
Automated code quality and repository organization enforcement
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Tuple
import shutil


def error_response(error_msg: str, error_code: str = "ERROR") -> Dict[str, Any]:
    """Standard error response"""
    return {"success": False, "error": error_msg, "error_code": error_code}


def success_response(data: Any) -> Dict[str, Any]:
    """Standard success response"""
    return {"success": True, "data": data}


class PreCommitHygiene:
    """Pre-commit hygiene orchestrator"""

    # Files that should stay in root
    ROOT_ALLOWED_FILES = {
        "README.md",
        "LICENSE",
        ".gitignore",
        ".env.example",
        ".dockerignore",
        "requirements.txt",
        "docker-compose.yml",
        "Dockerfile",
        "pyproject.toml",
        "setup.py",
        ".pre-commit-config.yaml",
    }

    # File type mappings
    FILE_MAPPINGS = {
        ".md": "docs/",  # Except README.md
        ".sh": "scripts/",
    }

    # Utility Python scripts (not source code)
    UTILITY_SCRIPTS = {
        "daily_checkin.py",
        "check_positions.py",
        "demo_trade.py",
        "state_manager.py",
        "autonomous_trader.py",
        "quickstart.sh",
        "setup_cron.sh",
        "setup_cto_reporting.sh",
        "setup_youtube_analysis.sh",
        "cto_daily_report.sh",
    }

    def __init__(self, project_root: Path = None):
        """Initialize hygiene checker"""
        self.project_root = project_root or Path.cwd()

    def check_file_organization(self, fix: bool = False) -> Dict[str, Any]:
        """
        Check if files are properly organized

        Args:
            fix: Automatically move files to correct locations

        Returns:
            Dict with issues found and actions taken
        """
        try:
            issues = []
            files_moved = 0

            # Get all files in root
            root_files = [
                f
                for f in os.listdir(self.project_root)
                if os.path.isfile(os.path.join(self.project_root, f))
            ]

            for filename in root_files:
                # Skip hidden files and allowed files
                if filename.startswith(".") or filename in self.ROOT_ALLOWED_FILES:
                    continue

                file_path = os.path.join(self.project_root, filename)
                issue = self._check_file_placement(filename, file_path)

                if issue:
                    issues.append(issue)

                    if fix and issue.get("target_dir"):
                        moved = self._move_file(filename, issue["target_dir"])
                        if moved:
                            files_moved += 1

            return success_response(
                {
                    "issues_found": len(issues),
                    "issues": issues,
                    "files_moved": files_moved,
                    "summary": (
                        f"{len(issues)} files need reorganization"
                        if issues
                        else "All files properly organized"
                    ),
                }
            )

        except Exception as e:
            return error_response(
                f"Error checking file organization: {str(e)}", "CHECK_ERROR"
            )

    def _check_file_placement(self, filename: str, filepath: str) -> Dict[str, Any]:
        """Check if a file is in the correct location"""
        ext = Path(filename).suffix

        # Check if it's a markdown file (except README.md)
        if ext == ".md" and filename != "README.md":
            return {
                "file": filename,
                "issue": "Documentation file in root",
                "recommendation": "Move to docs/",
                "severity": "warning",
                "target_dir": "docs",
            }

        # Check if it's a shell script
        if ext == ".sh":
            return {
                "file": filename,
                "issue": "Shell script in root",
                "recommendation": "Move to scripts/",
                "severity": "warning",
                "target_dir": "scripts",
            }

        # Check if it's a utility Python script
        if filename in self.UTILITY_SCRIPTS:
            return {
                "file": filename,
                "issue": "Utility script in root",
                "recommendation": "Move to scripts/",
                "severity": "warning",
                "target_dir": "scripts",
            }

        return None

    def _move_file(self, filename: str, target_dir: str) -> bool:
        """Move file to target directory"""
        try:
            source = os.path.join(self.project_root, filename)
            target_path = os.path.join(self.project_root, target_dir)

            # Create target directory if it doesn't exist
            os.makedirs(target_path, exist_ok=True)

            target_file = os.path.join(target_path, filename)

            # Move file
            shutil.move(source, target_file)
            print(f"✓ Moved {filename} → {target_dir}/{filename}")
            return True

        except Exception as e:
            print(f"✗ Failed to move {filename}: {str(e)}")
            return False

    def lint_python_code(
        self, files: List[str] = None, fix: bool = False
    ) -> Dict[str, Any]:
        """
        Run Python linters

        Args:
            files: Specific files to lint
            fix: Auto-fix issues

        Returns:
            Dict with linting results
        """
        try:
            results = {}

            # Find Python files if not specified
            if not files:
                files = self._find_python_files()

            # Run black
            results["black"] = self._run_black(files, fix)

            # Run flake8
            results["flake8"] = self._run_flake8(files)

            # Run mypy
            results["mypy"] = self._run_mypy(files)

            # Overall pass/fail
            results["overall_passed"] = all(
                [
                    results["black"]["passed"],
                    results["flake8"]["passed"],
                    results["mypy"]["passed"],
                ]
            )

            return success_response(results)

        except Exception as e:
            return error_response(f"Error linting code: {str(e)}", "LINT_ERROR")

    def _find_python_files(self) -> List[str]:
        """Find all Python files in project"""
        python_files = []
        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden and virtual env directories
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d not in ["venv", "__pycache__"]
            ]

            for file in files:
                if file.endswith(".py"):
                    python_files.append(os.path.join(root, file))

        return python_files

    def _run_black(self, files: List[str], fix: bool) -> Dict[str, Any]:
        """Run black formatter"""
        try:
            cmd = ["black", "--check"] if not fix else ["black"]
            cmd.extend(files)

            result = subprocess.run(cmd, capture_output=True, text=True)

            return {
                "passed": result.returncode == 0,
                "files_need_formatting": 0 if result.returncode == 0 else len(files),
                "output": result.stdout if result.stdout else result.stderr,
            }
        except FileNotFoundError:
            return {"passed": None, "error": "black not installed"}

    def _run_flake8(self, files: List[str]) -> Dict[str, Any]:
        """Run flake8 linter"""
        try:
            result = subprocess.run(["flake8"] + files, capture_output=True, text=True)

            violations = len(result.stdout.split("\n")) - 1 if result.stdout else 0

            return {
                "passed": result.returncode == 0,
                "violations": violations,
                "output": result.stdout,
            }
        except FileNotFoundError:
            return {"passed": None, "error": "flake8 not installed"}

    def _run_mypy(self, files: List[str]) -> Dict[str, Any]:
        """Run mypy type checker"""
        try:
            result = subprocess.run(["mypy"] + files, capture_output=True, text=True)

            return {"passed": result.returncode == 0, "output": result.stdout}
        except FileNotFoundError:
            return {"passed": None, "error": "mypy not installed"}

    def validate_commit_message(self, message: str) -> Dict[str, Any]:
        """
        Validate commit message format

        Args:
            message: Commit message to validate

        Returns:
            Dict with validation result
        """
        try:
            # Parse conventional commit format
            # Format: <type>(<scope>): <subject>
            import re

            pattern = (
                r"^(feat|fix|docs|style|refactor|test|chore)(\([a-z\-]+\))?: .{10,}"
            )

            match = re.match(pattern, message)

            if match:
                return success_response(
                    {"is_valid": True, "format": "conventional", "issues": []}
                )
            else:
                return success_response(
                    {
                        "is_valid": False,
                        "format": "unknown",
                        "issues": [
                            "Commit message should follow format: <type>(<scope>): <subject>",
                            "Valid types: feat, fix, docs, style, refactor, test, chore",
                            "Subject should be at least 10 characters",
                        ],
                    }
                )

        except Exception as e:
            return error_response(
                f"Error validating commit message: {str(e)}", "VALIDATION_ERROR"
            )

    def check_secrets(self, files: List[str] = None) -> Dict[str, Any]:
        """
        Check for accidentally committed secrets

        Args:
            files: Files to scan

        Returns:
            Dict with secret scan results
        """
        try:
            # Simple regex patterns for common secrets
            patterns = {
                "api_key": r'api[_-]?key[\'"]?\s*[:=]\s*[\'"]?([a-zA-Z0-9_-]{20,})',
                "password": r'password[\'"]?\s*[:=]\s*[\'"]?([^\s\'\"]{8,})',
                "token": r'token[\'"]?\s*[:=]\s*[\'"]?([a-zA-Z0-9_-]{20,})',
                "secret": r'secret[\'"]?\s*[:=]\s*[\'"]?([a-zA-Z0-9_-]{20,})',
            }

            violations = []

            if not files:
                files = self._find_python_files()

            import re

            for filepath in files:
                try:
                    with open(filepath, "r") as f:
                        content = f.read()

                        for secret_type, pattern in patterns.items():
                            matches = re.finditer(pattern, content, re.IGNORECASE)
                            for match in matches:
                                # Skip if it's just an example or placeholder
                                value = (
                                    match.group(1) if match.groups() else match.group(0)
                                )
                                if value.lower() not in [
                                    "your",
                                    "example",
                                    "placeholder",
                                    "xxx",
                                ]:
                                    violations.append(
                                        {
                                            "file": filepath,
                                            "type": secret_type,
                                            "line": content[: match.start()].count("\n")
                                            + 1,
                                        }
                                    )
                except Exception:
                    pass

            return success_response(
                {
                    "secrets_found": len(violations),
                    "violations": violations,
                    "safe_to_commit": len(violations) == 0,
                }
            )

        except Exception as e:
            return error_response(
                f"Error checking secrets: {str(e)}", "SECRET_CHECK_ERROR"
            )

    def organize_repository(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Automatically organize repository

        Args:
            dry_run: Preview changes without applying

        Returns:
            Dict with actions taken
        """
        try:
            actions = []

            # Check file organization
            check_result = self.check_file_organization(fix=not dry_run)

            if check_result["success"]:
                for issue in check_result["data"]["issues"]:
                    if issue.get("target_dir"):
                        actions.append(
                            {
                                "action": "move",
                                "from": issue["file"],
                                "to": f"{issue['target_dir']}/{issue['file']}",
                                "executed": not dry_run,
                            }
                        )

            return success_response(
                {
                    "actions": actions,
                    "files_moved": check_result["data"].get("files_moved", 0),
                    "dry_run": dry_run,
                }
            )

        except Exception as e:
            return error_response(
                f"Error organizing repository: {str(e)}", "ORGANIZE_ERROR"
            )

    def run_all_checks(self, fix: bool = False) -> Dict[str, Any]:
        """
        Run all pre-commit checks

        Args:
            fix: Auto-fix issues where possible

        Returns:
            Dict with all check results
        """
        try:
            results = {}

            # File organization
            org_result = self.check_file_organization(fix=fix)
            results["file_organization"] = (
                "passed" if org_result["data"]["issues_found"] == 0 else "failed"
            )

            # Python linting
            lint_result = self.lint_python_code(fix=fix)
            results["python_linting"] = (
                "passed" if lint_result["data"].get("overall_passed") else "failed"
            )

            # Secrets check
            secrets_result = self.check_secrets()
            results["secrets"] = (
                "passed" if secrets_result["data"]["safe_to_commit"] else "failed"
            )

            # Count passes and fails
            checks_passed = sum(1 for v in results.values() if v == "passed")
            checks_failed = sum(1 for v in results.values() if v == "failed")

            # Blocking issues
            blocking_issues = [k for k, v in results.items() if v == "failed"]

            return success_response(
                {
                    "checks_passed": checks_passed,
                    "checks_failed": checks_failed,
                    "results": results,
                    "blocking_issues": blocking_issues,
                    "can_commit": checks_failed == 0,
                }
            )

        except Exception as e:
            return error_response(f"Error running checks: {str(e)}", "CHECK_ERROR")


def main():
    """CLI interface"""
    parser = argparse.ArgumentParser(description="Pre-Commit Hygiene Orchestrator")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # check_file_organization
    org_parser = subparsers.add_parser(
        "check_file_organization", help="Check file organization"
    )
    org_parser.add_argument("--fix", action="store_true", help="Auto-fix issues")

    # lint_python_code
    lint_parser = subparsers.add_parser("lint_python_code", help="Lint Python code")
    lint_parser.add_argument("--files", nargs="+", help="Specific files to lint")
    lint_parser.add_argument("--fix", action="store_true", help="Auto-fix issues")

    # validate_commit_message
    commit_parser = subparsers.add_parser(
        "validate_commit_message", help="Validate commit message"
    )
    commit_parser.add_argument("message", help="Commit message")

    # check_secrets
    secrets_parser = subparsers.add_parser("check_secrets", help="Check for secrets")
    secrets_parser.add_argument("--files", nargs="+", help="Files to scan")

    # organize_repository
    organize_parser = subparsers.add_parser(
        "organize_repository", help="Organize repository"
    )
    organize_parser.add_argument(
        "--no-dry-run", action="store_true", help="Execute changes"
    )

    # run_all_checks
    all_parser = subparsers.add_parser("run_all_checks", help="Run all checks")
    all_parser.add_argument("--fix", action="store_true", help="Auto-fix issues")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize hygiene checker
    hygiene = PreCommitHygiene()

    # Execute command
    if args.command == "check_file_organization":
        result = hygiene.check_file_organization(fix=args.fix)
    elif args.command == "lint_python_code":
        result = hygiene.lint_python_code(
            files=getattr(args, "files", None), fix=args.fix
        )
    elif args.command == "validate_commit_message":
        result = hygiene.validate_commit_message(args.message)
    elif args.command == "check_secrets":
        result = hygiene.check_secrets(files=getattr(args, "files", None))
    elif args.command == "organize_repository":
        result = hygiene.organize_repository(dry_run=not args.no_dry_run)
    elif args.command == "run_all_checks":
        result = hygiene.run_all_checks(fix=args.fix)
    else:
        print(f"Unknown command: {args.command}")
        return

    # Print result
    print(json.dumps(result, indent=2))

    # Exit with error code if check failed
    if not result["success"] or (
        result["success"] and not result["data"].get("can_commit", True)
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()
