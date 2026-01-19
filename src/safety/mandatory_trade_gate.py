"""Mandatory Trade Gate - validates trades before execution.

This gate is called by AlpacaExecutor before every trade to ensure
compliance with risk rules, RAG lessons, and position limits.

ENFORCEMENT (Jan 2026): This is the FINAL checkpoint before execution.
No trade bypasses this gate. It enforces:
- Ticker whitelist (SPY/IWM only per CLAUDE.md strategy) - Jan 15, 2026
- Position size limits (max 5% of portfolio per position per CLAUDE.md)
- Daily loss limits (max 5% of portfolio per day)
- RAG lesson blocking (CRITICAL lessons block trades)
- Blind trading prevention (no $0 equity trades)
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# TICKER WHITELIST - CRITICAL ENFORCEMENT (Jan 15, 2026)
# Per CLAUDE.md: "CREDIT SPREADS on SPY/IWM ONLY"
# This prevents trades like SOFI that violated strategy
# UPDATED Jan 19: Import from central config (single source of truth)
# ============================================================
try:
    from src.core.trading_constants import ALLOWED_TICKERS
except ImportError:
    # Fallback if constants unavailable (shouldn't happen in production)
    ALLOWED_TICKERS = {"SPY", "IWM"}  # Per CLAUDE.md strategy
TICKER_WHITELIST_ENABLED = True  # Toggle for paper testing


def validate_ticker(symbol: str) -> tuple[bool, str]:
    """
    Validate ticker is in allowed whitelist.

    Only allow SPY and IWM trades per CLAUDE.md strategy.
    Handles both stock symbols and OCC option symbols.

    Args:
        symbol: Stock ticker or OCC option symbol (e.g., "SPY", "SPY260115P00585000")

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not TICKER_WHITELIST_ENABLED:
        return True, ""

    # Extract underlying from options symbol (OCC format)
    underlying = _extract_underlying(symbol)

    if underlying not in ALLOWED_TICKERS:
        return False, f"{underlying} not allowed. Strategy permits SPY/IWM only."
    return True, ""


def _extract_underlying(symbol: str) -> str:
    """
    Extract underlying symbol from option symbol (OCC format).

    OCC format: [UNDERLYING][YYMMDD][P/C][STRIKE*1000]
    Example: SOFI260206P00024000 -> SOFI
    Example: SPY260115C00600000 -> SPY

    Args:
        symbol: Stock or option symbol

    Returns:
        Underlying ticker symbol in uppercase
    """
    # Standard equity symbols pass through unchanged
    if len(symbol) <= 6:
        return symbol.upper()

    # Try to match OCC option format
    # Pattern: underlying (1-6 chars) + YYMMDD + P/C + 8 digit strike
    match = re.match(r"^([A-Z]{1,6})(\d{6})[PC](\d{8})$", symbol.upper())
    if match:
        return match.group(1)

    # Fallback: if it looks like it has a date embedded, try to extract
    if len(symbol) >= 15:
        # Last 15 chars are: YYMMDD (6) + P/C (1) + Strike (8)
        potential_underlying = symbol[:-15]
        if potential_underlying and potential_underlying.isalpha():
            return potential_underlying.upper()

    return symbol.upper()


@dataclass
class GateResult:
    """Result of mandatory trade gate validation."""

    approved: bool
    reason: str = ""
    rag_warnings: list = field(default_factory=list)
    ml_anomalies: list = field(default_factory=list)
    confidence: float = 1.0
    checks_performed: list = field(default_factory=list)


class TradeBlockedError(Exception):
    """Exception raised when trade is blocked by mandatory gate."""

    def __init__(self, gate_result: GateResult):
        self.gate_result = gate_result
        super().__init__(gate_result.reason)


# Configuration - HARDCODED from central constants (NO ENV VAR OVERRIDE)
# SECURITY FIX Jan 19, 2026: Removed env var bypass that allowed overriding position limits
# Per CLAUDE.md and LL-244 adversarial audit: These limits are NON-NEGOTIABLE
try:
    from src.constants.trading_thresholds import PositionSizing
    MAX_POSITION_PCT = PositionSizing.MAX_POSITION_PCT  # 5% max per CLAUDE.md
    MAX_DAILY_LOSS_PCT = PositionSizing.MAX_DAILY_LOSS_PCT  # 2% max daily loss
