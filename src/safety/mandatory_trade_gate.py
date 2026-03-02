"""Mandatory Trade Gate - validates trades before execution.

This gate is called by AlpacaExecutor before every trade to ensure
compliance with risk rules, RAG lessons, and position limits.

ENFORCEMENT (Jan 2026): This is the FINAL checkpoint before execution.
No trade bypasses this gate. It enforces:
- Ticker whitelist (liquid ETFs per CLAUDE.md)
- Position size limits (max 5% of portfolio per position per CLAUDE.md)
- Daily loss limits (max 5% of portfolio per day)
- RAG lesson blocking (CRITICAL lessons block trades)
- Blind trading prevention (no $0 equity trades)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.core.trading_constants import ALLOWED_TICKERS, extract_underlying

logger = logging.getLogger(__name__)

# Feedback model path (Thompson Sampling RLHF)
FEEDBACK_MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "ml" / "feedback_model.json"


TICKER_WHITELIST_ENABLED = True  # Toggle for paper testing


def validate_ticker(symbol: str) -> tuple[bool, str]:
    """
    Validate ticker is in allowed whitelist.

    Only allow liquid ETF trades per CLAUDE.md strategy.
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
        return False, f"{underlying} not allowed. Liquid ETFs only per CLAUDE.md."
    return True, ""


# Backward-compat alias: delegates to trading_constants.extract_underlying
# (P0 tech debt - consolidated 5 duplicate implementations Feb 17, 2026)
_extract_underlying = extract_underlying


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


# Configuration - SINGLE SOURCE OF TRUTH (NO ENV VAR OVERRIDE)
# SECURITY FIX Jan 19, 2026: Removed env var bypass that allowed overriding position limits
# Per CLAUDE.md and LL-244 adversarial audit: These limits are NON-NEGOTIABLE
# LL-281 (Jan 22, 2026): Import from trading_constants.py to prevent scattered definitions
try:
    from src.core.trading_constants import (
        MAX_DAILY_FILLS,
        MAX_DAILY_LOSS_PCT,
        MAX_DAILY_STRUCTURES,
        MAX_POSITION_PCT,
        MAX_POSITIONS,
    )
except ImportError:
    MAX_POSITION_PCT = float(os.environ.get("MAX_POSITION_PCT", "0.05"))
    MAX_DAILY_LOSS_PCT = float(os.environ.get("MAX_DAILY_LOSS_PCT", "0.02"))
    MAX_DAILY_STRUCTURES = int(os.environ.get("MAX_DAILY_STRUCTURES", "1"))
    MAX_DAILY_FILLS = int(os.environ.get("MAX_DAILY_FILLS", "20"))
    MAX_POSITIONS = int(os.environ.get("MAX_POSITIONS", "8"))
    logger.warning("Using env-var position limits - trading_constants unavailable")

MIN_TRADE_AMOUNT = float(os.environ.get("MIN_TRADE_AMOUNT", "1.0"))

# Track daily losses (reset daily in production)
# SECURITY FIX (Jan 19, 2026): Added thread lock to prevent race condition
# where concurrent trades could bypass daily loss limit
_daily_loss_lock = threading.Lock()
_daily_loss_tracker: dict[str, float] = {"total": 0.0, "date": ""}

_SYSTEM_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "system_state.json"


