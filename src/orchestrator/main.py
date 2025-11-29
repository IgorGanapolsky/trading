"""Hybrid funnel orchestrator (Momentum → RL → LLM → Risk)."""

from __future__ import annotations

import logging
from typing import List

from src.agents.momentum_agent import MomentumAgent
from src.agents.rl_agent import RLFilter
from src.execution.alpaca_executor import AlpacaExecutor
from src.langchain_agents.analyst import LangChainSentimentAgent
from src.orchestrator.budget import BudgetController
from src.risk.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class TradingOrchestrator:
    """
    Implements the four-gate funnel:

        Gate 1 - Momentum (math, free)
        Gate 2 - RL filter (local inference)
        Gate 3 - LLM analyst (budgeted)
        Gate 4 - Risk sizing (hard rules)
    """

    def __init__(self, tickers: List[str], paper: bool = True) -> None:
        self.tickers = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
        if not self.tickers:
            raise ValueError("At least one ticker symbol is required.")

        self.momentum_agent = MomentumAgent()
        self.rl_filter = RLFilter()
        self.llm_agent = LangChainSentimentAgent()
        self.budget_controller = BudgetController()
        self.risk_manager = RiskManager()
        self.executor = AlpacaExecutor(paper=paper)
        self.executor.sync_portfolio_state()

    def run(self) -> None:
        logger.info("Running hybrid funnel for tickers: %s", ", ".join(self.tickers))
        for ticker in self.tickers:
            self._process_ticker(ticker)

    def _process_ticker(self, ticker: str) -> None:
        logger.info("--- Processing %s ---", ticker)

        # Gate 1: deterministic momentum
        momentum_signal = self.momentum_agent.analyze(ticker)
        if not momentum_signal.is_buy:
            logger.info("Gate 1 (%s): REJECTED by momentum filter.", ticker)
            return
        logger.info(
            "Gate 1 (%s): PASSED (strength=%.2f)", ticker, momentum_signal.strength
        )

        # Gate 2: RL inference
        rl_decision = self.rl_filter.predict(momentum_signal.indicators)
        if rl_decision.get("confidence", 0.0) < 0.6:
            logger.info(
                "Gate 2 (%s): REJECTED by RL filter (confidence=%.2f).",
                ticker,
                rl_decision.get("confidence", 0.0),
            )
            return
        logger.info(
            "Gate 2 (%s): PASSED (action=%s, confidence=%.2f).",
            ticker,
            rl_decision.get("action"),
            rl_decision.get("confidence", 0.0),
        )

        # Gate 3: LLM sentiment (budget-aware)
        sentiment_score = 0.0
        if self.budget_controller.can_afford_execution():
            try:
                llm_result = self.llm_agent.analyze_news(
                    ticker, momentum_signal.indicators
                )
                sentiment_score = llm_result.get("score", 0.0)
                self.budget_controller.log_spend(llm_result.get("cost", 0.0))
                if sentiment_score < -0.2:
                    logger.info(
                        "Gate 3 (%s): REJECTED by LLM (score=%.2f, reason=%s).",
                        ticker,
                        sentiment_score,
                        llm_result.get("reason", "N/A"),
                    )
                    return
                logger.info(
                    "Gate 3 (%s): PASSED (sentiment=%.2f).", ticker, sentiment_score
                )
            except Exception as exc:  # noqa: BLE001 - fallback to RL decision
                logger.warning(
                    "Gate 3 (%s): Error calling LLM (%s). Falling back to RL output.",
                    ticker,
                    exc,
                )
        else:
            logger.info("Gate 3 (%s): Skipped to protect budget.", ticker)

        # Gate 4: Risk sizing and execution
        order_size = self.risk_manager.calculate_size(
            ticker=ticker,
            account_equity=self.executor.account_equity,
            signal_strength=momentum_signal.strength,
            rl_confidence=rl_decision.get("confidence", 0.0),
            sentiment_score=sentiment_score,
            multiplier=rl_decision.get("suggested_multiplier", 1.0),
        )

        if order_size <= 0:
            logger.info("Gate 4 (%s): REJECTED (position size calculated as 0).", ticker)
            return

        logger.info("Executing BUY %s for $%.2f", ticker, order_size)
        self.executor.place_order(
            ticker,
            order_size,
            side="buy",
        )

