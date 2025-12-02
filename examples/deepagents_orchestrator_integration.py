"""
Example: Integrating DeepAgents with existing TradingOrchestrator.

This demonstrates how to use deepagents alongside the existing agent framework.
"""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.data_agent import DataAgent
from src.deepagents_integration.bridge import (
    create_deepagents_research_agent,
    create_hybrid_analysis_agent,
)
from src.orchestrator.main import OrchestratorConfig, TradingOrchestrator
from src.orchestrator.state import FileStateProvider

from agent_framework import AgentConfig, RunContext, RunMode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger(__name__)


def create_orchestrator_with_deepagents() -> TradingOrchestrator:
    """
    Create orchestrator with deepagents integrated.

    This shows how to replace or supplement existing agents with deepagents.
    """
    # Create deepagents research agent
    try:
        deepagents_research = create_deepagents_research_agent()
        logger.info("✓ Created deepagents research agent")
    except Exception as e:
        logger.warning(f"Failed to create deepagents agent: {e}")
        logger.info("Falling back to traditional agents")
        deepagents_research = None

    # Create hybrid analysis agent (with fallback)
    hybrid_analysis = create_hybrid_analysis_agent()

    # Build agent list
    agents = [
        DataAgent(),  # Keep existing data agent
    ]

    # Add deepagents if available
    if deepagents_research:
        agents.append(deepagents_research)
        logger.info("✓ Added deepagents research agent to orchestrator")

    # Add hybrid agent
    agents.append(hybrid_analysis)
    logger.info("✓ Added hybrid analysis agent to orchestrator")

    # Create orchestrator
    orchestrator = TradingOrchestrator(
        OrchestratorConfig(
            agents=agents,
            state_provider=FileStateProvider("data/system_state.json"),
        )
    )

    return orchestrator


def example_run_with_deepagents():
    """Example: Run orchestrator with deepagents."""
    logger.info("=" * 80)
    logger.info("DeepAgents Orchestrator Integration Example")
    logger.info("=" * 80)

    # Create orchestrator
    orchestrator = create_orchestrator_with_deepagents()

    # Create context
    context = RunContext(
        mode=RunMode.DRY_RUN,
        force=True,
        config=AgentConfig(data={"symbols": ["SPY", "QQQ"]}),
    )

    # Run orchestrator
    logger.info("\nRunning orchestrator with deepagents...\n")
    results = orchestrator.run_once(context)

    # Display results
    logger.info("\n" + "=" * 80)
    logger.info("Results Summary")
    logger.info("=" * 80)

    for result in results:
        status = "✓ SUCCESS" if result.succeeded else "✗ FAILED"
        logger.info(f"{status}: {result.name}")

        if result.succeeded and result.payload:
            if "analysis" in result.payload:
                logger.info(f"  Analysis preview: {result.payload['analysis'][:200]}...")
        elif result.error:
            logger.error(f"  Error: {result.error}")

    return results


def example_standalone_deepagents():
    """Example: Use deepagents standalone (not in orchestrator)."""
    import asyncio

    async def run_research():
        from src.deepagents_integration import create_trading_research_agent

        logger.info("\n" + "=" * 80)
        logger.info("Standalone DeepAgents Research")
        logger.info("=" * 80)

        # Create agent
        agent = create_trading_research_agent()

        # Research query
        query = """
        Analyze SPY (S&P 500 ETF) for potential trading opportunity:
        1. Review current market conditions
        2. Check technical indicators
        3. Assess sentiment
        4. Provide recommendation with risk assessment
        """

        logger.info(f"\nQuery: {query}\n")
        logger.info("Agent processing...\n")

        # Invoke agent
        result = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})

        # Display result
        if "messages" in result:
            for message in result["messages"]:
                if hasattr(message, "content") and message.content:
                    logger.info(f"Response: {message.content[:500]}...")

        return result

    return asyncio.run(run_research())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DeepAgents integration examples")
    parser.add_argument(
        "--mode",
        choices=["orchestrator", "standalone"],
        default="orchestrator",
        help="Example mode to run",
    )

    args = parser.parse_args()

    if args.mode == "orchestrator":
        example_run_with_deepagents()
    elif args.mode == "standalone":
        example_standalone_deepagents()
    else:
        logger.error(f"Unknown mode: {args.mode}")
