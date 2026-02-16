"""
Pre-Trade Research Agent — DeepSeek-R1 powered IC entry opinion.

Autonomous advisory layer that runs before every iron condor entry.
Consumes: market regime, Thompson sampling stats, VIX data, RAG lessons.
Outputs: structured JSON opinion (trade/skip, confidence, suggested params).

The opinion is ADVISORY ONLY — hard risk limits in Python are never overridden.
Phil Town Rule #1: Don't lose money. The risk engine has final say.

Integration points:
- Called by iron_condor_trader.py between VIX check and find_trade()
- Uses model_selector for budget-aware routing (DeepSeek-R1 via OpenRouter)
- Falls back gracefully: if LLM call fails, trade proceeds with existing logic

Feb 2026 — Built per CEO directive for autonomous, smart, automated execution.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field
from src.utils.llm_gateway import (
    OPENROUTER_BASE_URL,
    resolve_openrouter_primary_and_fallback_configs,
)
from src.utils.model_selector import get_model_selector

logger = logging.getLogger(__name__)


# =============================================================================
# STRUCTURED OUTPUT SCHEMA
# =============================================================================


class TradeOpinion(BaseModel):
    """Structured pre-trade opinion from LLM research agent."""

    should_trade: bool = Field(description="Whether to enter the iron condor")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in recommendation")
    regime: str = Field(description="Detected market regime (calm/trending/volatile/spike)")
    suggested_short_delta: float = Field(
        ge=0.05,
        le=0.30,
        default=0.15,
        description="Suggested short strike delta (0.10-0.20 typical)",
    )
    suggested_dte: int = Field(
        ge=14,
        le=60,
        default=35,
        description="Suggested days to expiration",
    )
    reasoning: str = Field(description="Brief reasoning for the decision")
    risk_flags: list[str] = Field(
        default_factory=list,
        description="Any risk warnings (earnings, FOMC, etc.)",
    )


# =============================================================================
# PRE-TRADE RESEARCH AGENT
# =============================================================================


def get_trade_opinion(
    vix_current: float | None = None,
    thompson_stats: dict[str, Any] | None = None,
    regime: str | None = None,
    recent_lessons: list[str] | None = None,
) -> TradeOpinion | None:
    """
    Get pre-trade opinion from DeepSeek-R1 via OpenRouter.

    This is the autonomous research agent. It:
    1. Gathers context (VIX, Thompson stats, regime, RAG lessons)
    2. Sends structured prompt to DeepSeek-R1
    3. Returns a typed TradeOpinion object

    Returns None if the LLM call fails (trade proceeds with existing logic).
    """
    primary_cfg, fallback_cfg = resolve_openrouter_primary_and_fallback_configs()
    if not primary_cfg.api_key:
        logger.info("Trade opinion: missing OpenAI-compatible API key, skipping LLM advisory")
        return None

    # Select model via BATS framework
    selector = get_model_selector()
    model_id = selector.select_model("pre_trade_research")
    provider = selector.get_model_provider(model_id)

    if provider != "openrouter":
        logger.info(f"Trade opinion: model {model_id} is not OpenRouter, skipping")
        return None

    # Build the prompt
    prompt = _build_prompt(vix_current, thompson_stats, regime, recent_lessons)

    try:
        from openai import OpenAI
        from src.utils.model_selector import to_tars_model_id

        client = OpenAI(api_key=primary_cfg.api_key, base_url=primary_cfg.base_url)
        using_gateway = bool(primary_cfg.base_url) and (
            primary_cfg.base_url.rstrip("/") != OPENROUTER_BASE_URL.rstrip("/")
        )
        model_for_call = to_tars_model_id(model_id) if using_gateway else model_id

        try:
            response = client.chat.completions.create(
                model=model_for_call,
                messages=[
                    {"role": "system", "content": _system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
        except Exception as gateway_exc:
            # If we're routing through a gateway (TARS) and it fails, retry via
            # OpenRouter direct (if OPENROUTER_API_KEY is present).
            if fallback_cfg:
                logger.warning(
                    "Trade opinion: gateway call failed (%s). Retrying via OpenRouter direct.",
                    gateway_exc,
                )
                fallback_client = OpenAI(
                    api_key=fallback_cfg.api_key, base_url=fallback_cfg.base_url
                )
                response = fallback_client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": _system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=2048,
                    response_format={"type": "json_object"},
                )
            else:
                raise

        # Log usage for budget tracking
        if response.usage:
            selector.log_usage(
                model_id,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )

        # Parse response
        text = response.choices[0].message.content if response.choices else ""
        if not text:
            logger.warning("Trade opinion: empty response from LLM")
            return None

        data = json.loads(text)
        opinion = TradeOpinion.model_validate(data)

        logger.info(
            f"Trade opinion: should_trade={opinion.should_trade}, "
            f"confidence={opinion.confidence:.2f}, regime={opinion.regime}, "
            f"delta={opinion.suggested_short_delta}, dte={opinion.suggested_dte}"
        )
        if opinion.risk_flags:
            logger.warning(f"Trade opinion risk flags: {opinion.risk_flags}")

        return opinion

    except ImportError:
        logger.warning("Trade opinion: openai package not installed")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Trade opinion: failed to parse JSON response: {e}")
        return None
    except Exception as e:
        logger.warning(f"Trade opinion: LLM call failed: {e}")
        return None


def _system_prompt() -> str:
    """System prompt for the pre-trade research agent."""
    return """You are a quantitative options trading research agent.

Your role: Analyze market conditions and advise on SPY iron condor entry.

RULES (Phil Town Rule #1: Don't Lose Money):
- Iron condors profit when SPY stays in a range
- Ideal conditions: low/moderate volatility, no major catalysts
- VIX 15-25 is optimal. Below 15 = premiums too thin. Above 30 = too risky.
- 15-delta short strikes = ~85% probability of profit
- 30-45 DTE optimal for theta decay
- NEVER recommend trading during earnings, FOMC, or extreme volatility

You must respond with valid JSON matching the TradeOpinion schema.
Be concise in reasoning (1-2 sentences max)."""


def _build_prompt(
    vix_current: float | None,
    thompson_stats: dict[str, Any] | None,
    regime: str | None,
    recent_lessons: list[str] | None,
) -> str:
    """Build the research prompt with all available context."""
    sections = ["Analyze whether to enter a SPY iron condor today.\n"]

    # VIX context
    if vix_current is not None:
        sections.append(f"Current VIX: {vix_current:.2f}")

    # Thompson sampling stats
    if thompson_stats:
        wins = thompson_stats.get("wins", 0)
        losses = thompson_stats.get("losses", 0)
        posterior = thompson_stats.get("posterior_mean", 0.5)
        recommendation = thompson_stats.get("recommendation", "UNKNOWN")
        sections.append(
            f"Thompson Sampling: {wins}W/{losses}L, "
            f"posterior_mean={posterior:.3f}, recommendation={recommendation}"
        )

    # Market regime
    if regime:
        sections.append(f"Market Regime: {regime}")

    # RAG lessons (recent failures to avoid)
    if recent_lessons:
        sections.append("\nRecent lessons learned (avoid these mistakes):")
        for lesson in recent_lessons[:5]:  # Cap at 5 to control token usage
            sections.append(f"- {lesson[:200]}")

    sections.append(
        "\nRespond with JSON: {should_trade, confidence, regime, "
        "suggested_short_delta, suggested_dte, reasoning, risk_flags}"
    )

    return "\n".join(sections)
