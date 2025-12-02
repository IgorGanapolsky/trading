from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from langchain_agents.agents import build_price_action_agent

logger = logging.getLogger(__name__)


DEFAULT_PROMPT = """\
You are a price-action analyst preparing a concise morning brief for the trading desk.
Summarize the technical outlook for the specified ticker, include notable support/resistance
levels, volume context, and mention any sentiment insights retrieved from the sentiment tools.
If sentiment data is unavailable, state that explicitly. Keep the answer under 300 words.
"""


def run_price_action_analysis(
    ticker: str,
    custom_prompt: str | None = None,
) -> str:
    agent = build_price_action_agent()
    prompt = custom_prompt or DEFAULT_PROMPT
    full_input = f"{prompt}\n\nTicker: {ticker}"

    logger.info("Running price action analysis for %s", ticker)
    response = agent.invoke({"input": full_input})

    if isinstance(response, dict) and "output" in response:
        return response["output"]
    if isinstance(response, str):
        return response
    return str(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run price action analyst agent.")
    parser.add_argument("--ticker", default="SPY", help="Ticker symbol (default: SPY)")
    parser.add_argument(
        "--prompt",
        help="Optional custom prompt override.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the analysis (defaults to reports/).",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    report = run_price_action_analysis(args.ticker, args.prompt)
    print(report)

    output_path = (
        Path(args.output)
        if args.output
        else Path("reports") / f"price_action_{args.ticker.lower()}_{datetime.now().date()}.txt"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    logger.info("Report written to %s", output_path)


if __name__ == "__main__":
    main()
