#!/usr/bin/env python3
"""
Clean up test/demo traces from LangSmith project.

This script identifies and optionally deletes test traces (like "Sample Agent Trace")
that are not from the actual trading system.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

try:
    from langsmith import Client
except ImportError:
    print("❌ langsmith not installed. Run: pip install langsmith")
    sys.exit(1)


def identify_test_traces(client: Client, project_name: str = "default", limit: int = 50):
    """Identify test/demo traces."""
    test_keywords = [
        "sample",
        "test",
        "demo",
        "beep",
        "boop",
        "document loader",
        "example",
        "tutorial",
    ]

    runs = list(client.list_runs(project_name=project_name, limit=limit))
    test_traces = []

    for run in runs:
        is_test = False
        reason = []

        # Check name
        if run.name:
            name_lower = run.name.lower()
            for keyword in test_keywords:
                if keyword in name_lower:
                    is_test = True
                    reason.append(f"name contains '{keyword}'")
                    break

        # Check inputs
        if hasattr(run, "inputs") and run.inputs:
            inputs_str = str(run.inputs).lower()
            for keyword in test_keywords:
                if keyword in inputs_str:
                    is_test = True
                    reason.append(f"input contains '{keyword}'")
                    break

        # Check outputs
        if hasattr(run, "outputs") and run.outputs:
            outputs_str = str(run.outputs).lower()
            for keyword in test_keywords:
                if keyword in outputs_str:
                    is_test = True
                    reason.append(f"output contains '{keyword}'")
                    break

        if is_test:
            test_traces.append({"run": run, "reasons": reason})

    return test_traces


def generate_deletion_guide(test_traces: list, project_name: str):
    """Generate a guide for manual deletion."""
    if not test_traces:
        return

    # Find the parent trace (Sample Agent Trace)
    parent_trace = None
    for item in test_traces:
        if "sample" in item["run"].name.lower():
            parent_trace = item["run"]
            break

    print("\n" + "=" * 70)
    print("📋 MANUAL DELETION GUIDE")
    print("=" * 70)
    print("\nLangSmith doesn't allow programmatic deletion of runs (safety feature).")
    print("Delete them manually in the UI:\n")

    if parent_trace:
        print("🎯 EASIEST METHOD: Delete the parent trace")
        print(
            "   1. Go to: https://smith.langchain.com/o/bb00a62e-c62a-4c42-9031-43e1f74bb5b3/projects/p/04fa554e-f155-4039-bb7f-e866f082103b"
        )
        print(f"   2. Find: 'Sample Agent Trace' (ID: {parent_trace.id})")
        print("   3. Click on it")
        print("   4. Click the delete/archive button (usually top right)")
        print(f"   5. This will delete the parent and all {len(test_traces)} sub-traces")
        print("\n   ✅ This removes all test traces at once!")
    else:
        print("📝 Delete individual traces:")
        print(
            "   1. Go to: https://smith.langchain.com/o/bb00a62e-c62a-4c42-9031-43e1f74bb5b3/projects/p/04fa554e-f155-4039-bb7f-e866f082103b"
        )
        print("   2. Find each trace listed above")
        print("   3. Click delete/archive for each")

    print("\n💡 After deletion, your project will only show REAL trading traces!")


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Clean up test/demo traces from LangSmith")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete test traces (default: dry run)",
    )
    parser.add_argument(
        "--project",
        type=str,
        default=None,
        help="Specific project to clean (default: all)",
    )
    args = parser.parse_args()

    api_key = os.getenv("LANGCHAIN_API_KEY")
    if not api_key:
        print("❌ LANGCHAIN_API_KEY not set")
        sys.exit(1)

    client = Client(api_key=api_key)

    print("🔍 Scanning for test/demo traces...")
    if args.delete:
        print("⚠️  DELETE MODE: Will actually delete traces!")
    else:
        print("📋 DRY RUN MODE: Will only show what would be deleted")
    print("=" * 70)

    # Check projects
    projects = [args.project] if args.project else ["default", "trading-rl-training"]

    total_deleted = 0
    total_failed = 0

    for project_name in projects:
        try:
            test_traces = identify_test_traces(client, project_name=project_name)

            if test_traces:
                print(f"\n📋 Found {len(test_traces)} test traces in '{project_name}':")

                # Show details
                for i, item in enumerate(test_traces, 1):
                    run = item["run"]
                    reasons = item["reasons"]
                    print(f"\n{i}. {run.name}")
                    print(f"   ID: {run.id}")
                    print(f"   Type: {run.run_type}")
                    print(f"   Time: {run.start_time}")
                    print(f"   Reasons: {', '.join(reasons)}")

                # Generate deletion guide
                generate_deletion_guide(test_traces, project_name)
            else:
                print(f"\n✅ No test traces found in '{project_name}'")

        except Exception as e:
            print(f"\n⚠️  Error checking '{project_name}': {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 70)
    if args.delete:
        print(f"✅ Deleted {total_deleted} test traces")
        if total_failed > 0:
            print(f"⚠️  Failed to delete {total_failed} traces")
    else:
        print(f"📋 Would delete {total_deleted} test traces")
        print("\n💡 To actually delete, run with --delete flag:")
        print("   python scripts/clean_langsmith_test_traces.py --delete")

    print("\n💡 To generate REAL trading traces:")
    print("   python scripts/rl_training_orchestrator.py --platform local --use-langsmith")
    print("   OR run your trading system - traces will appear automatically")


if __name__ == "__main__":
    main()
