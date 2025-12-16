"""
Stirrup Market Scanner Agent
Lightweight autonomous market monitoring using Artificial Analysis' Stirrup framework.

Purpose:
- Run market scanning during regular market hours
- Generate trading signals using web search + sentiment analysis
- Feed signals to main trading system via UDM

Based on: https://github.com/ArtificialAnalysis/Stirrup

Usage:
    python -m src.agents.stirrup_market_scanner --symbol AAPL --mode scan
    python -m src.agents.stirrup_market_scanner --symbol GOOGL --mode research
"""

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Stirrup imports (requires: pip install stirrup)
try:
    from pydantic import BaseModel, Field
    from stirrup import Agent, Tool, ToolResult, ToolUseCountMetadata
    from stirrup.clients.chat_completions_client import ChatCompletionsClient
    from stirrup.tools import DEFAULT_TOOLS

    STIRRUP_AVAILABLE = True
except ImportError:
    STIRRUP_AVAILABLE = False
    print("Warning: Stirrup not installed. Run: pip install stirrup")

# Local imports - UDM integration
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.unified_domain_model import DomainValidator, TradeAction, factory

# =============================================================================
# SCANNER CONFIGURATION
# =============================================================================


class ScanMode(str, Enum):
    """Market scanning modes"""

    QUICK = "quick"  # Fast scan, 2-3 sources
    STANDARD = "standard"  # Normal scan, 5-7 sources
    DEEP = "deep"  # Deep research, 10+ sources


@dataclass
class ScannerConfig:
    """Configuration for market scanner"""

    symbols: list[str]
    mode: ScanMode = ScanMode.STANDARD
    model: str = "anthropic/claude-sonnet-4"  # Cost-effective for scanning
    max_turns: int = 10
    output_dir: str = "./data/scanner_output"

    # Thresholds
    min_confidence: float = 0.6
    signal_cooldown_minutes: int = 30


# =============================================================================
# CUSTOM TOOLS FOR TRADING
# =============================================================================

