"""
Real-Time Alpaca Position Reconciliation

Compares claimed positions to actual Alpaca API positions every trade.
Detects hallucinations where LLM claims positions that don't exist or
reports incorrect quantities/values.

Created: Dec 11, 2025
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

RECONCILIATION_LOG_PATH = Path("data/position_reconciliation.json")


@dataclass
class ReconciliationResult:
    """Result of a position reconciliation check."""

    timestamp: str
    is_reconciled: bool
    discrepancies: list[dict[str, Any]]
    claimed_positions: dict[str, Any]
    actual_positions: dict[str, Any]
    total_claimed_value: float
    total_actual_value: float
    value_difference: float
    value_difference_pct: float


class PositionReconciler:
    """
    Real-time position reconciliation against Alpaca API.

    Verifies that:
    1. Claimed positions actually exist
    2. Quantities match
    3. Values are within tolerance
    4. No phantom positions are claimed
    """

    def __init__(
        self,
        alpaca_api: Optional[Any] = None,
        value_tolerance_pct: float = 0.02,  # 2% tolerance for value differences
        qty_tolerance: float = 0.001,  # 0.1% for quantity (handles fractional shares)
    ):
        self.alpaca_api = alpaca_api
        self.value_tolerance_pct = value_tolerance_pct
        self.qty_tolerance = qty_tolerance
        self.reconciliation_history: list[ReconciliationResult] = []

        self._load_history()
        logger.info("PositionReconciler initialized")

    def reconcile(
        self,
        claimed_positions: dict[str, dict[str, Any]],
    ) -> ReconciliationResult:
        """
        Reconcile claimed positions against Alpaca API.

        Args:
            claimed_positions: Dict of symbol -> {qty, market_value, avg_cost, etc.}

        Returns:
            ReconciliationResult with any discrepancies
        """
        actual_positions = self._fetch_actual_positions()
        discrepancies = []

        total_claimed_value = 0.0
        total_actual_value = 0.0

        # Check each claimed position
        for symbol, claimed in claimed_positions.items():
            claimed_qty = float(claimed.get("qty", 0))
            claimed_value = float(claimed.get("market_value", 0))
            total_claimed_value += claimed_value

            if symbol not in actual_positions:
                # Phantom position - claimed but doesn't exist!
                discrepancies.append(
                    {
                        "type": "phantom_position",
                        "symbol": symbol,
                        "severity": "critical",
                        "claimed_qty": claimed_qty,
                        "actual_qty": 0,
                        "claimed_value": claimed_value,
                        "actual_value": 0,
                        "message": f"PHANTOM: Claimed position in {symbol} does not exist!",
                    }
                )
            else:
                actual = actual_positions[symbol]
                actual_qty = float(actual.get("qty", 0))
                actual_value = float(actual.get("market_value", 0))
                total_actual_value += actual_value

                # Check quantity
                qty_diff = abs(claimed_qty - actual_qty)
                if actual_qty > 0 and qty_diff / actual_qty > self.qty_tolerance:
                    discrepancies.append(
                        {
                            "type": "quantity_mismatch",
                            "symbol": symbol,
                            "severity": "high",
                            "claimed_qty": claimed_qty,
                            "actual_qty": actual_qty,
                            "difference": qty_diff,
                            "message": f"QTY MISMATCH: {symbol} claimed {claimed_qty}, actual {actual_qty}",
                        }
                    )

                # Check value
                if actual_value > 0:
                    value_diff_pct = abs(claimed_value - actual_value) / actual_value
                    if value_diff_pct > self.value_tolerance_pct:
                        discrepancies.append(
                            {
                                "type": "value_mismatch",
                                "symbol": symbol,
                                "severity": "medium",
                                "claimed_value": claimed_value,
                                "actual_value": actual_value,
                                "difference_pct": value_diff_pct,
                                "message": f"VALUE MISMATCH: {symbol} claimed ${claimed_value:.2f}, actual ${actual_value:.2f}",
                            }
                        )

        # Check for positions we have but weren't claimed (missing positions)
        for symbol, actual in actual_positions.items():
            if symbol not in claimed_positions:
                actual_value = float(actual.get("market_value", 0))
                total_actual_value += actual_value
                discrepancies.append(
                    {
                        "type": "missing_position",
                        "symbol": symbol,
                        "severity": "high",
                        "claimed_qty": 0,
                        "actual_qty": float(actual.get("qty", 0)),
                        "actual_value": actual_value,
                        "message": f"MISSING: Position in {symbol} exists but wasn't claimed!",
                    }
                )

        # Calculate overall value difference
        value_difference = total_claimed_value - total_actual_value
        value_difference_pct = (
            abs(value_difference) / total_actual_value if total_actual_value > 0 else 0
        )

        result = ReconciliationResult(
            timestamp=datetime.now(timezone.utc).isoformat(),
            is_reconciled=len(discrepancies) == 0,
            discrepancies=discrepancies,
            claimed_positions=claimed_positions,
            actual_positions=actual_positions,
            total_claimed_value=total_claimed_value,
            total_actual_value=total_actual_value,
            value_difference=value_difference,
            value_difference_pct=value_difference_pct,
        )

        self.reconciliation_history.append(result)
        self._save_history()

        if discrepancies:
            for d in discrepancies:
                logger.warning(f"Position reconciliation: {d['message']}")
        else:
            logger.info("Position reconciliation: All positions match")

        return result

    def _fetch_actual_positions(self) -> dict[str, dict[str, Any]]:
        """Fetch actual positions from Alpaca API."""
        if not self.alpaca_api:
            logger.warning("No Alpaca API configured - returning empty positions")
            return {}

        try:
            positions = self.alpaca_api.list_positions()
            return {
                p.symbol: {
                    "qty": float(p.qty),
                    "market_value": float(p.market_value),
                    "avg_entry_price": float(p.avg_entry_price),
                    "current_price": float(p.current_price),
                    "unrealized_pl": float(p.unrealized_pl),
                    "side": p.side,
                }
                for p in positions
            }
        except Exception as e:
            logger.error(f"Failed to fetch positions from Alpaca: {e}")
            return {}

    def get_reconciliation_report(self) -> dict[str, Any]:
        """Get summary report of recent reconciliations."""
        if not self.reconciliation_history:
            return {"message": "No reconciliation history"}

        recent = self.reconciliation_history[-100:]  # Last 100

        total_checks = len(recent)
        successful = sum(1 for r in recent if r.is_reconciled)
        failed = total_checks - successful

        # Count discrepancy types
        discrepancy_counts = {}
        for r in recent:
            for d in r.discrepancies:
                dtype = d["type"]
                discrepancy_counts[dtype] = discrepancy_counts.get(dtype, 0) + 1

        return {
            "total_reconciliations": total_checks,
            "successful": successful,
            "failed": failed,
            "success_rate": successful / total_checks if total_checks > 0 else 1.0,
            "discrepancy_breakdown": discrepancy_counts,
            "latest": {
                "timestamp": recent[-1].timestamp,
                "is_reconciled": recent[-1].is_reconciled,
                "value_difference": recent[-1].value_difference,
            }
            if recent
            else None,
        }

    def _load_history(self) -> None:
        """Load reconciliation history from disk."""
        if RECONCILIATION_LOG_PATH.exists():
            try:
                with open(RECONCILIATION_LOG_PATH) as f:
                    json.load(f)
                    # Just keep last 100 for memory efficiency
                    self.reconciliation_history = []
            except Exception as e:
                logger.warning(f"Could not load reconciliation history: {e}")

    def _save_history(self) -> None:
        """Save reconciliation history to disk."""
        RECONCILIATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Keep only last 100
        recent = self.reconciliation_history[-100:]

        data = {
            "reconciliations": [
                {
                    "timestamp": r.timestamp,
                    "is_reconciled": r.is_reconciled,
                    "discrepancies": r.discrepancies,
                    "total_claimed_value": r.total_claimed_value,
                    "total_actual_value": r.total_actual_value,
                    "value_difference": r.value_difference,
                }
                for r in recent
            ],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        try:
            with open(RECONCILIATION_LOG_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save reconciliation history: {e}")
