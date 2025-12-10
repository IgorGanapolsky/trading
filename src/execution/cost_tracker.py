"""
Live Execution Cost Tracker

Compares modeled slippage (from SlippageModel) against actual Alpaca fills
to validate our backtest assumptions match reality.

Key Features:
- Tracks every live order: expected price vs actual fill price
- Calculates slippage in basis points
- Daily/weekly summaries for model validation
- Alerts when model diverges significantly from reality

Author: Trading System
Created: 2025-12-05
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Storage path for execution costs
EXECUTION_COSTS_PATH = Path("data/execution_costs.json")


@dataclass
class FillRecord:
    """Record of a single order fill with slippage analysis."""

    order_id: str
    symbol: str
    side: str  # "buy" or "sell"
    quantity: float
    expected_price: float  # Price when order was submitted
    actual_price: float  # Filled average price
    slippage_bps: float  # Actual slippage in basis points
    modeled_slippage_bps: float  # What SlippageModel predicted
    divergence_bps: float  # actual - modeled
    notional: float  # Dollar value of trade
    slippage_cost: float  # Dollar cost of slippage
    timestamp: str
    order_type: str  # "market" or "limit"


@dataclass
class DailySummary:
    """Daily summary of execution costs."""

    date: str
    total_trades: int
    total_notional: float
    avg_slippage_bps: float
    avg_modeled_bps: float
    avg_divergence_bps: float
    model_accuracy: float  # 1 - (avg_divergence / avg_modeled)
    total_slippage_cost: float
    worst_slippage_bps: float
    best_slippage_bps: float


class ExecutionCostTracker:
    """
    Tracks live execution costs and compares to model predictions.

    Usage:
        tracker = ExecutionCostTracker()

        # Before placing order, get expected price
        expected_price = get_current_quote(symbol)

        # After order fills, track it
        tracker.track_fill(
            order_id=order["id"],
            symbol="SPY",
            side="buy",
            quantity=10,
            expected_price=450.00,
            actual_price=450.05,
            modeled_slippage_bps=2.5,
            order_type="market"
        )

        # Get daily summary
        summary = tracker.get_daily_summary()
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or EXECUTION_COSTS_PATH
        self.fills: list[FillRecord] = []
        self.daily_summaries: dict[str, DailySummary] = {}
        self._load()

    def _load(self) -> None:
        """Load existing data from storage."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)

                self.fills = [FillRecord(**f) for f in data.get("fills", [])]
                self.daily_summaries = {
                    k: DailySummary(**v) for k, v in data.get("daily_summaries", {}).items()
                }
                logger.info(
                    f"Loaded {len(self.fills)} fill records, "
                    f"{len(self.daily_summaries)} daily summaries"
                )
            except Exception as e:
                logger.warning(f"Failed to load execution costs: {e}")
                self.fills = []
                self.daily_summaries = {}

    def _save(self) -> None:
        """Persist data to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "fills": [asdict(f) for f in self.fills],
            "daily_summaries": {k: asdict(v) for k, v in self.daily_summaries.items()},
            "last_updated": datetime.now().isoformat(),
        }

        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def track_fill(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        expected_price: float,
        actual_price: float,
        modeled_slippage_bps: float,
        order_type: str = "market",
    ) -> FillRecord:
        """
        Track a fill and compare to model prediction.

        Args:
            order_id: Alpaca order ID
            symbol: Ticker symbol
            side: "buy" or "sell"
            quantity: Shares filled
            expected_price: Price when order was submitted (mid or quote)
            actual_price: Actual fill price from Alpaca
            modeled_slippage_bps: What SlippageModel predicted
            order_type: "market" or "limit"

        Returns:
            FillRecord with slippage analysis
        """
        # Calculate actual slippage
        if side.lower() == "buy":
            # For buys: paid more than expected = positive slippage
            slippage_pct = (actual_price - expected_price) / expected_price
        else:
            # For sells: received less than expected = positive slippage
            slippage_pct = (expected_price - actual_price) / expected_price

        slippage_bps = slippage_pct * 10000  # Convert to basis points
        divergence_bps = slippage_bps - modeled_slippage_bps

        notional = actual_price * quantity
        slippage_cost = abs(actual_price - expected_price) * quantity

        record = FillRecord(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            expected_price=expected_price,
            actual_price=actual_price,
            slippage_bps=slippage_bps,
            modeled_slippage_bps=modeled_slippage_bps,
            divergence_bps=divergence_bps,
            notional=notional,
            slippage_cost=slippage_cost,
            timestamp=datetime.now().isoformat(),
            order_type=order_type,
        )

        self.fills.append(record)
        self._save()

        # Log the fill
        logger.info(
            f"[FILL TRACKED] {symbol} {side}: "
            f"expected=${expected_price:.4f}, actual=${actual_price:.4f}, "
            f"slippage={slippage_bps:.2f}bps (modeled={modeled_slippage_bps:.2f}bps, "
            f"divergence={divergence_bps:.2f}bps)"
        )

        # Alert if significant divergence
        if abs(divergence_bps) > 5.0:  # More than 5 bps divergence
            logger.warning(
                f"[SLIPPAGE ALERT] {symbol}: Model divergence {divergence_bps:.2f}bps "
                f"exceeds threshold. Actual={slippage_bps:.2f}bps, "
                f"Modeled={modeled_slippage_bps:.2f}bps"
            )

        return record

    def get_daily_summary(self, date: Optional[str] = None) -> Optional[DailySummary]:
        """
        Get or calculate daily summary.

        Args:
            date: Date string (YYYY-MM-DD). Defaults to today.

        Returns:
            DailySummary for the requested date
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Check if we have a cached summary
        if date in self.daily_summaries:
            return self.daily_summaries[date]

        # Calculate from fills
        day_fills = [f for f in self.fills if f.timestamp.startswith(date)]

        if not day_fills:
            return None

        total_trades = len(day_fills)
        total_notional = sum(f.notional for f in day_fills)
        avg_slippage_bps = sum(f.slippage_bps for f in day_fills) / total_trades
        avg_modeled_bps = sum(f.modeled_slippage_bps for f in day_fills) / total_trades
        avg_divergence_bps = sum(f.divergence_bps for f in day_fills) / total_trades
        total_slippage_cost = sum(f.slippage_cost for f in day_fills)

        # Model accuracy: how close is model to actual?
        if avg_modeled_bps > 0:
            model_accuracy = max(0, 1 - abs(avg_divergence_bps) / avg_modeled_bps)
        else:
            model_accuracy = 1.0 if avg_slippage_bps == 0 else 0.0

        summary = DailySummary(
            date=date,
            total_trades=total_trades,
            total_notional=total_notional,
            avg_slippage_bps=avg_slippage_bps,
            avg_modeled_bps=avg_modeled_bps,
            avg_divergence_bps=avg_divergence_bps,
            model_accuracy=model_accuracy,
            total_slippage_cost=total_slippage_cost,
            worst_slippage_bps=max(f.slippage_bps for f in day_fills),
            best_slippage_bps=min(f.slippage_bps for f in day_fills),
        )

        self.daily_summaries[date] = summary
        self._save()

        return summary

    def get_weekly_summary(self) -> dict[str, Any]:
        """Get summary for the last 7 days."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        week_fills = [
            f
            for f in self.fills
            if start_date.isoformat() <= f.timestamp <= end_date.isoformat()
        ]

        if not week_fills:
            return {"error": "No fills in last 7 days"}

        total_trades = len(week_fills)
        avg_slippage_bps = sum(f.slippage_bps for f in week_fills) / total_trades
        avg_modeled_bps = sum(f.modeled_slippage_bps for f in week_fills) / total_trades
        avg_divergence_bps = sum(f.divergence_bps for f in week_fills) / total_trades

        # Model accuracy
        if avg_modeled_bps > 0:
            model_accuracy = max(0, 1 - abs(avg_divergence_bps) / avg_modeled_bps)
        else:
            model_accuracy = 1.0 if avg_slippage_bps == 0 else 0.0

        return {
            "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "total_trades": total_trades,
            "avg_slippage_bps": round(avg_slippage_bps, 2),
            "avg_modeled_bps": round(avg_modeled_bps, 2),
            "avg_divergence_bps": round(avg_divergence_bps, 2),
            "model_accuracy": round(model_accuracy, 4),
            "model_status": self._evaluate_model_status(avg_divergence_bps),
            "recommendation": self._get_recommendation(avg_divergence_bps, model_accuracy),
        }

    def _evaluate_model_status(self, avg_divergence_bps: float) -> str:
        """Evaluate if model is performing well."""
        abs_div = abs(avg_divergence_bps)
        if abs_div <= 1.0:
            return "EXCELLENT"
        elif abs_div <= 2.0:
            return "GOOD"
        elif abs_div <= 5.0:
            return "ACCEPTABLE"
        else:
            return "NEEDS_RECALIBRATION"

    def _get_recommendation(self, avg_divergence_bps: float, accuracy: float) -> str:
        """Get recommendation based on model performance."""
        if accuracy >= 0.9:
            return "Model performing well. No action needed."
        elif accuracy >= 0.7:
            return "Model acceptable. Monitor for trends."
        elif avg_divergence_bps > 0:
            return (
                f"Model UNDERESTIMATES slippage by {avg_divergence_bps:.1f}bps. "
                "Consider increasing base_spread_bps in SlippageModel."
            )
        else:
            return (
                f"Model OVERESTIMATES slippage by {abs(avg_divergence_bps):.1f}bps. "
                "Model is conservative (safe). Consider reducing for tighter backtests."
            )

    def check_model_health(self) -> dict[str, Any]:
        """
        Check if slippage model needs recalibration.

        Returns dict with:
            - healthy: bool
            - message: str
            - action_required: bool
        """
        weekly = self.get_weekly_summary()

        if "error" in weekly:
            return {
                "healthy": True,
                "message": "Insufficient data for model validation",
                "action_required": False,
            }

        status = weekly["model_status"]
        divergence = weekly["avg_divergence_bps"]

        if status == "NEEDS_RECALIBRATION":
            return {
                "healthy": False,
                "message": f"Model divergence {divergence:.1f}bps exceeds threshold",
                "action_required": True,
                "recommendation": weekly["recommendation"],
            }

        return {
            "healthy": True,
            "message": f"Model accuracy {weekly['model_accuracy']:.1%}",
            "action_required": False,
        }

    def get_symbol_analysis(self, symbol: str) -> dict[str, Any]:
        """Analyze slippage for a specific symbol."""
        symbol_fills = [f for f in self.fills if f.symbol.upper() == symbol.upper()]

        if not symbol_fills:
            return {"error": f"No fills for {symbol}"}

        total = len(symbol_fills)
        avg_slippage = sum(f.slippage_bps for f in symbol_fills) / total
        avg_divergence = sum(f.divergence_bps for f in symbol_fills) / total

        return {
            "symbol": symbol,
            "total_fills": total,
            "avg_slippage_bps": round(avg_slippage, 2),
            "avg_divergence_bps": round(avg_divergence, 2),
            "worst_fill_bps": max(f.slippage_bps for f in symbol_fills),
            "best_fill_bps": min(f.slippage_bps for f in symbol_fills),
        }


# Singleton instance for easy access
_tracker_instance: Optional[ExecutionCostTracker] = None


def get_cost_tracker() -> ExecutionCostTracker:
    """Get the global cost tracker instance."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = ExecutionCostTracker()
    return _tracker_instance
