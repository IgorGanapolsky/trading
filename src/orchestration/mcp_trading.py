"""
MCP-driven trading orchestrator.

This module composes the multi-agent trading stack with the new MCP-aware
OpenRouter and Alpaca code interfaces. Agents can import this orchestrator
inside a code-execution environment to run a full decision loop without
loading every tool definition into the prompt context.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
from mcp.servers import alpaca as alpaca_tools
from mcp.servers import openrouter as openrouter_tools
from src.agent_framework.context_engine import (
    ContextType,
    get_context_engine,
)
from src.agents.execution_agent import ExecutionAgent
from src.agents.meta_agent import MetaAgent
from src.agents.research_agent import ResearchAgent
from src.agents.risk_agent import RiskAgent
from src.agents.signal_agent import SignalAgent

logger = logging.getLogger(__name__)


def _bars_to_dataframe(bars: list[dict[str, Any]]) -> pd.DataFrame:
    if not bars:
        return pd.DataFrame()

    df = pd.DataFrame(bars)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)

    rename_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    df.rename(columns=rename_map, inplace=True)

    return df


def _compute_market_features(price_history: pd.DataFrame) -> dict[str, Any]:
    if price_history.empty or "Close" not in price_history.columns:
        return {
            "price": 0.0,
            "volatility": 0.0,
            "trend_strength": 0.0,
            "volume_ratio": 1.0,
            "market_trend": "UNKNOWN",
        }

    close = price_history["Close"]
    price = float(close.iloc[-1])

    returns = close.pct_change().dropna()
    volatility = float(returns.std() * (252**0.5)) if not returns.empty else 0.0

    ma_short = close.rolling(window=20).mean().iloc[-1] if len(close) >= 20 else close.iloc[-1]
    ma_long = close.rolling(window=50).mean().iloc[-1] if len(close) >= 50 else ma_short
    trend_strength = float((ma_short - ma_long) / ma_long) if ma_long else 0.0

    volume = price_history.get("Volume", None)
    if volume is not None and len(volume) >= 20:
        avg_volume = volume.rolling(window=20).mean().iloc[-1]
        volume_ratio = float(volume.iloc[-1] / avg_volume) if avg_volume else 1.0
    else:
        volume_ratio = 1.0

    if trend_strength > 0.02:
        market_trend = "BULLISH"
    elif trend_strength < -0.02:
        market_trend = "BEARISH"
    else:
        market_trend = "NEUTRAL"

    return {
        "price": price,
        "volatility": volatility,
        "trend_strength": trend_strength,
        "volume_ratio": volume_ratio,
        "market_trend": market_trend,
    }


@dataclass(slots=True)
class MCPTradingResult:
    symbol: str
    sentiment: dict[str, Any] = field(default_factory=dict)
    meta_decision: dict[str, Any] = field(default_factory=dict)
    risk_assessment: dict[str, Any] | None = None
    execution_plan: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


class MCPTradingOrchestrator:
    """
    Compose agents and MCP-backed tool wrappers into a reusable orchestrator.
    """

    def __init__(
        self,
        symbols: Sequence[str],
        *,
        paper: bool = True,
    ) -> None:
        self.symbols = list(dict.fromkeys(symbols))  # Preserve order, remove dupes
        self.paper = paper

        self.meta_agent = MetaAgent()
        self.research_agent = ResearchAgent()
        self.signal_agent = SignalAgent()
        self.risk_agent = RiskAgent()

        try:
            from mcp.client import get_alpaca_trader

            self._alpaca_trader = get_alpaca_trader(paper=paper)
            alpaca_api = self._alpaca_trader.api
        except Exception as exc:  # noqa: BLE001
            logger.warning("Alpaca trader unavailable: %s", exc)
            self._alpaca_trader = None
            alpaca_api = None

        self.execution_agent = ExecutionAgent(alpaca_api=alpaca_api)

        # Register specialist agents with meta-agent
        self.meta_agent.register_agent(self.research_agent)
        self.meta_agent.register_agent(self.signal_agent)
        self.meta_agent.register_agent(self.risk_agent)
        self.meta_agent.register_agent(self.execution_agent)

        # Initialize Context Engine for structured context management
        self.context_engine = get_context_engine()

    def run_once(self, *, execute_orders: bool = False) -> dict[str, Any]:
        """
        Execute a full analysis loop across configured symbols.
        """

        summary: dict[str, Any] = {
            "mode": "paper" if self.paper else "live",
            "symbols": [],
        }

        account_info: dict[str, Any] | None = None
        try:
            account_info = alpaca_tools.get_account_snapshot(paper=self.paper)
            summary["account"] = account_info
        except Exception as exc:  # noqa: BLE001
            logger.warning("Account snapshot unavailable: %s", exc)
            summary["account_error"] = str(exc)

        try:
            bars_map = alpaca_tools.get_latest_bars(
                self.symbols,
                limit=200,
                paper=self.paper,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to fetch market data: %s", exc)
            summary["error"] = f"Market data unavailable: {exc}"
            return summary

        portfolio_value = account_info.get("portfolio_value") if account_info else None

        for symbol in self.symbols:
            result = MCPTradingResult(symbol=symbol)
            bars = bars_map.get(symbol, [])
            price_history = _bars_to_dataframe(bars)

            if price_history.empty:
                result.errors.append("Missing price history")
                summary["symbols"].append(asdict(result))
                continue

            market_features = _compute_market_features(price_history)

            market_payload = {
                "symbol": symbol,
                "price": market_features["price"],
                "price_history": price_history,
                "volatility": market_features["volatility"],
                "trend_strength": market_features["trend_strength"],
                "volume_ratio": market_features["volume_ratio"],
                "fundamentals": {},  # TODO: Integrate fundamentals provider
                "news": [],
                "market_context": {
                    "sector": "Unknown",
                    "market_trend": market_features["market_trend"],
                    "volatility": market_features["volatility"],
                },
                "portfolio_value": portfolio_value,
            }

            try:
                # research_context = self.context_engine.get_agent_context(
                #     "research_agent"
                # )

                sentiment = openrouter_tools.detailed_sentiment(
                    market_payload, market_payload["news"]
                )
                result.sentiment = sentiment
                sentiment_score = sentiment.get("score", 0.0)
                market_payload["sentiment"] = sentiment_score

                # Store sentiment in context memory
                self.context_engine.store_memory(
                    agent_id="research_agent",
                    content={
                        "symbol": symbol,
                        "sentiment": sentiment,
                        "sentiment_score": sentiment_score,
                        "timestamp": datetime.now().isoformat(),
                    },
                    tags={symbol, "sentiment", "research"},
                )

                logger.info(
                    f"{symbol}: OpenRouter LLM sentiment analysis complete "
                    f"(score={sentiment_score:.3f})"
                )
            except Exception as exc:  # noqa: BLE001
                error_msg = f"Sentiment analysis failed: {exc}"
                logger.warning(f"{symbol}: {error_msg} - falling back to neutral sentiment")
                result.errors.append(error_msg)
                market_payload["sentiment"] = 0.0

            try:
                # Validate context flow before meta-agent analysis
                is_valid, errors = self.context_engine.validate_context_flow(
                    from_agent="research_agent",
                    to_agent="meta_agent",
                    context=market_payload,
                )
                if not is_valid:
                    logger.warning(f"Context validation warnings for {symbol}: {errors}")

                # meta_context = self.context_engine.get_agent_context("meta_agent")

                meta_decision = self.meta_agent.analyze(market_payload)
                result.meta_decision = meta_decision

                # Send context message from research to meta agent
                self.context_engine.send_context_message(
                    sender="research_agent",
                    receiver="meta_agent",
                    payload={
                        "symbol": symbol,
                        "market_payload": market_payload,
                        "sentiment": sentiment_score,
                    },
                    context_type=ContextType.TASK_CONTEXT,
                    metadata={"symbol": symbol},
                )
            except Exception as exc:  # noqa: BLE001
                error_msg = f"Meta-agent analysis failed: {exc}"
                logger.error(error_msg)
                result.errors.append(error_msg)
                summary["symbols"].append(asdict(result))
                continue

            final_decision = result.meta_decision.get("coordinated_decision", {})
            action = final_decision.get("action", "HOLD")
            confidence = final_decision.get("confidence", 0.5)

            if action in {"BUY", "SELL"}:
                risk_input = {
                    "portfolio_value": portfolio_value or 10000.0,
                    "proposed_action": action,
                    "symbol": symbol,
                    "confidence": confidence,
                    "volatility": market_features["volatility"],
                    "historical_win_rate": final_decision.get("historical_win_rate", 0.60),
                }

                try:
                    risk_assessment = self.risk_agent.analyze(risk_input)
                    result.risk_assessment = risk_assessment
                except Exception as exc:  # noqa: BLE001
                    error_msg = f"Risk assessment failed: {exc}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
                    summary["symbols"].append(result.__dict__)
                    continue

                if (
                    execute_orders
                    and result.risk_assessment
                    and result.risk_assessment.get("action") == "APPROVE"
                ):
                    position_size = result.risk_assessment.get(
                        "position_size",
                        result.risk_assessment.get("calculated_position_size", 0),
                    )

                    execution_payload = {
                        "action": action,
                        "symbol": symbol,
                        "position_size": position_size,
                        "market_conditions": {
                            "volatility": market_features["volatility"],
                            "volume_ratio": market_features["volume_ratio"],
                            "trend": market_features["market_trend"],
                        },
                    }

                    try:
                        execution_plan = self.execution_agent.analyze(execution_payload)
                        result.execution_plan = execution_plan
                    except Exception as exc:  # noqa: BLE001
                        error_msg = f"Execution planning failed: {exc}"
                        logger.error(error_msg)
                        result.errors.append(error_msg)

            summary["symbols"].append(asdict(result))

        return summary
