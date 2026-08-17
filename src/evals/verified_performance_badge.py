"""Verified Performance Badge: Cryptographic proof-of-work receipt generator.

Inspired by community milestone verification (Earn Your Leisure / Institutional Audit):
Audits closed trades from verified ledgers (data/trades.json / put_credit_entries.json),
computes statistical health (sample size n, win rate, expectancy, profit factor, max drawdown),
and generates a cryptographically hashed milestone receipt without leaking secrets.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Sequence


@dataclass(frozen=True)
class PerformanceMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    total_realized_pnl: float
    expectancy_per_trade: float
    profit_factor: float
    max_drawdown_pct: float
    cohort_target: int = 30


@dataclass(frozen=True)
class MilestoneBadge:
    strategy_id: str
    stage: str  # "PAPER_VALIDATION", "COHORT_PROVEN", "LIVE_READY"
    verified_status: str  # "PASS", "IN_PROGRESS", "FAILED"
    milestone_name: str
    metrics: PerformanceMetrics
    ledger_sha256: str
    timestamp: str
    badge_hash: str
    criteria_met: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "stage": self.stage,
            "verified_status": self.verified_status,
            "milestone_name": self.milestone_name,
            "metrics": {
                "total_trades": self.metrics.total_trades,
                "winning_trades": self.metrics.winning_trades,
                "losing_trades": self.metrics.losing_trades,
                "win_rate_pct": self.metrics.win_rate_pct,
                "total_realized_pnl": self.metrics.total_realized_pnl,
                "expectancy_per_trade": self.metrics.expectancy_per_trade,
                "profit_factor": self.metrics.profit_factor,
                "max_drawdown_pct": self.metrics.max_drawdown_pct,
                "cohort_target": self.metrics.cohort_target,
            },
            "ledger_sha256": self.ledger_sha256,
            "timestamp": self.timestamp,
            "badge_hash": self.badge_hash,
            "criteria_met": list(self.criteria_met),
            "blockers": list(self.blockers),
        }

    def markdown_badge(self) -> str:
        icon = (
            "🏆"
            if self.verified_status == "PASS"
            else ("🟡" if self.verified_status == "IN_PROGRESS" else "🔴")
        )
        return (
            f"### {icon} Verified Milestone Receipt: {self.milestone_name}\n"
            f"- **Strategy**: `{self.strategy_id}`\n"
            f"- **Stage**: `{self.stage}` ({self.verified_status})\n"
            f"- **Cohort Progress**: {self.metrics.total_trades}/{self.metrics.cohort_target} trades\n"
            f"- **Realized P/L**: ${self.metrics.total_realized_pnl:,.2f} (Expectancy: ${self.metrics.expectancy_per_trade:.2f}/trade)\n"
            f"- **Win Rate / PF**: {self.metrics.win_rate_pct:.1f}% / {self.metrics.profit_factor:.2f}\n"
            f"- **Integrity Hash**: `{self.badge_hash[:16]}...`\n"
        )


def compute_metrics_from_trades(trades: Sequence[dict[str, Any]]) -> PerformanceMetrics:
    """Calculate core performance metrics from closed trade records."""
    if not trades:
        return PerformanceMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate_pct=0.0,
            total_realized_pnl=0.0,
            expectancy_per_trade=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
        )

    pnls = [float(t.get("pnl", 0.0) or t.get("realized_pnl", 0.0)) for t in trades]
    total_trades = len(pnls)
    winning = [p for p in pnls if p > 0]
    losing = [p for p in pnls if p < 0]

    win_count = len(winning)
    loss_count = len(losing)
    win_rate = (win_count / total_trades) * 100.0 if total_trades > 0 else 0.0
    total_pnl = sum(pnls)
    expectancy = total_pnl / total_trades if total_trades > 0 else 0.0

    gross_profit = sum(winning)
    gross_loss = abs(sum(losing))
    profit_factor = (
        (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    )

    # Max Drawdown calculation
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    max_dd_pct = (max_dd / peak * 100.0) if peak > 0 else 0.0

    return PerformanceMetrics(
        total_trades=total_trades,
        winning_trades=win_count,
        losing_trades=loss_count,
        win_rate_pct=round(win_rate, 2),
        total_realized_pnl=round(total_pnl, 2),
        expectancy_per_trade=round(expectancy, 2),
        profit_factor=round(profit_factor, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
    )


def generate_milestone_badge(
    strategy_id: str,
    trades: Sequence[dict[str, Any]],
    target_cohort_size: int = 30,
) -> MilestoneBadge:
    """Generate a verifiable cryptographic proof-of-work badge."""
    metrics = compute_metrics_from_trades(trades)
    now_iso = datetime.now(UTC).isoformat()

    # Hash the trade content for tamper-proof verification
    ledger_str = json.dumps(trades, sort_keys=True, default=str)
    ledger_sha256 = hashlib.sha256(ledger_str.encode("utf-8")).hexdigest()

    criteria_met: list[str] = []
    blockers: list[str] = []

    if metrics.total_trades >= target_cohort_size:
        criteria_met.append(
            f"Sample size requirement satisfied ({metrics.total_trades}/{target_cohort_size})"
        )
    else:
        blockers.append(f"Cohort incomplete: {metrics.total_trades}/{target_cohort_size} trades")

    if metrics.expectancy_per_trade > 0:
        criteria_met.append(
            f"Positive expectancy proven (${metrics.expectancy_per_trade:.2f}/trade)"
        )
    else:
        blockers.append(f"Non-positive expectancy (${metrics.expectancy_per_trade:.2f}/trade)")

    if metrics.profit_factor >= 1.05:
        criteria_met.append(f"Profit factor healthy ({metrics.profit_factor:.2f})")
    else:
        blockers.append(f"Profit factor below threshold ({metrics.profit_factor:.2f} < 1.05)")

    if not blockers and metrics.total_trades >= target_cohort_size:
        stage = "COHORT_PROVEN"
        status = "PASS"
        milestone = "Green Jacket Tier 1: Verified Paper Cohort Proven"
    elif metrics.total_trades > 0:
        stage = "PAPER_VALIDATION"
        status = "IN_PROGRESS"
        milestone = f"Paper Cohort Validation ({metrics.total_trades}/{target_cohort_size})"
    else:
        stage = "PAPER_VALIDATION"
        status = "IN_PROGRESS"
        milestone = "Zero Closes: Cohort Initializing"

    badge_payload = {
        "strategy_id": strategy_id,
        "stage": stage,
        "metrics": metrics.__dict__,
        "ledger_sha256": ledger_sha256,
        "timestamp": now_iso,
    }
    badge_hash = hashlib.sha256(
        json.dumps(badge_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return MilestoneBadge(
        strategy_id=strategy_id,
        stage=stage,
        verified_status=status,
        milestone_name=milestone,
        metrics=metrics,
        ledger_sha256=ledger_sha256,
        timestamp=now_iso,
        badge_hash=badge_hash,
        criteria_met=criteria_met,
        blockers=blockers,
    )
