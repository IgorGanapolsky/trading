"""
Signal Decay Monitor

Tracks RL model performance vs baseline over time to detect signal decay.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class SignalDecayMonitor:
    """Monitor RL model performance for signal decay detection."""

    def __init__(self, data_dir: Path = Path("data")):
        self.data_dir = data_dir
        self.monitoring_dir = data_dir / "signal_decay"
        self.monitoring_dir.mkdir(parents=True, exist_ok=True)

    def record_model_performance(
        self,
        model_id: str,
        performance_metrics: dict[str, float],
        baseline_metrics: Optional[dict[str, float]] = None,
    ) -> None:
        """
        Record model performance for decay monitoring.

        Args:
            model_id: Model identifier
            performance_metrics: Current performance (sharpe, win_rate, etc.)
            baseline_metrics: Baseline performance for comparison
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "model_id": model_id,
            "performance": performance_metrics,
            "baseline": baseline_metrics,
        }

        # Calculate decay metrics
        if baseline_metrics:
            decay_metrics = {}
            for key in performance_metrics:
                if key in baseline_metrics:
                    baseline_val = baseline_metrics[key]
                    current_val = performance_metrics[key]
                    if baseline_val != 0:
                        decay_pct = ((current_val - baseline_val) / abs(baseline_val)) * 100
                        decay_metrics[f"{key}_decay_pct"] = decay_pct
                    else:
                        decay_metrics[f"{key}_decay_pct"] = None

            record["decay_metrics"] = decay_metrics

        # Save record
        filepath = self.monitoring_dir / f"{model_id}_{datetime.now().strftime('%Y%m%d')}.json"

        # Load existing records
        records = []
        if filepath.exists():
            try:
                with open(filepath) as f:
                    records = json.load(f)
            except Exception:
                records = []

        records.append(record)

        # Keep only last 90 days
        cutoff_date = datetime.now() - timedelta(days=90)
        records = [r for r in records if datetime.fromisoformat(r["timestamp"]) > cutoff_date]

        with open(filepath, "w") as f:
            json.dump(records, f, indent=2)

        logger.debug(f"Signal decay record saved for {model_id}")

    def detect_signal_decay(self, model_id: str, lookback_days: int = 30) -> dict[str, Any]:
        """
        Detect signal decay by comparing recent vs baseline performance.

        Args:
            model_id: Model identifier
            lookback_days: Days to look back for comparison

        Returns:
            Decay detection results
        """
        # Load recent records
        filepath = self.monitoring_dir / f"{model_id}_{datetime.now().strftime('%Y%m%d')}.json"

        if not filepath.exists():
            return {
                "decay_detected": False,
                "message": "No performance data available",
            }

        try:
            with open(filepath) as f:
                records = json.load(f)
        except Exception:
            return {
                "decay_detected": False,
                "message": "Failed to load performance data",
            }

        if len(records) < 2:
            return {
                "decay_detected": False,
                "message": "Insufficient data for decay detection",
            }

        # Get baseline (first record or specified baseline)
        baseline = records[0]
        baseline_perf = baseline.get("performance", {})

        # Get recent performance (last N records)
        recent_records = records[-lookback_days:] if len(records) > lookback_days else records
        recent_perfs = [r.get("performance", {}) for r in recent_records]

        # Calculate average recent performance
        recent_avg = {}
        for key in baseline_perf:
            values = [p.get(key) for p in recent_perfs if p.get(key) is not None]
            if values:
                recent_avg[key] = np.mean(values)

        # Compare vs baseline
        decay_detected = False
        decay_alerts = []

        for key in baseline_perf:
            if key in recent_avg:
                baseline_val = baseline_perf[key]
                recent_val = recent_avg[key]

                if baseline_val != 0:
                    decay_pct = ((recent_val - baseline_val) / abs(baseline_val)) * 100

                    # Alert if significant decay (>20% degradation)
                    if decay_pct < -20:
                        decay_detected = True
                        decay_alerts.append(
                            f"{key}: {decay_pct:.1f}% degradation "
                            f"(baseline: {baseline_val:.2f}, recent: {recent_val:.2f})"
                        )

        return {
            "decay_detected": decay_detected,
            "baseline_performance": baseline_perf,
            "recent_average": recent_avg,
            "alerts": decay_alerts,
            "lookback_days": lookback_days,
        }