except ImportError:
    # Fallback - STILL HARDCODED, not from env var
    MAX_POSITION_PCT = 0.05  # 5% max per CLAUDE.md - HARDCODED
    MAX_DAILY_LOSS_PCT = 0.02  # 2% max daily loss - HARDCODED
    logger.warning("Using fallback position limits - constants module unavailable")

MIN_TRADE_AMOUNT = 1.0  # $1 minimum trade - HARDCODED

# Track daily losses (reset daily in production)
# SECURITY FIX (Jan 19, 2026): Added thread lock to prevent race condition
# where concurrent trades could bypass daily loss limit
import threading

_daily_loss_lock = threading.Lock()
_daily_loss_tracker: dict[str, float] = {"total": 0.0, "date": ""}


def _reset_daily_tracker_if_needed():
    """Reset daily loss tracker at start of new day. Thread-safe."""
    from datetime import date

    # Lock is acquired by caller (_check_daily_loss_limit)
    today = str(date.today())
    if _daily_loss_tracker["date"] != today:
        _daily_loss_tracker["total"] = 0.0
        _daily_loss_tracker["date"] = today


def _check_position_size(symbol: str, amount: float, equity: float) -> tuple[bool, str]:
    """Check if position size is within limits."""
    if equity <= 0:
        return False, "Cannot calculate position size with zero equity"

    position_pct = amount / equity
    max_amount = equity * MAX_POSITION_PCT

    if position_pct > MAX_POSITION_PCT:
        return False, (
            f"Position ${amount:.2f} ({position_pct:.1%}) exceeds "
            f"max {MAX_POSITION_PCT:.0%} (${max_amount:.2f})"
        )

    return True, f"Position size OK: ${amount:.2f} ({position_pct:.1%})"


def _check_daily_loss_limit(equity: float, potential_loss: float = 0.0) -> tuple[bool, str]:
    """Check if daily loss limit would be exceeded. Thread-safe."""
    # SECURITY FIX (Jan 19, 2026): Use lock to prevent race condition
    with _daily_loss_lock:
        _reset_daily_tracker_if_needed()

        if equity <= 0:
            return False, "Cannot calculate daily loss with zero equity"

        max_loss = equity * MAX_DAILY_LOSS_PCT
        projected_loss = _daily_loss_tracker["total"] + potential_loss

        if projected_loss > max_loss:
            return False, (
                f"Daily loss ${projected_loss:.2f} would exceed "
                f"max {MAX_DAILY_LOSS_PCT:.0%} (${max_loss:.2f})"
            )

        return True, f"Daily loss OK: ${projected_loss:.2f} of ${max_loss:.2f} limit"


def _query_rag_for_blocking_lessons(symbol: str, strategy: str) -> tuple[bool, list[str]]:
    """
    Query RAG for lessons that should block this trade.

    Returns:
        (should_block, warnings_list)
    """
    warnings = []
    should_block = False

    try:
        # Try to import and query the lessons RAG
        from src.rag.lessons_rag import LessonsRAG

        rag = LessonsRAG()
        query = f"{symbol} {strategy} trading mistakes critical"
        results = rag.search(query=query, top_k=3)

        for lesson, score in results or []:
            if score > 0.15:  # Relevance threshold
                severity = getattr(lesson, "severity", "MEDIUM").upper()
                title = getattr(lesson, "title", "Unknown lesson")

                if severity == "CRITICAL" and score > 0.5:
                    should_block = True
                    warnings.append(f"[CRITICAL] {title} (score={score:.2f}) - BLOCKING")
                elif severity == "HIGH" and score > 0.7:
                    should_block = True
                    warnings.append(f"[HIGH] {title} (score={score:.2f}) - BLOCKING")
                elif severity in ("HIGH", "CRITICAL"):
                    warnings.append(f"[{severity}] {title} (score={score:.2f})")

    except ImportError:
        logger.debug("LessonsRAG not available - skipping RAG check")
    except Exception as e:
        logger.debug(f"RAG query failed (non-fatal): {e}")

    return should_block, warnings