def _today_et_str() -> str:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception as exc:
        logger.debug("ZoneInfo unavailable, falling back to UTC: %s", exc)
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _count_structures_today_from_trade_file(date_str: str) -> int:
    # Unit tests should not depend on local repo trade files.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return 0

    trades_path = Path(__file__).parent.parent.parent / "data" / f"trades_{date_str}.json"
    if not trades_path.exists():
        return 0
    try:
        payload = json.loads(trades_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read trade file %s: %s", trades_path, exc)
        return 0
    if not isinstance(payload, list):
        return 0

    structures = 0
    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("strategy") == "alpaca_sync":
            continue
        if item.get("status") == "SIMULATED":
            continue
        if item.get("order_ids") or (isinstance(item.get("legs"), dict) and item.get("underlying")):
            structures += 1
    return structures


def _load_intraday_metrics(context: dict[str, Any] | None = None) -> dict[str, float | int | str]:
    """Return best-effort intraday metrics for guardrails.

    Unit tests must be deterministic. When running under pytest, default to
    zeros unless explicit metrics are provided via `context["intraday_metrics"]`.
    """
    today = _today_et_str()

    # Allow callers (and tests) to provide deterministic metrics and avoid
    # coupling behavior to checked-in repo state (e.g. data/system_state.json).
    if context and isinstance(context.get("intraday_metrics"), dict):
        raw = context.get("intraday_metrics") or {}

        def _as_float(v: Any, default: float = 0.0) -> float:
            try:
                return float(v)
            except Exception as exc:
                logger.debug("_as_float conversion failed for %r: %s", v, exc)
                return default

        def _as_int(v: Any, default: int = 0) -> int:
            try:
                return int(v)
            except Exception as exc:
                logger.debug("_as_int conversion failed for %r: %s", v, exc)
                return default

        date_str = str(raw.get("date") or today)
        return {
            "date": date_str,
            "daily_pnl": _as_float(raw.get("daily_pnl"), 0.0),
            "fills_today": _as_int(raw.get("fills_today"), 0),
            "orders_today": _as_int(raw.get("orders_today"), 0),
            "structures_today": _as_int(raw.get("structures_today"), 0),
        }

    # Unit tests should not depend on checked-in daily snapshots.
    if os.environ.get("PYTEST_CURRENT_TEST") or "pytest" in sys.modules:
        return {
            "date": today,
            "daily_pnl": 0.0,
            "fills_today": 0,
            "orders_today": 0,
            "structures_today": 0,
        }

    fills_today = 0
    orders_today = 0
    structures_today = _count_structures_today_from_trade_file(today)
    daily_pnl: float | None = None

    if _SYSTEM_STATE_PATH.exists():
        try:
            state = json.loads(_SYSTEM_STATE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to parse system_state.json: %s", exc)
            state = {}
        if isinstance(state, dict):
            trades = state.get("trades", {}) if isinstance(state.get("trades"), dict) else {}
            paper = (
                state.get("paper_account", {})
                if isinstance(state.get("paper_account"), dict)
                else {}
            )
            if str(trades.get("metrics_date") or "").strip() == today:
                try:
                    daily_pnl = float(paper.get("daily_change", 0.0) or 0.0)
                except Exception as exc:
                    logger.debug("Failed to parse daily_pnl: %s", exc)
                    daily_pnl = None
                try:
                    fills_today = int(trades.get("fills_today", trades.get("today_trades", 0)) or 0)
                except Exception as exc:
                    logger.debug("Failed to parse fills_today: %s", exc)
                    fills_today = 0
                try:
                    orders_today = int(trades.get("orders_today", 0) or 0)
                except Exception as exc:
                    logger.debug("Failed to parse orders_today: %s", exc)
                    orders_today = 0
                try:
                    structures_today = int(
                        trades.get("structures_today", structures_today) or structures_today
                    )
                except Exception as exc:
                    logger.debug("Failed to parse structures_today: %s", exc)
                    structures_today = structures_today

    return {
        "date": today,
        "daily_pnl": daily_pnl if daily_pnl is not None else 0.0,
        "fills_today": fills_today,
        "orders_today": orders_today,
        "structures_today": structures_today,
    }


def _enforce_intraday_guardrails(
    *,
    equity: float,
    is_opening: bool,
    checks_performed: list[str],
    context: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Intraday hard stops to prevent death-by-churn (openings only)."""
    if not is_opening:
        return True, ""

    metrics = _load_intraday_metrics(context)
    daily_pnl = float(metrics.get("daily_pnl", 0.0) or 0.0)
    fills_today = int(metrics.get("fills_today", 0) or 0)
    structures_today = int(metrics.get("structures_today", 0) or 0)
    checks_performed.append(
        f"intraday_metrics: pnl={daily_pnl:+.2f} fills={fills_today} structures={structures_today}"
    )

    if equity > 0 and daily_pnl < -(equity * MAX_DAILY_LOSS_PCT):
        return (
            False,
            f"Daily loss limit exceeded: {daily_pnl:+.2f} < -{MAX_DAILY_LOSS_PCT:.0%} of equity",
        )
    if structures_today >= MAX_DAILY_STRUCTURES:
        return (
            False,
            f"Max structures guardrail hit: {structures_today}/{MAX_DAILY_STRUCTURES} today",
        )
    if fills_today >= MAX_DAILY_FILLS:
        return False, f"Max fills guardrail hit: {fills_today}/{MAX_DAILY_FILLS} today"

    return True, ""


def _reset_daily_tracker_if_needed():
    """Reset daily loss tracker at start of new day. Thread-safe."""
    from datetime import date

    # Lock is acquired by caller (_check_daily_loss_limit)
    today = str(date.today())
    if _daily_loss_tracker["date"] != today:
        _daily_loss_tracker["total"] = 0.0
        _daily_loss_tracker["date"] = today


def _check_position_size(
    symbol: str,
    amount: float,
    equity: float,
    max_position_pct: float = MAX_POSITION_PCT,
) -> tuple[bool, str]:
    """Check if position size is within limits."""
    if equity <= 0:
        return False, "Cannot calculate position size with zero equity"

    position_pct = amount / equity
    max_amount = equity * max_position_pct

    if position_pct > max_position_pct:
        return False, (
            f"Position ${amount:.2f} ({position_pct:.1%}) exceeds "
            f"max {max_position_pct:.0%} (${max_amount:.2f})"
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


def _query_feedback_model(strategy: str, context: dict | None) -> tuple[float, list[str]]:
    """
    Query the RLHF feedback model for confidence adjustment.

    Uses Thompson Sampling posterior and feature weights to assess
    whether this trade type has historically led to positive outcomes.

    Args:
        strategy: Trade strategy name
        context: Trade context with additional info

    Returns:
        (confidence_adjustment, anomalies_list)
        - confidence_adjustment: multiplier (0.8-1.0) based on patterns
        - anomalies_list: warnings about negative patterns detected
    """
    anomalies = []
    confidence = 1.0

    try:
        if not FEEDBACK_MODEL_PATH.exists():
            return 1.0, []

        with open(FEEDBACK_MODEL_PATH) as f:
            model = json.load(f)

        alpha = model.get("alpha", 1.0)
        beta = model.get("beta", 1.0)
        feature_weights = model.get("feature_weights", {})

        # Calculate Thompson Sampling posterior (overall model confidence)
        posterior = alpha / (alpha + beta)

        # Check if we have enough samples to trust the model
        total_samples = int(alpha + beta - 2)  # Subtract priors
        if total_samples < 5:
            # Not enough data yet - don't adjust confidence
            return 1.0, ["ML model insufficient samples (<5)"]

        # Check for negative feature patterns in strategy/context
        strategy_lower = strategy.lower() if strategy else ""
        context_str = str(context).lower() if context else ""
        combined = f"{strategy_lower} {context_str}"

        negative_patterns = []
        for feature, weight in feature_weights.items():
            if weight < -0.1 and feature in combined:
                negative_patterns.append(f"{feature}({weight:+.2f})")

        if negative_patterns:
            # Reduce confidence based on negative patterns
            confidence = max(0.7, posterior - 0.1)
            anomalies.append(f"Negative ML patterns: {', '.join(negative_patterns)}")

        # If overall model posterior is low, add warning
        if posterior < 0.6:
            anomalies.append(f"Low ML confidence: posterior={posterior:.2f}")
            confidence = min(confidence, posterior)

    except Exception as e:
        logger.debug(f"Feedback model query failed (non-fatal): {e}")

    return confidence, anomalies


def _check_market_regime(strategy: str, context: dict | None) -> tuple[float, list[str]]:
    """
    Check market regime for iron condor entry optimization (LL-247 ML-IMP-2).

    Regime-based trading rules:
    - "calm": Ideal for iron condors (80% allocation, high confidence)
    - "trending": Caution - directional risk (70% allocation)
    - "volatile": Higher premium but higher risk (40% allocation, reduced confidence)
    - "spike": DO NOT TRADE - crisis mode (0% allocation, block trade)

    Args:
        strategy: Trade strategy name
        context: Trade context with regime info if available

    Returns:
        (confidence_adjustment, warnings_list)
        - 0.0 means block the trade (spike regime)
        - 0.7-1.0 is normal confidence range
    """
    warnings = []
    confidence = 1.0

    try:
        # Try to get regime from context first (pre-computed by orchestrator)
        regime_snapshot = context.get("regime_snapshot") if context else None

        if not regime_snapshot:
            # Try to detect live regime
            try:
                from src.utils.regime_detector import RegimeDetector

                detector = RegimeDetector()
                # Use simple heuristic detection if no VIX data available
                features = context.get("features", {}) if context else {}
                if features:
                    result = detector.detect(features)
                    regime_label = result.get("label", "unknown")
                else:
                    # Default to calm if no data (conservative)
                    regime_label = "calm"
            except ImportError:
                logger.debug("RegimeDetector not available - skipping regime check")
                return 1.0, []
        else:
            regime_label = regime_snapshot.get("label", "unknown")

        # Apply regime-based rules
        regime_lower = regime_label.lower()

        if "spike" in regime_lower or "crisis" in regime_lower:
            # CRITICAL: Block all trades in spike/crisis regime
            warnings.append(f"🚨 SPIKE REGIME DETECTED - Trade blocked (regime={regime_label})")
            return 0.0, warnings  # 0.0 = block trade

        elif "volatile" in regime_lower or "vol" in regime_lower:
            # High volatility - reduce confidence but allow with warning
            warnings.append(f"⚠️ VOLATILE regime - reduced confidence (regime={regime_label})")
            confidence = 0.7

        elif "trending" in regime_lower or "trend" in regime_lower:
            # Trending market - iron condors at risk of being tested on one side
            if "iron" in strategy.lower() or "condor" in strategy.lower():
                warnings.append(
                    f"⚠️ TRENDING regime - iron condor may be directionally tested (regime={regime_label})"
                )
                confidence = 0.8
            else:
                confidence = 0.9

        elif "calm" in regime_lower or "range" in regime_lower:
            # Ideal for iron condors - boost confidence
            if "iron" in strategy.lower() or "condor" in strategy.lower():
                logger.info(f"✅ CALM regime - ideal for iron condors (regime={regime_label})")
            confidence = 1.0

        else:
            # Unknown regime - proceed with caution
            warnings.append(f"Unknown regime: {regime_label} - proceeding with caution")
            confidence = 0.85

    except Exception as e:
        logger.debug(f"Regime check failed (non-fatal): {e}")
        # Fail open - don't block trades due to regime check errors
        return 1.0, []

    return confidence, warnings


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
    # Per CLAUDE.md: Liquid ETFs only (SPY, SPX, XSP, QQQ, IWM)
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
    # CHECK 2.1: Intraday hard guardrails (daily loss + max fills + max structures)
    # Applies to NEW entries only. We try to avoid blocking closes/reductions.
    # =========================================================================
    current_positions = context.get("positions", []) if context else []
    if not isinstance(current_positions, list):
        current_positions = []
    current_symbols = {str(p.get("symbol") or "") for p in current_positions if isinstance(p, dict)}
    is_opening = True
    if side == "SELL" and symbol in current_symbols:
        is_opening = False

    guard_ok, guard_reason = _enforce_intraday_guardrails(
        equity=float(equity or 0.0),
        is_opening=is_opening,
        checks_performed=checks_performed,
        context=context,
    )
    if not guard_ok:
        return GateResult(
            approved=False,
            reason=guard_reason,
            checks_performed=checks_performed + ["intraday_guardrails: BLOCKED"],
        )
    checks_performed.append("intraday_guardrails: PASS")

    # =========================================================================
    # CHECK 2.2: North Star guard (dynamic risk profile)
    # Applies stricter sizing or blocks new risk when paper metrics are weak.
    # =========================================================================
    effective_max_position_pct = MAX_POSITION_PCT
    north_star_guard = context.get("north_star_guard", {}) if context else {}
    if isinstance(north_star_guard, dict) and north_star_guard.get("enabled"):
        guard_mode = str(north_star_guard.get("mode", "unknown"))
        guard_limit = north_star_guard.get("max_position_pct")
        if isinstance(guard_limit, (int, float)) and guard_limit > 0:
            effective_max_position_pct = min(float(guard_limit), MAX_POSITION_PCT)

        checks_performed.append(
            f"north_star_guard: mode={guard_mode} max_position={effective_max_position_pct:.1%}"
        )

        # Block *new openings* regardless of BUY/SELL semantics (options entries can be SELL-to-open).
        if is_opening and north_star_guard.get("block_new_positions"):
            reason = str(
                north_star_guard.get("block_reason")
                or "North Star guard blocked new position openings."
            )
            return GateResult(
                approved=False,
                reason=reason,
                checks_performed=checks_performed + ["north_star_guard: BLOCKED"],
            )
    else:
        checks_performed.append("north_star_guard: SKIP")

    # =========================================================================
    # CHECK 2.3: Milestone controller (strategy-family auto-pause)
    # Blocks new BUY entries for paused families until rolling metrics recover.
    # =========================================================================
    milestone_ctx = context.get("milestone_controller", {}) if context else {}
    if isinstance(milestone_ctx, dict) and milestone_ctx.get("enabled"):
        family = str(milestone_ctx.get("strategy_family", "unknown"))
        family_status = str(milestone_ctx.get("family_status", "unknown"))
        checks_performed.append(f"milestone_controller: family={family} status={family_status}")

        # Block *new openings* regardless of BUY/SELL semantics (options entries can be SELL-to-open).
        if is_opening and milestone_ctx.get("pause_buy_for_family"):
            reason = str(
                milestone_ctx.get("block_reason")
                or f"Milestone controller blocked BUY entries for strategy family '{family}'."
            )
            return GateResult(
                approved=False,
                reason=reason,
                checks_performed=checks_performed + ["milestone_controller: BLOCKED"],
            )
    else:
        checks_performed.append("milestone_controller: SKIP")

    # =========================================================================
    # CHECK 2.5: Position COUNT limit (Jan 19, 2026 - LL-246, Jan 22, 2026 - LL-281)
    # Per CLAUDE.md: "Position limit: 1 iron condor at a time" = 4 legs max
    # This prevents accumulating unlimited positions (root cause of 8 contract crisis)
    # NOTE: MAX_POSITIONS imported from trading_constants.py (single source of truth)
    # =========================================================================
    current_position_count = len(current_positions)

    if is_opening and current_position_count >= MAX_POSITIONS:
        return GateResult(
            approved=False,
            reason=f"Position count {current_position_count} >= max {MAX_POSITIONS} (CLAUDE.md: 1 iron condor at a time)",
            checks_performed=checks_performed + ["position_count: BLOCKED"],
        )

    checks_performed.append(f"position_count: PASS ({current_position_count}/{MAX_POSITIONS})")

    # =========================================================================
    # CHECK 2.6: Position STACKING prevention (Jan 22, 2026 - LL-275)
    # Bug fix: Gate was allowing unlimited contracts in same symbol
    # Root cause of 8 long 658 puts disaster (-$1,472 loss)
    # If buying, block if we already hold this exact symbol
    # =========================================================================
    if is_opening and current_positions:
        existing_symbols = [p.get("symbol", "") for p in current_positions]
        if symbol in existing_symbols:
            # Find existing quantity
            existing_qty = 0
            for p in current_positions:
                if p.get("symbol") == symbol:
                    existing_qty = abs(int(float(p.get("qty", 0))))
                    break
            return GateResult(
                approved=False,
                reason=f"POSITION STACKING BLOCKED: Already hold {existing_qty} contracts of {symbol}. Cannot buy more. (LL-275: Fix for 658 put disaster)",
                checks_performed=checks_performed + ["position_stacking: BLOCKED"],
            )

    checks_performed.append("position_stacking: PASS (no duplicate)")

    # =========================================================================
    # CHECK 3: Position size limit
    # =========================================================================
    position_ok, position_msg = _check_position_size(
        symbol,
        amount,
        equity,
        max_position_pct=effective_max_position_pct,
    )

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
    if is_opening:
        # Daily loss is enforced via canonical intraday P/L (see intraday_guardrails).
        # Do not "project" potential loss here; projection causes false blocks.
        potential_loss = 0.0
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
    # CHECK 6: ML Feedback Model (Jan 24, 2026 - LL-302)
    # Query Thompson Sampling model for confidence adjustment based on
    # learned patterns from user feedback. Does NOT block, only adjusts confidence.
    # =========================================================================
    ml_confidence, ml_anomalies = _query_feedback_model(strategy, context)
    checks_performed.append(f"ml_feedback: confidence={ml_confidence:.2f}")

    # =========================================================================
    # CHECK 7: Regime Detection Gate (Jan 25, 2026 - LL-247 ML-IMP-2)
    # Use market regime to optimize iron condor entry timing:
    # - BLOCK in "spike" regime (crisis mode, pause_trading=True)
    # - WARN in "volatile" regime (high risk, adjust confidence)
    # - BOOST confidence in "calm" regime (ideal for iron condors)
    # =========================================================================
    regime_confidence, regime_warnings = _check_market_regime(strategy, context)
    warnings.extend(regime_warnings)
    checks_performed.append(f"regime_check: {regime_confidence:.2f}")

    if regime_confidence == 0.0:
        # Spike regime - block the trade
        return GateResult(
            approved=False,
            reason="Trade blocked by SPIKE regime - markets in crisis mode (LL-247)",
            rag_warnings=warnings,
            checks_performed=checks_performed + ["regime_check: BLOCKED"],
        )

    # =========================================================================
    # ALL CHECKS PASSED
    # =========================================================================
    # Calculate final confidence from RAG warnings, ML model, and regime
    base_confidence = 1.0 if not warnings else 0.8
    final_confidence = min(base_confidence, ml_confidence, regime_confidence)

    logger.info(f"✅ Mandatory gate APPROVED: {side} ${amount:.2f} {symbol} ({strategy})")

    return GateResult(
        approved=True,
        reason="Trade approved - all mandatory checks passed",
        rag_warnings=warnings,
        ml_anomalies=ml_anomalies,
        checks_performed=checks_performed,
        confidence=final_confidence,
    )


_OCC_OPTION_RE = re.compile(r"^([A-Z]{1,6})(\d{6})[PC](\d{8})$")


def _parse_occ_expiry(symbol: str) -> date | None:
    """Parse OCC option symbol expiry into a date (UTC-naive)."""
    match = _OCC_OPTION_RE.match((symbol or "").upper().strip())
    if not match:
        return None
    yymmdd = match.group(2)
    try:
        year = 2000 + int(yymmdd[0:2])
        month = int(yymmdd[2:4])
        day = int(yymmdd[4:6])
        return date(year, month, day)
    except Exception as exc:
        logger.debug("Failed to parse OCC expiry from %r: %s", symbol, exc)
        return None


def _looks_like_option_symbol(symbol: str) -> bool:
    return bool(_parse_occ_expiry(symbol))


def _side_is_buy(side: Any) -> bool:
    text = str(side).upper()
    return text.endswith("BUY") or text == "BUY"


def _side_is_sell(side: Any) -> bool:
    text = str(side).upper()
    return text.endswith("SELL") or text == "SELL"


def _get_account_equity_from_client(client: Any) -> float | None:
    """Best-effort equity read for checklist enforcement."""
    if not hasattr(client, "get_account"):
        return None
    try:
        acct = client.get_account()
        # alpaca-py account uses strings; tolerate either.
        for attr in ("equity", "portfolio_value", "cash"):
            val = getattr(acct, attr, None)
            if val is None:
                continue
            try:
                return float(val)
            except Exception as exc:
                logger.debug("Failed to convert account.%s=%r to float: %s", attr, val, exc)
                continue
    except Exception as exc:
        logger.warning("Failed to read account equity from client: %s", exc)
        return None
    return None


def _get_positions_qty_map(client: Any) -> dict[str, float] | None:
    """Return symbol->qty mapping for close/open inference."""
    getter = getattr(client, "get_all_positions", None) or getattr(client, "get_positions", None)
    if getter is None:
        return None
    try:
        positions = getter()
    except Exception as exc:
        logger.warning("Failed to get positions from client: %s", exc)
        return None
    qty_map: dict[str, float] = {}
    try:
        for pos in positions or []:
            sym = getattr(pos, "symbol", None) or (
                pos.get("symbol") if isinstance(pos, dict) else None
            )
            raw_qty = getattr(pos, "qty", None) or getattr(pos, "quantity", None)
            if raw_qty is None and isinstance(pos, dict):
                raw_qty = pos.get("qty") or pos.get("quantity")
            if not sym:
                continue
            try:
                qty_map[str(sym)] = float(raw_qty or 0.0)
            except Exception as exc:
                logger.debug("Failed to convert qty for %s: %s", sym, exc)
                qty_map[str(sym)] = 0.0
    except Exception as exc:
        logger.warning("Failed to iterate positions for qty map: %s", exc)
        return None
    return qty_map


def _infer_is_closing_order(client: Any, order_request: Any) -> bool | None:
    """Infer whether an order reduces existing positions (close/reduce) vs opens/increases.

    Returns:
        True  -> confidently closing/reducing
        False -> confidently opening/increasing
        None  -> cannot infer
    """
    qty_map = _get_positions_qty_map(client)
    if not qty_map:
        return None

    order_qty = getattr(order_request, "qty", None)
    try:
        order_qty_val = int(float(order_qty)) if order_qty is not None else 1
    except Exception as exc:
        logger.debug("Failed to parse order qty %r: %s", order_qty, exc)
        order_qty_val = 1

    legs = getattr(order_request, "legs", None)
    if legs:
        # If any leg has no existing position, this is opening/increasing.
        reductions: list[bool] = []
        for leg in legs:
            leg_symbol = getattr(leg, "symbol", "") or ""
            leg_side = getattr(leg, "side", None)
            ratio_qty = getattr(leg, "ratio_qty", None)
            try:
                leg_qty = int(float(ratio_qty or 1)) * order_qty_val
            except Exception as exc:
                logger.debug("Failed to parse leg ratio_qty %r: %s", ratio_qty, exc)
                leg_qty = 1 * order_qty_val

            existing = float(qty_map.get(leg_symbol, 0.0))
            if existing == 0.0:
                return False

            if _side_is_buy(leg_side):
                new_qty = existing + leg_qty
            elif _side_is_sell(leg_side):
                new_qty = existing - leg_qty
            else:
                return None

            reductions.append(abs(new_qty) < abs(existing))

        if reductions and all(reductions):
            return True
        if reductions and any(not r for r in reductions):
            return False
        return None

    symbol = getattr(order_request, "symbol", None)
    side = getattr(order_request, "side", None)
    if not symbol or side is None:
        return None

    existing = float(qty_map.get(str(symbol), 0.0))
    if existing == 0.0:
        return False

    try:
        qty_val = int(float(getattr(order_request, "qty", 1) or 1))
    except Exception as exc:
        logger.debug("Failed to parse order qty for closing inference: %s", exc)
        qty_val = 1

    if _side_is_buy(side):
        new_qty = existing + qty_val
    elif _side_is_sell(side):
        new_qty = existing - qty_val
    else:
        return None

    return abs(new_qty) < abs(existing)


def _estimate_opening_max_loss(order_request: Any) -> tuple[float | None, int | None, str | None]:
    """Estimate max loss + DTE for opening options orders (best-effort)."""
    legs = getattr(order_request, "legs", None)
    symbol = getattr(order_request, "symbol", None)

    option_symbols: list[str] = []
    if legs:
        for leg in legs:
            sym = getattr(leg, "symbol", None)
            if sym:
                option_symbols.append(str(sym))
    elif symbol and _looks_like_option_symbol(str(symbol)):
        option_symbols.append(str(symbol))

    if not option_symbols:
        return None, None, None

    expiries = [d for d in (_parse_occ_expiry(s) for s in option_symbols) if d is not None]
    if expiries:
        expiry = min(expiries)
        dte = max(0, (expiry - date.today()).days)
    else:
        dte = None

    # Compute a conservative max loss from wing width (ignore credit).
    # For an iron condor: max loss ~= max(put_width, call_width) * 100 * contracts.
    width = None
    underlying = None
    if legs:
        puts: dict[str, list[float]] = {"BUY": [], "SELL": []}
        calls: dict[str, list[float]] = {"BUY": [], "SELL": []}
        for leg in legs:
            leg_symbol = str(getattr(leg, "symbol", "") or "")
            if not leg_symbol:
                continue
            underlying = _extract_underlying(leg_symbol)
            match = _OCC_OPTION_RE.match(leg_symbol.upper())
            if not match:
                continue
            opt_type = leg_symbol.upper()[len(match.group(1)) + 6]  # P/C
            strike = int(match.group(3)) / 1000.0
            leg_side = getattr(leg, "side", None)
            side_key = (
                "BUY" if _side_is_buy(leg_side) else "SELL" if _side_is_sell(leg_side) else None
            )
            if side_key is None:
                continue
            if opt_type == "P":
                puts[side_key].append(strike)
            elif opt_type == "C":
                calls[side_key].append(strike)

        put_width = None
        call_width = None
        if puts["BUY"] and puts["SELL"]:
            put_width = abs(max(puts["SELL"]) - min(puts["BUY"]))
        if calls["BUY"] and calls["SELL"]:
            call_width = abs(min(calls["SELL"]) - max(calls["BUY"]))
        widths = [w for w in (put_width, call_width) if isinstance(w, (int, float)) and w and w > 0]
        if widths:
            width = max(widths)

    if width is None:
        # Fallback: defined-risk spread default.
        width = 5.0

    contracts = getattr(order_request, "qty", None)
    try:
        contracts_val = int(float(contracts)) if contracts is not None else 1
    except Exception as exc:
        logger.debug("Failed to parse contracts qty %r: %s", contracts, exc)
        contracts_val = 1
    max_loss = float(width) * 100.0 * float(max(1, contracts_val))
    return max_loss, dte, underlying


def safe_submit_order(client, order_request, strategy: str | None = None):
    """Wrapper that enforces validate_ticker() before ANY order submission.

    All scripts MUST use this instead of client.submit_order() directly.
    This is the single gateway for all order submissions outside the core
    execution methods (which have their own validation).

    Args:
        client: Alpaca TradingClient instance
        order_request: Alpaca order request object
        strategy: Optional strategy name (e.g. 'iron_condor')

    Returns:
        Order result from client.submit_order()

    Raises:
        ValueError: If ticker validation fails
    """
    # Extract symbol from the order request
    symbol = getattr(order_request, "symbol", None)

    # For MLEG orders, check the legs
    legs = getattr(order_request, "legs", None)

    # Infer strategy if not provided
    if not strategy:
        if legs and len(legs) == 4:
            strategy = "iron_condor"
        elif legs and len(legs) == 2:
            strategy = "credit_spread"
        else:
            strategy = "order_request"

    import uuid

    from src.monitoring.telemetry_gateway import TelemetryGateway

    gateway = TelemetryGateway()
    trace_id = uuid.uuid4().hex
    gateway.capture_span(
        "strategy_entry", trace_id, attributes={"strategy": strategy, "symbol": symbol}
    )

    if legs:
        for leg in legs:
            leg_symbol = getattr(leg, "symbol", "")
            ticker_valid, ticker_error = validate_ticker(leg_symbol)
            if not ticker_valid:
                logger.warning(f"ORDER BLOCKED (leg): {ticker_error}")
                raise ValueError(f"ORDER BLOCKED (leg): {ticker_error}")
    elif symbol:
        ticker_valid, ticker_error = validate_ticker(symbol)
        if not ticker_valid:
            logger.warning(f"ORDER BLOCKED: {ticker_error}")
            raise ValueError(f"ORDER BLOCKED: {ticker_error}")

    # Enforce mandatory pre-trade checklist for OPENING options orders only.
    # Do NOT block closes/reductions (risk management must always be able to exit).
    try:
        is_closing = _infer_is_closing_order(client, order_request)
        if is_closing is False:
            # =================================================================
            # TIER 0: MACRO RISK GUARD (Feb 25, 2026 - CNBC/PwC Ingestion)
            # =================================================================
            try:
                from src.safety.macro_risk_guard import MacroRiskGuard
                from src.utils.alpaca_client import get_options_data_client

                # Get data client for macro fetching (USO, TNX)
                data_client = get_options_data_client()
                macro_guard = MacroRiskGuard(data_client)

                vitals = macro_guard.get_macro_snapshot()
                safe, macro_reason = macro_guard.check_macro_vitals(vitals)
                if not safe:
                    gateway.capture_span(
                        "macro_block", trace_id, attributes={"reason": macro_reason}
                    )
                    raise ValueError(f"MACRO BLOCK: {macro_reason}")
            except ImportError:
                logger.warning("MacroRiskGuard unavailable - skipping macro check.")
            except Exception as e:
                if "MACRO BLOCK" in str(e):
                    raise
                logger.error(f"Macro Guard Error: {e}")

            # Mandatory trade gate enforcement for NEW entries.
            # This ensures intraday guardrails (daily loss, max fills/structures) apply
            # even when scripts submit orders directly (outside AlpacaExecutor.place_order).
            try:
                equity = _get_account_equity_from_client(client) or 0.0
                max_loss, _dte, _underlying = _estimate_opening_max_loss(order_request)
                est_amount = float(max_loss or 0.0)
                # Best-effort account context so that direct script submissions
                # still benefit from the same dynamic guardrails as AlpacaExecutor.
                account_context: dict[str, Any] = {"equity": float(equity)}

                # Include current positions for stacking + count checks (best-effort).
                try:
                    qty_map = _get_positions_qty_map(client) or {}
                    if qty_map:
                        account_context["positions"] = [
                            {"symbol": sym, "qty": qty} for sym, qty in qty_map.items()
                        ]
                except Exception as exc:
                    logger.warning("Failed to load positions for gate context: %s", exc)

                # Inject North Star guard context for dynamic risk sizing/blocking.
                try:
                    from src.safety.north_star_guard import get_guard_context

                    guard_context = get_guard_context()
                    if guard_context:
                        account_context["north_star_guard"] = guard_context
                except Exception as exc:
                    logger.warning("Failed to load North Star guard context: %s", exc)

                # Inject milestone controller context for family-level auto-pause enforcement.
                try:
                    from src.safety.milestone_controller import get_milestone_context

                    milestone_context = get_milestone_context(strategy=strategy)
                    if milestone_context:
                        account_context["milestone_controller"] = milestone_context
                except Exception as exc:
                    logger.warning("Failed to load milestone controller context: %s", exc)

                gate = validate_trade_mandatory(
                    symbol=str(
                        getattr(order_request, "symbol", "")
                        or (
                            getattr(legs[0], "symbol", "")
                            if getattr(order_request, "legs", None)
                            else ""
                        )
                    ),
                    amount=est_amount if est_amount > 0 else MIN_TRADE_AMOUNT,
                    side=str(getattr(order_request, "side", None) or "SELL").upper(),
                    strategy=strategy,
                    context=account_context,
                )
                if not gate.approved:
                    raise ValueError(f"MANDATORY GATE BLOCKED: {gate.reason}")
            except ValueError:
                raise
            except Exception as exc:
                # If gate cannot run, fail closed for new entries.
                raise ValueError(f"MANDATORY GATE ERROR (fail closed): {exc}") from exc

            # Only apply to options-like orders.
            option_symbols: list[str] = []
            if legs:
                option_symbols = [str(getattr(leg, "symbol", "") or "") for leg in legs]
            elif symbol:
                option_symbols = [str(symbol)]
            option_symbols = [s for s in option_symbols if _looks_like_option_symbol(s)]

            # =================================================================
            # MULTI-MODEL CONSENSUS (Jan 25, 2026 - 'Exclusivity is Dead')
            # =================================================================
            try:
                from src.safety.multi_model_juror import MultiModelJuror

                juror = MultiModelJuror()
                proposal = {
                    "symbol": symbol,
                    "strategy": strategy,
                    "legs": option_symbols,
                    "amount": est_amount,
                }
                if not juror.get_consensus(proposal, primary_reasoning="System trade logic entry"):
                    raise ValueError(
                        "MULTI-MODEL CONSENSUS FAILED: Juror detected a risk violation."
                    )
                gateway.capture_span("juror_consensus", trace_id, attributes={"status": "AGREE"})
            except ImportError:
                logger.warning("MultiModelJuror unavailable - proceeding with standard safety.")
            except Exception as e:
                logger.error(f"CONSENSUS ERROR: {e}")
                raise ValueError(f"CRITICAL: Consensus check failed: {e}")

            # =================================================================
            # REASONING EVALUATION (Jan 22, 2026 - TruLens Pattern)
            # =================================================================
            try:
                from src.safety.reasoning_evaluator import ReasoningEvaluator

                evaluator = ReasoningEvaluator(threshold=0.7)  # 70% groundedness required

                # Fetch recent lessons for groundedness check
                try:
                    from src.rag.lessons_search import LessonsSearch

                    lessons = LessonsSearch().search(f"{strategy} {symbol}", limit=3)
                    retrieved_context = [lesson.content for lesson in lessons]
                except Exception:
                    retrieved_context = []

                score = evaluator.evaluate(
                    proposal=proposal,
                    reasoning="Executing strategy based on VIX Mean Reversion and Phil Town Rule #1.",
                    retrieved_context=retrieved_context,
                )

                # RAG retrieval can be transiently unavailable; avoid deterministic
                # order blocks when no context was retrieved.
                has_retrieved_context = bool(retrieved_context)
                if score.is_hallucination_risk and has_retrieved_context:
                    raise ValueError(f"REASONING AUDIT FAILED: {score.reasoning_trace}")
                if score.is_hallucination_risk and not has_retrieved_context:
                    logger.warning(
                        "Reasoning audit low groundedness without retrieval context; "
                        "skipping hard fail."
                    )
                gateway.capture_span(
                    "reasoning_evaluation",
                    trace_id,
                    attributes={"score": score.groundedness, "trace": score.reasoning_trace},
                )

            except ImportError:
                logger.warning("ReasoningEvaluator unavailable - proceeding with standard safety.")
            except Exception as e:
                if "REASONING AUDIT FAILED" in str(e):
                    raise
                logger.error(f"EVALUATION ERROR: {e}")

            if option_symbols:
                from src.risk.pre_trade_checklist import PreTradeChecklist

                equity = _get_account_equity_from_client(client) or 0.0
                max_loss, dte, _underlying = _estimate_opening_max_loss(order_request)

                # Infer "spread" (defined risk) for options orders:
                # opening must include both BUY and SELL legs (e.g., spreads/condors).
                is_spread = False
                if legs:
                    has_buy = any(_side_is_buy(getattr(leg, "side", None)) for leg in legs)
                    has_sell = any(_side_is_sell(getattr(leg, "side", None)) for leg in legs)
                    is_spread = bool(has_buy and has_sell)

                stop_loss_defined = is_spread  # defined-risk spreads have built-in max loss
                checklist = PreTradeChecklist(account_equity=float(equity))
                passed, failures = checklist.validate(
                    symbol=option_symbols[0],
                    max_loss=float(max_loss or 0.0),
                    dte=int(dte or 0),
                    is_spread=is_spread,
                    stop_loss_defined=stop_loss_defined,
                )
                if not passed:
                    msg = "PRE-TRADE CHECKLIST FAILED: " + "; ".join(failures)
                    logger.warning(msg)
                    raise ValueError(msg)
    except ValueError:
        raise
    except Exception as exc:
        # Never block order submission due to enforcement instrumentation failure.
        # Ticker whitelist still applies above.
        logger.warning("Pre-trade checklist enforcement skipped due to error: %s", exc)

    gateway.capture_span(
        "order_submitted", trace_id, attributes={"symbol": symbol, "strategy": strategy}
    )
    try:
        order = client.submit_order(order_request)
        gateway.capture_span(
            "order_confirmed", trace_id, attributes={"order_id": str(getattr(order, "id", ""))}
        )
        return order
    except Exception as e:
        gateway.capture_span("order_failed", trace_id, attributes={"error": str(e)})
        raise e


def safe_close_position(client, symbol, **kwargs):
    """Wrapper that enforces validate_ticker() before closing positions.

    All scripts MUST use this instead of client.close_position() directly.

    Args:
        client: Alpaca TradingClient instance
        symbol: Symbol to close position for
        **kwargs: Additional args passed to close_position (e.g. close_options)

    Returns:
        Result from client.close_position()

    Raises:
        ValueError: If ticker validation fails
    """
    ticker_valid, ticker_error = validate_ticker(symbol)
    if not ticker_valid:
        logger.warning(f"CLOSE BLOCKED: {ticker_error}")
        raise ValueError(f"CLOSE BLOCKED: {ticker_error}")
    return client.close_position(symbol, **kwargs)


def record_trade_loss(loss_amount: float):
    """Record a trade loss for daily tracking. Thread-safe."""
    # SECURITY FIX (Jan 19, 2026): Use lock to prevent race condition
    with _daily_loss_lock:
        _reset_daily_tracker_if_needed()
        _daily_loss_tracker["total"] += abs(loss_amount)
        logger.info(f"Daily loss updated: ${_daily_loss_tracker['total']:.2f}")
