#!/usr/bin/env python3
"""
Verify Workflow Secrets Configuration

This script checks that all GitHub Actions workflows that make LLM calls
have the complete observability stack configured:
- LangSmith tracing (LANGCHAIN_API_KEY, LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT)
- Helicone cost tracking (HELICONE_API_KEY)
- OpenRouter API (OPENROUTER_API_KEY)

Lesson Learned: ll_017 - Missing LangSmith env vars caused blind production runs.

Usage:
    python scripts/verify_workflow_secrets.py
    python scripts/verify_workflow_secrets.py --fix  # Show what needs to be added

Exit codes:
    0 - All workflows properly configured
    1 - Missing configuration found
"""

import argparse
import sys
from pathlib import Path

# Workflows that make LLM calls
LLM_WORKFLOWS = [
    ".github/workflows/daily-trading.yml",
    ".github/workflows/combined-trading.yml",
]

# Complete observability stack requirements
OBSERVABILITY_VARS = {
    "langsmith": {
        "vars": [
            "LANGCHAIN_API_KEY",
            "LANGCHAIN_TRACING_V2",
            "LANGCHAIN_PROJECT",
        ],
        "description": "LangSmith tracing for LLM debugging",
    },
    "helicone": {
        "vars": ["HELICONE_API_KEY"],
        "description": "Helicone gateway for cost tracking",
    },
    "openrouter": {
        "vars": ["OPENROUTER_API_KEY"],
        "description": "OpenRouter API for LLM inference",
    },
}


def check_workflow(workflow_path: Path) -> dict:
    """Check a single workflow for required env vars."""
    if not workflow_path.exists():
        return {"exists": False, "path": str(workflow_path)}

    content = workflow_path.read_text()
    results = {
        "exists": True,
        "path": str(workflow_path),
        "missing": {},
        "present": {},
    }

    for stack_name, config in OBSERVABILITY_VARS.items():
        missing = []
        present = []

        for var in config["vars"]:
            if var in content:
                present.append(var)
            else:
                missing.append(var)

        if missing:
            results["missing"][stack_name] = {
                "vars": missing,
                "description": config["description"],
            }
        if present:
            results["present"][stack_name] = present

    return results


def print_fix_suggestion(missing_stack: str, missing_vars: list) -> str:
    """Generate YAML snippet to fix missing vars."""
    suggestions = {
        "LANGCHAIN_API_KEY": "          LANGCHAIN_API_KEY: ${{ secrets.LANGCHAIN_API_KEY }}",
        "LANGCHAIN_TRACING_V2": "          LANGCHAIN_TRACING_V2: 'true'",
        "LANGCHAIN_PROJECT": "          LANGCHAIN_PROJECT: 'trading-rl-training'",
        "HELICONE_API_KEY": "          HELICONE_API_KEY: ${{ secrets.HELICONE_API_KEY }}",
        "OPENROUTER_API_KEY": "          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}",
    }

    lines = [f"# Add to env: section ({missing_stack})"]
    for var in missing_vars:
        if var in suggestions:
            lines.append(suggestions[var])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Verify workflow observability config")
    parser.add_argument("--fix", action="store_true", help="Show YAML snippets to fix issues")
    parser.add_argument("--ci", action="store_true", help="Exit with code 1 if any issues found")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    all_passed = True
    total_missing = 0

    print("=" * 60)
    print("Workflow Observability Verification")
    print("Lesson Learned: ll_017 - Missing LangSmith env vars")
    print("=" * 60)
    print()

    for workflow_rel_path in LLM_WORKFLOWS:
        workflow_path = project_root / workflow_rel_path

        print(f"Checking: {workflow_rel_path}")
        result = check_workflow(workflow_path)

        if not result["exists"]:
            print("  ⚠️  File not found (skipping)")
            print()
            continue

        if not result["missing"]:
            print("  ✅ All observability vars present")
            for stack, vars_list in result["present"].items():
                print(f"     {stack}: {', '.join(vars_list)}")
        else:
            all_passed = False
            print("  ❌ Missing configuration:")
            for stack_name, info in result["missing"].items():
                print(f"     {stack_name}: {', '.join(info['vars'])}")
                print(f"        ({info['description']})")
                total_missing += len(info["vars"])

                if args.fix:
                    print()
                    print("     FIX: Add to workflow env: section:")
                    print(print_fix_suggestion(stack_name, info["vars"]))

        print()

    # Summary
    print("=" * 60)
    if all_passed:
        print("✅ All workflows have complete observability configuration!")
        print()
        print("Observability stack:")
        print("  - LangSmith: Detailed LLM tracing and debugging")
        print("  - Helicone: Cost tracking and analytics")
        print("  - OpenRouter: Multi-model LLM inference")
    else:
        print(f"❌ Found {total_missing} missing env var(s)")
        print()
        print("Required GitHub Secrets:")
        print("  - LANGCHAIN_API_KEY: Get from https://smith.langchain.com/settings")
        print("  - HELICONE_API_KEY: Get from https://helicone.ai/settings")
        print("  - OPENROUTER_API_KEY: Get from https://openrouter.ai/keys")
        print()
        print("Add secrets at: Settings → Secrets → Actions → New repository secret")

    print("=" * 60)

    if args.ci and not all_passed:
        sys.exit(1)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
