"""
P/L Validator - Prevents false claims about trading performance.

Created: Feb 6, 2026
Root cause: Claude made incorrect P/L projections by:
  1. Projecting 4.3%/month from 7 days of data
  2. Misattributing pre-existing position gains to iron condor trading

This module decomposes P/L by source and flags rule violations.
All P/L claims MUST go through validate_pl_report() before being presented.
"""

import logging
import re
from dataclasses import dataclass, field

from src.core.trading_constants import ALLOWED_TICKERS, extract_underlying

logger = logging.getLogger(__name__)

# Minimum completed iron condor trades before any projection is allowed
MIN_TRADES_FOR_PROJECTION = 30


@dataclass
class OrderClassification:
    """Classification of a single order."""

    symbol: str
    side: str
    qty: float
    filled_price: float
    created_at: str
    is_spy_option: bool = False
    is_iron_condor_leg: bool = False
    violation_reason: str = ""


@dataclass
class PLReport:
    """Decomposed P/L report with compliance check."""

    total_equity: float = 0.0
    starting_equity: float = 0.0
    total_pl: float = 0.0
    compliant_orders: list = field(default_factory=list)
    violating_orders: list = field(default_factory=list)
    total_orders: int = 0
    completed_iron_condors: int = 0
    can_project: bool = False
    violations_summary: str = ""


def extract_base_ticker(option_symbol: str) -> str:
    """Extract the base ticker from an options symbol like SPY260220P00660000."""
    return extract_underlying(option_symbol)


def is_spy_option(symbol: str) -> bool:
    """Check if a symbol is a SPY/SPX/XSP option."""
    return bool(re.match(r"^(SPY|SPX|SPXW?|XSP)\d{6}[PC]\d{8}$", symbol))


def classify_order(order) -> OrderClassification:
    """Classify a single Alpaca order for compliance."""
    symbol = order.get("symbol", "") if isinstance(order, dict) else str(order.symbol)
    side = order.get("side", "") if isinstance(order, dict) else str(order.side)
    qty = (
        float(order.get("qty", 0) or order.get("filled_qty", 0))
        if isinstance(order, dict)
        else float(order.qty or 0)
    )
    filled = (
        float(order.get("filled_avg_price", 0) or 0)
        if isinstance(order, dict)
        else float(order.filled_avg_price or 0)
    )
    created = order.get("created_at", "") if isinstance(order, dict) else str(order.created_at)

    classification = OrderClassification(
        symbol=symbol,
        side=side,
        qty=qty,
        filled_price=filled,
        created_at=created,
    )

    # Check if it's a SPY option
    if is_spy_option(symbol):
        classification.is_spy_option = True
        classification.is_iron_condor_leg = True
        return classification

    # Check if it's an allowed underlying stock (not option)
    if symbol in ALLOWED_TICKERS:
        classification.violation_reason = f"{symbol} stock trade (not an iron condor option)"
        return classification

    # Check if it's a non-allowed option
    base = extract_base_ticker(symbol)
    if base != symbol and base not in ALLOWED_TICKERS:
        classification.violation_reason = f"Non-allowed option ({base})"
        return classification

    # Non-allowed stock/crypto/ETF
    if symbol not in ALLOWED_TICKERS:
        classification.violation_reason = f"Non-allowed instrument: {symbol}"
        return classification

    return classification


def count_completed_iron_condors(orders: list) -> int:
    """
    Count completed iron condor trades from order history.

    An iron condor = 4 SPY option legs opened together (within same minute).
    A completed iron condor = opened AND closed.
    """
    spy_option_groups: dict[str, list] = {}

    for order in orders:
        symbol = order.get("symbol", "") if isinstance(order, dict) else str(order.symbol)
        created = (
            order.get("created_at", "")[:16]
            if isinstance(order, dict)
            else str(order.created_at)[:16]
        )
        status = order.get("status", "") if isinstance(order, dict) else str(order.status)

        if not is_spy_option(symbol):
            continue
        if "filled" not in str(status).lower():
            continue

        if created not in spy_option_groups:
            spy_option_groups[created] = []
        spy_option_groups[created].append(symbol)

    # Count groups with exactly 4 legs (iron condor)
    condor_count = sum(1 for legs in spy_option_groups.values() if len(legs) == 4)
    return condor_count


def validate_pl_report(
    orders: list,
    current_equity: float,
    starting_equity: float,
) -> PLReport:
    """
    Validate and decompose P/L from Alpaca order history.

    This MUST be called before presenting any P/L claims.
    It separates compliant iron condor trades from rule violations.

    Args:
        orders: List of Alpaca order objects or dicts
        current_equity: Current account equity
        starting_equity: Starting account equity (base_value)

    Returns:
        PLReport with full decomposition and compliance status
    """
    report = PLReport(
        total_equity=current_equity,
        starting_equity=starting_equity,
        total_pl=current_equity - starting_equity,
        total_orders=len(orders),
    )

    for order in orders:
        status = order.get("status", "") if isinstance(order, dict) else str(order.status)
        if "filled" not in str(status).lower():
            continue

        classification = classify_order(order)

        if classification.violation_reason:
            report.violating_orders.append(classification)
        else:
            report.compliant_orders.append(classification)

    report.completed_iron_condors = count_completed_iron_condors(orders)
    report.can_project = report.completed_iron_condors >= MIN_TRADES_FOR_PROJECTION

    # Build violations summary
    if report.violating_orders:
        violation_types: dict[str, int] = {}
        for v in report.violating_orders:
            reason = v.violation_reason
            violation_types[reason] = violation_types.get(reason, 0) + 1
        lines = [
            f"  - {reason}: {count} orders" for reason, count in sorted(violation_types.items())
        ]
        report.violations_summary = "\n".join(lines)

    return report


def format_pl_report(report: PLReport) -> str:
    """Format a PLReport as a human-readable string."""
    lines = [
        f"Account: ${report.total_equity:,.2f} (started ${report.starting_equity:,.2f})",
        f"Total P/L: ${report.total_pl:,.2f}",
        f"Total orders: {report.total_orders}",
        f"Compliant SPY option orders: {len(report.compliant_orders)}",
        f"Violating orders: {len(report.violating_orders)}",
        f"Completed iron condors: {report.completed_iron_condors}",
    ]

    if report.violations_summary:
        lines.append(f"\nRule Violations:\n{report.violations_summary}")

    if not report.can_project:
        lines.append(
            f"\nProjection BLOCKED: {report.completed_iron_condors}/{MIN_TRADES_FOR_PROJECTION} "
            f"completed iron condors. Need {MIN_TRADES_FOR_PROJECTION} before any return projection."
        )

    return "\n".join(lines)
