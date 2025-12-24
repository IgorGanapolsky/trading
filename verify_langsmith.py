#!/usr/bin/env python3
"""
LangSmith Verification Script - Ensures tracing is properly configured.

Run this before trading to verify LangSmith connectivity and trace delivery.
Exit code 0 = success, 1 = failure (blocks trading if used as gate).
"""

import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)


def verify_langsmith() -> bool:
    """Verify LangSmith is properly configured and can receive traces."""
    try:
        from langsmith import Client
    except ImportError:
        print("❌ CRITICAL: langsmith package not installed")
        return False

    project_name = os.getenv("LANGCHAIN_PROJECT", "igor-trading-system")
    api_key = os.getenv("LANGCHAIN_API_KEY")

    print("🔍 Verifying LangSmith configuration...")
    print(f"   Project: {project_name}")
    print(f"   API Key: {'✅ Set' if api_key else '❌ Missing'}")

    if not api_key:
        print("❌ CRITICAL: LANGCHAIN_API_KEY is missing")
        print("   Set it in .env or GitHub secrets")
        return False

    try:
        client = Client()

        # 1. Verify we can connect
        print("📡 Testing LangSmith connectivity...")

        # 2. Create the project if it doesn't exist
        if not client.has_project(project_name):
            client.create_project(project_name, description="Trading system observability")
            print(f"   Created project '{project_name}'")
        else:
            print(f"   Project '{project_name}' exists")

        # 3. Send a test trace with timezone-aware datetime
        print("📤 Sending verification trace...")
        now = datetime.now(timezone.utc)
        client.create_run(
            name="ci_verification_trace",
            inputs={"test": "verification", "timestamp": now.isoformat()},
            outputs={"status": "ok"},
            run_type="chain",
            project_name=project_name,
            start_time=now,
            end_time=now,
            tags=["verification", "ci"],
        )
        print("✅ Verification trace sent successfully")

        # 4. Get project URL for reference
        project = client.read_project(project_name=project_name)
        org_id = client.info.org_id if hasattr(client, "info") and client.info else "unknown"
        print(
            f"\n👉 LangSmith Dashboard: https://smith.langchain.com/o/{org_id}/projects/p/{project.id}"
        )

        return True

    except Exception as e:
        print(f"❌ LangSmith verification failed: {e}")
        return False


if __name__ == "__main__":
    success = verify_langsmith()
    sys.exit(0 if success else 1)
