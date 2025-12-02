"""Hybrid funnel orchestrator (Momentum → RL → LLM → Risk)."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

import holidays
from src.agents.momentum_agent import MomentumAgent
from src.agents.rl_agent import RLFilter
from src.analyst.bias_store import BiasProvider, BiasSnapshot, BiasStore
from src.execution.alpaca_executor import AlpacaExecutor
from src.langchain_agents.analyst import LangChainSentimentAgent
from src.orchestrator.anomaly_monitor import AnomalyMonitor
from src.orchestrator.budget import BudgetController
from src.orchestrator.failure_isolation import FailureIsolationManager
from src.orchestrator.telemetry import OrchestratorTelemetry
from src.risk.capital_efficiency import get_capital_calculator
from src.risk.options_risk_monitor import OptionsRiskMonitor
from src.risk.risk_manager import RiskManager
from src.risk.trade_gateway import TradeGateway, TradeRequest
from src.signals.microstructure_features import MicrostructureFeatureExtractor
from src.utils.regime_detector import RegimeDetector

logger = logging.getLogger(__name__)

_US_HOLIDAYS_CACHE: dict[int, holidays.HolidayBase] = {}


def _get_us_holidays(year: int) -> holidays.HolidayBase:
    if year not in _US_HOLIDAYS_CACHE:
        _US_HOLIDAYS_CACHE[year] = holidays.US(years=[year])
    return _US_HOLIDAYS_CACHE[year]


def is_us_market_day(day: date | None = None) -> bool:
    current_day = day or datetime.utcnow().date()
    if current_day.weekday() >= 5:  # Saturday/Sunday
        return False
    calendar = _get_us_holidays(current_day.year)
    return current_day not in calendar


class TradingOrchestrator:
    """
    Implements the four-gate funnel:

        Gate 1 - Momentum (math, free)
        Gate 2 - RL filter (local inference)
        Gate 3 - LLM analyst (budgeted)
        Gate 4 - Risk sizing (hard rules)
    """

    def __init__(self, tickers: list[str], paper: bool = True) -> None:
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
        self.anomaly_monitor = AnomalyMonitor(
            telemetry=self.telemetry,
            window=int(os.getenv("ANOMALY_WINDOW", "40")),
            rejection_threshold=float(os.getenv("ANOMALY_REJECTION_THRESHOLD", "0.8")),
            confidence_floor=float(os.getenv("ANOMALY_CONFIDENCE_FLOOR", "0.45")),
        )
        self.failure_manager = FailureIsolationManager(self.telemetry)
        self.options_risk_monitor = OptionsRiskMonitor(paper=paper)
        # CRITICAL: All trades must go through the gateway - no direct executor calls
        self.trade_gateway = TradeGateway(executor=self.executor, paper=paper)
        # Capital efficiency calculator - determines what strategies are viable
        self.capital_calculator = get_capital_calculator(daily_deposit_rate=10.0)
        self.session_profile: dict[str, Any] | None = None
        self.microstructure = MicrostructureFeatureExtractor()
        self.regime_detector = RegimeDetector()

        bias_dir = os.getenv("BIAS_DATA_DIR", "data/bias")
        self.bias_store = BiasStore(bias_dir)
        self.bias_fresh_minutes = int(os.getenv("BIAS_FRESHNESS_MINUTES", "90"))
        self.bias_snapshot_ttl_minutes = int(
            os.getenv("BIAS_TTL_MINUTES", str(max(self.bias_fresh_minutes, 360)))
        )
        enable_async_analyst = os.getenv("ENABLE_ASYNC_ANALYST", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        self.bias_provider: BiasProvider | None = None
        if enable_async_analyst:
            self.bias_provider = BiasProvider(
                self.bias_store,
                freshness=timedelta(minutes=self.bias_fresh_minutes),
            )

    def run(self) -> None:
        session_profile = self._build_session_profile()
        active_tickers = session_profile["tickers"]
        self.session_profile = session_profile

        self.momentum_agent.configure_regime(session_profile.get("momentum_overrides"))

        self.telemetry.record(
            event_type="session.profile",
            ticker="SYSTEM",
            status="info",
            payload={
                "session_type": session_profile["session_type"],
                "market_day": session_profile["is_market_day"],
                "tickers": active_tickers,
                "rl_threshold": session_profile["rl_threshold"],
            },
        )

        logger.info(
            "Running hybrid funnel (%s) for tickers: %s",
            session_profile["session_type"],
            ", ".join(active_tickers),
        )

        for ticker in active_tickers:
            self._process_ticker(ticker, rl_threshold=session_profile["rl_threshold"])

        # Gate 5: Post-execution delta rebalancing
        self.run_delta_rebalancing()

        # Gate 6: Phil Town Rule #1 Options Strategy
        self.run_options_strategy()

    def _build_session_profile(self) -> dict[str, Any]:
        today = datetime.utcnow().date()
        market_day = is_us_market_day(today)
        proxy_symbols = os.getenv("WEEKEND_PROXY_SYMBOLS", "BITO,RWCR")
        proxy_list = [
            symbol.strip().upper() for symbol in proxy_symbols.split(",") if symbol.strip()
        ]
        momentum_overrides: dict[str, float] = {}
        rl_threshold = float(os.getenv("RL_CONFIDENCE_THRESHOLD", "0.6"))
        session_type = "market_hours"

        if not market_day:
            session_type = "off_hours_crypto_proxy"
            proxy_list = proxy_list or ["BITO"]
            momentum_overrides = {
                "rsi_overbought": float(os.getenv("WEEKEND_RSI_OVERBOUGHT", "65.0")),
                "macd_threshold": float(os.getenv("WEEKEND_MACD_THRESHOLD", "-0.05")),
                "volume_min": float(os.getenv("WEEKEND_VOLUME_MIN", "0.5")),
            }
            rl_threshold = float(os.getenv("RL_WEEKEND_CONFIDENCE_THRESHOLD", "0.55"))

        tickers = self.tickers if market_day else proxy_list

        return {
            "session_type": session_type,
            "is_market_day": market_day,
            "tickers": tickers,
            "rl_threshold": rl_threshold,
            "momentum_overrides": momentum_overrides,
        }

    def _estimate_execution_costs(self, notional: float) -> dict[str, float]:
        sec_fee_rate = float(os.getenv("SEC_FEE_RATE", "0.000018"))
        broker_fee_rate = float(os.getenv("BROKER_FEE_RATE", "0.0005"))
        slip_bps = float(os.getenv("EXECUTION_SLIPPAGE_BPS", "25.0"))

        slippage_cost = (slip_bps / 10_000.0) * notional
        fee_cost = (sec_fee_rate + broker_fee_rate) * notional
        total_cost = slippage_cost + fee_cost

        return {
            "slippage_cost": round(slippage_cost, 4),
            "fees": round(fee_cost, 4),
            "total_cost": round(total_cost, 4),
            "slippage_bps": slip_bps,
            "fee_rate": sec_fee_rate + broker_fee_rate,
        }

    def _track_gate_event(
        self,
        *,
        gate: str,
        ticker: str,
        status: str,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        try:
            self.anomaly_monitor.track(
                gate=gate,
                ticker=ticker,
                status=status,
                metrics=metrics or {},
            )
        except Exception as exc:  # pragma: no cover - non-critical
            logger.debug("Anomaly monitor tracking failed for %s: %s", gate, exc)

    def _process_ticker(self, ticker: str, rl_threshold: float) -> None:
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
            self._track_gate_event(
                gate="momentum",
                ticker=ticker,
                status="reject",
                metrics={"confidence": momentum_signal.strength},
            )
            return
        logger.info("Gate 1 (%s): PASSED (strength=%.2f)", ticker, momentum_signal.strength)
        self.telemetry.gate_pass(
            "momentum",
            ticker,
            {
                "strength": momentum_signal.strength,
                "indicators": momentum_signal.indicators,
            },
        )
        self._track_gate_event(
            gate="momentum",
            ticker=ticker,
            status="pass",
            metrics={"confidence": momentum_signal.strength},
        )

        # Gate 2: RL inference
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
            self._track_gate_event(
                gate="rl_filter",
                ticker=ticker,
                status="error",
                metrics={"confidence": 0.0},
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
            self._track_gate_event(
                gate="rl_filter",
                ticker=ticker,
                status="reject",
                metrics={"confidence": rl_decision.get("confidence", 0.0)},
            )
            return
        logger.info(
            "Gate 2 (%s): PASSED (action=%s, confidence=%.2f).",
            ticker,
            rl_decision.get("action"),
            rl_decision.get("confidence", 0.0),
        )
        self.telemetry.gate_pass("rl_filter", ticker, rl_decision)
        self.telemetry.explainability_event(
            gate="rl_filter",
            ticker=ticker,
            contributions=rl_decision.get("explainability", {}),
            metadata={"sources": rl_decision.get("sources")},
        )
        self._track_gate_event(
            gate="rl_filter",
            ticker=ticker,
            status="pass",
            metrics={"confidence": rl_decision.get("confidence", 0.0)},
        )

        micro_features = {}
        regime_snapshot = {"label": "unknown", "confidence": 0.0}
        try:
            micro_features = self.microstructure.extract(ticker)
            if "microstructure_error" not in micro_features:
                momentum_signal.indicators.update(micro_features)
                regime_snapshot = self.regime_detector.detect(micro_features)
                self.telemetry.record(
                    event_type="microstructure",
                    ticker=ticker,
                    status="ok",
                    payload={**micro_features, **regime_snapshot},
                )
            else:
                self.telemetry.record(
                    event_type="microstructure",
                    ticker=ticker,
                    status="error",
                    payload=micro_features,
                )
        except Exception as exc:  # pragma: no cover - diagnostics only
            self.telemetry.record(
                event_type="microstructure",
                ticker=ticker,
                status="exception",
                payload={"error": str(exc)},
            )

        # Gate 3: LLM sentiment (budget-aware, bias-cache first)
        sentiment_score = 0.0
        llm_model = getattr(self.llm_agent, "model_name", None)
        neg_threshold = float(os.getenv("LLM_NEGATIVE_SENTIMENT_THRESHOLD", "-0.2"))
        bias_snapshot: BiasSnapshot | None = None

        if self.bias_provider:
            bias_snapshot = self.bias_provider.get_bias(ticker)

        if bias_snapshot:
            sentiment_score = bias_snapshot.score
            payload = bias_snapshot.to_dict()
            payload["source"] = "bias_store"
            if sentiment_score < neg_threshold:
                logger.info(
                    "Gate 3 (%s): REJECTED by bias store (score=%.2f, reason=%s).",
                    ticker,
                    sentiment_score,
                    bias_snapshot.reason,
                )
                self.telemetry.gate_reject(
                    "llm",
                    ticker,
                    {**payload, "trigger": "negative_sentiment"},
                )
                return
            logger.info(
                "Gate 3 (%s): PASSED via bias store (sentiment=%.2f).",
                ticker,
                sentiment_score,
            )
            self.telemetry.gate_pass("llm", ticker, payload)
        elif self.budget_controller.can_afford_execution(model=llm_model):
            llm_outcome = self.failure_manager.run(
                gate="llm",
                ticker=ticker,
                operation=lambda: self.llm_agent.analyze_news(ticker, momentum_signal.indicators),
                retry=2,
            )
            if llm_outcome.ok:
                llm_result = llm_outcome.result
                sentiment_score = llm_result.get("score", 0.0)
                self.budget_controller.log_spend(llm_result.get("cost", 0.0))
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
                    self._track_gate_event(
                        gate="llm",
                        ticker=ticker,
                        status="reject",
                        metrics={"confidence": sentiment_score},
                    )
                    return
                logger.info("Gate 3 (%s): PASSED (sentiment=%.2f).", ticker, sentiment_score)
                self.telemetry.gate_pass("llm", ticker, llm_result)
                self._track_gate_event(
                    gate="llm",
                    ticker=ticker,
                    status="pass",
                    metrics={"confidence": sentiment_score},
                )
                self._persist_bias_from_llm(ticker, llm_result)
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
                self._track_gate_event(
                    gate="llm",
                    ticker=ticker,
                    status="error",
                    metrics={"confidence": sentiment_score},
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
            self._track_gate_event(
                gate="llm",
                ticker=ticker,
                status="skipped",
                metrics={"confidence": sentiment_score},
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
                market_regime=regime_snapshot.get("label"),
            ),
            event_type="gate.risk",
        )
        if not risk_outcome.ok:
            logger.error(
                "Gate 4 (%s): Risk sizing failed: %s",
                ticker,
                risk_outcome.failure.error,
            )
            self._track_gate_event(
                gate="risk",
                ticker=ticker,
                status="error",
                metrics={"confidence": rl_decision.get("confidence", 0.0)},
            )
            return

        order_size = risk_outcome.result

        if order_size <= 0:
            logger.info("Gate 4 (%s): REJECTED (position size calculated as 0).", ticker)
            self.telemetry.gate_reject(
                "risk",
                ticker,
                {
                    "order_size": order_size,
                    "account_equity": self.executor.account_equity,
                },
            )
            self._track_gate_event(
                gate="risk",
                ticker=ticker,
                status="reject",
                metrics={"confidence": rl_decision.get("confidence", 0.0)},
            )
            return

        logger.info("Executing BUY %s for $%.2f", ticker, order_size)

        # CRITICAL: All trades go through the mandatory gateway
        trade_request = TradeRequest(
            symbol=ticker, side="buy", notional=order_size, source="orchestrator"
        )
        gateway_decision = self.trade_gateway.evaluate(trade_request)

        if not gateway_decision.approved:
            logger.warning(
                "Gate GATEWAY (%s): REJECTED by Trade Gateway - %s",
                ticker,
                [r.value for r in gateway_decision.rejection_reasons],
            )
            self.telemetry.gate_reject(
                "gateway",
                ticker,
                {
                    "rejection_reasons": [r.value for r in gateway_decision.rejection_reasons],
                    "risk_score": gateway_decision.risk_score,
                },
            )
            return

        order_outcome = self.failure_manager.run(
            gate="execution.order",
            ticker=ticker,
            operation=lambda: self.trade_gateway.execute(gateway_decision),
            event_type="execution.order",
        )
        if not order_outcome.ok:
            logger.error("Execution failed for %s: %s", ticker, order_outcome.failure.error)
            return
        order = order_outcome.result
        self.telemetry.gate_pass(
            "risk",
            ticker,
            {"order_size": order_size, "account_equity": self.executor.account_equity},
        )
        self._track_gate_event(
            gate="risk",
            ticker=ticker,
            status="pass",
            metrics={"confidence": rl_decision.get("confidence", 0.0)},
        )
        cost_estimate = self._estimate_execution_costs(order_size)
        self.telemetry.order_event(
            ticker,
            {
                "order": order,
                "rl": rl_decision,
                "cost_estimate": cost_estimate,
                "session_type": (self.session_profile or {}).get("session_type"),
            },
        )

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

    def _persist_bias_from_llm(self, ticker: str, llm_payload: dict) -> None:
        try:
            score = float(llm_payload.get("score", 0.0))
            now = datetime.now(timezone.utc)
            snapshot = BiasSnapshot(
                symbol=ticker,
                score=score,
                direction=self._score_to_direction(score),
                conviction=min(1.0, max(0.0, abs(score))),
                reason=llm_payload.get("reason", "llm sentiment"),
                created_at=now,
                expires_at=now + timedelta(minutes=self.bias_snapshot_ttl_minutes),
                model=llm_payload.get("model"),
                sources=llm_payload.get("sources", []),
                metadata={"source": "orchestrator.llm", "raw": llm_payload},
            )
            self.bias_store.persist(snapshot)
        except Exception as exc:  # pragma: no cover - analytics only
            logger.debug("Failed to persist bias snapshot for %s: %s", ticker, exc)

    @staticmethod
    def _score_to_direction(score: float) -> str:
        if score >= 0.2:
            return "bullish"
        if score <= -0.2:
            return "bearish"
        return "neutral"

    def run_delta_rebalancing(self) -> dict:
        """
        Gate 5: Delta-Neutral Rebalancing (Post-Execution)

        McMillan Rule: If |net delta| > 60, buy/sell SPY shares to bring it under 25.

        This should be called after all ticker processing to ensure the overall
        portfolio delta exposure remains within acceptable bounds.

        CAPITAL GUARD: Delta hedging requires $50k+ to be efficient.
        For smaller accounts, frequent adjustments destroy alpha through fees.

        Returns:
            Dict with rebalancing results
        """
        logger.info("--- Gate 5: Delta-Neutral Rebalancing Check ---")

        # CRITICAL: Capital efficiency guard - disable delta hedging for small accounts
        account_equity = self.executor.account_equity
        delta_hedge_check = self.capital_calculator.should_enable_delta_hedging(account_equity)

        if not delta_hedge_check["enabled"]:
            logger.warning("Gate 5: Delta hedging DISABLED - %s", delta_hedge_check["reason"])
            self.telemetry.record(
                event_type="gate.delta_rebalance",
                ticker="PORTFOLIO",
                status="disabled",
                payload={
                    "reason": delta_hedge_check["reason"],
                    "account_equity": account_equity,
                    "capital_gap": delta_hedge_check.get("capital_gap", 0),
                    "days_to_enable": delta_hedge_check.get("days_to_enable", 0),
                },
            )
            return {
                "action": "disabled",
                "reason": delta_hedge_check["reason"],
                "recommendation": delta_hedge_check.get(
                    "recommendation", "Use defined-risk strategies"
                ),
            }

        try:
            # Calculate current delta exposure
            delta_analysis = self.options_risk_monitor.calculate_net_delta()

            self.telemetry.record(
                event_type="gate.delta_rebalance",
                ticker="PORTFOLIO",
                status="checking",
                payload={
                    "net_delta": delta_analysis["net_delta"],
                    "max_allowed": delta_analysis["max_allowed"],
                    "rebalance_needed": delta_analysis["rebalance_needed"],
                },
            )

            if not delta_analysis["rebalance_needed"]:
                logger.info(
                    "Gate 5: Delta exposure acceptable (net delta: %.1f, max: %.1f)",
                    delta_analysis["net_delta"],
                    delta_analysis["max_allowed"],
                )
                return {"action": "none", "delta_analysis": delta_analysis}

            # Calculate hedge trade
            hedge = self.options_risk_monitor.calculate_delta_hedge(delta_analysis["net_delta"])

            if hedge["action"] == "NONE":
                return {"action": "none", "delta_analysis": delta_analysis}

            logger.warning(
                "Gate 5: Delta rebalancing triggered - %s %d %s",
                hedge["action"],
                hedge["quantity"],
                hedge["symbol"],
            )

            # Execute the hedge through the gateway
            try:
                hedge_request = TradeRequest(
                    symbol=hedge["symbol"],
                    side=hedge["action"].lower(),
                    quantity=hedge["quantity"],
                    source="delta_hedge",
                )
                hedge_decision = self.trade_gateway.evaluate(hedge_request)

                if not hedge_decision.approved:
                    logger.warning(
                        "Delta hedge rejected by gateway: %s",
                        [r.value for r in hedge_decision.rejection_reasons],
                    )
                    return {
                        "action": "rejected",
                        "reasons": [r.value for r in hedge_decision.rejection_reasons],
                    }

                order = self.trade_gateway.execute(hedge_decision)

                self.telemetry.record(
                    event_type="gate.delta_rebalance",
                    ticker=hedge["symbol"],
                    status="executed",
                    payload={
                        "hedge": hedge,
                        "order": order,
                        "pre_rebalance_delta": delta_analysis["net_delta"],
                        "target_delta": hedge.get("target_delta"),
                    },
                )

                logger.info(
                    "✅ Delta hedge executed: %s %d %s (Order ID: %s)",
                    hedge["action"],
                    hedge["quantity"],
                    hedge["symbol"],
                    order.get("id", "N/A"),
                )

                return {
                    "action": "hedged",
                    "hedge": hedge,
                    "order": order,
                    "delta_analysis": delta_analysis,
                }

            except Exception as e:
                logger.error("Failed to execute delta hedge: %s", e)
                self.telemetry.record(
                    event_type="gate.delta_rebalance",
                    ticker=hedge["symbol"],
                    status="failed",
                    payload={"error": str(e), "hedge": hedge},
                )
                return {"action": "failed", "error": str(e), "hedge": hedge}

        except Exception as e:
            logger.error("Delta rebalancing check failed: %s", e)
            return {"action": "error", "error": str(e)}

    def run_options_risk_check(self, option_prices: dict = None) -> dict:
        """
        Run options position risk check (stop-losses and delta management).

        McMillan Rules Applied:
        - Credit spreads/iron condors: Exit at 2.2x credit received
        - Long options: Exit at 50% loss
        - Delta: Rebalance if |net delta| > 60

        Args:
            option_prices: Dict mapping option symbols to current prices
                          If None, will attempt to fetch from executor

        Returns:
            Risk check results with any actions taken
        """
        logger.info("--- Running Options Risk Check ---")

        if option_prices is None:
            option_prices = {}

        try:
            results = self.options_risk_monitor.run_risk_check(
                current_prices=option_prices, executor=self.executor
            )

            self.telemetry.record(
                event_type="options.risk_check",
                ticker="PORTFOLIO",
                status="completed",
                payload={
                    "positions_checked": results["positions_checked"],
                    "stop_loss_exits": len(results["stop_loss_exits"]),
                    "rebalance_needed": results["delta_analysis"]["rebalance_needed"]
                    if results["delta_analysis"]
                    else False,
                },
            )

            return results

        except Exception as e:
            logger.error("Options risk check failed: %s", e)
            return {"error": str(e)}
