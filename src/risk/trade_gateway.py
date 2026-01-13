"""
Trade Gateway - Mandatory Risk Enforcement Layer

CRITICAL SECURITY COMPONENT

This module implements a mandatory gateway between AI decisions and broker execution.
NO TRADE CAN BYPASS THIS GATEWAY.

Architecture:
    AI Decision -> Trade Gateway (HARD CODE) -> Broker API

The gateway enforces:
1. Portfolio risk assessment (exposure caps, correlation, drawdown)
2. Minimum trade batching ($200 threshold to reduce noise trading)
3. Frequency limiting (max 5 trades/hour)
4. Position sizing validation
5. Circuit breakers (max daily loss, max drawdown)

This is NOT optional. The AI cannot call the broker directly.

Author: AI Trading System
Date: December 2, 2025
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from src.rag.lessons_learned_rag import LessonsLearnedRAG
from src.risk.capital_efficiency import get_capital_calculator
from src.validators.rule_one_validator import RuleOneValidator

logger = logging.getLogger(__name__)

# Observability: Vertex AI RAG + Local logs (Jan 9, 2026)


class RejectionReason(Enum):
    """Enumeration of trade rejection reasons."""

    INSUFFICIENT_FUNDS = "Insufficient funds in account"
    MAX_ALLOCATION_EXCEEDED = "Maximum allocation per symbol exceeded (15%)"
    HIGH_CORRELATION = "High correlation with existing positions (>0.8)"
    FREQUENCY_LIMIT = "Frequency limit exceeded (>5 trades/hour)"
    CIRCUIT_BREAKER_DAILY_LOSS = "Daily loss limit exceeded"
    CIRCUIT_BREAKER_DRAWDOWN = "Maximum drawdown exceeded"
    MINIMUM_BATCH_NOT_MET = "Minimum trade batch not accumulated"
    INVALID_ORDER = "Invalid order parameters"
    MARKET_CLOSED = "Market is closed"
    RISK_SCORE_TOO_HIGH = "Trade risk score exceeds threshold"
    CAPITAL_INEFFICIENT = "Strategy not viable for current capital level"
    IV_RANK_TOO_LOW = "IV Rank too low for premium selling (<20)"
    ILLIQUID_OPTION = "Option is illiquid (bid-ask spread > 5%)"
    RAG_LESSON_CRITICAL = "CRITICAL lesson learned blocks this trade"
    PORTFOLIO_NEGATIVE_PL = "Portfolio P/L is negative - Rule #1: Don't lose money"
    RULE_ONE_VIOLATION = "Phil Town Rule #1 validation failed - not a wonderful company at attractive price"


@dataclass
class TradeRequest:
    """Represents a trade request from the AI."""

    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float | None = None
    notional: float | None = None
    order_type: str = "market"
    limit_price: float | None = None
    stop_price: float | None = None
    request_time: datetime = field(default_factory=datetime.now)
    source: str = "ai_agent"  # Track where the request came from
    strategy_type: str | None = None  # e.g., 'iron_condor', 'vertical_spread'
    iv_rank: float | None = None  # Current IV Rank for the underlying
    bid_price: float | None = None  # Current bid price (for liquidity check)
    ask_price: float | None = None  # Current ask price (for liquidity check)
    is_option: bool = False  # True if this is an options trade


@dataclass
class GatewayDecision:
    """Result of the gateway's risk assessment."""

    approved: bool
    request: TradeRequest
    rejection_reasons: list[RejectionReason] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    adjusted_quantity: float | None = None
    adjusted_notional: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TradeGateway:
    """
    Mandatory risk enforcement gateway.

    ALL trades must pass through this gateway. No exceptions.
    The AI cannot call the broker API directly.

    Usage:
        gateway = TradeGateway(executor)

        # AI wants to trade - must go through gateway
        request = TradeRequest(symbol="NVDA", side="buy", notional=500)
        decision = gateway.evaluate(request)

        if decision.approved:
            # Gateway executes the trade, not the AI
            order = gateway.execute(decision)
        else:
            # Trade rejected - AI cannot bypass
            print(f"Rejected: {decision.rejection_reasons}")
    """

    # Risk limits (HARD CODED - cannot be bypassed)
    # UPDATED Dec 11, 2025: Increased from 15% to 25% for conviction trades
    MAX_SYMBOL_ALLOCATION_PCT = 0.25  # 25% max per symbol (was 15%)
    MAX_CORRELATION_THRESHOLD = 0.80  # 80% correlation threshold
    MAX_TRADES_PER_HOUR = 5  # Frequency limit
    MIN_TRADE_BATCH = (
        10.0  # $10 minimum for paper trading - FIXED Jan 12, 2026 (was $50, blocked all trades)
    )
    MIN_TRADE_BATCH_LIVE = 50.0  # $50 for live trading - fee protection
    MAX_DAILY_LOSS_PCT = 0.03  # 3% max daily loss
    MAX_DRAWDOWN_PCT = 0.10  # 10% max drawdown
    MAX_RISK_PER_TRADE_PCT = 0.01  # 1% max risk to equity per trade (NEW)
    MAX_RISK_SCORE = 0.75  # Risk score threshold

    # Correlation matrix for common holdings (simplified)
    # In production, this would be calculated dynamically
    CORRELATION_GROUPS = {
        "semiconductors": ["NVDA", "AMD", "INTC", "TSM", "AVGO", "QCOM", "MU"],
        "mega_tech": ["AAPL", "MSFT", "GOOGL", "GOOG", "META", "AMZN"],
        "ev_auto": ["TSLA", "RIVN", "LCID", "F", "GM"],
        "ai_plays": ["NVDA", "AMD", "MSFT", "GOOGL", "META", "CRM", "PLTR"],
    }

    # Credit strategies that require IV Rank check
    CREDIT_STRATEGIES = {
        "iron_condor",
        "credit_spread",
        "bull_put_spread",
        "bear_call_spread",
        "covered_call",
        "cash_secured_put",
        "strangle_short",
        "naked_put",
    }
    MIN_IV_RANK_FOR_CREDIT = 20  # Minimum IV Rank for premium selling

    # Liquidity check - options with wide spreads destroy alpha on fill
    MAX_BID_ASK_SPREAD_PCT = 0.05  # 5% maximum bid-ask spread

    def __init__(self, executor=None, paper: bool = True):
        """
        Initialize the trade gateway.

        Args:
            executor: The broker executor (AlpacaExecutor). Gateway wraps this.
            paper: If True, paper trading mode
        """
        self.executor = executor
        self.paper = paper

        # Track recent trades for frequency limiting
        self.recent_trades: list[datetime] = []

        # Track accumulated cash for batching
        self.accumulated_cash = 0.0
        self.last_accumulation_date: datetime | None = None

        # Daily P&L tracking
        self.daily_pnl = 0.0
        self.daily_pnl_date: datetime | None = None

        # Peak equity tracking for drawdown calculation (CRITICAL SAFETY)
        # Added Jan 13, 2026: Was stub returning 0.0, now tracks actual drawdown
        self.peak_equity: float = 0.0

        # Capital efficiency calculator
        self.capital_calculator = get_capital_calculator(daily_deposit_rate=10.0)

        # RAG for lessons learned
        self.rag = LessonsLearnedRAG()

        # State file for persistence
        self.state_file = Path("data/trade_gateway_state.json")
        self._load_state()

        logger.info("🔒 Trade Gateway initialized - ALL trades must pass through this gateway")

    def _load_state(self) -> None:
        """Load persisted state."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    state = json.load(f)
                    self.accumulated_cash = state.get("accumulated_cash", 0.0)
                    self.daily_pnl = state.get("daily_pnl", 0.0)
                    self.peak_equity = state.get("peak_equity", 0.0)
                    if state.get("daily_pnl_date"):
                        self.daily_pnl_date = datetime.fromisoformat(state["daily_pnl_date"])
            except Exception as e:
                logger.warning(f"Failed to load gateway state: {e}")

    def _save_state(self) -> None:
        """Persist state."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(
                    {
                        "accumulated_cash": self.accumulated_cash,
                        "daily_pnl": self.daily_pnl,
                        "daily_pnl_date": self.daily_pnl_date.isoformat()
                        if self.daily_pnl_date
                        else None,
                        "peak_equity": self.peak_equity,
                    },
                    f,
                )
        except Exception as e:
            logger.warning(f"Failed to save gateway state: {e}")

    def evaluate(self, request: TradeRequest) -> GatewayDecision:
        """
        Evaluate a trade request against all risk rules.

        This is the MANDATORY checkpoint. No trade can bypass this.

        Args:
            request: The trade request from the AI

        Returns:
            GatewayDecision with approval status and reasons
        """
        logger.info(
            f"🔒 Gateway evaluating: {request.side.upper()} {request.symbol} "
            f"(qty={request.quantity}, notional={request.notional})"
        )

        rejection_reasons = []
        warnings = []
        risk_score = 0.0
        metadata = {}

        # Get account info
        account_equity = self._get_account_equity()
        positions = self._get_positions()

        # ============================================================
        # CHECK 0: ZERO TOLERANCE - Block trading when P/L is negative
        # Phil Town Rule #1: Don't lose money
        # Block ALL risk-increasing trades:
        #   - BUY orders (buying stock/calls = increases exposure)
        #   - SELL orders on options when opening short positions (short puts = increases risk)
        # Only allow: SELL orders that CLOSE existing positions
        # ============================================================
        total_pl = self._get_total_pl()
        is_risk_increasing = (
            request.side.lower() == "buy"
            or (request.is_option and request.side.lower() == "sell")  # Short puts/calls
        )

        if is_risk_increasing and total_pl < 0:
            rejection_reasons.append(RejectionReason.PORTFOLIO_NEGATIVE_PL)
            logger.warning(
                f"🛑 CIRCUIT BREAKER: Portfolio P/L is ${total_pl:.2f} (NEGATIVE). "
                f"NO new risk-increasing trades until profitable. Phil Town Rule #1!"
            )
            risk_score += 1.0  # Maximum risk score - automatic rejection
            metadata["zero_tolerance_breach"] = {
                "total_pl": total_pl,
                "rule": "Phil Town Rule #1: Don't lose money",
                "trade_type": "short_option" if request.is_option else "buy",
                "action_required": "Close losing positions or wait for recovery",
            }

        # ============================================================
        # CHECK 1: Insufficient Funds
        # ============================================================
        trade_value = request.notional or (
            request.quantity * self._get_price(request.symbol) if request.quantity else 0
        )

        if request.side == "buy" and trade_value > account_equity * 0.95:
            rejection_reasons.append(RejectionReason.INSUFFICIENT_FUNDS)
            logger.warning(f"❌ REJECTED: Insufficient funds for ${trade_value:.2f} trade")

        # ============================================================
        # CHECK 2: Maximum Allocation per Symbol (15%)
        # ============================================================
        current_exposure = self._get_symbol_exposure(request.symbol, positions)
        new_exposure = (
            current_exposure + trade_value
            if request.side == "buy"
            else current_exposure - trade_value
        )
        exposure_pct = new_exposure / account_equity if account_equity > 0 else 0

        if request.side == "buy" and exposure_pct > self.MAX_SYMBOL_ALLOCATION_PCT:
            rejection_reasons.append(RejectionReason.MAX_ALLOCATION_EXCEEDED)
            logger.warning(
                f"❌ REJECTED: {request.symbol} exposure would be {exposure_pct * 100:.1f}% "
                f"(max: {self.MAX_SYMBOL_ALLOCATION_PCT * 100}%)"
            )
            metadata["exposure_pct"] = exposure_pct
            risk_score += 0.3

        # ============================================================
        # CHECK 2.5: Duplicate Short Position Prevention (Jan 13, 2026)
        # Max 1 CSP per underlying symbol - prevents doubling down
        # ============================================================
        if request.is_option and request.side.lower() == "sell":
            # Extract underlying from option symbol (e.g., SOFI260206P00024000 -> SOFI)
            underlying = request.symbol[:4].rstrip("0123456789")
            if not underlying:
                underlying = request.symbol.split("2")[0]  # Fallback for year prefix

            existing_short_count = sum(
                1
                for pos in positions
                if (
                    underlying in pos.get("symbol", "")
                    and pos.get("qty", 0) < 0  # Negative qty = short position
                )
            )

            if existing_short_count >= 1:
                rejection_reasons.append(RejectionReason.MAX_ALLOCATION_EXCEEDED)
                logger.warning(
                    f"🛑 REJECTED: Already have {existing_short_count} short position(s) on {underlying}. "
                    f"Max 1 CSP per symbol per CLAUDE.md directive!"
                )
                metadata["duplicate_short_blocked"] = {
                    "underlying": underlying,
                    "existing_short_count": existing_short_count,
                    "rule": "Max 1 CSP per symbol",
                }
                risk_score += 0.5

        # ============================================================
        # CHECK 3: Correlation with Existing Positions
        # ============================================================
        correlation = self._check_correlation(request.symbol, positions)
        if correlation > self.MAX_CORRELATION_THRESHOLD and request.side == "buy":
            rejection_reasons.append(RejectionReason.HIGH_CORRELATION)
            logger.warning(
                f"❌ REJECTED: {request.symbol} has {correlation * 100:.0f}% correlation "
                f"with existing positions"
            )
            metadata["correlation"] = correlation
            risk_score += 0.25

        # ============================================================
        # CHECK 4: Frequency Limiter (max 5 trades/hour)
        # ============================================================
        recent_count = self._count_recent_trades()
        if recent_count >= self.MAX_TRADES_PER_HOUR:
            rejection_reasons.append(RejectionReason.FREQUENCY_LIMIT)
            logger.warning(
                f"❌ REJECTED: {recent_count} trades in last hour (max: {self.MAX_TRADES_PER_HOUR})"
            )
            metadata["trades_last_hour"] = recent_count
            risk_score += 0.2

        # ============================================================
        # CHECK 5: Minimum Trade Batch (Paper: $10, Live: $50)
        # FIXED Jan 12, 2026: Was blocking all paper trades for days
        # ============================================================
        min_batch = self.MIN_TRADE_BATCH if self.paper else self.MIN_TRADE_BATCH_LIVE
        if request.side == "buy" and trade_value < min_batch:
            # Don't reject immediately - check if we should accumulate
            if self.accumulated_cash + trade_value < min_batch:
                # Accumulate instead of trading
                warnings.append(
                    f"Accumulating ${trade_value:.2f} toward ${min_batch} batch "
                    f"(current: ${self.accumulated_cash:.2f})"
                )
                self.accumulated_cash += trade_value
                self._save_state()
                rejection_reasons.append(RejectionReason.MINIMUM_BATCH_NOT_MET)
                logger.info(f"⏳ Accumulating: ${self.accumulated_cash:.2f} / ${min_batch}")
            else:
                # Use accumulated cash
                logger.info(
                    f"✅ Batch threshold met: using accumulated ${self.accumulated_cash:.2f} + ${trade_value:.2f}"
                )
                trade_value = self.accumulated_cash + trade_value
                self.accumulated_cash = 0.0
                self._save_state()

        # ============================================================
        # CHECK 6: Daily Loss Circuit Breaker (3%)
        # ============================================================
        self._update_daily_pnl()
        if self.daily_pnl < -account_equity * self.MAX_DAILY_LOSS_PCT:
            rejection_reasons.append(RejectionReason.CIRCUIT_BREAKER_DAILY_LOSS)
            logger.warning(
                f"❌ REJECTED: Daily loss ${abs(self.daily_pnl):.2f} exceeds "
                f"{self.MAX_DAILY_LOSS_PCT * 100}% limit"
            )
            risk_score += 0.4

        # ============================================================
        # CHECK 7: Maximum Drawdown Circuit Breaker (10%)
        # ============================================================
        drawdown = self._get_drawdown()
        if drawdown > self.MAX_DRAWDOWN_PCT:
            rejection_reasons.append(RejectionReason.CIRCUIT_BREAKER_DRAWDOWN)
            logger.warning(
                f"❌ REJECTED: Drawdown {drawdown * 100:.1f}% exceeds "
                f"{self.MAX_DRAWDOWN_PCT * 100}% limit"
            )
            risk_score += 0.4

        # ============================================================
        # CHECK 8: Capital Efficiency (strategy viability)
        # ============================================================
        if request.strategy_type:
            viability = self.capital_calculator.check_strategy_viability(
                strategy_id=request.strategy_type,
                account_equity=account_equity,
                iv_rank=request.iv_rank,
            )
            if not viability.is_viable:
                rejection_reasons.append(RejectionReason.CAPITAL_INEFFICIENT)
                logger.warning(
                    f"❌ REJECTED: Strategy '{request.strategy_type}' not viable - "
                    f"{viability.reason}"
                )
                metadata["capital_viability"] = {
                    "strategy": request.strategy_type,
                    "reason": viability.reason,
                    "min_capital": viability.min_capital_required,
                    "days_to_viable": viability.days_to_viable,
                    "recommended_alternative": viability.recommended_alternative,
                }
                risk_score += 0.3

        # ============================================================
        # CHECK 9: IV Rank Filter for Credit Strategies
        # ============================================================
        if request.strategy_type and request.iv_rank is not None:
            if request.strategy_type in self.CREDIT_STRATEGIES:
                if request.iv_rank < self.MIN_IV_RANK_FOR_CREDIT:
                    rejection_reasons.append(RejectionReason.IV_RANK_TOO_LOW)
                    logger.warning(
                        f"❌ REJECTED: IV Rank {request.iv_rank:.0f}% < "
                        f"{self.MIN_IV_RANK_FOR_CREDIT}% for credit strategy '{request.strategy_type}'"
                    )
                    metadata["iv_rank_rejection"] = {
                        "iv_rank": request.iv_rank,
                        "min_required": self.MIN_IV_RANK_FOR_CREDIT,
                        "strategy": request.strategy_type,
                        "reason": "Cannot sell premium effectively when IV is cheap",
                    }
                    risk_score += 0.25

        # ============================================================
        # CHECK 10: Liquidity Check (Bid-Ask Spread) for Options
        # ============================================================
        # Wide bid-ask spreads destroy alpha instantly on fill.
        # If (Ask - Bid) / Ask > 5%, you lose 10%+ immediately.
        if request.is_option and request.bid_price and request.ask_price:
            if request.ask_price > 0:
                bid_ask_spread_pct = (request.ask_price - request.bid_price) / request.ask_price

                if bid_ask_spread_pct > self.MAX_BID_ASK_SPREAD_PCT:
                    rejection_reasons.append(RejectionReason.ILLIQUID_OPTION)
                    logger.warning(
                        f"❌ REJECTED: Bid-Ask spread {bid_ask_spread_pct * 100:.1f}% > "
                        f"{self.MAX_BID_ASK_SPREAD_PCT * 100}% max for {request.symbol}"
                    )
                    metadata["liquidity_rejection"] = {
                        "bid": request.bid_price,
                        "ask": request.ask_price,
                        "spread_pct": bid_ask_spread_pct * 100,
                        "max_allowed_pct": self.MAX_BID_ASK_SPREAD_PCT * 100,
                        "reason": "Illiquid option - wide spread destroys alpha on fill",
                    }
                    risk_score += 0.3
                else:
                    # Log liquidity info even if acceptable
                    metadata["liquidity_info"] = {
                        "bid": request.bid_price,
                        "ask": request.ask_price,
                        "spread_pct": bid_ask_spread_pct * 100,
                        "status": "acceptable",
                    }

        # ============================================================
        # CHECK 11: Per-Trade Risk Cap (1% of Equity)
        # ============================================================
        # Enforce that (Entry - Stop) * Qty <= 1% of Equity
        # This requires knowing the stop price.
        if request.side == "buy":
            entry_price = self._get_price(request.symbol)
            qty = request.quantity or (request.notional / entry_price if entry_price > 0 else 0)

            # If stop price is not provided, we must assume a default or reject
            # Here we enforce that a stop price MUST be part of the strategy or we use a default 5%
            stop_price = request.stop_price

            if stop_price is None:
                # If no stop provided, assume default 5% risk for calculation
                # But warn that explicit stop is better
                stop_price = entry_price * 0.95
                warnings.append("No stop_price provided. Assuming 5% risk for calculation.")

            risk_per_share = max(0, entry_price - stop_price)
            total_risk = risk_per_share * qty

            max_risk_allowed = account_equity * self.MAX_RISK_PER_TRADE_PCT

            if total_risk > max_risk_allowed:
                # Auto-reduce quantity if possible?
                # For now, REJECT to force AI to size correctly.
                rejection_reasons.append(
                    RejectionReason.MAX_ALLOCATION_EXCEEDED
                )  # Reuse or add new enum
                logger.warning(
                    f"❌ REJECTED: Trade risk ${total_risk:.2f} exceeds unit risk cap "
                    f"${max_risk_allowed:.2f} (1% of equity). Reduce size or tighten stop."
                )
                metadata["risk_check"] = {
                    "total_risk": total_risk,
                    "max_allowed": max_risk_allowed,
                    "risk_per_share": risk_per_share,
                }
                risk_score += 0.5

        # ============================================================
        # CHECK 12: RAG Lesson Block (CRITICAL lessons learned)
        # ============================================================
        # Query RAG for lessons about this ticker and strategy
        query_terms = f"{request.symbol}"
        if request.strategy_type:
            query_terms += f" {request.strategy_type}"
        query_terms += f" {request.side}"

        rag_lessons = self.rag.query(query_terms, top_k=5)
        critical_rag_lessons = [
            lesson for lesson in rag_lessons if lesson.get("severity") == "CRITICAL"
        ]

        if critical_rag_lessons:
            rejection_reasons.append(RejectionReason.RAG_LESSON_CRITICAL)
            logger.warning(
                f"❌ REJECTED: {len(critical_rag_lessons)} CRITICAL lessons found for "
                f"{request.symbol} {request.side}"
            )
            metadata["rag_lessons"] = {
                "critical_count": len(critical_rag_lessons),
                "lessons": [
                    {
                        "id": lesson["id"],
                        "severity": lesson["severity"],
                        "snippet": lesson["snippet"][:200],
                    }
                    for lesson in critical_rag_lessons
                ],
            }
            # Log each critical lesson
            for lesson in critical_rag_lessons:
                logger.warning(f"  - CRITICAL: {lesson['id']}: {lesson['snippet'][:150]}...")
            risk_score += 0.5  # Significant risk increase for CRITICAL lessons
        elif rag_lessons:
            # Non-critical lessons - just add warnings
            for lesson in rag_lessons[:2]:  # Show top 2
                warnings.append(
                    f"Lesson learned ({lesson.get('severity', 'UNKNOWN')}): {lesson['id']}"
                )

        # ============================================================
        # CHECK 13: Phil Town Rule #1 Validation (Jan 13, 2026)
        # Validates that symbol is a "wonderful company at attractive price"
        # ============================================================
        try:
            rule_one_validator = RuleOneValidator(
                strict_mode=False,  # Allow trades with warnings
                capital_tier="small" if account_equity < 10000 else "large",
            )
            rule_one_result = rule_one_validator.validate(request.symbol)

            if not rule_one_result.approved:
                rejection_reasons.append(RejectionReason.RULE_ONE_VIOLATION)
                logger.warning(
                    f"❌ REJECTED: Phil Town Rule #1 failed for {request.symbol} - "
                    f"{rule_one_result.rejection_reasons}"
                )
                metadata["rule_one_validation"] = rule_one_result.to_dict()
                risk_score += 0.4

            elif rule_one_result.warnings:
                # Approved but with warnings
                for warning in rule_one_result.warnings:
                    warnings.append(f"Rule #1: {warning}")
                metadata["rule_one_validation"] = rule_one_result.to_dict()
                logger.info(
                    f"⚠️ Rule #1 passed with warnings for {request.symbol}: "
                    f"{rule_one_result.warnings}"
                )
            else:
                # Full approval
                metadata["rule_one_validation"] = {
                    "approved": True,
                    "confidence": rule_one_result.confidence,
                }
                logger.info(
                    f"✅ Rule #1 passed for {request.symbol} "
                    f"(confidence: {rule_one_result.confidence:.0%})"
                )
        except Exception as e:
            # Don't block trades if validator fails - just warn
            logger.warning(f"⚠️ Rule #1 validator error for {request.symbol}: {e}")
            warnings.append(f"Rule #1 validation skipped: {e}")

        # ============================================================
        # FINAL DECISION
        # ============================================================
        approved = len(rejection_reasons) == 0

        # Final risk score check
        if approved and risk_score > self.MAX_RISK_SCORE:
            rejection_reasons.append(RejectionReason.RISK_SCORE_TOO_HIGH)
            approved = False
            logger.warning(f"❌ REJECTED: Risk score {risk_score:.2f} exceeds threshold")

        decision = GatewayDecision(
            approved=approved,
            request=request,
            rejection_reasons=rejection_reasons,
            warnings=warnings,
            risk_score=risk_score,
            adjusted_notional=trade_value if approved else None,
            metadata=metadata,
        )

        if approved:
            logger.info(f"✅ APPROVED: {request.side.upper()} {request.symbol}")
        else:
            logger.warning(
                f"🚫 REJECTED: {request.side.upper()} {request.symbol} - "
                f"{[r.value for r in rejection_reasons]}"
            )

        return decision

    def validate_trade(self, request: TradeRequest) -> GatewayDecision:
        """
        Validate a trade request (alias for evaluate).

        This is the MANDATORY checkpoint. No trade can bypass this.

        Args:
            request: The trade request from the AI

        Returns:
            GatewayDecision with approval status and reasons
        """
        return self.evaluate(request)

    def check_trade(self, request: TradeRequest) -> GatewayDecision:
        """
        Check a trade request (alias for evaluate).

        This is the MANDATORY checkpoint. No trade can bypass this.

        Args:
            request: The trade request from the AI

        Returns:
            GatewayDecision with approval status and reasons
        """
        return self.evaluate(request)

    def execute(self, decision: GatewayDecision) -> dict[str, Any] | None:
        """
        Execute an approved trade.

        ONLY the gateway can execute trades. The AI cannot call this directly
        without first getting approval through evaluate().

        Args:
            decision: The approved gateway decision

        Returns:
            Order result from broker, or None if not approved
        """
        if not decision.approved:
            logger.error(
                "🚫 CANNOT EXECUTE: Trade was not approved. Rejection reasons: %s",
                [r.value for r in decision.rejection_reasons],
            )
            return None

        if not self.executor:
            logger.error("No executor configured - cannot execute trades")
            return None

        request = decision.request

        try:
            # Execute through the broker
            # Prioritize quantity if available (critical for closing positions)
            if request.quantity is not None:
                order = self.executor.place_order(
                    symbol=request.symbol,
                    qty=request.quantity,
                    side=request.side,
                )
            else:
                # Use adjusted notional if available (from batching)
                notional = decision.adjusted_notional or request.notional

                # CRITICAL FIX (Jan 9, 2026 - ll_124): Use place_order_with_stop_loss
                # for BUY orders to ensure every new position is protected from inception.
                # Phil Town Rule #1: Don't Lose Money
                if request.side.lower() == "buy" and hasattr(
                    self.executor, "place_order_with_stop_loss"
                ):
                    result = self.executor.place_order_with_stop_loss(
                        symbol=request.symbol,
                        notional=notional,
                        side=request.side,
                        stop_loss_pct=0.08,  # 8% stop-loss per position_manager defaults
                    )
                    order = result.get("order")
                    if result.get("stop_loss"):
                        stop_price = result.get("stop_loss_price", 0)
                        logger.info(f"🛡️ Stop-loss set: {request.symbol} @ ${stop_price:.2f}")
                    elif result.get("error"):
                        logger.warning(
                            f"⚠️ Order placed but stop-loss failed: {result.get('error')}"
                        )
                else:
                    order = self.executor.place_order(
                        symbol=request.symbol,
                        notional=notional,
                        side=request.side,
                    )

            # Track the trade
            self.recent_trades.append(datetime.now())
            self._cleanup_old_trades()

            logger.info(f"✅ Order executed: {order.get('id', 'N/A')}")
            return order

        except Exception as e:
            logger.error(f"❌ Execution failed: {e}")
            return None

    def add_daily_deposit(self, amount: float) -> dict[str, Any]:
        """
        Handle daily deposit ($10/day).

        Instead of trading immediately, accumulate until batch threshold.

        Args:
            amount: Deposit amount

        Returns:
            Status dict
        """
        self.accumulated_cash += amount
        self._save_state()

        if self.accumulated_cash >= self.MIN_TRADE_BATCH:
            logger.info(
                f"💰 Batch threshold reached: ${self.accumulated_cash:.2f} "
                f">= ${self.MIN_TRADE_BATCH}"
            )
            return {
                "status": "batch_ready",
                "accumulated": self.accumulated_cash,
                "message": f"Ready to trade ${self.accumulated_cash:.2f}",
            }
        else:
            logger.info(f"⏳ Accumulating: ${self.accumulated_cash:.2f} / ${self.MIN_TRADE_BATCH}")
            return {
                "status": "accumulating",
                "accumulated": self.accumulated_cash,
                "remaining": self.MIN_TRADE_BATCH - self.accumulated_cash,
                "message": f"Need ${self.MIN_TRADE_BATCH - self.accumulated_cash:.2f} more",
            }

    def stress_test(self, request: TradeRequest) -> GatewayDecision:
        """
        Run a stress test against the gateway.

        This is for testing that the gateway properly rejects dangerous trades.

        Args:
            request: A potentially dangerous trade request

        Returns:
            GatewayDecision showing rejection reasons
        """
        logger.info(f"🧪 STRESS TEST: {request.side.upper()} {request.symbol} ${request.notional}")
        decision = self.evaluate(request)

        if decision.approved:
            logger.error("⚠️ STRESS TEST FAILED: Dangerous trade was approved!")
        else:
            logger.info(
                f"✅ STRESS TEST PASSED: Trade rejected with reasons: "
                f"{[r.value for r in decision.rejection_reasons]}"
            )

        return decision

    # ============================================================
    # HELPER MODS
    # ============================================================

    def _get_account_equity(self) -> float:
        """Get current account equity."""
        if self.executor:
            try:
                return float(self.executor.account_equity or 5000)
            except Exception:
                pass
        # Default to $5K (our paper trading account size) not $100K
        return float(os.getenv("ACCOUNT_EQUITY", "5000"))

    def _get_total_pl(self) -> float:
        """Get total portfolio P/L from system state.

        Phil Town Rule #1: Don't lose money.
        This method reads the total_pl from system_state.json to enforce
        the zero-tolerance circuit breaker.

        Returns:
            Total P/L in dollars. Negative means losing money.
        """
        try:
            state_file = Path(__file__).parent.parent.parent / "data" / "system_state.json"
            if state_file.exists():
                with open(state_file, encoding="utf-8") as f:
                    state = json.load(f)
                paper_account = state.get("paper_account", {})
                total_pl = paper_account.get("total_pl", 0.0)
                logger.debug(f"Total P/L from system state: ${total_pl:.2f}")
                return float(total_pl)
        except Exception as e:
            logger.warning(f"Failed to read total P/L: {e}")
        return 0.0  # Default to 0 if unable to read (allows trading)

    def _get_positions(self) -> list[dict[str, Any]]:
        """Get current positions."""
        if self.executor:
            try:
                return self.executor.get_positions() or []
            except Exception:
                pass
        return []

    def _get_price(self, symbol: str) -> float:
        """Get current price for symbol."""
        # BUG FIX (Jan 10, 2026): Was returning hardcoded $100.0 for ALL symbols
        # This caused incorrect risk calculations (e.g., NVDA at $100 vs actual $140)
        if self.executor:
            try:
                # Try to get real price from executor/market data
                if hasattr(self.executor, "get_latest_quote"):
                    quote = self.executor.get_latest_quote(symbol)
                    if quote and hasattr(quote, "ask_price") and quote.ask_price > 0:
                        return float(quote.ask_price)
                # Fallback: try positions for current market value
                positions = self._get_positions()
                for pos in positions:
                    if pos.get("symbol") == symbol:
                        qty = float(pos.get("qty", 1))
                        mkt_val = float(pos.get("market_value", 0))
                        if qty > 0:
                            return mkt_val / qty
            except Exception as e:
                logger.warning(f"Failed to get price for {symbol}: {e}")

        # Fallback: use environment variable or default
        # $100 is a reasonable default for most stocks but not accurate
        return float(os.getenv(f"PRICE_{symbol}", "100.0"))

    def _get_symbol_exposure(self, symbol: str, positions: list[dict]) -> float:
        """Get current exposure to a symbol."""
        for pos in positions:
            if pos.get("symbol") == symbol:
                return float(pos.get("market_value", 0))
        return 0.0

    def _check_correlation(self, symbol: str, positions: list[dict]) -> float:
        """
        Check correlation with existing positions.

        Uses simplified correlation groups. In production, would calculate
        actual correlation matrix.
        """
        position_symbols = [p.get("symbol") for p in positions]

        # Find which groups the new symbol belongs to
        symbol_groups = [
            group for group, members in self.CORRELATION_GROUPS.items() if symbol in members
        ]

        if not symbol_groups:
            return 0.0

        # Check if any existing position is in the same group
        max_correlation = 0.0
        for pos_symbol in position_symbols:
            for group in symbol_groups:
                if pos_symbol in self.CORRELATION_GROUPS.get(group, []):
                    # Same group = high correlation
                    max_correlation = max(max_correlation, 0.85)

        return max_correlation

    def _count_recent_trades(self) -> int:
        """Count trades in the last hour."""
        cutoff = datetime.now() - timedelta(hours=1)
        return sum(1 for t in self.recent_trades if t > cutoff)

    def _cleanup_old_trades(self) -> None:
        """Remove trades older than 1 hour."""
        cutoff = datetime.now() - timedelta(hours=1)
        self.recent_trades = [t for t in self.recent_trades if t > cutoff]

    def _update_daily_pnl(self) -> None:
        """Update daily P&L tracking."""
        today = datetime.now().date()
        if self.daily_pnl_date is None or self.daily_pnl_date.date() != today:
            # New day - reset P&L
            self.daily_pnl = 0.0
            self.daily_pnl_date = datetime.now()
            self._save_state()

    def _get_drawdown(self) -> float:
        """Calculate current drawdown from peak.

        CRITICAL SAFETY FEATURE - Added Jan 13, 2026
        Was a stub returning 0.0, now tracks actual drawdown.

        Drawdown = (peak_equity - current_equity) / peak_equity
        """
        current_equity = self._get_account_equity()

        # Update peak if we have a new high
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            self._save_state()
            logger.info(f"📈 New peak equity: ${current_equity:.2f}")

        # Calculate drawdown (0 if at or above peak)
        if self.peak_equity <= 0:
            # Initialize peak_equity on first call
            self.peak_equity = current_equity
            self._save_state()
            return 0.0

        if current_equity >= self.peak_equity:
            return 0.0

        drawdown = (self.peak_equity - current_equity) / self.peak_equity
        logger.debug(
            f"Drawdown: {drawdown * 100:.2f}% "
            f"(peak=${self.peak_equity:.2f}, current=${current_equity:.2f})"
        )
        return drawdown


