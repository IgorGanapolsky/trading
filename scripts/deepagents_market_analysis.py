#!/usr/bin/env python3
"""
DeepAgents-Powered Market Analysis

CTO Decision: Use DeepAgents for comprehensive market analysis and recommendations.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Check for required API key
if not os.getenv("ANTHROPIC_API_KEY"):
    print("ERROR: ANTHROPIC_API_KEY environment variable not set")
    sys.exit(1)

try:
    from src.deepagents_integration import create_trading_research_agent
except ImportError as e:
    print(f"ERROR: DeepAgents integration not available: {e}")
    print("Note: Requires Python 3.11-3.13 (Python 3.14 has compatibility issues)")
    sys.exit(1)


async def analyze_market():
    """Conduct comprehensive market analysis using DeepAgents."""
    print("=" * 80)
    print("🧠 DEEPAGENTS MARKET ANALYSIS")
    print("=" * 80)

    # Create research agent
    print("\n🤖 Initializing DeepAgents research agent...")
    try:
        agent = create_trading_research_agent(
            model="anthropic:claude-sonnet-4-5-20250929",
            include_mcp_tools=True,
            temperature=0.3,
        )
        print("✅ Agent initialized")
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        return None

    # Analysis query
    query = """
    Conduct comprehensive market analysis for our trading portfolio:

    Current Positions:
    - SPY: Down -1.78% (largest loss)
    - NVDA: Down -6.00% (critical)
    - GOOGL: Up +1.25% (profitable)

    Tasks:
    1. Analyze current market conditions and regime
    2. Review technical indicators for each position
    3. Assess sentiment for SPY, NVDA, GOOGL
    4. Provide specific recommendations:
       - Should we hold, add, or reduce positions?
       - What are the risk factors?
       - What are the opportunities?
    5. Generate actionable trading plan

    Use your planning tools to break this down, then execute comprehensive analysis.
    Save your findings to a file for future reference.
    """

    print(f"\n📊 Analysis Query:\n{query}\n")
    print("🤖 Agent processing (this may take a minute)...\n")

    try:
        # Invoke agent
        result = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})

        # Extract and display results
        print("=" * 80)
        print("📋 ANALYSIS RESULTS")
        print("=" * 80)

        if "messages" in result:
            for message in result["messages"]:
                if hasattr(message, "content") and message.content:
                    content = str(message.content)
                    # Display first 2000 chars
                    print(content[:2000])
                    if len(content) > 2000:
                        print(f"\n... (truncated, {len(content)} total characters)")

        # Check for files created
        analysis_files = list(Path(".").glob("**/analysis_*.md"))
        analysis_files.extend(Path(".").glob("**/market_analysis_*.md"))

        if analysis_files:
            print("\n✅ Analysis files created:")
            for f in analysis_files:
                print(f"   - {f}")

        return result

    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return None


def main():
    """Main execution."""
    try:
        result = asyncio.run(analyze_market())
        if result:
            print("\n✅ Market analysis complete!")
        else:
            print("\n⚠️  Analysis incomplete - check errors above")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
