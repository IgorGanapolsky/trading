"""
DeepAgents Trading System Example

Demonstrates how to use deepagents for trading research and analysis
with planning, sub-agent delegation, and filesystem capabilities.
"""

import asyncio
import os

from src.deepagents_integration import (
    create_market_analysis_agent,
    create_trading_research_agent,
)


async def example_research_agent():
    """Example: Using deepagents for comprehensive trading research."""
    print("=" * 80)
    print("Example 1: Trading Research Agent")
    print("=" * 80)

    # Create research agent
    agent = create_trading_research_agent(
        model="anthropic:claude-sonnet-4-5-20250929",
        include_mcp_tools=True,
        temperature=0.3,
    )

    # Research task
    research_query = """
    Conduct comprehensive research on NVDA (NVIDIA) stock:
    1. Analyze recent price action and technical indicators
    2. Review sentiment from news and social media
    3. Assess market regime (bullish/bearish/range-bound)
    4. Provide investment recommendation with risk assessment
    5. Save your analysis to a file for future reference
    """

    print(f"\nResearch Query: {research_query}\n")
    print("Agent is processing...\n")

    # Invoke agent (async)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": research_query}]})

    # Display results
    if "messages" in result:
        for message in result["messages"]:
            if hasattr(message, "content"):
                print(f"Agent Response:\n{message.content}\n")

    return result


async def example_market_analysis():
    """Example: Using deepagents for market analysis with sub-agents."""
    print("\n" + "=" * 80)
    print("Example 2: Market Analysis Agent with Sub-Agents")
    print("=" * 80)

    # Define specialized sub-agents
    risk_subagent = {
        "name": "risk-analyst",
        "description": "Specialized agent for risk assessment and position sizing",
        "system_prompt": """You are a risk management specialist.
        Your role is to:
        1. Assess portfolio risk for proposed trades
        2. Calculate appropriate position sizes
        3. Evaluate stop-loss and take-profit levels
        4. Identify potential risk factors

        Always provide structured risk assessments with quantitative metrics.""",
        "tools": [],  # Can add risk-specific tools here
    }

    # Create market analysis agent with sub-agents
    agent = create_market_analysis_agent(
        model="anthropic:claude-sonnet-4-5-20250929",
        include_mcp_tools=True,
        temperature=0.2,
        subagents=[risk_subagent],
    )

    # Analysis task
    analysis_query = """
    Analyze SPY (S&P 500 ETF) for potential trading opportunity:
    1. Review current market conditions and technical setup
    2. Check sentiment indicators
    3. Delegate risk assessment to the risk-analyst sub-agent
    4. Generate a complete trade recommendation with:
       - Entry price and timing
       - Stop loss level
       - Take profit targets
       - Position size recommendation
       - Conviction score (0-1)
    5. Save the analysis to a file
    """

    print(f"\nAnalysis Query: {analysis_query}\n")
    print("Agent is processing with sub-agent delegation...\n")

    # Stream results to see agent thinking process
    async for chunk in agent.astream(
        {"messages": [{"role": "user", "content": analysis_query}]},
        stream_mode="values",
    ):
        if "messages" in chunk and len(chunk["messages"]) > 0:
            last_message = chunk["messages"][-1]
            if hasattr(last_message, "content") and last_message.content:
                # Print incremental updates
                print(f"Update: {last_message.content[:200]}...\n")

    return chunk


async def example_planning_workflow():
    """Example: Demonstrating planning capabilities."""
    print("\n" + "=" * 80)
    print("Example 3: Planning Workflow")
    print("=" * 80)

    agent = create_trading_research_agent()

    # Task that requires planning
    planning_query = """
    Create a comprehensive market analysis report for QQQ (NASDAQ ETF):

    Break this down into steps using write_todos, then execute:
    1. Gather market data for QQQ and related tech stocks
    2. Analyze technical indicators
    3. Review sentiment data
    4. Compare with historical patterns
    5. Generate final report

    Use the filesystem to save intermediate results and the final report.
    """

    print(f"\nPlanning Query: {planning_query}\n")

    result = await agent.ainvoke({"messages": [{"role": "user", "content": planning_query}]})

    # Check if agent created todos
    if "messages" in result:
        print("\nAgent completed the task with planning!\n")
        for message in result["messages"]:
            if hasattr(message, "content"):
                content = str(message.content)
                if "todo" in content.lower() or "plan" in content.lower():
                    print(f"Planning output: {content[:500]}...\n")

    return result


def main():
    """Run all examples."""
    # Check for required API keys
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("Please set it before running this example.")
        return

    print("\n" + "=" * 80)
    print("DeepAgents Trading System Examples")
    print("=" * 80)
    print("\nThis demonstrates:")
    print("1. Trading research with planning")
    print("2. Market analysis with sub-agent delegation")
    print("3. Filesystem integration for saving results")
    print("\n" + "=" * 80 + "\n")

    # Run examples
    asyncio.run(example_research_agent())
    # asyncio.run(example_market_analysis())  # Uncomment to test sub-agents
    # asyncio.run(example_planning_workflow())  # Uncomment to test planning

    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)
    print("\nCheck the filesystem for saved analysis files.")
    print("The agent uses write_file to save intermediate and final results.")


if __name__ == "__main__":
    main()
