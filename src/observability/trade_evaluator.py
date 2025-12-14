"""
Trade Decision Evaluator for Deep Agent Evaluation.

Creates evaluation datasets to measure and improve trade decision quality.
Supports A/B testing of prompts, strategies, and model configurations.

Based on LangChain's evaluation framework for production agents.

Usage:
    from src.observability.trade_evaluator import TradeEvaluator

    evaluator = TradeEvaluator()

    # After each trade
    evaluator.record_decision(
        signal=signal,
        decision="BUY",
        reasoning="Momentum score 0.85, positive sentiment",
        outcome={"profit_pct": 2.5, "held_minutes": 45}
    )

    # Get evaluation metrics
    metrics = evaluator.get_metrics()
    print(f"Decision accuracy: {metrics['accuracy']:.1%}")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DecisionOutcome(Enum):
    """Outcome classification for trade decisions."""

    PROFITABLE = "profitable"  # Made money
    BREAKEVEN = "breakeven"  # -0.5% to +0.5%
    LOSS = "loss"  # Lost money
    AVOIDED_LOSS = "avoided_loss"  # Correctly didn't trade
    MISSED_GAIN = "missed_gain"  # Should have traded
    PENDING = "pending"  # Not yet resolved


class DecisionQuality(Enum):
    """Quality classification based on reasoning."""

    EXCELLENT = "excellent"  # Right decision, right reasoning
    GOOD = "good"  # Right decision, okay reasoning
    LUCKY = "lucky"  # Right outcome, wrong reasoning
    UNLUCKY = "unlucky"  # Wrong outcome, right reasoning
    POOR = "poor"  # Wrong decision, wrong reasoning


@dataclass
class TradeDecisionRecord:
    """Record of a single trade decision for evaluation."""

    record_id: str
    timestamp: datetime
    symbol: str

    # Decision details
    decision: str  # BUY, SELL, HOLD
    confidence: float
    reasoning: str

    # Context at decision time
    price_at_decision: float
    momentum_score: float
    sentiment_score: float
    regime: str

    # Strategy/model used
    strategy_version: str = "v1"
    model_used: str = "default"
    prompt_version: str = "v1"

    # Outcome (filled in later)
    outcome: DecisionOutcome = DecisionOutcome.PENDING
    profit_pct: Optional[float] = None
    price_at_exit: Optional[float] = None
    exit_timestamp: Optional[datetime] = None

    # Evaluation
    quality: Optional[DecisionQuality] = None
    evaluator_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "decision": self.decision,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "price_at_decision": self.price_at_decision,
            "momentum_score": self.momentum_score,
            "sentiment_score": self.sentiment_score,
            "regime": self.regime,
            "strategy_version": self.strategy_version,
            "model_used": self.model_used,
            "prompt_version": self.prompt_version,
            "outcome": self.outcome.value,
            "profit_pct": self.profit_pct,
            "price_at_exit": self.price_at_exit,
            "exit_timestamp": self.exit_timestamp.isoformat() if self.exit_timestamp else None,
            "quality": self.quality.value if self.quality else None,
            "evaluator_notes": self.evaluator_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TradeDecisionRecord:
        return cls(
            record_id=data["record_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            symbol=data["symbol"],
            decision=data["decision"],
            confidence=data["confidence"],
            reasoning=data["reasoning"],
            price_at_decision=data["price_at_decision"],
            momentum_score=data["momentum_score"],
            sentiment_score=data["sentiment_score"],
            regime=data["regime"],
            strategy_version=data.get("strategy_version", "v1"),
            model_used=data.get("model_used", "default"),
            prompt_version=data.get("prompt_version", "v1"),
            outcome=DecisionOutcome(data.get("outcome", "pending")),
            profit_pct=data.get("profit_pct"),
            price_at_exit=data.get("price_at_exit"),
            exit_timestamp=datetime.fromisoformat(data["exit_timestamp"])
            if data.get("exit_timestamp")
            else None,
            quality=DecisionQuality(data["quality"]) if data.get("quality") else None,
            evaluator_notes=data.get("evaluator_notes", ""),
        )


@dataclass
class EvaluationMetrics:
    """Aggregated evaluation metrics."""

    total_decisions: int = 0
    resolved_decisions: int = 0

    # Outcome counts
    profitable_count: int = 0
    breakeven_count: int = 0
    loss_count: int = 0
    avoided_loss_count: int = 0
    missed_gain_count: int = 0

    # Quality counts
    excellent_count: int = 0
    good_count: int = 0
    lucky_count: int = 0
    unlucky_count: int = 0
    poor_count: int = 0

    # Calculated metrics
    win_rate: float = 0.0
    avg_profit_pct: float = 0.0
    avg_confidence: float = 0.0
    calibration_error: float = 0.0  # Diff between confidence and actual accuracy

    # By strategy/model
    by_strategy: dict[str, dict[str, float]] = field(default_factory=dict)
    by_model: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_decisions": self.total_decisions,
            "resolved_decisions": self.resolved_decisions,
            "outcomes": {
                "profitable": self.profitable_count,
                "breakeven": self.breakeven_count,
                "loss": self.loss_count,
                "avoided_loss": self.avoided_loss_count,
                "missed_gain": self.missed_gain_count,
            },
            "quality": {
                "excellent": self.excellent_count,
                "good": self.good_count,
                "lucky": self.lucky_count,
                "unlucky": self.unlucky_count,
                "poor": self.poor_count,
            },
            "metrics": {
                "win_rate": self.win_rate,
                "avg_profit_pct": self.avg_profit_pct,
                "avg_confidence": self.avg_confidence,
                "calibration_error": self.calibration_error,
            },
            "by_strategy": self.by_strategy,
            "by_model": self.by_model,
        }


class TradeEvaluator:
    """
    Evaluates trade decisions for continuous improvement.

    Key features:
    - Records every decision with full context
    - Links decisions to outcomes when trades close
    - Calculates win rate, calibration, and quality metrics
    - Supports A/B testing by strategy/model/prompt version
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("data/evaluations")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.records_file = self.storage_path / "trade_decisions.jsonl"
        self.pending_file = self.storage_path / "pending_decisions.json"

        # Load pending decisions (awaiting outcome)
        self._pending: dict[str, TradeDecisionRecord] = self._load_pending()

        logger.info(f"TradeEvaluator initialized with {len(self._pending)} pending decisions")

    def _load_pending(self) -> dict[str, TradeDecisionRecord]:
        """Load pending decisions from file."""
        if not self.pending_file.exists():
            return {}

        try:
            with open(self.pending_file) as f:
                data = json.load(f)
                return {k: TradeDecisionRecord.from_dict(v) for k, v in data.items()}
        except Exception as e:
            logger.warning(f"Failed to load pending decisions: {e}")
            return {}

    def _save_pending(self):
        """Save pending decisions to file."""
        with open(self.pending_file, "w") as f:
            json.dump({k: v.to_dict() for k, v in self._pending.items()}, f, indent=2)

    def record_decision(
        self,
        symbol: str,
        decision: str,
        confidence: float,
        reasoning: str,
        price: float,
        momentum_score: float = 0.0,
        sentiment_score: float = 0.0,
        regime: str = "unknown",
        strategy_version: str = "v1",
        model_used: str = "default",
        prompt_version: str = "v1",
    ) -> str:
        """
        Record a trade decision for later evaluation.

        Returns the record_id for linking to outcome.
        """
        import uuid

        record = TradeDecisionRecord(
            record_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc),
            symbol=symbol,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            price_at_decision=price,
            momentum_score=momentum_score,
            sentiment_score=sentiment_score,
            regime=regime,
            strategy_version=strategy_version,
            model_used=model_used,
            prompt_version=prompt_version,
        )

        # Store as pending
        self._pending[record.record_id] = record
        self._save_pending()

        logger.info(
            f"Recorded decision {record.record_id}: {decision} {symbol} "
            f"@ ${price:.2f} (confidence: {confidence:.1%})"
        )

        return record.record_id

    def record_outcome(
        self,
        record_id: str,
        exit_price: float,
        profit_pct: Optional[float] = None,
        notes: str = "",
    ) -> Optional[TradeDecisionRecord]:
        """
        Record the outcome of a previously recorded decision.

        Calculates profit if not provided and evaluates decision quality.
        """
        if record_id not in self._pending:
            logger.warning(f"Unknown record_id: {record_id}")
            return None

        record = self._pending.pop(record_id)
        record.price_at_exit = exit_price
        record.exit_timestamp = datetime.now(timezone.utc)

        # Calculate profit if not provided
        if profit_pct is None:
            if record.decision == "BUY":
                profit_pct = (
                    (exit_price - record.price_at_decision) / record.price_at_decision
                ) * 100
            elif record.decision == "SELL":
                profit_pct = (
                    (record.price_at_decision - exit_price) / record.price_at_decision
                ) * 100
            else:
                profit_pct = 0.0

        record.profit_pct = profit_pct

        # Classify outcome
        if profit_pct > 0.5:
            record.outcome = DecisionOutcome.PROFITABLE
        elif profit_pct < -0.5:
            record.outcome = DecisionOutcome.LOSS
        else:
            record.outcome = DecisionOutcome.BREAKEVEN

        # Evaluate quality (simplified heuristic)
        correct_direction = (
            (record.decision == "BUY" and profit_pct > 0)
            or (record.decision == "SELL" and profit_pct > 0)
            or (record.decision == "HOLD" and abs(profit_pct) < 1)
        )

        high_confidence = record.confidence > 0.7

        if correct_direction and high_confidence:
            record.quality = DecisionQuality.EXCELLENT
        elif correct_direction:
            record.quality = DecisionQuality.GOOD
        elif not correct_direction and high_confidence:
            record.quality = DecisionQuality.POOR
        elif correct_direction and not high_confidence:
            record.quality = DecisionQuality.LUCKY
        else:
            record.quality = DecisionQuality.UNLUCKY

        record.evaluator_notes = notes

        # Save to permanent records
        with open(self.records_file, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

        self._save_pending()

        logger.info(
            f"Outcome recorded for {record_id}: {record.outcome.value} "
            f"({profit_pct:+.2f}%), quality: {record.quality.value}"
        )

        return record

    def record_non_trade(
        self,
        symbol: str,
        decision: str,  # HOLD or SKIP
        confidence: float,
        reasoning: str,
        price: float,
        price_after: float,
        hours_later: int = 24,
    ):
        """
        Record outcome for a decision NOT to trade.

        Evaluates if HOLD/SKIP was correct by checking price movement.
        """
        potential_profit = ((price_after - price) / price) * 100

        # Classify
        if abs(potential_profit) < 1:
            outcome = (
                DecisionOutcome.AVOIDED_LOSS if potential_profit < 0 else DecisionOutcome.BREAKEVEN
            )
        elif potential_profit > 2:
            outcome = DecisionOutcome.MISSED_GAIN
        else:
            outcome = DecisionOutcome.AVOIDED_LOSS

        import uuid

        record = TradeDecisionRecord(
            record_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc) - timedelta(hours=hours_later),
            symbol=symbol,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            price_at_decision=price,
            momentum_score=0.0,
            sentiment_score=0.0,
            regime="unknown",
            outcome=outcome,
            profit_pct=0.0,  # Didn't trade
            price_at_exit=price_after,
            exit_timestamp=datetime.now(timezone.utc),
        )

        # Evaluate quality
        if outcome == DecisionOutcome.AVOIDED_LOSS:
            record.quality = DecisionQuality.EXCELLENT
        elif outcome == DecisionOutcome.MISSED_GAIN and confidence < 0.5:
            record.quality = DecisionQuality.UNLUCKY
        elif outcome == DecisionOutcome.MISSED_GAIN:
            record.quality = DecisionQuality.POOR
        else:
            record.quality = DecisionQuality.GOOD

        with open(self.records_file, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

        logger.info(f"Non-trade recorded: {decision} {symbol}, outcome: {outcome.value}")

    def get_metrics(self, days: int = 30) -> EvaluationMetrics:
        """Calculate evaluation metrics for the past N days."""
        metrics = EvaluationMetrics()

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        records: list[TradeDecisionRecord] = []

        if self.records_file.exists():
            with open(self.records_file) as f:
                for line in f:
                    record = TradeDecisionRecord.from_dict(json.loads(line))
                    if record.timestamp >= cutoff:
                        records.append(record)

        if not records:
            return metrics

        metrics.total_decisions = len(records)

        # Count outcomes
        profits = []
        confidences = []

        for record in records:
            confidences.append(record.confidence)

            if record.outcome == DecisionOutcome.PENDING:
                continue

            metrics.resolved_decisions += 1

            if record.outcome == DecisionOutcome.PROFITABLE:
                metrics.profitable_count += 1
                if record.profit_pct:
                    profits.append(record.profit_pct)
            elif record.outcome == DecisionOutcome.BREAKEVEN:
                metrics.breakeven_count += 1
            elif record.outcome == DecisionOutcome.LOSS:
                metrics.loss_count += 1
                if record.profit_pct:
                    profits.append(record.profit_pct)
            elif record.outcome == DecisionOutcome.AVOIDED_LOSS:
                metrics.avoided_loss_count += 1
            elif record.outcome == DecisionOutcome.MISSED_GAIN:
                metrics.missed_gain_count += 1

            # Count quality
            if record.quality == DecisionQuality.EXCELLENT:
                metrics.excellent_count += 1
            elif record.quality == DecisionQuality.GOOD:
                metrics.good_count += 1
            elif record.quality == DecisionQuality.LUCKY:
                metrics.lucky_count += 1
            elif record.quality == DecisionQuality.UNLUCKY:
                metrics.unlucky_count += 1
            elif record.quality == DecisionQuality.POOR:
                metrics.poor_count += 1

            # Track by strategy
            strategy = record.strategy_version
            if strategy not in metrics.by_strategy:
                metrics.by_strategy[strategy] = {"count": 0, "wins": 0, "total_profit": 0.0}
            metrics.by_strategy[strategy]["count"] += 1
            if record.outcome == DecisionOutcome.PROFITABLE:
                metrics.by_strategy[strategy]["wins"] += 1
            if record.profit_pct:
                metrics.by_strategy[strategy]["total_profit"] += record.profit_pct

            # Track by model
            model = record.model_used
            if model not in metrics.by_model:
                metrics.by_model[model] = {"count": 0, "wins": 0, "total_profit": 0.0}
            metrics.by_model[model]["count"] += 1
            if record.outcome == DecisionOutcome.PROFITABLE:
                metrics.by_model[model]["wins"] += 1
            if record.profit_pct:
                metrics.by_model[model]["total_profit"] += record.profit_pct

        # Calculate aggregate metrics
        if metrics.resolved_decisions > 0:
            wins = metrics.profitable_count + metrics.avoided_loss_count
            metrics.win_rate = wins / metrics.resolved_decisions

        if profits:
            metrics.avg_profit_pct = sum(profits) / len(profits)

        if confidences:
            metrics.avg_confidence = sum(confidences) / len(confidences)
            # Calibration error: |avg confidence - actual win rate|
            metrics.calibration_error = abs(metrics.avg_confidence - metrics.win_rate)

        return metrics

    def get_worst_decisions(self, limit: int = 10) -> list[TradeDecisionRecord]:
        """Get the worst decisions for learning."""
        records = []

        if self.records_file.exists():
            with open(self.records_file) as f:
                for line in f:
                    record = TradeDecisionRecord.from_dict(json.loads(line))
                    if record.quality in [DecisionQuality.POOR, DecisionQuality.LUCKY]:
                        records.append(record)

        # Sort by profit (worst first)
        records.sort(key=lambda r: r.profit_pct or 0)

        return records[:limit]

    def export_for_finetuning(self, output_path: Path) -> int:
        """
        Export excellent decisions as training data for finetuning.

        Returns number of examples exported.
        """
        examples = []

        if self.records_file.exists():
            with open(self.records_file) as f:
                for line in f:
                    record = TradeDecisionRecord.from_dict(json.loads(line))
                    if record.quality == DecisionQuality.EXCELLENT:
                        # Format as conversation for finetuning
                        example = {
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are a trading analyst. Analyze the market data and make a trading decision.",
                                },
                                {
                                    "role": "user",
                                    "content": f"Symbol: {record.symbol}\n"
                                    f"Price: ${record.price_at_decision:.2f}\n"
                                    f"Momentum Score: {record.momentum_score:.2f}\n"
                                    f"Sentiment Score: {record.sentiment_score:.2f}\n"
                                    f"Regime: {record.regime}\n\n"
                                    f"What is your trading decision?",
                                },
                                {
                                    "role": "assistant",
                                    "content": f"Decision: {record.decision}\n"
                                    f"Confidence: {record.confidence:.1%}\n"
                                    f"Reasoning: {record.reasoning}",
                                },
                            ]
                        }
                        examples.append(example)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            for example in examples:
                f.write(json.dumps(example) + "\n")

        logger.info(f"Exported {len(examples)} examples for finetuning to {output_path}")
        return len(examples)