def validate_trade_mandatory(
    symbol: str,
    amount: float,
    side: str,
    strategy: str,
    context: dict[str, Any] | None = None,
) -> GateResult:
    """
    Validate trade against mandatory safety checks.

    This is the FINAL checkpoint before execution. All trades must pass.

    Args:
        symbol: Trading symbol (e.g., "SPY", "SOFI260206P00024000")
        amount: Trade notional value in dollars
        side: Trade side ("BUY" or "SELL")
        strategy: Strategy name (e.g., "CSP", "momentum")
        context: Optional account context with equity, positions, etc.

    Returns:
        GateResult with approval status and any warnings
    """
    warnings: list[str] = []
    checks_performed: list[str] = []

    # =========================================================================
    # CHECK 0: TICKER WHITELIST (Jan 15, 2026 - per CLAUDE.md)
    # Per CLAUDE.md: "CREDIT SPREADS on SPY/IWM ONLY"
    # This is the FIRST check - reject non-allowed tickers immediately
    # =========================================================================
    ticker_valid, ticker_error = validate_ticker(symbol)
    if not ticker_valid:
        logger.warning(f"🚫 TICKER BLOCKED: {ticker_error}")
        return GateResult(
            approved=False,
            reason=f"TICKER NOT ALLOWED: {ticker_error}",
            checks_performed=["ticker_whitelist: BLOCKED"],
        )
    checks_performed.append(f"ticker_whitelist: PASS ({_extract_underlying(symbol)})")

    # =========================================================================
    # CHECK 1: Basic sanity checks
    # =========================================================================
    if amount < MIN_TRADE_AMOUNT:
        return GateResult(
            approved=False,
            reason=f"Trade amount ${amount:.2f} below minimum ${MIN_TRADE_AMOUNT:.2f}",
            checks_performed=["sanity_check"],
        )

    if side not in ("BUY", "SELL"):
        return GateResult(
            approved=False,
            reason=f"Invalid trade side: {side}",
            checks_performed=["sanity_check"],
        )

    checks_performed.append("sanity_check: PASS")

    # =========================================================================
    # CHECK 2: Blind trading prevention (ll_051)
    # =========================================================================
    equity = context.get("equity", 0) if context else 0

    if equity == 0:
        return GateResult(
            approved=False,
            reason="Cannot trade with $0 equity (blind trading prevention - ll_051)",
            rag_warnings=["ll_051: Blind trading prevention"],
            checks_performed=checks_performed + ["equity_check: FAIL"],
        )

    checks_performed.append(f"equity_check: PASS (${equity:.2f})")

    # =========================================================================
    # CHECK 3: Position size limit
    # =========================================================================
    position_ok, position_msg = _check_position_size(symbol, amount, equity)

    if not position_ok:
        return GateResult(
            approved=False,
            reason=position_msg,
            checks_performed=checks_performed + ["position_size: FAIL"],
        )

    checks_performed.append("position_size: PASS")

    # =========================================================================
    # CHECK 4: Daily loss limit (for new positions)
    # =========================================================================
    if side == "BUY":
        # Assume worst case: lose 10% of position (stop loss)
        potential_loss = amount * 0.10
        loss_ok, loss_msg = _check_daily_loss_limit(equity, potential_loss)

        if not loss_ok:
            return GateResult(
                approved=False,
                reason=loss_msg,
                checks_performed=checks_performed + ["daily_loss: FAIL"],
            )

        checks_performed.append("daily_loss: PASS")

    # =========================================================================
    # CHECK 5: RAG lesson blocking
    # =========================================================================
    rag_block, rag_warnings = _query_rag_for_blocking_lessons(symbol, strategy)
    warnings.extend(rag_warnings)

    if rag_block:
        return GateResult(
            approved=False,
            reason=f"Trade blocked by RAG lesson: {rag_warnings[0] if rag_warnings else 'Unknown'}",
            rag_warnings=rag_warnings,
            checks_performed=checks_performed + ["rag_check: BLOCKED"],
        )

    checks_performed.append(f"rag_check: PASS ({len(rag_warnings)} warnings)")

    # =========================================================================
    # ALL CHECKS PASSED
    # =========================================================================
    logger.info(f"✅ Mandatory gate APPROVED: {side} ${amount:.2f} {symbol} ({strategy})")

    return GateResult(
        approved=True,
        reason="Trade approved - all mandatory checks passed",
        rag_warnings=warnings,
        checks_performed=checks_performed,
        confidence=1.0 if not warnings else 0.8,
    )


def record_trade_loss(loss_amount: float):
    """Record a trade loss for daily tracking. Thread-safe."""
    # SECURITY FIX (Jan 19, 2026): Use lock to prevent race condition
    with _daily_loss_lock:
        _reset_daily_tracker_if_needed()
        _daily_loss_tracker["total"] += abs(loss_amount)
        logger.info(f"Daily loss updated: ${_daily_loss_tracker['total']:.2f}")
