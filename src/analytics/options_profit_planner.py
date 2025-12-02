"""
Options Profit Planner
----------------------

Transforms Rule #1 options signals (puts + calls) into an actionable plan
for achieving a target daily profit via premium selling.

Key capabilities:
- Normalize signals emitted from `RuleOneOptionsStrategy` or persisted JSON
- Compute per-contract and portfolio-level premium pacing
- Highlight the shortfall vs a configured daily target (defaults to $10/day)
- Recommend the additional number of contracts required to close the gap
- Persist structured summaries under `data/options_signals/`
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

logger = logging.getLogger(__name__)

try:  # Optional import for runtime typing; not required for JSON snapshots
    from src.strategies.rule_one_options import RuleOneOptionsSignal  # type: ignore
except Exception:  # pragma: no cover - fallback for test environments without full deps
    RuleOneOptionsSignal = Any  # type: ignore


SignalInput = Union[dict[str, Any], "RuleOneOptionsSignal"]


@dataclass
class SignalProfitProjection:
    """Computed premium pacing for a single options signal."""

    symbol: str
    signal_type: str
    strike: float
    expiration: str
    contracts: int
    days_to_expiry: int
    premium_per_contract: float
    total_premium: float
    daily_premium_per_contract: float
    daily_premium_total: float
    annualized_return: float
    iv_rank: float | None
    delta: float | None
    rationale: str


class OptionsProfitPlanner:
    """
    Analyze options signals and determine whether we are on track
    to hit a configurable daily premium target (default: $10/day).
    """

    def __init__(
        self,
        target_daily_profit: float = 10.0,
        trading_days_per_month: int = 21,
        snapshot_dir: Path | None = None,
    ):
        self.target_daily_profit = target_daily_profit
        self.trading_days_per_month = trading_days_per_month
        self.snapshot_dir = snapshot_dir or Path("data/options_signals")
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------- #
    # Snapshot helpers
    # --------------------------------------------------------------------- #
    def load_latest_snapshot(self) -> dict[str, Any] | None:
        """Load the most recent options snapshot from disk."""
        if not self.snapshot_dir.exists():
            return None

        files = sorted(self.snapshot_dir.glob("*.json"))
        if not files:
            return None

        latest_path = files[-1]
        try:
            with latest_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            payload["_source_path"] = str(latest_path)
            return payload
        except Exception as exc:
            logger.error("Failed to read snapshot %s: %s", latest_path, exc)
            return None

    def persist_summary(self, summary: dict[str, Any]) -> Path:
        """Persist planner output for downstream dashboards."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        output_path = self.snapshot_dir / f"options_profit_plan_{timestamp}.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
        logger.info("Saved options profit plan → %s", output_path)
        return output_path

    # --------------------------------------------------------------------- #
    # Core analysis
    # --------------------------------------------------------------------- #
    def summarize(
        self,
        put_signals: Sequence[SignalInput],
        call_signals: Sequence[SignalInput],
        data_source: str | None = None,
    ) -> dict[str, Any]:
        """Generate profit pacing summary for supplied signals."""
        put_metrics = [self._score_signal(signal) for signal in put_signals]
        call_metrics = [self._score_signal(signal) for signal in call_signals]

        combined = put_metrics + call_metrics
        daily_run_rate = sum(m.daily_premium_total for m in combined)
        monthly_run_rate = daily_run_rate * self.trading_days_per_month
        annualized_run_rate = daily_run_rate * 252  # trading days per year
        gap = max(0.0, self.target_daily_profit - daily_run_rate)

        recommendation = self._recommend_contract_plan(combined, gap)

        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_daily_profit": self.target_daily_profit,
            "daily_run_rate": round(daily_run_rate, 2),
            "monthly_run_rate": round(monthly_run_rate, 2),
            "annualized_run_rate": round(annualized_run_rate, 2),
            "gap_to_target": round(gap, 2),
            "signals_analyzed": len(combined),
            "puts": [asdict(m) for m in put_metrics],
            "calls": [asdict(m) for m in call_metrics],
            "recommendation": recommendation,
            "data_source": data_source,
            "notes": self._build_notes(combined, gap),
        }
        return summary

    def build_summary_from_snapshot(self, snapshot: dict[str, Any] | None) -> dict[str, Any]:
        """
        Convenience method for snapshot payloads persisted by
        `RuleOneOptionsStrategy.generate_daily_signals()`.
        """
        if not snapshot:
            return self._empty_summary("No snapshot available (run signals first).")

        puts = snapshot.get("put_opportunities", [])
        calls = snapshot.get("call_opportunities", [])

        if not puts and not calls:
            return self._empty_summary(
                "Snapshot contains zero opportunities (likely due to missing data or tight filters).",
                data_source=snapshot.get("_source_path"),
            )

        source = snapshot.get("_source_path")
        return self.summarize(puts, calls, data_source=source or "in-memory")

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #
    def _empty_summary(self, reason: str, data_source: str | None = None) -> dict[str, Any]:
        """Return placeholder summary when no signals are available."""
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_daily_profit": self.target_daily_profit,
            "daily_run_rate": 0.0,
            "monthly_run_rate": 0.0,
            "annualized_run_rate": 0.0,
            "gap_to_target": self.target_daily_profit,
            "signals_analyzed": 0,
            "puts": [],
            "calls": [],
            "recommendation": None,
            "data_source": data_source,
            "notes": [reason],
        }

    def _score_signal(self, signal: SignalInput) -> SignalProfitProjection:
        """Normalize a signal and compute profit pacing metrics."""
        payload = self._to_payload(signal)
        days = self._resolve_days_to_expiry(payload)
        contracts = max(1, int(payload.get("contracts") or 1))

        premium = max(float(payload.get("premium") or 0.0), 0.0)
        premium_per_contract = premium * 100  # options quote is per share
        total_premium = premium_per_contract * contracts
        daily_per_contract = premium_per_contract / days
        daily_total = daily_per_contract * contracts

        projection = SignalProfitProjection(
            symbol=str(payload.get("symbol")),
            signal_type=str(payload.get("signal_type") or payload.get("type")),
            strike=float(payload.get("strike") or 0.0),
            expiration=str(payload.get("expiration") or ""),
            contracts=contracts,
            days_to_expiry=days,
            premium_per_contract=round(premium_per_contract, 2),
            total_premium=round(total_premium, 2),
            daily_premium_per_contract=round(daily_per_contract, 2),
            daily_premium_total=round(daily_total, 2),
            annualized_return=float(payload.get("annualized_return") or 0.0),
            iv_rank=self._maybe_float(payload.get("iv_rank")),
            delta=self._maybe_float(payload.get("delta")),
            rationale=str(payload.get("rationale") or payload.get("reason", "")),
        )
        return projection

    @staticmethod
    def _to_payload(signal: SignalInput) -> dict[str, Any]:
        """Coerce dataclass or dict signals into a plain dict."""
        if hasattr(signal, "__dict__"):
            return {key: value for key, value in signal.__dict__.items() if not key.startswith("_")}
        if isinstance(signal, dict):
            return dict(signal)
        raise TypeError(f"Unsupported signal type: {type(signal)}")

    @staticmethod
    def _resolve_days_to_expiry(payload: dict[str, Any]) -> int:
        """Best-effort resolution of days to expiry."""
        days = payload.get("days_to_expiry")
        if days is None and payload.get("expiration"):
            try:
                exp = datetime.fromisoformat(str(payload["expiration"])[:10])
                days = (exp.date() - datetime.utcnow().date()).days
            except ValueError:
                days = None

        if days is None:
            days = 30  # conservative default for pacing

        days = max(1, int(days))
        return days

    @staticmethod
    def _maybe_float(value: Any) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _recommend_contract_plan(
        self, projections: Sequence[SignalProfitProjection], gap: float
    ) -> dict[str, Any] | None:
        """Recommend additional contracts required to close the gap."""
        if gap <= 0 or not projections:
            return None

        # Sort by best daily premium per contract
        best = max(projections, key=lambda proj: proj.daily_premium_per_contract)
        per_contract_daily = best.daily_premium_per_contract
        if per_contract_daily <= 0:
            return None

        additional_contracts = math.ceil(gap / per_contract_daily)
        return {
            "recommended_symbol": best.symbol,
            "signal_type": best.signal_type,
            "daily_premium_per_contract": best.daily_premium_per_contract,
            "gap_to_target": round(gap, 2),
            "additional_contracts_needed": int(additional_contracts),
            "suggested_action": (
                f"Sell {additional_contracts} more {best.signal_type} contract(s) "
                f"similar to {best.symbol} to close the ${gap:.2f}/day gap."
            ),
        }

    def _build_notes(
        self,
        projections: Sequence[SignalProfitProjection],
        gap: float,
    ) -> list[str]:
        """Generate human-readable notes for the summary."""
        notes = []
        if not projections:
            notes.append("No qualifying put/call signals met IV/delta filters.")
            return notes

        top_symbols = {proj.symbol for proj in projections}
        notes.append(f"Analyzed {len(projections)} signals across {len(top_symbols)} symbols.")

        if gap > 0:
            notes.append(
                f"Premium run-rate is ${gap:.2f}/day below the ${self.target_daily_profit:.2f} target."
            )
        else:
            notes.append(
                f"Current premium pace meets or exceeds the ${self.target_daily_profit:.2f}/day target."
            )

        return notes