if STIRRUP_AVAILABLE:

    class GenerateSignalParams(BaseModel):
        """Parameters for signal generation tool"""

        symbol: str = Field(description="Trading symbol (e.g., AAPL, GOOGL)")
        action: str = Field(description="Trade action: BUY, SELL, or HOLD")
        confidence: float = Field(ge=0.0, le=1.0, description="Confidence 0.0-1.0")
        reasoning: str = Field(description="Brief explanation of the signal")
        sources: list[str] = Field(default=[], description="Source URLs/references")

    def generate_signal(params: GenerateSignalParams) -> ToolResult[ToolUseCountMetadata]:
        """
        Generate a trading signal using UDM.
        This tool creates validated signals that integrate with our trading system.
        """
        try:
            # Create equity symbol using UDM factory
            symbol = factory.create_equity_symbol(params.symbol.upper())

            # Map action string to enum
            action_map = {
                "BUY": TradeAction.BUY,
                "SELL": TradeAction.SELL,
                "HOLD": TradeAction.HOLD,
            }
            action = action_map.get(params.action.upper(), TradeAction.HOLD)

            # Create signal using UDM factory
            signal = factory.create_signal(
                symbol=symbol, action=action, confidence=params.confidence, source="stirrup_scanner"
            )

            # Add metadata
            signal.metadata = {
                "reasoning": params.reasoning,
                "sources": params.sources,
                "generated_at": datetime.utcnow().isoformat(),
                "scanner_version": "1.0.0",
            }

            # Validate the signal
            if not DomainValidator.is_valid(signal):
                result = DomainValidator.validate(signal)
                return ToolResult(
                    content=f"Signal validation failed: {[e.message for e in result.errors]}",
                    metadata=ToolUseCountMetadata(),
                )

            # Save signal to file for main system to consume
            signal_file = (
                Path("./data/scanner_signals")
                / f"signal_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            )
            signal_file.parent.mkdir(parents=True, exist_ok=True)
            signal_file.write_text(json.dumps(signal.to_dict(), indent=2))

            return ToolResult(
                content=f"Signal generated: {action.value} {params.symbol} (confidence: {params.confidence:.0%})\n"
                f"Reasoning: {params.reasoning}\n"
                f"Saved to: {signal_file}",
                metadata=ToolUseCountMetadata(),
            )

        except Exception as e:
            return ToolResult(
                content=f"Error generating signal: {str(e)}", metadata=ToolUseCountMetadata()
            )

    GENERATE_SIGNAL_TOOL = Tool(
        name="generate_trading_signal",
        description=(
            "Generate a trading signal after analyzing market data. "
            "Use this when you've gathered enough information to make a BUY, SELL, or HOLD recommendation. "
            "The signal will be validated and saved for the main trading system to consume."
        ),
        parameters=GenerateSignalParams,
        executor=generate_signal,
    )

    class CheckMarketStatusParams(BaseModel):
        """Parameters for market status check"""

        market: str = Field(default="US", description="Market to check: US, CRYPTO")

    def check_market_status(params: CheckMarketStatusParams) -> ToolResult[ToolUseCountMetadata]:
        """Check if markets are open"""
        from datetime import datetime

        import pytz

        now = datetime.now(pytz.timezone("US/Eastern"))

        # US stock market hours
        is_weekday = now.weekday() < 5
        is_market_hours = 9 <= now.hour < 16 or (now.hour == 9 and now.minute >= 30)

        if is_weekday and is_market_hours:
            status = "OPEN"
        else:
            status = "CLOSED"

        return ToolResult(
            content=f"US markets are {status}. Current time: {now.strftime('%Y-%m-%d %H:%M:%S ET')}",
            metadata=ToolUseCountMetadata(),
        )

    CHECK_MARKET_TOOL = Tool(
        name="check_market_status",
        description="Check if stock/crypto markets are currently open for trading",
        parameters=CheckMarketStatusParams,
        executor=check_market_status,
    )


# =============================================================================
# MARKET SCANNER AGENT
# =============================================================================


class MarketScanner:
    """
    Autonomous market scanner using Stirrup framework.
    Runs independently and generates signals for the main trading system.
    """

    def __init__(self, config: ScannerConfig):
        if not STIRRUP_AVAILABLE:
            raise ImportError("Stirrup not installed. Run: pip install stirrup")

        self.config = config

        # Initialize Stirrup client with OpenRouter
        self.client = ChatCompletionsClient(
            base_url="https://openrouter.ai/api/v1",
            model=config.model,
            api_key=os.environ.get("OPENROUTER_API_KEY"),
        )

        # Create agent with trading tools
        self.agent = Agent(
            client=self.client,
            name="market_scanner",
            max_turns=config.max_turns,
            tools=[
                *DEFAULT_TOOLS,
                GENERATE_SIGNAL_TOOL,
                CHECK_MARKET_TOOL,
            ],
        )

    def _build_scan_prompt(self, symbol: str) -> str:
        """Build the scanning prompt based on mode"""
        mode_instructions = {
            ScanMode.QUICK: "Do a quick 2-3 source scan focusing on latest news headlines.",
            ScanMode.STANDARD: "Scan 5-7 sources including news, social sentiment, and price action.",
            ScanMode.DEEP: "Comprehensive research with 10+ sources, technical analysis, and fundamental factors.",
        }

        return f"""
You are an autonomous market scanner for a trading system.

## Your Task
Analyze {symbol} and generate a trading signal.

## Instructions
1. {mode_instructions[self.config.mode]}
2. Search for recent news, price movements, and sentiment
3. Consider both bullish and bearish factors
4. Generate a signal ONLY if confidence >= {self.config.min_confidence:.0%}
5. If uncertain, generate a HOLD signal with your reasoning

## Signal Requirements
- Must include: symbol, action (BUY/SELL/HOLD), confidence (0.0-1.0), reasoning
- Cite your sources
- Be specific about timeframe (day trade, swing, etc.)

## Current Context
- Symbol: {symbol}
- Scan Mode: {self.config.mode.value}
- Minimum Confidence: {self.config.min_confidence:.0%}
- Timestamp: {datetime.utcnow().isoformat()}

Begin your analysis. Use web search to gather current market data.
"""

    async def scan_symbol(self, symbol: str) -> Optional[dict[str, Any]]:
        """Scan a single symbol and generate signal"""
        output_dir = (
            Path(self.config.output_dir) / symbol / datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        prompt = self._build_scan_prompt(symbol)

        try:
            async with self.agent.session(output_dir=str(output_dir)) as session:
                finish_params, history, metadata = await session.run(prompt)

                # Save scan results
                results = {
                    "symbol": symbol,
                    "timestamp": datetime.utcnow().isoformat(),
                    "mode": self.config.mode.value,
                    "history_length": len(history) if history else 0,
                    "output_dir": str(output_dir),
                }

                (output_dir / "scan_results.json").write_text(json.dumps(results, indent=2))

                return results

        except Exception as e:
            print(f"Error scanning {symbol}: {e}")
            return None

    async def scan_all(self) -> list[dict[str, Any]]:
        """Scan all configured symbols"""
        results = []
        for symbol in self.config.symbols:
            print(f"Scanning {symbol}...")
            result = await self.scan_symbol(symbol)
            if result:
                results.append(result)
        return results


# =============================================================================
# CONTINUOUS MONITORING MODE
# =============================================================================


async def run_continuous_scanner(
    symbols: list[str],
    interval_minutes: int = 60,
    mode: ScanMode = ScanMode.STANDARD,
):
    """
    Run scanner continuously at specified interval.
    Designed for deployment as background process.
    """
    config = ScannerConfig(
        symbols=symbols,
        mode=mode,
    )
    scanner = MarketScanner(config)

    print(f"Starting continuous scanner for {symbols}")
    print(f"Interval: {interval_minutes} minutes, Mode: {mode.value}")

    while True:
        print(f"\n{'=' * 50}")
        print(f"Scan starting at {datetime.utcnow().isoformat()}")
        print(f"{'=' * 50}")

        results = await scanner.scan_all()

        print(f"Completed {len(results)} scans")
        print(f"Next scan in {interval_minutes} minutes...")

        await asyncio.sleep(interval_minutes * 60)


# =============================================================================
# CLI INTERFACE
# =============================================================================


async def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Stirrup Market Scanner")
    parser.add_argument("--symbol", "-s", type=str, default="AAPL", help="Symbol to scan")
    parser.add_argument("--symbols", type=str, help="Comma-separated symbols")
    parser.add_argument(
        "--mode", "-m", type=str, default="standard", choices=["quick", "standard", "deep"]
    )
    parser.add_argument("--continuous", "-c", action="store_true", help="Run in continuous mode")
    parser.add_argument(
        "--interval", "-i", type=int, default=60, help="Scan interval in minutes (continuous mode)"
    )

    args = parser.parse_args()

    # Parse symbols
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]
    else:
        symbols = [args.symbol.upper()]

    mode = ScanMode(args.mode)

    if args.continuous:
        await run_continuous_scanner(symbols, args.interval, mode)
    else:
        config = ScannerConfig(symbols=symbols, mode=mode)
        scanner = MarketScanner(config)
        results = await scanner.scan_all()
        print(f"\nScan complete. Results: {json.dumps(results, indent=2)}")


if __name__ == "__main__":
    if not STIRRUP_AVAILABLE:
        print("ERROR: Stirrup not installed.")
        print("Install with: pip install stirrup")
        print("Or with all extras: pip install 'stirrup[all]'")
        exit(1)

    asyncio.run(main())
