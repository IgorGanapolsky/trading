"""Deterministic statistical evidence for trading edge and income planning."""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class EdgeStatistics:
    sample_size: int
    wins: int
    losses: int
    breakeven: int
    total_realized_pnl: float
    expectancy_per_trade: float | None
    expectancy_lower_95: float | None
    expectancy_upper_95: float | None
    profit_factor: float | None
    win_rate_pct: float | None
    average_win: float | None
    average_loss: float | None
    max_closed_trade_drawdown: float

    def as_dict(self) -> dict:
        return asdict(self)


def _finite_pnls(values: Iterable[float]) -> list[float]:
    result: list[float] = []
    for value in values:
        parsed = float(value)
        if math.isfinite(parsed):
            result.append(parsed)
    return result


def to_json_safe(value: Any) -> Any:
    """Return a standards-compliant JSON view without changing metric math.

    Profit factor is mathematically infinite when a non-empty sample has no
    losing trades. JSON has no numeric infinity literal, so serialization
    boundaries encode it explicitly as a string while in-process analytics
    retain ``math.inf`` for comparisons and golden-answer tests.
    """
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return None
        return "Infinity" if value > 0 else "-Infinity"
    if isinstance(value, dict):
        return {key: to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_safe(item) for item in value]
    return value


def closed_trade_max_drawdown(pnls: Iterable[float]) -> float:
    """Maximum peak-to-trough loss in cumulative closed-trade P/L dollars."""
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for pnl in _finite_pnls(pnls):
        equity += pnl
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return round(worst, 2)


def calculate_edge_statistics(pnls: Iterable[float]) -> EdgeStatistics:
    """Calculate row-derived edge statistics with a conservative 95% mean CI.

    The interval is intentionally undefined below two observations and is not a
    substitute for multi-regime or out-of-sample validation. It prevents a
    positive point estimate from being treated as proven positive expectancy.
    """
    values = _finite_pnls(pnls)
    n = len(values)
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    breakeven = n - len(wins) - len(losses)
    total = sum(values)
    mean = statistics.fmean(values) if values else None
    lower: float | None = None
    upper: float | None = None
    if n >= 2 and mean is not None:
        standard_error = statistics.stdev(values) / math.sqrt(n)
        # A fixed normal critical value is deterministic and conservative at
        # the n>=100 desk-grade gate. Small samples are never live-eligible.
        margin = 1.96 * standard_error
        lower = mean - margin
        upper = mean + margin
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss else (math.inf if wins else None)
    return EdgeStatistics(
        sample_size=n,
        wins=len(wins),
        losses=len(losses),
        breakeven=breakeven,
        total_realized_pnl=round(total, 2),
        expectancy_per_trade=round(mean, 4) if mean is not None else None,
        expectancy_lower_95=round(lower, 4) if lower is not None else None,
        expectancy_upper_95=round(upper, 4) if upper is not None else None,
        profit_factor=round(profit_factor, 4) if profit_factor is not None else None,
        win_rate_pct=round(len(wins) / n * 100.0, 2) if n else None,
        average_win=round(statistics.fmean(wins), 2) if wins else None,
        average_loss=round(statistics.fmean(losses), 2) if losses else None,
        max_closed_trade_drawdown=closed_trade_max_drawdown(values),
    )


def required_pretax_monthly(after_tax_target: float, tax_reserve_rate: float) -> float:
    """Return the pre-tax realized profit required by the configured reserve."""
    target = max(0.0, float(after_tax_target))
    rate = float(tax_reserve_rate)
    if not 0.0 <= rate < 1.0:
        raise ValueError("tax_reserve_rate must be in [0, 1)")
    return round(target / (1.0 - rate), 2)
