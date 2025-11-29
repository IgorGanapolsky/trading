"""Runtime agent implementations for the trading orchestrator."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

import pandas as pd

from agent_framework import AgentResult, RunContext, TradingAgent

logger = logging.getLogger(__name__)


class StrategyAgent(TradingAgent):
    """Score symbols fetched by DataAgent and emit a trade intent."""

    def __init__(
        self,
        lookback_days: int = 10,
        min_history: int = 15,
        default_allocation: float = 10.0,
    ) -> None:
        super().__init__("strategy-agent")
        self.lookback_days = lookback_days
        self.min_history = min_history
        self.default_allocation = default_allocation

    def execute(self, context: RunContext) -> AgentResult:
        market_data = context.state_cache.get("market_data", {})
        frames: Dict[str, pd.DataFrame] = market_data.get("frames", {})
        if not frames:
            message = "No market data found in context; run DataAgent first."
            logger.warning(message)
            return AgentResult(
                name=self.agent_name,
                succeeded=False,
                payload={"message": message},
            )

        scored: List[Dict[str, Any]] = []
        for symbol, frame in frames.items():
            try:
                signal = self._score_symbol(symbol, frame)
            except ValueError as exc:
                logger.debug("Skipping %s: %s", symbol, exc)
                continue
            scored.append(signal)

        if not scored:
            message = "All symbols failed signal validation; no intent emitted."
            logger.warning(message)
            return AgentResult(
                name=self.agent_name,
                succeeded=False,
                payload={"message": message},
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        top_signal = scored[0]
        allocation = float(context.config.get("daily_allocation", self.default_allocation))

        intent = {
            "symbol": top_signal["symbol"],
            "score": round(top_signal["score"], 4),
            "notional": round(allocation, 2),
            "confidence": round(top_signal["confidence"], 3),
            "metrics": top_signal,
        }

        context.state_cache["strategy"] = {
            "intent": intent,
            "candidates": scored,
        }

        logger.info(
            "Strategy selected %s (score=%.2f, confidence=%.2f) for $%.2f",
            intent["symbol"],
            intent["score"],
            intent["confidence"],
            intent["notional"],
        )

        return AgentResult(name=self.agent_name, succeeded=True, payload=intent)

    def _score_symbol(self, symbol: str, frame: pd.DataFrame) -> Dict[str, Any]:
        if not isinstance(frame, pd.DataFrame):
            raise ValueError("market frame is not a DataFrame")
        if len(frame) < self.min_history:
            raise ValueError("insufficient history for analysis")
        if "Close" not in frame.columns:
            raise ValueError("missing Close column")

        closes = frame["Close"].astype(float)
        recent = closes.tail(self.lookback_days)
        if len(recent) < self.lookback_days:
            raise ValueError("not enough rows for lookback window")

        momentum = (recent.iloc[-1] / recent.iloc[0]) - 1
        slope = recent.pct_change().mean()
        volatility = closes.pct_change().tail(self.lookback_days).std()
        short_ma = recent.mean()
        long_ma = closes.tail(self.lookback_days * 2).mean()

        score = momentum * 100 + slope * 50 - (volatility or 0) * 10
        confidence = max(0.0, min(1.0, (momentum + 0.02) * 10))

        return {
            "symbol": symbol,
            "momentum": round(float(momentum), 6),
            "slope": round(float(slope if pd.notna(slope) else 0.0), 6),
            "volatility": round(float(volatility if pd.notna(volatility) else 0.0), 6),
            "short_ma": round(float(short_ma), 4),
            "long_ma": round(float(long_ma), 4),
            "score": round(float(score), 6),
            "confidence": round(float(confidence), 6),
        }


class RiskAgent(TradingAgent):
    """Apply basic sizing and exposure checks to the proposed trade."""

    def __init__(
        self,
        max_position_pct: float = 0.05,
        max_trade_amount: float = 50.0,
        min_trade_amount: float = 5.0,
        default_account_equity: float = 5000.0,
    ) -> None:
        super().__init__("risk-agent")
        self.max_position_pct = max_position_pct
        self.max_trade_amount = max_trade_amount
        self.min_trade_amount = min_trade_amount
        self.default_account_equity = default_account_equity

    def execute(self, context: RunContext) -> AgentResult:
        strategy_block = context.state_cache.get("strategy", {})
        intent = strategy_block.get("intent")
        if not intent:
            message = "No trade intent present; skipping risk checks."
            logger.warning(message)
            return AgentResult(
                name=self.agent_name,
                succeeded=False,
                payload={"message": message},
            )

        state = context.state_cache.get("state", {})
        account_equity = (
            state.get("portfolio", {}).get("equity")
            or state.get("account", {}).get("equity")
            or context.config.get("account_equity")
            or self.default_account_equity
        )

        max_allowed_by_pct = float(account_equity) * self.max_position_pct
        planned_notional = float(intent.get("notional", 0.0))
        recommended = min(planned_notional, max_allowed_by_pct, self.max_trade_amount)

        warnings: List[str] = []
        approved = recommended >= self.min_trade_amount
        if not approved:
            warnings.append(
                f"Recommended size ${recommended:.2f} below minimum ${self.min_trade_amount:.2f}"
            )

        coverage_ratio = (recommended / account_equity) if account_equity else 0.0
        plan = {
            "approved": approved,
            "symbol": intent["symbol"],
            "requested_notional": planned_notional,
            "position_size": round(recommended, 2),
            "account_equity": round(float(account_equity), 2),
            "max_position_pct": self.max_position_pct,
            "exposure_pct": round(coverage_ratio * 100, 4),
            "warnings": warnings,
        }

        context.state_cache["risk"] = {"plan": plan}

        logger.info(
            "Risk %s trade for %s @ $%.2f (exposure %.2f%%)",
            "approved" if approved else "rejected",
            plan["symbol"],
            plan["position_size"],
            plan["exposure_pct"],
        )

        return AgentResult(name=self.agent_name, succeeded=True, payload=plan)


class ExecutionAgent(TradingAgent):
    """Simulate or execute the order produced by the risk module."""

    def __init__(
        self,
        simulate_only: bool = True,
        log_path: Path | None = None,
    ) -> None:
        super().__init__("execution-agent")
        self.simulate_only = simulate_only
        self.log_path = log_path or Path("data/orchestrator_execution_log.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def execute(self, context: RunContext) -> AgentResult:
        risk_block = context.state_cache.get("risk", {})
        plan = risk_block.get("plan")
        if not plan or not plan.get("approved"):
            message = "No approved risk plan available; execution skipped."
            logger.warning(message)
            return AgentResult(
                name=self.agent_name,
                succeeded=False,
                payload={"message": message},
            )

        order = self._simulate_order(plan)
        context.state_cache.setdefault("execution", {})["order"] = order
        self._append_log(order)

        logger.info(
            "Execution recorded order %s for %s ($%.2f)",
            order["order_id"],
            order["symbol"],
            order["filled_notional"],
        )

        return AgentResult(name=self.agent_name, succeeded=True, payload=order)

    def _simulate_order(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        order = {
            "order_id": f"SIM-{uuid4().hex[:12].upper()}",
            "symbol": plan["symbol"],
            "side": "buy",
            "filled_notional": round(float(plan["position_size"]), 2),
            "status": "filled",
            "timestamp": datetime.utcnow().isoformat(),
            "mode": "simulation" if self.simulate_only else "live",
        }
        return order

    def _append_log(self, order: Dict[str, Any]) -> None:
        try:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(order) + "\n")
        except Exception:  # pragma: no cover - log only
            logger.exception("Failed to append execution log")


class AuditAgent(TradingAgent):
    """Persist a summary of the orchestrator run for observability."""

    def __init__(self, history_limit: int = 20, log_path: Path | None = None) -> None:
        super().__init__("audit-agent")
        self.history_limit = history_limit
        self.log_path = log_path or Path("data/orchestrator_audit.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def execute(self, context: RunContext) -> AgentResult:
        state = context.state_cache.setdefault("state", {})
        summary = self._build_summary(context)

        orchestrator_state = state.setdefault("orchestrator", {})
        history: List[Dict[str, Any]] = orchestrator_state.setdefault("history", [])
        history.append(summary)
        if len(history) > self.history_limit:
            del history[0 : len(history) - self.history_limit]
        orchestrator_state["last_run"] = summary

        context.state_cache["state"] = state
        self._append_log(summary)

        logger.info("Audit recorded orchestrator summary for %s", summary.get("symbol"))
        return AgentResult(name=self.agent_name, succeeded=True, payload=summary)

    def _build_summary(self, context: RunContext) -> Dict[str, Any]:
        strategy = context.state_cache.get("strategy", {})
        risk = context.state_cache.get("risk", {})
        execution = context.state_cache.get("execution", {})

        intent = strategy.get("intent") or {}
        plan = risk.get("plan") or {}
        order = execution.get("order") or {}

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "mode": context.mode.value,
            "symbol": intent.get("symbol"),
            "strategy_score": intent.get("score"),
            "requested_notional": intent.get("notional"),
            "approved_notional": plan.get("position_size"),
            "execution_status": order.get("status", "skipped"),
            "order_id": order.get("order_id"),
            "warnings": plan.get("warnings", []),
        }

    def _append_log(self, summary: Dict[str, Any]) -> None:
        try:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(summary) + "\n")
        except Exception:  # pragma: no cover - log only
            logger.exception("Failed to append audit log")

