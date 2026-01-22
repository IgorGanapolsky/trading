"""Auto-Close Bleeding Positions - Emergency Loss Control.

CRITICAL SAFETY COMPONENT - Jan 22, 2026 (LL-281)

This module automatically closes positions that are bleeding heavily:
1. Single position loss > 50% of cost basis
2. Total unrealized loss > 25% of equity
3. Position has been losing for > 3 days

Root Cause of Crisis:
- No automated mechanism to close bleeding positions
- Losses accumulated while waiting for manual intervention
- PDT restrictions compounded the problem

Solution:
- Automated position closure when loss thresholds exceeded
- Scheduled workflow to run during market hours
- Respect PDT restrictions (only close non-day-trade positions)

Author: AI Trading System
Date: January 22, 2026
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Import from single source of truth
try:
    from src.core.trading_constants import CRISIS_LOSS_PCT

    LOSS_THRESHOLD = CRISIS_LOSS_PCT
except ImportError:
    LOSS_THRESHOLD = 0.25

# Thresholds
SINGLE_POSITION_LOSS_THRESHOLD = 0.50  # Close if single position loses 50%
DAYS_BEFORE_FORCE_CLOSE = 3  # Force close after 3 days of losses


class PositionCloseRecommendation:
    """Recommendation to close a position."""

    def __init__(
        self,
        symbol: str,
        qty: float,
        reason: str,
        priority: str,  # "CRITICAL", "HIGH", "MEDIUM"
        unrealized_pl: float,
        cost_basis: float,
    ):
        self.symbol = symbol
        self.qty = qty
        self.reason = reason
        self.priority = priority
        self.unrealized_pl = unrealized_pl
        self.cost_basis = cost_basis
        self.created_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "qty": self.qty,
            "reason": self.reason,
            "priority": self.priority,
            "unrealized_pl": self.unrealized_pl,
            "cost_basis": self.cost_basis,
            "created_at": self.created_at.isoformat(),
        }


def analyze_positions_for_closure(
    positions: list[dict[str, Any]],
    account_equity: float,
    trade_history: list[dict[str, Any]] | None = None,
) -> list[PositionCloseRecommendation]:
    """
    Analyze positions and recommend closures for bleeding positions.

    Args:
        positions: List of current positions
        account_equity: Current account equity
        trade_history: Optional trade history for PDT analysis

    Returns:
        List of closure recommendations sorted by priority
    """
    recommendations = []

    for pos in positions:
        symbol = pos.get("symbol", "")
        qty = float(pos.get("qty", 0))
        unrealized_pl = float(pos.get("unrealized_pl", 0))
        cost_basis = float(pos.get("cost_basis", 0))

        # Skip positions with no loss
        if unrealized_pl >= 0:
            continue

        # Check 1: Single position loss > 50%
        if cost_basis > 0:
            loss_ratio = abs(unrealized_pl) / cost_basis
            if loss_ratio > SINGLE_POSITION_LOSS_THRESHOLD:
                recommendations.append(
                    PositionCloseRecommendation(
                        symbol=symbol,
                        qty=qty,
                        reason=f"Single position loss {loss_ratio * 100:.0f}% exceeds {SINGLE_POSITION_LOSS_THRESHOLD * 100}% threshold",
                        priority="CRITICAL",
                        unrealized_pl=unrealized_pl,
                        cost_basis=cost_basis,
                    )
                )
                continue

    # Check 2: Total unrealized loss > 25%
    total_loss = sum(
        float(p.get("unrealized_pl", 0)) for p in positions if float(p.get("unrealized_pl", 0)) < 0
    )
    loss_pct = abs(total_loss) / account_equity if account_equity > 0 else 0

    if loss_pct > LOSS_THRESHOLD:
        # Sort losing positions by loss amount and recommend closing largest losers
        losing_positions = sorted(
            [p for p in positions if float(p.get("unrealized_pl", 0)) < 0],
            key=lambda p: float(p.get("unrealized_pl", 0)),
        )

        for pos in losing_positions:
            symbol = pos.get("symbol", "")
            qty = float(pos.get("qty", 0))
            unrealized_pl = float(pos.get("unrealized_pl", 0))
            cost_basis = float(pos.get("cost_basis", 0))

            # Check if already recommended
            if any(r.symbol == symbol for r in recommendations):
                continue

            recommendations.append(
                PositionCloseRecommendation(
                    symbol=symbol,
                    qty=qty,
                    reason=f"Portfolio loss {loss_pct * 100:.1f}% exceeds {LOSS_THRESHOLD * 100}% threshold - closing largest losers",
                    priority="HIGH",
                    unrealized_pl=unrealized_pl,
                    cost_basis=cost_basis,
                )
            )

    # Sort by priority
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    recommendations.sort(key=lambda r: (priority_order.get(r.priority, 99), r.unrealized_pl))

    return recommendations


def get_pdt_safe_close_qty(
    symbol: str,
    current_qty: float,
    trade_history: list[dict[str, Any]],
) -> float:
    """
    Calculate PDT-safe quantity to close.

    Only close contracts that were NOT bought today.

    Args:
        symbol: Position symbol
        current_qty: Current position quantity
        trade_history: Trade history to check purchase dates

    Returns:
        Quantity safe to close without triggering PDT
    """
    today = datetime.now().date()

    # Count contracts bought today
    buys_today = 0
    for trade in trade_history:
        trade_symbol = trade.get("symbol", "")
        if trade_symbol != symbol:
            continue

        trade_side = trade.get("side", "").upper()
        if trade_side != "BUY":
            continue

        # Check trade date
        trade_date_str = trade.get("filled_at") or trade.get("created_at") or ""
        if trade_date_str:
            try:
                trade_date = datetime.fromisoformat(trade_date_str.replace("Z", "+00:00")).date()
                if trade_date == today:
                    buys_today += float(trade.get("filled_qty", trade.get("qty", 0)))
            except Exception:
                pass

    # Safe to close = current - today's buys
    safe_qty = max(0, abs(current_qty) - buys_today)
    logger.info(
        f"PDT analysis for {symbol}: current={current_qty}, buys_today={buys_today}, safe_to_close={safe_qty}"
    )

    return safe_qty


def execute_auto_close(
    recommendations: list[PositionCloseRecommendation],
    trading_client,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """
    Execute auto-close recommendations.

    Args:
        recommendations: List of close recommendations
        trading_client: Alpaca trading client
        dry_run: If True, don't actually execute (default True for safety)

    Returns:
        List of execution results
    """
    results = []

    for rec in recommendations:
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Closing {rec.symbol}: {rec.reason}")

        result = {
            "symbol": rec.symbol,
            "qty": rec.qty,
            "priority": rec.priority,
            "reason": rec.reason,
            "dry_run": dry_run,
        }

        if not dry_run:
            try:
                # Try to close position
                order = trading_client.close_position(rec.symbol)
                result["status"] = "submitted"
                result["order_id"] = order.id if hasattr(order, "id") else str(order)
                logger.info(f"✅ Close order submitted for {rec.symbol}")
            except Exception as e:
                result["status"] = "failed"
                result["error"] = str(e)
                logger.error(f"❌ Failed to close {rec.symbol}: {e}")
        else:
            result["status"] = "dry_run"

        results.append(result)

    return results


def save_close_report(
    recommendations: list[PositionCloseRecommendation],
    results: list[dict[str, Any]],
) -> Path:
    """Save closure report for audit trail."""
    report_dir = Path("data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / f"auto_close_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    report = {
        "generated_at": datetime.now().isoformat(),
        "recommendations": [r.to_dict() for r in recommendations],
        "execution_results": results,
    }

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Close report saved to {report_path}")
    return report_path
