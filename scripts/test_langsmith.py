# scripts/test_langsmith.py
"""
Simple script to verify LangSmith tracing.
Run:
    source venv/bin/activate
    python scripts/test_langsmith.py
"""

import os
import sys

from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

try:
    from langsmith import Client
except ImportError:
    print("❌ LangSmith not installed. Run: pip install langsmith")
    sys.exit(1)

from langsmith import traceable


@traceable
def my_test_function(text: str):
    return f"Processed: {text}"


def main() -> None:
    api_key = os.getenv("LANGCHAIN_API_KEY")
    project = os.getenv("LANGCHAIN_PROJECT")

    if not api_key:
        print("❌ LANGCHAIN_API_KEY not found in environment")
        return

    if not project:
        print("❌ LANGCHAIN_PROJECT not found in environment")
        return

    print(f"Testing LangSmith connection for project: {project}")

    try:
        result = my_test_function("hello langsmith")
        print(f"✅ Function executed: {result}")
        print("Check your LangSmith dashboard for the trace.")
    except Exception as e:
        print(f"❌ Failed to run traceable function: {e}")


if __name__ == "__main__":
    main()
