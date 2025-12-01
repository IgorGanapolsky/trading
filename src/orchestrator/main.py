"""Hybrid funnel orchestrator (Momentum → RL → LLM → Risk)."""

from __future__ import annotations

import logging
import os
from typing import List

from src.agents.momentum_agent import MomentumAgent
from src.agents.rl_agent import RLFilter
from src.execution.alpaca_executor import AlpacaExecutor
from src.langchain_agents.analyst import LangChainSentimentAgent
from src.orchestrator.budget import BudgetController
from src.orchestrator.failure_isolation import FailureIsolationManager
from src.orchestrator.telemetry import OrchestratorTelemetry
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

        import os as _os
        self.momentum_agent = MomentumAgent(
            min_score=float(_os.getenv("MOMENTUM_MIN_SCORE", "0.0"))
        )
        self.rl_filter = RLFilter()
        self.llm_agent = LangChainSentimentAgent()
        self.budget_controller = BudgetController()
        self.risk_manager = RiskManager()
        self.executor = AlpacaExecutor(paper=paper)
        self.executor.sync_portfolio_state()
        self.telemetry = OrchestratorTelemetry()
        self.failure_manager = FailureIsolationManager(self.telemetry)

    def run(self) -> None:
        logger.info("Running hybrid funnel for tickers: %s", ", ".join(self.tickers))
        for ticker in self.tickers:
            self._process_ticker(ticker)

    def _process_ticker(self, ticker: str) -> None:
        logger.info("--- Processing %s ---", ticker)

        # Gate 1: deterministic momentum
        momentum_outcome = self.failure_manager.run(
            gate="momentum",
            ticker=ticker,
            operation=lambda: self.momentum_agent.analyze(ticker),
        )
        if not momentum_outcome.ok:
            logger.error(
                "Gate 1 (%s): momentum analysis failed: %s",
                ticker,
                momentum_outcome.failure.error,
            )
            return

        momentum_signal = momentum_outcome.result
        if not momentum_signal.is_buy:
            logger.info("Gate 1 (%s): REJECTED by momentum filter.", ticker)
            self.telemetry.gate_reject(
                "momentum",
                ticker,
                {
                    "strength": momentum_signal.strength,
                    "indicators": momentum_signal.indicators,
                },
            )
            return
        logger.info(
            "Gate 1 (%s): PASSED (strength=%.2f)", ticker, momentum_signal.strength
        )
        self.telemetry.gate_pass(
            "momentum",
            ticker,
            {
                "strength": momentum_signal.strength,
                "indicators": momentum_signal.indicators,
            },
        )

        # Gate 2: RL inference
        rl_threshold = float(os.getenv("RL_CONFIDENCE_THRESHOLD", "0.6"))
        rl_outcome = self.failure_manager.run(
            gate="rl_filter",
            ticker=ticker,
            operation=lambda: self.rl_filter.predict(momentum_signal.indicators),
        )
        if not rl_outcome.ok:
            logger.error(
                "Gate 2 (%s): RL filter failed: %s",
                ticker,
                rl_outcome.failure.error,
            )
            return

        rl_decision = rl_outcome.result
        if rl_decision.get("confidence", 0.0) < rl_threshold:
            logger.info(
                "Gate 2 (%s): REJECTED by RL filter (confidence=%.2f).",
                ticker,
                rl_decision.get("confidence", 0.0),
            )
            self.telemetry.gate_reject(
                "rl_filter",
                ticker,
                rl_decision,
            )
            return
        logger.info(
            "Gate 2 (%s): PASSED (action=%s, confidence=%.2f).",
            ticker,
            rl_decision.get("action"),
            rl_decision.get("confidence", 0.0),
        )
        self.telemetry.gate_pass("rl_filter", ticker, rl_decision)

        # Gate 3: LLM sentiment (budget-aware)
        sentiment_score = 0.0
        llm_model = getattr(self.llm_agent, "model_name", None)
        if self.budget_controller.can_afford_execution(model=llm_model):
            llm_outcome = self.failure_manager.run(
                gate="llm",
                ticker=ticker,
                operation=lambda: self.llm_agent.analyze_news(
                    ticker, momentum_signal.indicators
                ),
                retry=2,
            )
            if llm_outcome.ok:
                llm_result = llm_outcome.result
                sentiment_score = llm_result.get("score", 0.0)
                self.budget_controller.log_spend(llm_result.get("cost", 0.0))
                neg_threshold = float(
                    os.getenv("LLM_NEGATIVE_SENTIMENT_THRESHOLD", "-0.2")
                )
                if sentiment_score < neg_threshold:
                    logger.info(
                        "Gate 3 (%s): REJECTED by LLM (score=%.2f, reason=%s).",
                        ticker,
                        sentiment_score,
                        llm_result.get("reason", "N/A"),
                    )
                    self.telemetry.gate_reject(
                        "llm",
                        ticker,
                        {**llm_result, "trigger": "negative_sentiment"},
                    )
                    return
                logger.info(
                    "Gate 3 (%s): PASSED (sentiment=%.2f).", ticker, sentiment_score
                )
                self.telemetry.gate_pass("llm", ticker, llm_result)
            else:
                logger.warning(
                    "Gate 3 (%s): Error calling LLM (%s). Falling back to RL output.",
                    ticker,
                    llm_outcome.failure.error,
                )
                self.telemetry.gate_reject(
                    "llm",
                    ticker,
                    {
                        "error": llm_outcome.failure.error,
                        "reason": "exception",
                        "attempts": llm_outcome.failure.metadata.get("attempts"),
                    },
                )
        else:
            logger.info("Gate 3 (%s): Skipped to protect budget.", ticker)
            self.telemetry.record(
                event_type="gate.llm",
                ticker=ticker,
                status="skipped",
                payload={
                    "remaining_budget": self.budget_controller.remaining_budget,
                    "model": llm_model,
                },
            )

        # Gather recent history for ATR-based sizing and stops
        hist = None
        current_price = momentum_signal.indicators.get("last_price")
        atr_pct = None
        try:
            from src.utils.market_data import MarketDataFetcher
            from src.utils.technical_indicators import calculate_atr

            fetcher = MarketDataFetcher()
            res = fetcher.get_daily_bars(symbol=ticker, lookback_days=60)
            hist = res.data
            if current_price is None and hist is not None and not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
            if hist is not None and current_price:
                atr_val = float(calculate_atr(hist))
                if atr_val and current_price:
                    atr_pct = atr_val / float(current_price)
        except Exception as exc:  # pragma: no cover - fail-open
            logger.debug("History fetch failed for %s: %s", ticker, exc)

        # Gate 4: Risk sizing and execution
        risk_outcome = self.failure_manager.run(
            gate="risk",
            ticker=ticker,
            operation=lambda: self.risk_manager.calculate_size(
                ticker=ticker,
                account_equity=self.executor.account_equity,
                signal_strength=momentum_signal.strength,
                rl_confidence=rl_decision.get("confidence", 0.0),
                sentiment_score=sentiment_score,
                multiplier=rl_decision.get("suggested_multiplier", 1.0),
                current_price=current_price,
                hist=hist,
            ),
            event_type="gate.risk",
        )
        if not risk_outcome.ok:
            logger.error(
                "Gate 4 (%s): Risk sizing failed: %s",
                ticker,
                risk_outcome.failure.error,
            )
            return

        order_size = risk_outcome.result

        if order_size <= 0:
            logger.info(
                "Gate 4 (%s): REJECTED (position size calculated as 0).", ticker
            )
            self.telemetry.gate_reject(
                "risk",
                ticker,
                {
                    "order_size": order_size,
                    "account_equity": self.executor.account_equity,
                },
            )
            return

        logger.info("Executing BUY %s for $%.2f", ticker, order_size)
        order_outcome = self.failure_manager.run(
            gate="execution.order",
            ticker=ticker,
            operation=lambda: self.executor.place_order(
                ticker,
                order_size,
                side="buy",
            ),
            event_type="execution.order",
        )
        if not order_outcome.ok:
            logger.error(
                "Execution failed for %s: %s", ticker, order_outcome.failure.error
            )
            return
        order = order_outcome.result
        self.telemetry.gate_pass(
            "risk",
            ticker,
            {"order_size": order_size, "account_equity": self.executor.account_equity},
        )
        self.telemetry.order_event(ticker, {"order": order, "rl": rl_decision})

        # Place ATR-based stop-loss if possible
        try:
            if current_price and current_price > 0:
                stop_price = self.risk_manager.calculate_stop_loss(
                    ticker=ticker, entry_price=float(current_price), direction="long", hist=hist
                )
                # Approximate quantity from notional if fill qty unavailable
                qty = order.get("filled_qty") or (order_size / float(current_price))
                stop_order = self.executor.set_stop_loss(ticker, float(qty), float(stop_price))
                self.telemetry.record(
                    event_type="execution.stop",
                    ticker=ticker,
                    status="submitted",
                    payload={
                        "stop": stop_order,
                        "atr_pct": atr_pct,
                        "atr_multiplier": float(os.getenv("ATR_STOP_MULTIPLIER", "2.0")),
                    },
                )
        except Exception as exc:  # pragma: no cover - non-fatal
            logger.info("Stop-loss placement skipped for %s: %s", ticker, exc)
