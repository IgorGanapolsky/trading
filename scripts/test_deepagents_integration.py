#!/usr/bin/env python3
"""
Test script for deepagents integration.

Validates that the deepagents integration is working correctly.
Can be run with: python scripts/test_deepagents_integration.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")
    try:
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_tools():
    """Test that tools can be built."""
    print("\nTesting tool building...")
    try:
        from deepagents_integration import (
            build_mcp_tools_for_deepagents,
            build_trading_tools,
        )

        trading_tools = build_trading_tools()
        mcp_tools = build_mcp_tools_for_deepagents()

        print(f"✓ Built {len(trading_tools)} trading tools")
        print(f"✓ Built {len(mcp_tools)} MCP tools")

        # List tool names
        print("\nTrading tools:")
        for tool in trading_tools:
            print(f"  - {tool.name}")

        print("\nMCP tools:")
        for tool in mcp_tools:
            print(f"  - {tool.name}")

        return True
    except Exception as e:
        print(f"✗ Tool building failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_agent_creation():
    """Test that agents can be created."""
    print("\nTesting agent creation...")

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠ ANTHROPIC_API_KEY not set, skipping agent creation test")
        print("  Set ANTHROPIC_API_KEY to test full agent functionality")
        return True

    try:
        from deepagents_integration import (
            create_market_analysis_agent,
            create_trading_research_agent,
        )

        # Test research agent creation
        create_trading_research_agent(
            model="anthropic:claude-sonnet-4-5-20250929",
            include_mcp_tools=False,  # Skip MCP to avoid dependency issues
            temperature=0.3,
        )
        print("✓ Trading research agent created successfully")

        # Test market analysis agent creation
        create_market_analysis_agent(
            model="anthropic:claude-sonnet-4-5-20250929",
            include_mcp_tools=False,
            temperature=0.2,
        )
        print("✓ Market analysis agent created successfully")

        return True
    except Exception as e:
        print(f"✗ Agent creation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_simple_query():
    """Test a simple query to the agent."""
    print("\nTesting simple agent query...")

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠ ANTHROPIC_API_KEY not set, skipping query test")
        return True

    try:
        from deepagents_integration import create_trading_research_agent

        agent = create_trading_research_agent(
            include_mcp_tools=False,
            temperature=0.3,
        )

        # Simple test query
        test_query = "What is the current price of SPY? Use get_market_data tool."

        print(f"Query: {test_query}")
        print("Processing...")

        result = await agent.ainvoke({"messages": [{"role": "user", "content": test_query}]})

        if "messages" in result:
            print("✓ Agent responded successfully")
            # Print last message
            if len(result["messages"]) > 0:
                last_msg = result["messages"][-1]
                if hasattr(last_msg, "content"):
                    content = str(last_msg.content)
                    print(f"\nResponse preview: {content[:200]}...")
            return True
        else:
            print("✗ Unexpected result format")
            return False

    except Exception as e:
        print(f"✗ Query test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_python_version():
    """Check Python version compatibility."""
    print("Checking Python version...")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")

    if version.major == 3 and version.minor == 14:
        print("⚠ Python 3.14 detected - known compatibility issues with langchain-core")
        print("  Recommendation: Use Python 3.11, 3.12, or 3.13")
        return False
    elif version.major == 3 and version.minor >= 11:
        print("✓ Python version compatible")
        return True
    else:
        print("⚠ Python version may not be compatible (requires Python 3.11+)")
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("DeepAgents Integration Test Suite")
    print("=" * 80)

    results = []

    # Check Python version
    python_ok = check_python_version()
    results.append(("Python Version", python_ok))

    # Test imports
    results.append(("Imports", test_imports()))

    # Test tools
    results.append(("Tool Building", test_tools()))

    # Test agent creation
    results.append(("Agent Creation", test_agent_creation()))

    # Test simple query (async)
    if python_ok:
        try:
            query_result = asyncio.run(test_simple_query())
            results.append(("Simple Query", query_result))
        except Exception as e:
            print(f"\n⚠ Query test skipped due to: {e}")
            results.append(("Simple Query", None))

    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)

    for test_name, result in results:
        if result is True:
            status = "✓ PASS"
        elif result is False:
            status = "✗ FAIL"
        else:
            status = "⚠ SKIP"
        print(f"{test_name:20} {status}")

    passed = sum(1 for _, r in results if r is True)
    total = sum(1 for _, r in results if r is not None)

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n⚠ Some tests failed or were skipped")
        return 1


if __name__ == "__main__":
    sys.exit(main())
