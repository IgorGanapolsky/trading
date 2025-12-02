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
from typing import Any, Optional

from src.risk.capital_efficiency import get_capital_calculator

logger = logging.getLogger(__name__)


class RejectionReason(Enum):
    """Enumeration of trade rejection reasons."""

    INSUFFICIENT_FUNDS = "Insufficient funds in account"
    MAX_ALLOCATION_EXCEEDED = "Maximum allocation per symbol exceeded (15%)"
    HIGH_CORRELATION = "High correlation with existing positions (>0.8)"
    FREQUENCY_LIMIT = "Frequency limit exceeded (>5 trades/hour)"
    CIRCUIT_BREAKER_DAILY_LOSS = "Daily loss limit exceeded"
    CIRCUIT_BREAKER_DRAWDOWN = "Maximum drawdown exceeded"
    MINIMUM_BATCH_NOT_MET = "Minimum trade batch not accumulated ($200)"
    INVALID_ORDER = "Invalid order parameters"
    MARKET_CLOSED = "Market is closed"
    RISK_SCORE_TOO_HIGH = "Trade risk score exceeds threshold"
    CAPITAL_INEFFICIENT = "Strategy not viable for current capital level"
    IV_RANK_TOO_LOW = "IV Rank too low for premium selling (<20)"
    ILLIQUID_OPTION = "Option is illiquid (bid-ask spread > 5%)"


@dataclass
class TradeRequest:
    """Represents a trade request from the AI."""

    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: Optional[float] = None
    notional: Optional[float] = None
    order_type: str = "market"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    request_time: datetime = field(default_factory=datetime.now)
    source: str = "ai_agent"  # Track where the request came from
    strategy_type: Optional[str] = None  # e.g., 'iron_condor', 'vertical_spread'
    iv_rank: Optional[float] = None  # Current IV Rank for the underlying
    bid_price: Optional[float] = None  # Current bid price (for liquidity check)
    ask_price: Optional[float] = None  # Current ask price (for liquidity check)
    is_option: bool = False  # True if this is an options trade


@dataclass
class GatewayDecision:
    """Result of the gateway's risk assessment."""

    approved: bool
    request: TradeRequest
    rejection_reasons: list[RejectionReason] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    adjusted_quantity: Optional[float] = None
    adjusted_notional: Optional[float] = None
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
    MAX_SYMBOL_ALLOCATION_PCT = 0.15  # 15% max per symbol
    MAX_CORRELATION_THRESHOLD = 0.80  # 80% correlation threshold
    MAX_TRADES_PER_HOUR = 5  # Frequency limit
    MIN_TRADE_BATCH = 200.0  # $200 minimum to reduce noise
    MAX_DAILY_LOSS_PCT = 0.03  # 3% max daily loss
    MAX_DRAWDOWN_PCT = 0.10  # 10% max drawdown
    MAX_RISK_SCORE = 0.75  # Risk score threshold

    # Correlation matrix for common holdings (simplified)
    # In production, this would be calculated dynamically
    CORRELATION_GROUPS = {
        "semiconductors": ["NVDA", "AMD", "INTC", "TSM", "AVGO", "QCOM", "MU"],
        "mega_tech": ["AAPL", "MSFT", "GOOGL", "GOOG", "META", "AMZN"],
        "ev_auto": ["TSLA", "RIVN", "LCID", "F", "GM"],
        "crypto_adjacent": ["COIN", "MSTR", "SQ", "PYPL"],
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
        self.last_accumulation_date: Optional[datetime] = None

        # Daily P&L tracking
        self.daily_pnl = 0.0
        self.daily_pnl_date: Optional[datetime] = None

        # Capital efficiency calculator
        self.capital_calculator = get_capital_calculator(daily_deposit_rate=10.0)

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
        # CHECK 5: Minimum Trade Batch ($200)
        # ============================================================
        if request.side == "buy" and trade_value < self.MIN_TRADE_BATCH:
            # Don't reject immediately - check if we should accumulate
            if self.accumulated_cash + trade_value < self.MIN_TRADE_BATCH:
                # Accumulate instead of trading
                warnings.append(
                    f"Accumulating ${trade_value:.2f} toward ${self.MIN_TRADE_BATCH} batch "
                    f"(current: ${self.accumulated_cash:.2f})"
                )
                self.accumulated_cash += trade_value
                self._save_state()
                rejection_reasons.append(RejectionReason.MINIMUM_BATCH_NOT_MET)
                logger.info(
                    f"⏳ Accumulating: ${self.accumulated_cash:.2f} / ${self.MIN_TRADE_BATCH}"
                )
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

    def execute(self, decision: GatewayDecision) -> Optional[dict[str, Any]]:
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
            # Use adjusted notional if available (from batching)
            notional = decision.adjusted_notional or request.notional

            logger.info(
                f"🚀 Gateway executing: {request.side.upper()} {request.symbol} ${notional:.2f}"
            )

            # Execute through the broker
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
    # HELPER METHODS
    # ============================================================

    def _get_account_equity(self) -> float:
        """Get current account equity."""
        if self.executor:
            try:
                return float(self.executor.account_equity or 100000)
            except:
                pass
        return float(os.getenv("ACCOUNT_EQUITY", "100000"))

    def _get_positions(self) -> list[dict[str, Any]]:
        """Get current positions."""
        if self.executor:
            try:
                return self.executor.get_positions() or []
            except:
                pass
        return []

    def _get_price(self, symbol: str) -> float:
        """Get current price for symbol."""
        # In production, fetch from market data
        return 100.0  # Placeholder

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
        """Calculate current drawdown from peak."""
        # In production, track peak equity and calculate drawdown
        return 0.0  # Placeholder


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
