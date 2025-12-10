"""Volatility-aware trade auditing utilities."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.utils.telemetry_summary import load_events, summarize_events

logger = logging.getLogger(__name__)


class AdaptiveTradeAuditor:
    """Run heavier trade critiques when volatility spikes."""

    def __init__(
        self,
        telemetry_log: str | Path | None = None,
        *,
        state_path: str | Path | None = None,
        audit_log: str | Path | None = None,
        tax_rate: float = 0.28,
    ) -> None:
        self.telemetry_log = Path(telemetry_log or "data/audit_trail/hybrid_funnel_runs.jsonl")
        self.telemetry_log.parent.mkdir(parents=True, exist_ok=True)
        self.state_path = Path(state_path or "data/audit_trail/auditor_state.json")
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_log = Path(audit_log or "data/audit_trail/audit_reports.jsonl")
        self.audit_log.parent.mkdir(parents=True, exist_ok=True)
        self.tax_rate = tax_rate
        self._kb = None

    def run_if_due(
        self,
        *,
        frequency: str,
        vix_level: float,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Run an audit if cadence threshold has elapsed."""

        now = now or datetime.now(timezone.utc)
        if not self._should_run(frequency=frequency, now=now):
            return None

        report = self._run_audit(frequency=frequency, vix_level=vix_level, now=now)
        if not report:
            return None

        self._update_state(frequency=frequency, timestamp=now)
        self._append_report(report)
        return report

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _should_run(self, *, frequency: str, now: datetime) -> bool:
        state = self._load_state()
        last_run = state.get(frequency)
        if not last_run:
            return True
        try:
            last_dt = datetime.fromisoformat(last_run)
        except ValueError:
            return True

        interval = timedelta(days=1 if frequency == "daily" else 7)
        return now - last_dt >= interval

    def _run_audit(
        self,
        *,
        frequency: str,
        vix_level: float,
        now: datetime,
    ) -> dict[str, Any] | None:
        window_days = 3 if frequency == "daily" else 7
        cutoff = now - timedelta(days=window_days)

        try:
            events = load_events(self.telemetry_log)
        except FileNotFoundError:
            logger.debug("Telemetry log %s not found; skipping audit.", self.telemetry_log)
            return None

        filtered = []
        for event in events:
            ts = event.get("ts")
            if not ts:
                continue
            try:
                ts_dt = datetime.fromisoformat(ts)
            except ValueError:
                continue
            if ts_dt.replace(tzinfo=timezone.utc) >= cutoff:
                filtered.append(event)

        if not filtered:
            return None

        gate_failures = [event for event in filtered if event.get("status") in {"reject", "error"}]
        execution_events = [event for event in filtered if event.get("event") == "execution.order"]

        try:
            summary = summarize_events(filtered)
        except Exception:
            summary = {}

        account_state = self._load_account_state()
        tax_sweep = None
        if account_state:
            profit = float(account_state.get("total_pl", 0.0))
            if profit > 0:
                tax_sweep = round(profit * self.tax_rate, 2)

        guidance = self._theta_guidance()

        report = {
            "generated_at": now.isoformat(),
            "frequency": frequency,
            "event_window_days": window_days,
            "vix_level": vix_level,
            "events_analyzed": len(filtered),
            "gate_failures": len(gate_failures),
            "execution_events": len(execution_events),
            "recent_failures": gate_failures[-3:],
            "top_tickers": summary.get("top_tickers") if summary else None,
            "tax_sweep_recommendation": tax_sweep,
            "account_snapshot": account_state,
            "theta_guidance": guidance,
        }
        return report

    def _theta_guidance(self) -> str | None:
        if self._kb is None:
            try:
                from src.rag.collectors.mcmillan_options_collector import (  # type: ignore
                    McMillanOptionsKnowledgeBase,
                )

                self._kb = McMillanOptionsKnowledgeBase()
            except Exception as exc:  # pragma: no cover - optional dependency
                logger.debug("McMillan knowledge base unavailable: %s", exc)
                self._kb = False

        if not self._kb:
            return None

        try:
            theta = self._kb.get_greek_guidance("theta")
        except Exception:  # pragma: no cover - knowledge base errors
            return None

        if not theta:
            return None

        return (
            f"Theta insight: {theta.get('interpretation')} "
            f"Trading implication: {theta.get('trading_implications')}"
        )

    def _load_account_state(self) -> dict[str, Any] | None:
        state_path = Path("data/system_state.json")
        if not state_path.exists():
            return None
        try:
            with state_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
                return payload.get("account")
        except Exception:
            return None

    def _load_state(self) -> dict[str, str]:
        if not self.state_path.exists():
            return {}
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return {}

    def _update_state(self, *, frequency: str, timestamp: datetime) -> None:
        state = self._load_state()
        state[frequency] = timestamp.isoformat()
        try:
            with self.state_path.open("w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2)
        except Exception as exc:
            logger.warning("Failed to persist auditor state: %s", exc)

    def _append_report(self, report: dict[str, Any]) -> None:
        try:
            with self.audit_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(report, default=str) + "\n")
        except Exception as exc:
            logger.warning("Failed to append audit report: %s", exc)


# Backwards compatibility: older modules import VolatilityAuditor
class VolatilityAuditor(AdaptiveTradeAuditor):
    """Alias for AdaptiveTradeAuditor used in legacy code paths."""

    pass
