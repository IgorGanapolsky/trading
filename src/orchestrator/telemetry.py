"""Telemetry helpers for the hybrid funnel orchestrator."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Tax configuration
TAX_RESERVE_PCT = float(os.getenv("TAX_RESERVE_PCT", "28.0"))  # 28% for short-term gains
QUARTERLY_SWEEP_ENABLED = os.getenv("QUARTERLY_SWEEP_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}


class OrchestratorTelemetry:
    """Append structured events to a JSONL audit trail."""

    def __init__(self, log_path: str | Path | None = None) -> None:
        default_path = Path("data/audit_trail/hybrid_funnel_runs.jsonl")
        self.log_path = Path(log_path) if log_path else default_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_id = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        self.run_id = os.getenv("GITHUB_RUN_ID") or os.getenv("RUN_ID")

    def record(self, event_type: str, ticker: str, status: str, payload: dict[str, Any]) -> None:
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "session": self.session_id,
            "run_id": self.run_id,
            "event": event_type,
            "ticker": ticker,
            "status": status,
            "payload": payload,
        }
        try:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.warning("Telemetry write failed: %s", exc)

    def gate_pass(self, gate: str, ticker: str, payload: dict[str, Any]) -> None:
        self.record(event_type=f"gate.{gate}", ticker=ticker, status="pass", payload=payload)

    def gate_reject(self, gate: str, ticker: str, payload: dict[str, Any]) -> None:
        self.record(event_type=f"gate.{gate}", ticker=ticker, status="reject", payload=payload)

    def order_event(self, ticker: str, payload: dict[str, Any]) -> None:
        self.record(
            event_type="execution.order",
            ticker=ticker,
            status="submitted",
            payload=payload,
        )

    def explainability_event(
        self,
        gate: str,
        ticker: str,
        contributions: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {"contributions": contributions}
        if metadata:
            payload.update(metadata)
        self.record(
            event_type=f"explainability.{gate}",
            ticker=ticker,
            status="generated",
            payload=payload,
        )

    def anomaly_event(
        self,
        *,
        ticker: str,
        gate: str,
        reason: str,
        metrics: dict[str, Any],
    ) -> None:
        payload = {
            "gate": gate,
            "reason": reason,
            "metrics": metrics,
        }
        self.record(
            event_type="anomaly",
            ticker=ticker,
            status="triggered",
            payload=payload,
        )

    def profit_sweep_event(
        self,
        *,
        sweep_type: str,
        amount: float,
        destination: str,
        details: dict[str, Any],
    ) -> None:
        """Record a quarterly profit sweep event."""
        self.record(
            event_type=f"profit_sweep.{sweep_type}",
            ticker="SYSTEM",
            status="executed",
            payload={
                "amount": amount,
                "destination": destination,
                "tax_reserve_pct": TAX_RESERVE_PCT,
                **details,
            },
        )


class QuarterlyProfitSweeper:
    """
    Quarterly profit sweep for tax reserve management.

    At the end of each quarter, calculates realized profits and
    sweeps 28% to a designated tax reserve (HYSA or similar).

    This prevents tax-time surprises and ensures funds are available
    for estimated tax payments.

    Integration:
    - Runs automatically at quarter end (Mar 31, Jun 30, Sep 30, Dec 31)
    - Can be triggered manually via CLI
    - Logs to telemetry for audit trail
    """

    QUARTER_END_MONTHS = [3, 6, 9, 12]  # March, June, September, December

    def __init__(
        self,
        telemetry: OrchestratorTelemetry | None = None,
        tax_reserve_pct: float = TAX_RESERVE_PCT,
    ) -> None:
        self.telemetry = telemetry or OrchestratorTelemetry()
        self.tax_reserve_pct = tax_reserve_pct
        self.sweep_log_path = Path("data/audit_trail/profit_sweeps.jsonl")
        self.sweep_log_path.parent.mkdir(parents=True, exist_ok=True)

    def is_quarter_end(self, check_date: datetime | None = None) -> bool:
        """Check if today is the last day of a quarter."""
        today = check_date or datetime.now(timezone.utc)
        if today.month not in self.QUARTER_END_MONTHS:
            return False

        # Check if it's the last day of the month
        import calendar

        last_day = calendar.monthrange(today.year, today.month)[1]
        return today.day == last_day

    def calculate_quarterly_profit(
        self,
        start_equity: float,
        end_equity: float,
        deposits: float = 0.0,
        withdrawals: float = 0.0,
    ) -> dict[str, float]:
        """
        Calculate quarterly profit for tax purposes.

        Args:
            start_equity: Equity at quarter start
            end_equity: Current equity
            deposits: Total deposits during quarter
            withdrawals: Total withdrawals during quarter

        Returns:
            Dict with profit breakdown
        """
        # Net change = end - start - deposits + withdrawals
        net_change = end_equity - start_equity - deposits + withdrawals

        # Only positive gains are taxable
        taxable_profit = max(0.0, net_change)
        tax_reserve = taxable_profit * (self.tax_reserve_pct / 100)

        return {
            "start_equity": round(start_equity, 2),
            "end_equity": round(end_equity, 2),
            "deposits": round(deposits, 2),
            "withdrawals": round(withdrawals, 2),
            "net_change": round(net_change, 2),
            "taxable_profit": round(taxable_profit, 2),
            "tax_reserve_amount": round(tax_reserve, 2),
            "tax_reserve_pct": self.tax_reserve_pct,
        }

    def execute_sweep(
        self,
        profit_calc: dict[str, float],
        destination: str = "HYSA",
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        Execute the quarterly profit sweep.

        Args:
            profit_calc: Output from calculate_quarterly_profit
            destination: Where to sweep funds (HYSA, tax_account, etc.)
            dry_run: If True, only simulate the sweep

        Returns:
            Sweep result details
        """
        sweep_amount = profit_calc["tax_reserve_amount"]

        if sweep_amount <= 0:
            logger.info("No positive profit to sweep this quarter")
            return {
                "status": "skipped",
                "reason": "No taxable profit",
                "profit_calc": profit_calc,
            }

        sweep_id = f"sweep_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        result = {
            "sweep_id": sweep_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "dry_run" if dry_run else "executed",
            "amount": sweep_amount,
            "destination": destination,
            "profit_calc": profit_calc,
            "quarter": self._get_quarter_label(),
        }

        if not dry_run:
            # In production, this would initiate an actual transfer
            # For now, we just log the intent
            logger.warning(
                "💰 QUARTERLY TAX SWEEP: $%.2f to %s",
                sweep_amount,
                destination,
            )

            # Log to telemetry
            self.telemetry.profit_sweep_event(
                sweep_type="quarterly_tax",
                amount=sweep_amount,
                destination=destination,
                details=profit_calc,
            )

            result["status"] = "executed"
        else:
            logger.info(
                "📋 DRY RUN: Would sweep $%.2f to %s for Q%s taxes",
                sweep_amount,
                destination,
                self._get_quarter_label(),
            )

        # Persist sweep record
        self._persist_sweep(result)

        return result

    def _get_quarter_label(self) -> str:
        """Get current quarter label (e.g., 'Q4 2025')."""
        now = datetime.now(timezone.utc)
        quarter = (now.month - 1) // 3 + 1
        return f"Q{quarter} {now.year}"

    def _persist_sweep(self, result: dict[str, Any]) -> None:
        """Append sweep record to log."""
        try:
            with self.sweep_log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(result, default=str) + "\n")
        except Exception as e:
            logger.warning("Failed to persist sweep: %s", e)

    def run_quarterly_check(
        self,
        start_equity: float,
        end_equity: float,
        deposits: float = 0.0,
        force: bool = False,
        dry_run: bool = True,
    ) -> dict[str, Any] | None:
        """
        Run quarterly sweep check.

        Only executes on quarter-end dates unless forced.

        Args:
            start_equity: Equity at quarter start
            end_equity: Current equity
            deposits: Total deposits during quarter
            force: Force sweep regardless of date
            dry_run: Simulate only

        Returns:
            Sweep result or None if not quarter end
        """
        if not QUARTERLY_SWEEP_ENABLED:
            logger.debug("Quarterly sweep disabled via config")
            return None

        if not force and not self.is_quarter_end():
            logger.debug("Not quarter end - skipping sweep check")
            return None

        profit_calc = self.calculate_quarterly_profit(
            start_equity=start_equity,
            end_equity=end_equity,
            deposits=deposits,
        )

        return self.execute_sweep(profit_calc, dry_run=dry_run)


def run_quarterly_sweep(
    start_equity: float,
    end_equity: float,
    deposits: float = 0.0,
    force: bool = False,
    dry_run: bool = True,
) -> dict[str, Any] | None:
    """
    Convenience function for quarterly profit sweep.

    Args:
        start_equity: Equity at quarter start
        end_equity: Current equity
        deposits: Total deposits during quarter
        force: Force sweep regardless of date
        dry_run: Simulate only

    Returns:
        Sweep result or None
    """
    sweeper = QuarterlyProfitSweeper()
    return sweeper.run_quarterly_check(
        start_equity=start_equity,
        end_equity=end_equity,
        deposits=deposits,
        force=force,
        dry_run=dry_run,
    )
