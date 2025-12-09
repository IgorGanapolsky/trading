#!/usr/bin/env python3
"""
Workflow Secrets Validator - Zero Tolerance for Missing Secrets

This script validates that all required secrets are ACTUALLY PASSED to workflow
environments, not just that they exist in GitHub Secrets.

The HELICONE_API_KEY incident (Dec 2025) happened because:
- Secret was SET in GitHub Secrets ✅
- Secret was NOT PASSED to workflow env ❌

This validator catches that gap.
"""

import sys
from pathlib import Path

import yaml


def load_workflow(path: Path) -> dict:
    """Load a GitHub Actions workflow YAML file."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_workflow_env_vars(workflow: dict) -> set[str]:
    """Extract all env vars that are actually passed in a workflow."""
    env_vars = set()

    # Top-level env
    if "env" in workflow:
        env_vars.update(workflow["env"].keys())

    # Job-level and step-level env
    jobs = workflow.get("jobs", {})
    for job_name, job in jobs.items():
        if isinstance(job, dict):
            # Job-level env
            if "env" in job:
                env_vars.update(job["env"].keys())

            # Step-level env
            for step in job.get("steps", []):
                if isinstance(step, dict) and "env" in step:
                    env_vars.update(step["env"].keys())

    return env_vars


def validate_daily_trading_workflow(workflow_path: Path) -> tuple[bool, list[str]]:
    """
    Validate daily-trading.yml has all required secrets passed.

    Returns:
        (is_valid, list of missing secrets)
    """
    # ALL secrets that MUST be passed to daily-trading workflow
    # This is the source of truth - add any new secrets here
    REQUIRED_SECRETS = {
        # Trading - Critical
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
        # LLM / AI - Required for multi-LLM analysis
        "OPENROUTER_API_KEY",
        # Observability - Required for monitoring
        "HELICONE_API_KEY",
    }

    # Secrets that SHOULD be passed (warnings only)
    RECOMMENDED_SECRETS = {
        "ALPHA_VANTAGE_API_KEY",
        "POLYGON_API_KEY",
        "FINNHUB_API_KEY",
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
    }

    workflow = load_workflow(workflow_path)
    env_vars = get_workflow_env_vars(workflow)

    missing_required = []
    missing_recommended = []

    for secret in REQUIRED_SECRETS:
        if secret not in env_vars:
            missing_required.append(secret)

    for secret in RECOMMENDED_SECRETS:
        if secret not in env_vars:
            missing_recommended.append(secret)

    # Report
    print(f"🔍 Validating: {workflow_path.name}")
    print(f"   Found {len(env_vars)} env vars passed to workflow")
    print()

    if missing_required:
        print("❌ MISSING REQUIRED SECRETS (FAIL):")
        for secret in missing_required:
            print(f"   - {secret}")
        print()
        print("   These secrets MUST be added to the workflow's 'env' section!")
        print("   Example:")
        print(f"     {missing_required[0]}: ${{{{ secrets.{missing_required[0]} }}}}")
        print()

    if missing_recommended:
        print("⚠️  MISSING RECOMMENDED SECRETS (WARNING):")
        for secret in missing_recommended:
            print(f"   - {secret}")
        print()

    if not missing_required:
        print("✅ All required secrets are passed to workflow")

    return len(missing_required) == 0, missing_required


def validate_all_workflows() -> bool:
    """Validate all trading-related workflows."""
    workflows_dir = Path(".github/workflows")

    if not workflows_dir.exists():
        print("❌ .github/workflows directory not found!")
        return False

    # Workflows that need full secret validation
    critical_workflows = [
        "daily-trading.yml",
        "weekend-crypto-trading.yml",
    ]

    all_valid = True
    total_missing = []

    for workflow_name in critical_workflows:
        workflow_path = workflows_dir / workflow_name
        if workflow_path.exists():
            print("=" * 60)
            valid, missing = validate_daily_trading_workflow(workflow_path)
            if not valid:
                all_valid = False
                total_missing.extend(missing)
            print()
        else:
            print(f"⚠️  Workflow not found: {workflow_name}")

    print("=" * 60)
    if all_valid:
        print("✅ ALL WORKFLOW VALIDATIONS PASSED")
        return True
    else:
        print(f"❌ VALIDATION FAILED: {len(total_missing)} missing secrets")
        print()
        print("To fix: Add these secrets to the workflow's 'env' section:")
        for secret in set(total_missing):
            print(f"  {secret}: ${{{{ secrets.{secret} }}}}")
        return False


def main():
    """Main entry point."""
    print("🛡️  Workflow Secrets Validator")
    print("   Zero Tolerance Policy - Catch missing secrets BEFORE deployment")
    print()

    # Change to repo root if needed
    repo_root = Path(__file__).parent.parent
    if (repo_root / ".github").exists():
        import os

        os.chdir(repo_root)

    success = validate_all_workflows()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
