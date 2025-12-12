"""
Minimal OpenAI Agents SDK bridge for the trading system.

Goals:
- Provide a ready-to-run supervisor with research/risk/execution sub-agents.
- Reuse existing market-data utilities for deterministic, low-risk tools.
- Keep the public surface small so it can be swapped into orchestrators.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from agents import Agent, GuardrailFunctionOutput, Runner, SQLiteSession, output_guardrail
from agents.tool import function_tool
from src.utils.market_data import DataSource, get_market_data_provider

logger = logging.getLogger(__name__)

# Model selection (Dec 2025): Use GPT-5.2 for SOTA performance if enabled
_USE_GPT52 = os.getenv("OPENAI_AGENTS_USE_GPT52", "false").lower() in {"1", "true", "yes"}
_AGENT_MODEL = "gpt-5.2" if _USE_GPT52 else "gpt-4.1-mini"
_SUPERVISOR_MODEL = "gpt-5.2" if _USE_GPT52 else "gpt-4.1"

if _USE_GPT52:
    logger.info("OpenAI Agents: Using GPT-5.2 (SOTA coding/tool-calling)")
else:
    logger.debug("OpenAI Agents: Using GPT-4.1/4.1-mini (set OPENAI_AGENTS_USE_GPT52=true to upgrade)")


@output_guardrail(name="summary_presence_guard")
async def _summary_presence_guard(context, agent, output):
    """
    Warn if the agent fails to produce a labeled summary despite instructions.
    """

    rendered = output if isinstance(output, str) else str(output)
    has_summary = '"summary"' in rendered.lower() or "summary:" in rendered.lower()
    if not has_summary:
        logger.warning(
            "Agent %s output is missing a summary label; ensure you emit a 'summary' key.",
            agent.name,
        )
    return GuardrailFunctionOutput(output_info="summary_presence_check", tripwire_triggered=False)


def _fetch_price_snapshot(symbol: str) -> dict[str, Any]:
    """Get the most recent close plus simple risk stats."""
    provider = get_market_data_provider()
    result = provider.get_daily_bars(symbol, lookback_days=30)

    if result.data.empty:
        raise ValueError(f"No price data for {symbol}")

    close_series = result.data["Close"]
    close = float(close_series.iat[-1])
    prev = float(close_series.iat[-2]) if len(close_series) > 1 else close
    change_pct = (close / prev - 1) * 100 if prev else 0.0
    pct_std = close_series.pct_change().std()
    volatility_pct = float(pct_std * 100) if len(close_series) > 5 else 0.0

    return {
        "symbol": symbol.upper(),
        "close": round(close, 4),
        "prev_close": round(prev, 4),
        "change_pct": round(change_pct, 2),
        "volatility_pct": round(volatility_pct, 2),
        "source": result.source.value
        if isinstance(result.source, DataSource)
        else str(result.source),
        "samples": len(close_series),
        "tool_name": "fetch_last_close",
        "timestamp": datetime.now().isoformat(),
    }


@function_tool
def fetch_last_close(symbol: str) -> dict[str, Any]:
    """
    Return the latest close price, 1-day change %, and volatility proxy.
    """

    return _fetch_price_snapshot(symbol)


@function_tool
def quick_signal(symbol: str) -> dict[str, Any]:
    """
    Create a lightweight momentum signal using 5-day vs 20-day averages.
    """

    provider = get_market_data_provider()
    result = provider.get_daily_bars(symbol, lookback_days=40)
    if result.data.empty:
        raise ValueError(f"No price data for {symbol}")

    closes = result.data["Close"].tail(40)
    ma_fast = closes.tail(5).mean().item()
    ma_slow = closes.tail(20).mean().item()
    bias = "BULLISH" if ma_fast > ma_slow else "BEARISH"

    return {
        "symbol": symbol.upper(),
        "ma_fast_5": round(ma_fast, 4),
        "ma_slow_20": round(ma_slow, 4),
        "bias": bias,
        "source": result.source.value
        if isinstance(result.source, DataSource)
        else str(result.source),
        "tool_name": "quick_signal",
        "timestamp": datetime.now().isoformat(),
    }


@function_tool
def plan_execution(symbol: str, action: str = "BUY", notional: float = 1000.0) -> dict[str, Any]:
    """
    Produce an execution stub (paper) without sending live orders.
    """

    snap = _fetch_price_snapshot(symbol)
    per_share = snap["close"]
    qty = max(int(notional // per_share), 1)

    return {
        "symbol": snap["symbol"],
        "action": action.upper(),
        "order_type": "market",
        "quantity": qty,
        "notional": round(qty * per_share, 2),
        "assumptions": {
            "slippage_bps": 10,
            "volatility_pct": snap["volatility_pct"],
        },
        "note": "Preview only; hook into ExecutionAgent for live trading.",
        "tool_name": "plan_execution",
        "source_snapshot": snap,
        "timestamp": datetime.now().isoformat(),
    }


def create_trading_agents() -> dict[str, Agent]:
    """
    Build a supervisor and its sub-agents for the OpenAI Agents SDK runtime.
    """

    research_agent = Agent(
        name="ResearchAgent",
        instructions=(
            "Research summary: start with that label, then emit a clean JSON object with keys "
            '"summary", "bias", "tool_metadata", and "actionable_next_steps". '
            "Describe which tools you used and why. Keep the first modal statement brief so risk/execution agents can parse the JSON easily."
        ),
        tools=[fetch_last_close, quick_signal],
        model=_AGENT_MODEL,
        output_guardrails=[_summary_presence_guard],
    )

    risk_agent = Agent(
        name="RiskAgent",
        instructions=(
            'Risk signal: begin with that label and return JSON with keys "summary", '
            '"high_volatility_flags", "risk_actions", and "prior_research" (copy or paraphrase the research JSON). '
            "Highlight change_pct >5% or volatility_pct >10%. Reference the research JSON so the handoff stays explicit."
        ),
        tools=[fetch_last_close],
        model=_AGENT_MODEL,
        output_guardrails=[_summary_presence_guard],
    )

    execution_agent = Agent(
        name="ExecutionAgent",
        instructions=(
            "Execution plan: start with that label and reply with JSON containing "
            '"summary", "order_preview", "risk_context", and "confidence". '
            "Call plan_execution for notional math and cite the risk JSON verbatim so the supervisor can trust the handoff."
        ),
        tools=[plan_execution],
        model=_AGENT_MODEL,
        output_guardrails=[_summary_presence_guard],
    )

    supervisor = Agent(
        name="TradingSupervisor",
        instructions=(
            "For context, here is the conversation so far between the user and the previous agent: "
            "Repeat that phrase and the last agent's JSON before calling the next agent. "
            'Run research → risk → execution in order and emit a final JSON with keys "final_summary", '
            '"bias", "risk_flags", and "execution_plan" so downstream orchestrators can parse it without extra parsing logic.'
        ),
        handoffs=[research_agent, risk_agent, execution_agent],
        model=_SUPERVISOR_MODEL,
        output_guardrails=[_summary_presence_guard],
    )

    return {
        "supervisor": supervisor,
        "research": research_agent,
        "risk": risk_agent,
        "execution": execution_agent,
    }


def run_supervisor_sync(prompt: str, session_path: str | Path | None = None) -> Any:
    """
    Convenience helper: run the supervisor synchronously with optional persisted session.
    """

    agents = create_trading_agents()
    runner = Runner()

    run_kwargs: dict[str, Any] = {}
    if session_path:
        run_kwargs["session"] = SQLiteSession(str(Path(session_path)))

    logger.info("Running OpenAI Agents SDK supervisor with prompt: %s", prompt)
    return runner.run_sync(agents["supervisor"], prompt, **run_kwargs)
