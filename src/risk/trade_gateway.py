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
from src.risk.pre_trade_checklist import PreTradeChecklist
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
    RULE_ONE_VIOLATION = (
        "Phil Town Rule #1 validation failed - not a wonderful company at attractive price"
    )
    EARNINGS_BLACKOUT = "Ticker is in earnings blackout period - avoid new positions"
    POSITION_SIZE_TOO_LARGE = "Position max loss exceeds 5% of portfolio"
    TICKER_NOT_ALLOWED = "Ticker not in whitelist - SPY ONLY per CLAUDE.md Jan 19, 2026"
    FORBIDDEN_STRATEGY = "Strategy is forbidden - naked positions not allowed"
    PRE_TRADE_CHECKLIST_FAILED = "Pre-trade checklist failed - CLAUDE.md rules violated"
    DTE_OUT_OF_RANGE = "DTE must be 30-45 days per CLAUDE.md"
    CUMULATIVE_RISK_TOO_HIGH = "Cumulative position risk exceeds 5% limit"
    MAX_IRON_CONDORS_EXCEEDED = "Max 1 iron condor at a time per CLAUDE.md"


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
    # ADDED Jan 15, 2026: For PreTradeChecklist integration
    dte: int | None = None  # Days to expiration (30-45 per CLAUDE.md)
    is_spread: bool = True  # True if spread, False if naked (naked forbidden)
    max_loss: float | None = None  # Maximum potential loss in dollars
    spread_width: float | None = None  # Width of spread in dollars (e.g., 5.0)
    premium_received: float | None = None  # Premium received for credit spreads


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
    # UPDATED Jan 19, 2026: Enforced 5% per CLAUDE.md (Phil Town Rule #1)
    # Previous: 10% per symbol (Jan 14) - Still too high, caused 35% exposure
    MAX_SYMBOL_ALLOCATION_PCT = 0.05  # 5% max per symbol per CLAUDE.md
    MAX_CORRELATION_THRESHOLD = 0.80  # 80% correlation threshold
    MAX_TRADES_PER_HOUR = 5  # Frequency limit
    MIN_TRADE_BATCH = (
        10.0  # $10 minimum for paper trading - FIXED Jan 12, 2026 (was $50, blocked all trades)
    )
    MIN_TRADE_BATCH_LIVE = 50.0  # $50 for live trading - fee protection
    # FIXED Jan 19, 2026: Import from central constants for consistency
    try:
        from src.core.trading_constants import MAX_DAILY_LOSS_PCT as _CENTRAL_DAILY_LOSS

        MAX_DAILY_LOSS_PCT = _CENTRAL_DAILY_LOSS
    except ImportError:
        MAX_DAILY_LOSS_PCT = 0.05  # 5% fallback per trading_constants.py
    MAX_DRAWDOWN_PCT = 0.10  # 10% max drawdown
    MAX_RISK_PER_TRADE_PCT = 0.02  # 2% max risk per trade - INDUSTRY STANDARD (was 1%)
    MAX_RISK_SCORE = 0.75  # Risk score threshold
    MIN_CASH_RESERVE_PCT = 0.50  # 50% cash reserve minimum (NEW Jan 14, 2026)

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
        # REMOVED: "naked_put" - NO NAKED PUTS per CLAUDE.md (Jan 14, 2026)
    }
    MIN_IV_RANK_FOR_CREDIT = 20  # Minimum IV Rank for premium selling

    # ============================================================
    # TICKER WHITELIST - CRITICAL ENFORCEMENT (Jan 19, 2026)
    # Per CLAUDE.md: "SPY ONLY - best liquidity, tightest spreads"
    # This prevents trades like SOFI/IWM that violated strategy
    # UPDATED Jan 19: Import from central config (single source of truth)
    # ============================================================
    try:
        from src.core.trading_constants import ALLOWED_TICKERS as _CENTRAL_TICKERS

        ALLOWED_TICKERS = _CENTRAL_TICKERS
    except ImportError:
        ALLOWED_TICKERS = {"SPY"}  # Fallback - SPY ONLY per CLAUDE.md Jan 19
    TICKER_WHITELIST_ENABLED = True  # Toggle for paper testing

    # FORBIDDEN strategies - will be rejected outright
    FORBIDDEN_STRATEGIES = {
        "naked_put",  # NO NAKED PUTS - must use spreads
        "naked_call",  # NO NAKED CALLS
        "short_straddle",  # Undefined risk
        "short_strangle",  # Undefined risk without wings
    }

    # Liquidity check - options with wide spreads destroy alpha on fill
    MAX_BID_ASK_SPREAD_PCT = 0.05  # 5% maximum bid-ask spread

    # Earnings blackout calendar (Jan 2026)
    # UPDATED Jan 15, 2026: Block trades 7 days before through 1 day after earnings
    # LL-190: SOFI CSP was opened during blackout - caused 48% portfolio risk
    # LL-191: SOFI position still open despite strategy saying "AVOID until Feb 1"
    EARNINGS_BLACKOUTS = {
        "SOFI": {
            "start": "2026-01-23",
            "end": "2026-02-01",
            "earnings": "2026-01-30",
        },  # 7 days before earnings
        "F": {
            "start": "2026-02-03",
            "end": "2026-02-11",
            "earnings": "2026-02-10",
        },  # 7 days before earnings
        # Add more tickers as needed
    }

    # Maximum position risk as percentage of portfolio
    # LL-190: SOFI CSP had 48% portfolio risk - unacceptable
    # UPDATED Jan 15, 2026: Changed from 10% to 5% per CLAUDE.md mandate
    # CLAUDE.md: "Position limit: 1 spread at a time (5% max = $248 risk)"
    MAX_POSITION_RISK_PCT = 0.05  # 5% max risk per position - MANDATORY per CLAUDE.md

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

    def _get_underlying_symbol(self, symbol: str) -> str:
        """Extract underlying symbol from option symbol (OCC format)."""
        # OCC format: SOFI260206P00024000 -> SOFI
        # Format: [UNDERLYING][YYMMDD][P/C][STRIKE*1000]
        # Strike is always 8 digits, P/C is 1 char, date is 6 digits
        # So underlying = symbol[:-15] for standard options

        import re

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

    def _check_earnings_blackout(self, symbol: str) -> tuple[bool, str]:
        """
        Check if symbol is in earnings blackout period.

        Args:
            symbol: Stock or option symbol

        Returns:
            (is_blocked, reason_message)
        """
        today = datetime.now().date()
        underlying = self._get_underlying_symbol(symbol)

        if underlying.upper() in self.EARNINGS_BLACKOUTS:
            blackout = self.EARNINGS_BLACKOUTS[underlying.upper()]
            start = datetime.strptime(blackout["start"], "%Y-%m-%d").date()
            end = datetime.strptime(blackout["end"], "%Y-%m-%d").date()
            earnings = blackout["earnings"]

            if start <= today <= end:
                return (
                    True,
                    f"{underlying} in earnings blackout {start} to {end} (earnings: {earnings})",
                )

        return False, ""

    def _check_position_size_risk(
        self, request: TradeRequest, account_equity: float
    ) -> tuple[bool, str]:
        """
        Check if position max loss exceeds portfolio risk limit.

        For options:
        - Short put max loss = strike * 100 (per contract)
        - Credit spread max loss = spread width * 100

        Args:
            request: Trade request
            account_equity: Current account equity

        Returns:
            (is_too_risky, reason_message)
        """
        if not request.is_option:
            # For stocks, check notional vs equity
            trade_value = request.notional or 0
            if trade_value > account_equity * self.MAX_POSITION_RISK_PCT:
                return (
                    True,
                    f"Trade value ${trade_value:.0f} exceeds {self.MAX_POSITION_RISK_PCT * 100:.0f}% of equity",
                )
            return False, ""

        # For options, estimate max loss based on strategy
        # This is a simplified check - full calculation would need Greeks
        max_loss = 0

        if request.strategy_type in ["cash_secured_put", "naked_put"]:
            # Max loss = strike price * 100 * quantity
            # Try to extract strike from symbol or use limit price as proxy
            strike = request.limit_price or 25  # Default assumption
            max_loss = strike * 100 * (request.quantity or 1)
        elif request.strategy_type in ["bull_put_spread", "credit_spread"]:
            # Max loss = spread width * 100 * quantity
            # Typically $5 wide spreads = $500 max loss
            max_loss = 500 * (request.quantity or 1)
        else:
            # Conservative default for unknown option strategies
            max_loss = 500 * (request.quantity or 1)

        max_risk_pct = max_loss / account_equity if account_equity > 0 else 1.0

        if max_risk_pct > self.MAX_POSITION_RISK_PCT:
            return (
                True,
                f"Max loss ${max_loss:.0f} ({max_risk_pct * 100:.1f}%) exceeds {self.MAX_POSITION_RISK_PCT * 100:.0f}% limit",
            )

        return False, ""

    def _calculate_credit_spread_max_loss(self, request: TradeRequest) -> float:
        """
        Calculate max loss for a credit spread position.

        Per CLAUDE.md: max_loss = (spread_width * 100) - premium

        For a standard $5 wide spread with $0.70 premium:
        max_loss = ($5 * 100) - $70 = $500 - $70 = $430 per contract

        Args:
            request: Trade request with spread details

        Returns:
            Maximum potential loss in dollars
        """
        # If max_loss is already provided, use it
        if request.max_loss is not None:
            return request.max_loss

        # If spread_width and premium are provided, calculate
        if request.spread_width is not None:
            spread_width = request.spread_width
            premium = request.premium_received or 0.0
            contracts = request.quantity or 1

            # max_loss = (spread_width * 100 * contracts) - (premium * 100 * contracts)
            max_loss = (spread_width * 100 * contracts) - (premium * 100 * contracts)
            return max(0, max_loss)  # Can't be negative

        # Fallback: estimate based on strategy type
        contracts = request.quantity or 1
        if request.strategy_type in ["bull_put_spread", "bear_call_spread", "credit_spread"]:
            # Default $5 spread, $0.50 premium = $450 max loss per contract
            return 450.0 * contracts
        elif request.strategy_type == "iron_condor":
            # Default $5 wings, $1.00 total premium = $400 max loss per contract
            return 400.0 * contracts
        elif request.strategy_type in ["cash_secured_put", "naked_put"]:
            # For CSP/naked put: max_loss = strike * 100 (full assignment risk)
            # Use limit_price as strike proxy
            strike = request.limit_price or 25  # Default conservative estimate
            return strike * 100 * contracts

        # Conservative default for unknown option strategies
        return 500.0 * contracts

    def _check_cumulative_position_risk(
        self, request: TradeRequest, account_equity: float, positions: list
    ) -> tuple[bool, str]:
        """
        Check CUMULATIVE position risk including existing positions.

        LL-XXX (Jan 22, 2026): Individual trades passing 5% check but accumulating
        to 19.6% risk. This check prevents that by summing existing + new risk.

        Args:
            request: New trade request
            account_equity: Current account equity
            positions: Existing positions

        Returns:
            (is_too_risky, reason_message)
        """
        # Calculate existing risk from positions
        existing_risk = 0.0
        for pos in positions:
            symbol = pos.get("symbol", "")
            unrealized_pl = float(pos.get("unrealized_pl", 0))

            # Only count option positions for risk
            if len(symbol) > 10:  # Option symbols are longer
                # Estimate risk as max potential loss
                # For long options: premium paid (use market value as proxy)
                # For short options: spread width * 100 - premium
                mkt_val = abs(float(pos.get("market_value", 0)))
                if unrealized_pl < 0:
                    existing_risk += abs(unrealized_pl)  # Already losing
                else:
                    existing_risk += mkt_val * 0.5  # Estimate half of market value as risk

        # Calculate new trade risk
        new_risk = self._calculate_credit_spread_max_loss(request)

        # Total risk
        total_risk = existing_risk + new_risk
        total_risk_pct = total_risk / account_equity if account_equity > 0 else 1.0

        # CLAUDE.md says 5% max - but we allow up to 10% cumulative to account for volatility
        MAX_CUMULATIVE_RISK_PCT = 0.10

        if total_risk_pct > MAX_CUMULATIVE_RISK_PCT:
            return (
                True,
                f"Cumulative risk ${total_risk:.0f} ({total_risk_pct * 100:.1f}%) exceeds "
                f"{MAX_CUMULATIVE_RISK_PCT * 100:.0f}% limit. Existing: ${existing_risk:.0f}, "
                f"New: ${new_risk:.0f}",
            )

        return False, ""

    def _check_iron_condor_limit(self, positions: list) -> tuple[bool, str]:
        """
        Enforce '1 iron condor at a time' rule per CLAUDE.md.

        LL-XXX (Jan 22, 2026): System was placing multiple iron condors,
        violating the position limit rule.

        Returns:
            (has_existing_condor, reason_message)
        """
        # Count iron condor structures
        # An iron condor has: 2 short options + 2 long options at different strikes
        # Group by expiration to detect condors

        option_positions = [p for p in positions if len(p.get("symbol", "")) > 10]

        if len(option_positions) < 4:
            return False, ""  # Not enough positions for a condor

        # Group by expiration date
        by_expiry = {}
        for pos in option_positions:
            symbol = pos.get("symbol", "")
            # Extract expiry: SPY260220P00658000 -> 260220
            if len(symbol) > 15:
                expiry = symbol[3:9]  # YYMMDD
                if expiry not in by_expiry:
                    by_expiry[expiry] = []
                by_expiry[expiry].append(pos)

        # Check if any expiry has 4+ option legs (potential iron condor)
        for expiry, legs in by_expiry.items():
            if len(legs) >= 4:
                short_count = sum(1 for p in legs if float(p.get("qty", 0)) < 0)
                long_count = sum(1 for p in legs if float(p.get("qty", 0)) > 0)

                if short_count >= 2 and long_count >= 2:
                    return (
                        True,
                        f"Already have iron condor structure (exp {expiry}): "
                        f"{short_count} short, {long_count} long legs. "
                        f"Per CLAUDE.md: Max 1 iron condor at a time.",
                    )

        return False, ""

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
        # CHECK 0: DAILY LOSS LIMIT - Block trading when daily loss exceeds 5%
        # Phil Town Rule #1: Don't lose money - enforced via daily limit, not total P/L
        # FIXED Jan 14, 2026 (LL-205): Previous logic blocked ALL trades when total P/L
        # was negative, making recovery impossible. Now uses daily loss limit only.
        # This allows recovery trading while still protecting against runaway losses.
        # ============================================================
        total_pl = self._get_total_pl()
        is_risk_increasing = (
            request.side.lower() == "buy"
            or (request.is_option and request.side.lower() == "sell")  # Short puts/calls
        )

        # ONLY block if DAILY loss exceeds limit - not total P/L
        # This allows trading to recover from previous losses
        self._update_daily_pnl()
        account_equity = self._get_account_equity()
        daily_loss_limit = account_equity * self.MAX_DAILY_LOSS_PCT  # 5% default

        if is_risk_increasing and self.daily_pnl < -daily_loss_limit:
            rejection_reasons.append(RejectionReason.PORTFOLIO_NEGATIVE_PL)
            logger.warning(
                f"🛑 DAILY LOSS LIMIT: Today's P/L is ${self.daily_pnl:.2f}, "
                f"exceeds {self.MAX_DAILY_LOSS_PCT * 100}% limit (${-daily_loss_limit:.2f}). "
                f"NO new trades until tomorrow. Phil Town Rule #1!"
            )
            risk_score += 1.0  # Maximum risk score - automatic rejection
            metadata["daily_loss_breach"] = {
                "daily_pnl": self.daily_pnl,
                "daily_limit": -daily_loss_limit,
                "total_pl": total_pl,
                "rule": "Phil Town Rule #1: Don't lose more than 5% per day",
                "action_required": "Wait until tomorrow to trade again",
            }
        elif total_pl < 0:
            # Log warning but DON'T block - allow recovery trading
            logger.info(
                f"📊 NOTE: Total P/L is ${total_pl:.2f} (negative), but daily loss "
                f"${self.daily_pnl:.2f} is within limit. Allowing recovery trade."
            )
            metadata["recovery_trade_allowed"] = {
                "total_pl": total_pl,
                "daily_pnl": self.daily_pnl,
                "reason": "Daily loss within limit - recovery trading permitted",
            }

        # ============================================================
        # CHECK 0.1: PRE-TRADE CHECKLIST (Jan 15, 2026)
        # Enforces MANDATORY Pre-Trade Checklist from CLAUDE.md:
        # 1. Is ticker SPY?
        # 2. Is position size <=5% of account?
        # 3. Is it a SPREAD (not naked)?
        # 4. Earnings blackout check
        # 5. 30-45 DTE expiration
        # 6. Stop-loss defined
        # Phil Town Rule #1: Don't lose money
        # ============================================================
        if request.is_option:
            # Calculate max loss for options trades
            calculated_max_loss = self._calculate_credit_spread_max_loss(request)

            # Get DTE from request or use default (35 = middle of 30-45 range)
            trade_dte = request.dte if request.dte is not None else 35

            # Create checklist with current account equity
            pre_trade_checklist = PreTradeChecklist(account_equity=account_equity)

            # Determine if stop-loss is defined
            stop_loss_defined = request.stop_price is not None or request.strategy_type in [
                "bull_put_spread",
                "bear_call_spread",
                "credit_spread",
                "iron_condor",
            ]  # Spreads have built-in max loss

            # Run checklist validation
            checklist_passed, checklist_failures = pre_trade_checklist.validate(
                symbol=request.symbol,
                max_loss=calculated_max_loss,
                dte=trade_dte,
                is_spread=request.is_spread,
                stop_loss_defined=stop_loss_defined,
            )

            if not checklist_passed:
                rejection_reasons.append(RejectionReason.PRE_TRADE_CHECKLIST_FAILED)
                logger.warning(
                    f"🛑 PRE-TRADE CHECKLIST FAILED: {len(checklist_failures)} violations"
                )
                for failure in checklist_failures:
                    logger.warning(f"   - {failure}")
                risk_score += 1.0  # Maximum risk - hard block
                metadata["pre_trade_checklist"] = {
                    "passed": False,
                    "failures": checklist_failures,
                    "max_loss": calculated_max_loss,
                    "max_allowed": pre_trade_checklist.max_risk,
                    "dte": trade_dte,
                    "is_spread": request.is_spread,
                    "rule": "CLAUDE.md MANDATORY Pre-Trade Checklist",
                }
            else:
                logger.info(
                    f"✅ PRE-TRADE CHECKLIST PASSED: {request.symbol} "
                    f"(max_loss=${calculated_max_loss:.2f}, limit=${pre_trade_checklist.max_risk:.2f})"
                )
                metadata["pre_trade_checklist"] = {
                    "passed": True,
                    "max_loss": calculated_max_loss,
                    "max_allowed": pre_trade_checklist.max_risk,
                    "dte": trade_dte,
                    "is_spread": request.is_spread,
                }

        # ============================================================
        # CHECK 0.3: TICKER WHITELIST (Jan 14, 2026 - LL-192)
        # CLAUDE.md: "CREDIT SPREADS on SPY ONLY"
        # This would have prevented the $40.74 SOFI loss
        # ============================================================
        if self.TICKER_WHITELIST_ENABLED:
            underlying = self._get_underlying_symbol(request.symbol)
            if underlying not in self.ALLOWED_TICKERS:
                rejection_reasons.append(RejectionReason.TICKER_NOT_ALLOWED)
                logger.warning(
                    f"🛑 TICKER BLOCKED: {underlying} not in whitelist {self.ALLOWED_TICKERS}. "
                    f"Per CLAUDE.md Jan 19: SPY ONLY!"
                )
                risk_score += 1.0  # Maximum risk - hard block
                metadata["ticker_whitelist_violation"] = {
                    "ticker": underlying,
                    "allowed": list(self.ALLOWED_TICKERS),
                    "rule": "CLAUDE.md Jan 19: SPY ONLY - best liquidity, tightest spreads",
                }

        # ============================================================
        # CHECK 0.4: FORBIDDEN STRATEGIES (Jan 14, 2026 - LL-192)
        # NO naked puts/calls - must use defined-risk spreads
        # ============================================================
        if request.strategy_type and request.strategy_type in self.FORBIDDEN_STRATEGIES:
            rejection_reasons.append(RejectionReason.FORBIDDEN_STRATEGY)
            logger.warning(
                f"🛑 STRATEGY BLOCKED: '{request.strategy_type}' is FORBIDDEN. "
                f"Use spreads for defined risk!"
            )
            risk_score += 1.0  # Maximum risk - hard block
            metadata["forbidden_strategy"] = {
                "strategy": request.strategy_type,
                "reason": "Naked positions have undefined risk",
                "alternative": "Use bull_put_spread or bear_call_spread instead",
            }

        # ============================================================
        # CHECK 0.5: EARNINGS BLACKOUT (LL-190)
        # Don't open NEW positions during earnings blackout periods
        # ============================================================
        is_blackout, blackout_reason = self._check_earnings_blackout(request.symbol)
        if is_blackout and request.side.lower() in ["buy", "sell"]:
            # Only block NEW positions, not closing existing ones
            rejection_reasons.append(RejectionReason.EARNINGS_BLACKOUT)
            logger.warning(f"🛑 EARNINGS BLACKOUT: {blackout_reason}")
            risk_score += 0.5
            metadata["earnings_blackout"] = {
                "reason": blackout_reason,
                "action": "Wait until blackout ends or choose different ticker",
            }

        # ============================================================
        # CHECK 0.6: POSITION SIZE RISK (LL-190)
        # Max loss cannot exceed 10% of portfolio
        # ============================================================
        is_too_risky, risk_reason = self._check_position_size_risk(request, account_equity)
        if is_too_risky:
            rejection_reasons.append(RejectionReason.POSITION_SIZE_TOO_LARGE)
            logger.warning(f"🛑 POSITION SIZE: {risk_reason}")
            risk_score += 0.5
            metadata["position_size_risk"] = {
                "reason": risk_reason,
                "max_allowed": f"{self.MAX_POSITION_RISK_PCT * 100:.0f}% of ${account_equity:.0f} = ${account_equity * self.MAX_POSITION_RISK_PCT:.0f}",
            }

        # ============================================================
        # CHECK 0.7: CUMULATIVE POSITION RISK (LL-XXX Jan 22, 2026)
        # Individual trades passing but accumulating to dangerous levels
        # ============================================================
        is_cumulative_risky, cumulative_reason = self._check_cumulative_position_risk(
            request, account_equity, positions
        )
        if is_cumulative_risky:
            rejection_reasons.append(RejectionReason.CUMULATIVE_RISK_TOO_HIGH)
            logger.warning(f"🛑 CUMULATIVE RISK: {cumulative_reason}")
            risk_score += 0.5
            metadata["cumulative_risk"] = {
                "reason": cumulative_reason,
                "action": "Close existing positions before adding new ones",
            }

        # ============================================================
        # CHECK 0.8: MAX IRON CONDORS (CLAUDE.md: 1 at a time)
        # ============================================================
        if request.strategy_type == "iron_condor" or request.is_option:
            has_existing_condor, condor_reason = self._check_iron_condor_limit(positions)
            if has_existing_condor and request.side.lower() in ["buy", "sell"]:
                rejection_reasons.append(RejectionReason.MAX_IRON_CONDORS_EXCEEDED)
                logger.warning(f"🛑 IRON CONDOR LIMIT: {condor_reason}")
                risk_score += 0.5
                metadata["iron_condor_limit"] = {
                    "reason": condor_reason,
                    "action": "Close existing iron condor before opening new one",
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
        # FIX Jan 15, 2026: Only block if lesson SPECIFICALLY mentions this ticker
        # Previous bug: lessons about SOFI were blocking SPY trades
        # ============================================================
        # Query RAG for lessons about this ticker and strategy
        query_terms = f"{request.symbol}"
        if request.strategy_type:
            query_terms += f" {request.strategy_type}"
        query_terms += f" {request.side}"

        underlying = self._get_underlying_symbol(request.symbol)
        rag_lessons = self.rag.query(query_terms, top_k=5)

        # Only consider CRITICAL lessons that specifically mention THIS ticker
        critical_rag_lessons = []
        for lesson in rag_lessons:
            if lesson.get("severity") != "CRITICAL":
                continue
            # Check if lesson specifically mentions this ticker
            lesson_content = lesson.get("content", "") + lesson.get("snippet", "")
            lesson_id = lesson.get("id", "").upper()
            # Only block if ticker appears in lesson content or ID
            if underlying.upper() in lesson_content.upper() or underlying.upper() in lesson_id:
                critical_rag_lessons.append(lesson)
            else:
                # Log that we skipped this lesson (not ticker-specific)
                logger.debug(
                    f"Skipping non-ticker-specific lesson: {lesson.get('id')} "
                    f"(searching for {underlying})"
                )

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
            except Exception as e:
                logger.warning(f"Failed to get account equity from executor: {e}, using default")
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
            except Exception as e:
                logger.warning(f"Failed to get positions from executor: {e}, returning empty list")
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

    def check_positions_for_earnings(self) -> list[dict[str, Any]]:
        """
        Monitor existing positions for upcoming earnings blackouts.

        AUTOMATION: This method allows the system to proactively warn about
        positions that will cross earnings dates, enabling automated
        position management before volatility events.

        Returns:
            List of position alerts with action recommendations
        """
        alerts = []
        today = datetime.now().date()
        positions = self._get_positions()

        for position in positions:
            symbol = position.get("symbol", "")
            qty = float(position.get("qty", 0))
            unrealized_pl = float(position.get("unrealized_pl", 0))

            # Extract underlying symbol (handles options)
            underlying = self._get_underlying_symbol(symbol)

            if underlying.upper() in self.EARNINGS_BLACKOUTS:
                blackout = self.EARNINGS_BLACKOUTS[underlying.upper()]
                blackout_start = datetime.strptime(blackout["start"], "%Y-%m-%d").date()
                blackout_end = datetime.strptime(blackout["end"], "%Y-%m-%d").date()
                earnings_date = datetime.strptime(blackout["earnings"], "%Y-%m-%d").date()

                days_to_blackout = (blackout_start - today).days
                days_to_earnings = (earnings_date - today).days

                # Check if position is at risk
                if days_to_blackout <= 14:  # Alert 2 weeks before blackout
                    alert = {
                        "symbol": symbol,
                        "underlying": underlying,
                        "qty": qty,
                        "unrealized_pl": unrealized_pl,
                        "earnings_date": str(earnings_date),
                        "blackout_start": str(blackout_start),
                        "blackout_end": str(blackout_end),
                        "days_to_blackout": days_to_blackout,
                        "days_to_earnings": days_to_earnings,
                        "status": "IN_BLACKOUT" if days_to_blackout <= 0 else "APPROACHING",
                        "action": self._get_earnings_action(
                            days_to_blackout, unrealized_pl, symbol
                        ),
                    }
                    alerts.append(alert)
                    logger.warning(
                        f"⚠️ EARNINGS ALERT: {symbol} - {alert['status']} "
                        f"(earnings: {earnings_date}, {days_to_earnings} days)"
                    )

        return alerts

    def _get_earnings_action(self, days_to_blackout: int, unrealized_pl: float, symbol: str) -> str:
        """Determine recommended action for position approaching earnings."""
        is_option = len(symbol) > 10  # Options have longer symbols

        if days_to_blackout <= 0:
            # Already in blackout
            if unrealized_pl > 0:
                return "CLOSE_AT_PROFIT: Lock in gains before earnings volatility"
            else:
                return "MONITOR_CLOSELY: Consider closing to limit loss before earnings"
        elif days_to_blackout <= 7:
            # Within 1 week of blackout
            if unrealized_pl > 0:
                return "CONSIDER_CLOSING: Profit at risk from earnings IV crush"
            else:
                return "EVALUATE_EXIT: Weigh loss vs earnings risk"
        else:
            # 1-2 weeks out
            if is_option:
                return "PLAN_EXIT: Options decay accelerates near earnings"
            else:
                return "MONITOR: Track position as blackout approaches"


# Singleton instance
_gateway_instance = None


def get_trade_gateway(executor=None, paper: bool = True) -> TradeGateway:
    """Get or create TradeGateway instance."""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = TradeGateway(executor=executor, paper=paper)
    return _gateway_instance
