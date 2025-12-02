#!/usr/bin/env python3
"""
Command-line entry point for the MCP trading orchestrator.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from src.orchestration.mcp_trading import MCPTradingOrchestrator


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the MCP-based multi-agent trading orchestrator."
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="SPY,QQQ",
        help="Comma-separated list of symbols to analyze (default: SPY,QQQ)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live trading credentials (default: paper trading)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute approved trades (default: analyze only).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="json",
        choices=["json"],
        help="Output format (currently only json).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()]

    orchestrator = MCPTradingOrchestrator(symbols=symbols, paper=not args.live)
    summary = orchestrator.run_once(execute_orders=args.execute)

    if args.output == "json":
        print(json.dumps(summary, indent=2, default=str))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