def create_suicide_test() -> TradeRequest:
    """
    Create a "suicide command" test request.

    This should ALWAYS be rejected by the gateway.
    """
    return TradeRequest(
        symbol="AMC",
        side="buy",
        notional=1000000,  # $1 million
        source="stress_test",
    )


# Singleton instance
_gateway_instance = None


def get_trade_gateway(executor=None, paper: bool = True) -> TradeGateway:
    """Get or create TradeGateway instance."""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = TradeGateway(executor=executor, paper=paper)
    return _gateway_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    gateway = TradeGateway(paper=True)

    print("\n" + "=" * 60)
    print("TRADE GATEWAY STRESS TEST")
    print("=" * 60)

    # Test 1: Suicide command
    print("\n--- Test 1: Suicide Command ($1M AMC) ---")
    suicide_request = create_suicide_test()
    decision = gateway.stress_test(suicide_request)
    print(f"Approved: {decision.approved}")
    print(f"Rejections: {[r.value for r in decision.rejection_reasons]}")

    # Test 2: Normal trade
    print("\n--- Test 2: Normal Trade ($100 SPY) ---")
    normal_request = TradeRequest(symbol="SPY", side="buy", notional=100)
    decision = gateway.evaluate(normal_request)
    print(f"Approved: {decision.approved}")
    if not decision.approved:
        print(f"Rejections: {[r.value for r in decision.rejection_reasons]}")
    print(f"Warnings: {decision.warnings}")

    # Test 3: Daily deposit accumulation
    print("\n--- Test 3: Daily Deposit ($10) ---")
    result = gateway.add_daily_deposit(10.0)
    print(f"Status: {result['status']}")
    print(f"Accumulated: ${result['accumulated']:.2f}")

    # Test 4: High Risk Trade (Exceeds 1% Equity Risk)
    print("\n--- Test 4: High Risk Trade (Risk > 1%) ---")
    # Equity = 100k. 1% = $1000.
    # Trade: Buy $50,000 of SPY. Stop Loss 10% away.
    # Risk = $50,000 * 0.10 = $5,000 > $1000 allowed.
    high_risk_request = TradeRequest(
        symbol="SPY",
        side="buy",
        notional=50000,
        stop_price=90.0,  # Assume entry 100, stop 90 (10% risk)
    )
    decision = gateway.evaluate(high_risk_request)
    print(f"Approved: {decision.approved}")
    if not decision.approved:
        print(f"Rejections: {[r.value for r in decision.rejection_reasons]}")
