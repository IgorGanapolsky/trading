"""
Anomaly-to-Training Bridge.

Connects the verification layer to the ML training layer:
1. Anomalies detected → Synthetic negative training examples
2. Recurring patterns → Priority retraining triggers
3. Feature importance tracking → Reward function weighting

This closes the loop: Detection → Learning → Prevention

Usage:
    from src.ml.anomaly_to_training_bridge import AnomalyToTrainingBridge

    bridge = AnomalyToTrainingBridge()

    # When anomaly detected
    bridge.record_anomaly_for_training(anomaly_dict)

    # Check if retraining needed
    if bridge.should_trigger_retraining():
        bridge.trigger_retraining()

Author: Trading System
Created: 2025-12-15
"""

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Paths
ANOMALY_TRAINING_DB = Path("data/ml/anomaly_training_queue.json")
RETRAINING_HISTORY = Path("data/ml/retraining_history.json")


@dataclass
class AnomalyTrainingExample:
    """Represents an anomaly converted to a training signal."""

    anomaly_id: str
    anomaly_type: str
    timestamp: str
    features: dict
    negative_reward: float  # Penalty for this type of behavior
    context: dict = field(default_factory=dict)
    used_in_training: bool = False

    def to_dict(self) -> dict:
        return {
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type,
            "timestamp": self.timestamp,
            "features": self.features,
            "negative_reward": self.negative_reward,
            "context": self.context,
            "used_in_training": self.used_in_training,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AnomalyTrainingExample":
        return cls(**data)


class AnomalyToTrainingBridge:
    """
    Bridge between anomaly detection and model training.

    Converts anomalies into training signals that help the RL agent
    avoid similar mistakes.

    Key Functions:
    1. Convert anomalies to negative reward examples
    2. Track anomaly patterns for priority retraining
    3. Adjust feature weights based on failure modes
    4. Trigger retraining when thresholds exceeded
    """

    # Reward penalties by severity
    SEVERITY_PENALTIES = {
        "CRITICAL": -1.0,
        "HIGH": -0.7,
        "MEDIUM": -0.4,
        "LOW": -0.2,
    }

    # Retraining thresholds
    RETRAINING_THRESHOLDS = {
        "anomaly_count": 10,  # Retrain after N anomalies
        "critical_count": 3,  # Retrain after N critical anomalies
        "time_since_last": timedelta(days=7),  # Max time between retrainings
        "loss_threshold": -200.0,  # Retrain if cumulative loss exceeds
    }

    def __init__(
        self,
        training_db_path: Optional[Path] = None,
        history_path: Optional[Path] = None,
    ):
        self.training_db_path = training_db_path or ANOMALY_TRAINING_DB
        self.history_path = history_path or RETRAINING_HISTORY

        # Ensure directories exist
        self.training_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing data
        self.training_queue: list[AnomalyTrainingExample] = []
        self.retraining_history: list[dict] = []
        self._load_data()

    def record_anomaly_for_training(
        self,
        anomaly: dict,
        additional_features: Optional[dict] = None,
    ) -> AnomalyTrainingExample:
        """
        Convert an anomaly to a training example.

        Args:
            anomaly: Anomaly dict from detector
            additional_features: Extra features to include

        Returns:
            Created training example
        """
        # Extract features from anomaly
        features = self._extract_features(anomaly)
        if additional_features:
            features.update(additional_features)

        # Determine penalty based on severity
        severity = self._map_severity(anomaly.get("level", "medium"))
        penalty = self.SEVERITY_PENALTIES.get(severity, -0.5)

        # Adjust penalty based on financial impact if available
        financial_impact = anomaly.get("details", {}).get("financial_impact")
        if financial_impact and financial_impact < 0:
            # Scale penalty with actual loss
            penalty = min(penalty, financial_impact / 100.0)  # Normalize

        example = AnomalyTrainingExample(
            anomaly_id=anomaly.get("anomaly_id", f"ANO-{datetime.now().timestamp()}"),
            anomaly_type=anomaly.get("type", "unknown"),
            timestamp=anomaly.get("detected_at", datetime.now().isoformat()),
            features=features,
            negative_reward=penalty,
            context={
                "symbol": anomaly.get("context", {}).get("symbol"),
                "severity": severity,
                "message": anomaly.get("message", "")[:200],
            },
        )

        self.training_queue.append(example)
        self._save_data()

        logger.info(
            f"Recorded anomaly for training: {example.anomaly_id} "
            f"(penalty: {penalty:.2f})"
        )

        return example

    def should_trigger_retraining(self) -> dict:
        """
        Check if retraining should be triggered.

        Returns:
            Dict with:
            - should_retrain: bool
            - reason: str
            - stats: dict
        """
        unused = [e for e in self.training_queue if not e.used_in_training]
        critical = [e for e in unused if e.context.get("severity") == "CRITICAL"]

        # Calculate cumulative loss from unused examples
        cumulative_loss = sum(e.negative_reward for e in unused)

        # Check time since last retraining
        last_retrain = self._get_last_retraining_time()
        time_since = datetime.now() - last_retrain if last_retrain else timedelta(days=999)

        stats = {
            "unused_anomalies": len(unused),
            "critical_anomalies": len(critical),
            "cumulative_loss": cumulative_loss,
            "days_since_retrain": time_since.days,
            "anomaly_types": dict(Counter(e.anomaly_type for e in unused)),
        }

        # Check thresholds
        reasons = []

        if len(unused) >= self.RETRAINING_THRESHOLDS["anomaly_count"]:
            reasons.append(f"anomaly_count ({len(unused)})")

        if len(critical) >= self.RETRAINING_THRESHOLDS["critical_count"]:
            reasons.append(f"critical_count ({len(critical)})")

        if time_since >= self.RETRAINING_THRESHOLDS["time_since_last"]:
            reasons.append(f"time_since_last ({time_since.days} days)")

        if cumulative_loss <= self.RETRAINING_THRESHOLDS["loss_threshold"]:
            reasons.append(f"loss_threshold ({cumulative_loss:.2f})")

        should_retrain = len(reasons) > 0

        return {
            "should_retrain": should_retrain,
            "reason": ", ".join(reasons) if reasons else "No trigger",
            "stats": stats,
        }

    def get_training_batch(
        self,
        max_examples: int = 100,
        include_used: bool = False,
    ) -> list[dict]:
        """
        Get a batch of training examples for the RL agent.

        Args:
            max_examples: Maximum examples to return
            include_used: Whether to include previously used examples

        Returns:
            List of training example dicts with features and rewards
        """
        if include_used:
            examples = self.training_queue
        else:
            examples = [e for e in self.training_queue if not e.used_in_training]

        # Sort by severity (critical first)
        examples.sort(key=lambda e: self.SEVERITY_PENALTIES.get(
            e.context.get("severity", "LOW"), -0.2
        ))

        batch = []
        for example in examples[:max_examples]:
            batch.append({
                "features": example.features,
                "reward": example.negative_reward,
                "anomaly_type": example.anomaly_type,
                "context": example.context,
            })

        return batch

    def mark_batch_used(self, anomaly_ids: list[str]) -> int:
        """
        Mark examples as used in training.

        Args:
            anomaly_ids: List of anomaly IDs that were used

        Returns:
            Number of examples marked
        """
        marked = 0
        for example in self.training_queue:
            if example.anomaly_id in anomaly_ids:
                example.used_in_training = True
                marked += 1

        self._save_data()
        return marked

    def trigger_retraining(self, dry_run: bool = False) -> dict:
        """
        Trigger model retraining with anomaly examples.

        Args:
            dry_run: If True, don't actually retrain

        Returns:
            Retraining result dict
        """
        check = self.should_trigger_retraining()

        if not check["should_retrain"] and not dry_run:
            logger.info("Retraining not needed")
            return {"triggered": False, "reason": "thresholds not met"}

        batch = self.get_training_batch()

        result = {
            "triggered": True,
            "timestamp": datetime.now().isoformat(),
            "reason": check["reason"],
            "examples_count": len(batch),
            "stats": check["stats"],
            "dry_run": dry_run,
        }

        if not dry_run:
            # Import and call retraining
            try:
                from scripts.rl_daily_retrain import retrain_rl_model

                # Add anomaly examples as negative samples
                retrain_result = retrain_rl_model(
                    additional_negative_examples=batch
                )
                result["retrain_result"] = retrain_result

                # Mark examples as used
                anomaly_ids = [e.anomaly_id for e in self.training_queue
                              if not e.used_in_training]
                self.mark_batch_used(anomaly_ids[:len(batch)])

            except ImportError:
                logger.warning("rl_daily_retrain not available, queueing examples")
                result["retrain_result"] = "queued"
            except Exception as e:
                logger.error(f"Retraining failed: {e}")
                result["retrain_result"] = f"error: {e}"

        # Record in history
        self.retraining_history.append(result)
        self._save_history()

        logger.info(f"Retraining {'simulated' if dry_run else 'triggered'}: {result}")
        return result

    def get_feature_importance_adjustments(self) -> dict:
        """
        Calculate feature importance adjustments based on anomaly patterns.

        Returns:
            Dict mapping feature names to weight adjustments
        """
        adjustments = {}

        # Count which features appear in anomalies
        feature_counts = Counter()
        for example in self.training_queue:
            for feature_name in example.features.keys():
                feature_counts[feature_name] += 1

        total = len(self.training_queue) or 1

        # Features that appear in many anomalies should be weighted higher
        for feature, count in feature_counts.items():
            frequency = count / total
            if frequency > 0.5:
                # Feature appears in >50% of anomalies - increase weight
                adjustments[feature] = 1.5
            elif frequency > 0.3:
                adjustments[feature] = 1.2
            else:
                adjustments[feature] = 1.0

        return adjustments

    # ========== Private Methods ==========

    def _extract_features(self, anomaly: dict) -> dict:
        """Extract ML features from anomaly."""
        details = anomaly.get("details", {})
        context = anomaly.get("context", {})

        features = {}

        # Numeric features
        numeric_keys = ["amount", "price", "pnl", "multiplier", "threshold",
                       "volatility", "deviation"]
        for key in numeric_keys:
            if key in details:
                features[f"anomaly_{key}"] = float(details[key])

        # Categorical features (one-hot encoded)
        if context.get("symbol"):
            features[f"symbol_{context['symbol']}"] = 1.0

        features["anomaly_type_" + anomaly.get("type", "unknown")] = 1.0

        # Time features
        try:
            dt = datetime.fromisoformat(anomaly.get("detected_at", ""))
            features["hour_of_day"] = dt.hour / 24.0
            features["day_of_week"] = dt.weekday() / 7.0
        except (ValueError, TypeError):
            pass

        return features

    def _map_severity(self, level: str) -> str:
        """Map anomaly level to severity."""
        level_map = {
            "block": "CRITICAL",
            "critical": "CRITICAL",
            "warning": "HIGH",
            "high": "HIGH",
            "medium": "MEDIUM",
            "info": "LOW",
            "low": "LOW",
        }
        return level_map.get(level.lower(), "MEDIUM")

    def _get_last_retraining_time(self) -> Optional[datetime]:
        """Get timestamp of last retraining."""
        if not self.retraining_history:
            return None

        for entry in reversed(self.retraining_history):
            if not entry.get("dry_run", False):
                try:
                    return datetime.fromisoformat(entry["timestamp"])
                except (KeyError, ValueError):
                    continue

        return None

    def _load_data(self) -> None:
        """Load training queue from disk."""
        if self.training_db_path.exists():
            try:
                with open(self.training_db_path) as f:
                    data = json.load(f)
                self.training_queue = [
                    AnomalyTrainingExample.from_dict(e) for e in data
                ]
                logger.info(f"Loaded {len(self.training_queue)} training examples")
            except Exception as e:
                logger.error(f"Failed to load training queue: {e}")

        if self.history_path.exists():
            try:
                with open(self.history_path) as f:
                    self.retraining_history = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load retraining history: {e}")

    def _save_data(self) -> None:
        """Save training queue to disk."""
        try:
            with open(self.training_db_path, "w") as f:
                json.dump([e.to_dict() for e in self.training_queue], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save training queue: {e}")

    def _save_history(self) -> None:
        """Save retraining history to disk."""
        try:
            with open(self.history_path, "w") as f:
                json.dump(self.retraining_history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save retraining history: {e}")


# =============================================================================
# INTEGRATION FUNCTIONS
# =============================================================================


def integrate_with_anomaly_loop():
    """
    Integrate the training bridge with anomaly detection.

    Call this at system startup to enable automatic learning.
    """
    from src.verification.anomaly_learning_feedback_loop import AnomalyLearningLoop

    bridge = AnomalyToTrainingBridge()
    original_process = AnomalyLearningLoop.process_anomaly

    def enhanced_process(self, anomaly: dict) -> dict:
        # Original processing
        result = original_process(self, anomaly)

        # Also record for training
        try:
            bridge.record_anomaly_for_training(anomaly)

            # Check if retraining should be triggered
            check = bridge.should_trigger_retraining()
            if check["should_retrain"]:
                result["retraining_triggered"] = True
                result["retraining_reason"] = check["reason"]
                # Trigger async retraining (non-blocking)
                # In production, this would be a background task
                logger.info(f"Retraining queued: {check['reason']}")
        except Exception as e:
            logger.warning(f"Failed to record anomaly for training: {e}")

        return result

    AnomalyLearningLoop.process_anomaly = enhanced_process
    logger.info("Integrated AnomalyToTrainingBridge with AnomalyLearningLoop")


if __name__ == "__main__":
    """Demo the anomaly-to-training bridge."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("ANOMALY-TO-TRAINING BRIDGE DEMO")
    print("=" * 80)

    bridge = AnomalyToTrainingBridge()

    # Demo: Record some anomalies
    print("\n1. Recording anomalies...")

    anomalies = [
        {
            "anomaly_id": "DEMO-001",
            "type": "order_amount",
            "level": "warning",
            "message": "Order amount exceeds threshold",
            "details": {"amount": 150, "threshold": 100},
            "detected_at": datetime.now().isoformat(),
            "context": {"symbol": "SPY"},
        },
        {
            "anomaly_id": "DEMO-002",
            "type": "trade_loss",
            "level": "high",
            "message": "Significant trade loss",
            "details": {"pnl": -75.50, "financial_impact": -75.50},
            "detected_at": datetime.now().isoformat(),
            "context": {"symbol": "NVDA"},
        },
    ]

    for anomaly in anomalies:
        example = bridge.record_anomaly_for_training(anomaly)
        print(f"   Recorded: {example.anomaly_id} (penalty: {example.negative_reward:.2f})")

    # Check retraining status
    print("\n2. Checking retraining status...")
    check = bridge.should_trigger_retraining()
    print(f"   Should retrain: {check['should_retrain']}")
    print(f"   Reason: {check['reason']}")
    print(f"   Stats: {check['stats']}")

    # Get training batch
    print("\n3. Getting training batch...")
    batch = bridge.get_training_batch(max_examples=5)
    print(f"   Batch size: {len(batch)}")
    for item in batch:
        print(f"   - {item['anomaly_type']}: reward={item['reward']:.2f}")

    # Get feature importance adjustments
    print("\n4. Feature importance adjustments...")
    adjustments = bridge.get_feature_importance_adjustments()
    for feature, weight in list(adjustments.items())[:5]:
        print(f"   - {feature}: {weight:.2f}x")

    print("\n" + "=" * 80)
    print("Bridge ready for integration with training pipeline")
    print("=" * 80)
