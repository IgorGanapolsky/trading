"""Risk-Gate Metrics Tracker — durable counters for safety gates + win-rate by weekday.

Tracks:
1. Defense alpha: how many trades were blocked at each safety gate (generic dict
   so we don't bake gate names into the schema — yesterday's `thursday_gate_blocks`
   field outlasted the gate itself).
2. Win-rate by weekday: honest 5-bucket split with sample sizes, instead of the
   prior Thursday-vs-other split that prejudged the conclusion.
3. ML alignment: how often RAG penalties fired during GRPO training.

The previous shape (thursday_win_rate / monday_win_rate / other_days_win_rate +
thursday_gate_blocks) was retired 2026-05-20: it embedded the Thursday-only
hypothesis that docs/research/2026-05-19-edge-analysis.md disproved at
Bonferroni adj_p=0.190. Backward compatibility for old persisted JSON is
preserved via _migrate_legacy().
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
ALPHA_METRICS_PATH = PROJECT_ROOT / "data" / "alpha_metrics.json"

_WEEKDAY_LABELS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class AlphaMetricsTracker:
    def __init__(self, repo_root: Path = PROJECT_ROOT):
        self.repo_root = repo_root
        self.metrics_file = repo_root / "data" / "alpha_metrics.json"
        self.metrics = self._load_metrics()

    def _load_metrics(self) -> dict[str, Any]:
        if self.metrics_file.exists():
            try:
                raw = json.loads(self.metrics_file.read_text())
                return self._migrate_legacy(raw)
            except Exception as e:
                logger.warning(f"Failed to load metrics: {e}")
                return self._default_metrics()
        return self._default_metrics()

    def _default_metrics(self) -> dict[str, Any]:
        return {
            "last_updated": datetime.now().isoformat(),
            "defense_alpha": {
                "blocked_trades_total": 0,
                "gate_blocks": {},  # gate_name -> count
                "estimated_loss_prevented": 0.0,
            },
            "weekday_performance": {
                "win_rate": {label: 0.0 for label in _WEEKDAY_LABELS[:5]},
                "sample_size": {label: 0 for label in _WEEKDAY_LABELS[:5]},
            },
            "ml_alignment": {"rag_penalties_applied": 0, "policy_compliance_rate": 0.0},
        }

    def _migrate_legacy(self, raw: dict[str, Any]) -> dict[str, Any]:
        # Old schema had top-level thursday_gate_blocks + dte_gate_blocks +
        # vix_gate_blocks as siblings of gate_blocks, and thursday/monday/other
        # win_rate keys directly under regime_performance. Coerce both to the
        # new shape so loading old data is non-destructive.
        new = self._default_metrics()
        new["last_updated"] = raw.get("last_updated", new["last_updated"])

        legacy_defense = raw.get("defense_alpha") or {}
        new["defense_alpha"]["blocked_trades_total"] = int(
            legacy_defense.get("blocked_trades_total", 0)
        )
        new["defense_alpha"]["estimated_loss_prevented"] = float(
            legacy_defense.get("estimated_loss_prevented", 0.0)
        )
        gate_blocks: dict[str, int] = dict(legacy_defense.get("gate_blocks") or {})
        for legacy_key, value in legacy_defense.items():
            if legacy_key.endswith("_gate_blocks") and isinstance(value, (int, float)):
                gate_name = legacy_key.removesuffix("_gate_blocks")
                # Skip thursday — gate was retired, counter is meaningless going forward
                if gate_name == "thursday":
                    continue
                gate_blocks[gate_name] = int(value)
        new["defense_alpha"]["gate_blocks"] = gate_blocks

        # Discard regime_performance entirely — the bucket boundaries assumed
        # the Thursday anomaly. Old win_rate numbers (e.g. 60% Thursday) are
        # exactly the disproved claim we should not propagate.
        new["weekday_performance"] = new["weekday_performance"]

        legacy_ml = raw.get("ml_alignment") or {}
        new["ml_alignment"]["rag_penalties_applied"] = int(
            legacy_ml.get("rag_penalties_applied", 0)
        )
        new["ml_alignment"]["policy_compliance_rate"] = float(
            legacy_ml.get("policy_compliance_rate", 0.0)
        )
        return new

    def record_block(self, gate_type: str, estimated_loss: float = 0.0) -> None:
        """Increment the blocked-trades counter for `gate_type` (e.g. 'dte', 'vix')."""
        gate = gate_type.lower()
        self.metrics["defense_alpha"]["blocked_trades_total"] += 1
        gate_blocks = self.metrics["defense_alpha"].setdefault("gate_blocks", {})
        gate_blocks[gate] = int(gate_blocks.get(gate, 0)) + 1
        self.metrics["defense_alpha"]["estimated_loss_prevented"] += float(estimated_loss)
        self.save()

    def update_weekday_stats(self, trades: list[dict[str, Any]]) -> None:
        """Compute win rate + sample size for each of the 5 trading weekdays.

        No bucket is treated as special. All 5 are equal columns.
        """
        win_rate: dict[str, float] = {}
        sample_size: dict[str, int] = {}
        for weekday_index, label in enumerate(_WEEKDAY_LABELS[:5]):
            bucket = [t for t in trades if self._get_weekday(t.get("entry_date")) == weekday_index]
            win_rate[label] = self._win_rate(bucket)
            sample_size[label] = len(bucket)
        self.metrics["weekday_performance"]["win_rate"] = win_rate
        self.metrics["weekday_performance"]["sample_size"] = sample_size
        self.save()

    # Back-compat alias (used by the __main__ self-test and any older callers).
    update_regime_stats = update_weekday_stats

    def _get_weekday(self, date_str: str | None) -> int:
        if not date_str:
            return -1
        try:
            return datetime.fromisoformat(date_str).weekday()
        except (ValueError, TypeError):
            return -1

    def _win_rate(self, trades: list[dict[str, Any]]) -> float:
        if not trades:
            return 0.0
        wins = len([t for t in trades if t.get("outcome") == "win" or t.get("realized_pnl", 0) > 0])
        return round((wins / len(trades)) * 100, 2)

    def save(self) -> None:
        self.metrics["last_updated"] = datetime.now().isoformat()
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self.metrics_file.write_text(json.dumps(self.metrics, indent=2))


if __name__ == "__main__":
    tracker = AlphaMetricsTracker()
    trades_file = PROJECT_ROOT / "data" / "trades.json"
    if trades_file.exists():
        trades_data = json.loads(trades_file.read_text())
        tracker.update_weekday_stats(trades_data.get("trades", []))
    print(f"Alpha metrics updated: {tracker.metrics_file}")
