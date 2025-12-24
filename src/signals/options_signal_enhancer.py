"""
Options Signal Enhancer - Integrate IV/Expected Move with Sentiment Signals

This module provides the KEY integration per user requirement:
"whenever sentiment says overbought it cross-checks McMillan's expected move
calc before slapping on a call"

Workflow:
1. Receive sentiment signal (overbought, oversold, bullish, bearish)
2. Fetch current IV metrics
3. Calculate McMillan's expected move
4. Cross-check signal validity
5. Enhance with book knowledge (strategy rules, risk management)
6. Return validated trading recommendation

Author: AI Trading System
Date: December 2, 2025
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Import dependencies
try:
    from src.rag.collectors.mcmillan_options_collector import McMillanOptionsKnowledgeBase
    from src.rag.options_book_retriever import get_options_book_retriever

    MCMILLAN_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Optional import failed: {e}")
    McMillanOptionsKnowledgeBase = None
    get_options_book_retriever = None
    MCMILLAN_AVAILABLE = False

try:
    from src.utils.iv_analyzer import IVAnalyzer, IVMetrics
except ImportError:
    IVAnalyzer = None
    IVMetrics = None
    logger.warning("IVAnalyzer not available - using fallback calculations")


@dataclass
class EnhancedSignal:
    """
    Enhanced trading signal with IV cross-check.

    Contains the original sentiment signal plus McMillan's expected move
    validation and recommended action.
    """

    # Original signal
    ticker: str
    original_signal: str  # 'overbought', 'oversold', 'bullish', 'bearish', 'neutral'
    sentiment_score: float  # -1.0 to 1.0
    sentiment_confidence: float  # 0.0 to 1.0

    # IV Analysis
    current_iv: float
    iv_rank: float
    iv_percentile: float

    # Expected Move (McMillan's formula)
    expected_move_pct: float
    expected_move_dollars: float
    price_range_low: float
    price_range_high: float

    # Cross-Check Result
    is_validated: bool
    alignment_status: str  # 'ALIGNED', 'CAUTION', 'REJECT'
    alignment_reason: str

    # Recommendation
    recommended_action: str  # 'BUY_CALL', 'BUY_PUT', 'SELL_CALL', 'IRON_CONDOR', 'WAIT', etc.
    recommended_strategy: str
    position_sizing_pct: float  # % of portfolio
    target_delta: float
    target_dte: int

    # Book Reference
    mcmillan_guidance: str
    book_references: list[str]

    # Metadata
    timestamp: str
    current_price: float


class OptionsSignalEnhancer:
    """
    Enhances sentiment signals with IV analysis and McMillan's expected move.

    This is the bridge between sentiment analysis and options execution.
    Every signal goes through McMillan's expected move validation before
    being passed to the trading system.

    Usage:
        enhancer = OptionsSignalEnhancer()

        # Enhance a sentiment signal
        enhanced = enhancer.enhance_signal(
            ticker="SPY",
            sentiment_signal="overbought",
            sentiment_score=-0.65,
            sentiment_confidence=0.80
        )

        if enhanced.is_validated:
            print(f"Execute: {enhanced.recommended_action}")
        else:
            print(f"Wait: {enhanced.alignment_reason}")
    """

    # Sentiment signal mappings
    SIGNAL_DIRECTIONS = {
        "overbought": "bearish",
        "oversold": "bullish",
        "bullish": "bullish",
        "bearish": "bearish",
        "neutral": "neutral",
    }

    # IV-based strategy mappings
    HIGH_IV_STRATEGIES = {
        "bullish": ["covered_call", "cash_secured_put", "bull_put_spread"],
        "bearish": ["bear_call_spread", "naked_put"],  # Careful with naked
        "neutral": ["iron_condor", "strangle_short", "butterfly"],
    }

    LOW_IV_STRATEGIES = {
        "bullish": ["long_call", "call_debit_spread", "long_straddle"],
        "bearish": ["long_put", "put_debit_spread"],
        "neutral": ["calendar_spread", "long_butterfly"],
    }

    # CRITICAL: IV Rank minimum thresholds for premium selling strategies
    # McMillan Rule: NEVER sell premium when IV is cheap (IV Rank < 20)
    CREDIT_SPREAD_MIN_IV_RANK = 20  # Hard floor for credit strategies
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

    def __init__(self, portfolio_value: float = 10000.0):
        """
        Initialize signal enhancer.

        Args:
            portfolio_value: Portfolio value for position sizing
        """
        self.portfolio_value = portfolio_value

        # Initialize McMillan knowledge base if available
        if MCMILLAN_AVAILABLE and McMillanOptionsKnowledgeBase:
            try:
                self.mcmillan_kb = McMillanOptionsKnowledgeBase()
            except Exception as e:
                logger.warning(f"McMillan KB init failed: {e}")
                self.mcmillan_kb = None
        else:
            self.mcmillan_kb = None

        # Initialize IV analyzer if available
        if IVAnalyzer:
            try:
                self.iv_analyzer = IVAnalyzer()
            except Exception as e:
                logger.warning(f"IVAnalyzer init failed: {e}")
                self.iv_analyzer = None
        else:
            self.iv_analyzer = None

        # Initialize book retriever
        if MCMILLAN_AVAILABLE and get_options_book_retriever:
            try:
                self.book_retriever = get_options_book_retriever()
            except Exception as e:
                logger.warning(f"Book retriever init failed: {e}")
                self.book_retriever = None
        else:
            self.book_retriever = None

        logger.info("Options Signal Enhancer initialized")

    def enhance_signal(
        self,
        ticker: str,
        sentiment_signal: str,
        sentiment_score: float,
        sentiment_confidence: float,
        current_price: float | None = None,
        current_iv: float | None = None,
        iv_rank: float | None = None,
        dte: int = 30,
    ) -> EnhancedSignal:
        """
        Enhance a sentiment signal with IV/expected move cross-check.

        This is the MAIN entry point - called whenever the trading system
        receives a sentiment signal.

        Args:
            ticker: Stock symbol
            sentiment_signal: 'overbought', 'oversold', 'bullish', 'bearish', 'neutral'
            sentiment_score: Raw sentiment score (-1.0 to 1.0)
            sentiment_confidence: Confidence in the signal (0.0 to 1.0)
            current_price: Current stock price (optional, will fetch if not provided)
            current_iv: Current IV (optional, will fetch if not provided)
            iv_rank: IV Rank 0-100 (optional, will calculate if not provided)
            dte: Days to expiration for expected move calc

        Returns:
            EnhancedSignal with validation and recommendation
        """
        logger.info(
            f"Enhancing signal for {ticker}: {sentiment_signal} "
            f"(score={sentiment_score:.2f}, conf={sentiment_confidence:.2f})"
        )

        # Step 1: Get IV metrics
        iv_metrics = self._get_iv_metrics(
            ticker=ticker, current_price=current_price, current_iv=current_iv, iv_rank=iv_rank
        )

        # Step 2: Calculate expected move (McMillan's formula)
        if self.mcmillan_kb:
            expected_move = self.mcmillan_kb.calculate_expected_move(
                stock_price=iv_metrics["current_price"],
                implied_volatility=iv_metrics["current_iv"],
                days_to_expiration=dte,
                confidence_level=1.0,  # 1 std dev
            )
        else:
            # Fallback calculation when McMillan KB not available
            import math

            stock_price = iv_metrics["current_price"]
            iv = iv_metrics["current_iv"]
            expected_move_amt = stock_price * iv * math.sqrt(dte / 365.0)
            expected_move = {
                "expected_move": expected_move_amt,
                "move_percentage": (expected_move_amt / stock_price) * 100,
                "upper_bound": stock_price + expected_move_amt,
                "lower_bound": stock_price - expected_move_amt,
            }

        # Step 3: Cross-check sentiment with expected move
        alignment = self._cross_check_alignment(
            sentiment_signal=sentiment_signal,
            sentiment_score=sentiment_score,
            sentiment_confidence=sentiment_confidence,
            expected_move=expected_move,
            iv_metrics=iv_metrics,
        )

        # Step 4: Get strategy recommendation
        strategy_rec = self._get_strategy_recommendation(
            direction=self.SIGNAL_DIRECTIONS.get(sentiment_signal, "neutral"),
            iv_rank=iv_metrics["iv_rank"],
            alignment=alignment,
        )

        # Step 5: Calculate position sizing
        position_sizing = self._calculate_position_size(
            strategy=strategy_rec["strategy"],
            iv_rank=iv_metrics["iv_rank"],
            confidence=sentiment_confidence,
        )

        # Step 6: Get book references
        book_refs = self._get_book_references(
            sentiment_signal=sentiment_signal, strategy=strategy_rec["strategy"]
        )

        # Build enhanced signal
        enhanced = EnhancedSignal(
            ticker=ticker,
            original_signal=sentiment_signal,
            sentiment_score=sentiment_score,
            sentiment_confidence=sentiment_confidence,
            current_iv=iv_metrics["current_iv"],
            iv_rank=iv_metrics["iv_rank"],
            iv_percentile=iv_metrics.get("iv_percentile", iv_metrics["iv_rank"]),
            expected_move_pct=expected_move["move_percentage"],
            expected_move_dollars=expected_move["expected_move"],
            price_range_low=expected_move["lower_bound"],
            price_range_high=expected_move["upper_bound"],
            is_validated=alignment["is_valid"],
            alignment_status=alignment["status"],
            alignment_reason=alignment["reason"],
            recommended_action=strategy_rec["action"],
            recommended_strategy=strategy_rec["strategy"],
            position_sizing_pct=position_sizing["size_pct"],
            target_delta=strategy_rec["delta"],
            target_dte=dte,
            mcmillan_guidance=alignment["mcmillan_guidance"],
            book_references=book_refs,
            timestamp=datetime.now().isoformat(),
            current_price=iv_metrics["current_price"],
        )

        logger.info(
            f"Signal enhanced: {enhanced.alignment_status} - "
            f"{enhanced.recommended_action} ({enhanced.recommended_strategy})"
        )

        return enhanced

    def _get_iv_metrics(
        self,
        ticker: str,
        current_price: float | None,
        current_iv: float | None,
        iv_rank: float | None,
    ) -> dict[str, float]:
        """Get IV metrics, fetching from analyzer if needed."""

        # Try to get live data if analyzer available
        if self.iv_analyzer and current_iv is None:
            try:
                metrics = self.iv_analyzer.analyze(ticker)
                if metrics:
                    return {
                        "current_price": metrics.current_price,
                        "current_iv": metrics.current_iv,
                        "iv_rank": metrics.iv_rank,
                        "iv_percentile": metrics.iv_percentile,
                    }
            except Exception as e:
                logger.warning(f"Failed to fetch IV metrics: {e}")

        # Use provided values or defaults
        return {
            "current_price": current_price or 100.0,
            "current_iv": current_iv or 0.25,  # Default 25% IV
            "iv_rank": iv_rank or 50.0,  # Default middle range
            "iv_percentile": iv_rank or 50.0,
        }

    def _cross_check_alignment(
        self,
        sentiment_signal: str,
        sentiment_score: float,
        sentiment_confidence: float,
        expected_move: dict,
        iv_metrics: dict,
    ) -> dict[str, Any]:
        """
        Cross-check if sentiment signal aligns with expected move.

        This is McMillan's key insight: don't just follow sentiment,
        validate that IV supports the expected magnitude of move.
        """
        move_pct = expected_move["move_percentage"]
        iv_rank = iv_metrics["iv_rank"]

        # Minimum expected move for signal to be valid
        # If sentiment says big move but expected move is tiny, signal is weak
        min_move_threshold = 2.0  # At least 2% expected move for directional trades

        # For neutral/range-bound strategies, we want SMALL expected moves
        if sentiment_signal == "neutral":
            # Perfect for iron condors when expected move is small
            if move_pct < 5.0:  # Less than 5% expected move
                is_valid = True
                status = "ALIGNED"
                reason = (
                    f"Neutral sentiment with small expected move (±{move_pct:.1f}%). "
                    "Ideal for iron condor or butterfly."
                )
            else:
                is_valid = False
                status = "CAUTION"
                reason = (
                    f"Neutral sentiment but expected move is large (±{move_pct:.1f}%). "
                    "Stock may break out of range. Consider straddle instead."
                )

        elif sentiment_signal in ["overbought", "bearish"]:
            # Bearish signals - want enough expected move for profit
            if move_pct >= min_move_threshold:
                if sentiment_confidence >= 0.6:
                    is_valid = True
                    status = "ALIGNED"
                    reason = (
                        f"Bearish signal validated. Expected move ±{move_pct:.1f}% "
                        f"supports potential downside to ${expected_move['lower_bound']:.2f}."
                    )
                else:
                    is_valid = True
                    status = "CAUTION"
                    reason = (
                        f"Bearish signal weak (conf={sentiment_confidence:.0%}). "
                        "Consider defined-risk spread instead of naked options."
                    )
            else:
                is_valid = False
                status = "REJECT"
                reason = (
                    f"Bearish signal but expected move only ±{move_pct:.1f}%. "
                    "IV doesn't support expected magnitude. Wait or sell premium instead."
                )

        elif sentiment_signal in ["oversold", "bullish"]:
            # Bullish signals - want enough expected move for profit
            if move_pct >= min_move_threshold:
                if sentiment_confidence >= 0.6:
                    is_valid = True
                    status = "ALIGNED"
                    reason = (
                        f"Bullish signal validated. Expected move ±{move_pct:.1f}% "
                        f"supports potential upside to ${expected_move['upper_bound']:.2f}."
                    )
                else:
                    is_valid = True
                    status = "CAUTION"
                    reason = (
                        f"Bullish signal weak (conf={sentiment_confidence:.0%}). "
                        "Consider defined-risk spread instead of outright call."
                    )
            else:
                is_valid = False
                status = "REJECT"
                reason = (
                    f"Bullish signal but expected move only ±{move_pct:.1f}%. "
                    "IV doesn't support expected magnitude. Wait or sell put instead."
                )
        else:
            is_valid = False
            status = "UNKNOWN"
            reason = f"Unknown signal type: {sentiment_signal}"

        # Get McMillan's IV guidance
        if self.mcmillan_kb:
            iv_rec = self.mcmillan_kb.get_iv_recommendation(
                iv_rank=iv_rank, iv_percentile=iv_metrics.get("iv_percentile", iv_rank)
            )
        else:
            # Fallback IV recommendation when McMillan KB not available
            if iv_rank > 50:
                iv_rec = {"recommendation": "High IV - favor premium selling strategies"}
            else:
                iv_rec = {"recommendation": "Low IV - favor premium buying strategies"}

        # CRITICAL: Add IV Rank < 20 warning for credit strategies
        iv_rank_warning = ""
        if iv_rank < self.CREDIT_SPREAD_MIN_IV_RANK:
            iv_rank_warning = (
                f" ⚠️ IV RANK TOO LOW ({iv_rank:.0f}% < {self.CREDIT_SPREAD_MIN_IV_RANK}%): "
                "Credit spreads BLOCKED. Premium is cheap - use debit strategies only."
            )
            logger.warning(
                f"IV Rank filter triggered for {sentiment_signal}: "
                f"IV Rank {iv_rank:.0f}% < {self.CREDIT_SPREAD_MIN_IV_RANK}% minimum"
            )

        mcmillan_guidance = (
            f"IV Rank: {iv_rank:.0f}. {iv_rec['recommendation']}. "
            f"Expected move formula: Price × IV × √(DTE/365) = "
            f"${expected_move['expected_move']:.2f} ({move_pct:.1f}%).{iv_rank_warning}"
        )

        return {
            "is_valid": is_valid,
            "status": status,
            "reason": reason,
            "mcmillan_guidance": mcmillan_guidance,
            "iv_recommendation": iv_rec["recommendation"],
        }

    def _get_strategy_recommendation(
        self, direction: str, iv_rank: float, alignment: dict
    ) -> dict[str, Any]:
        """Get recommended strategy based on direction and IV."""

        # CRITICAL IV RANK FILTER: Reject credit spreads when IV < 20
        # McMillan Rule: Don't sell premium when premium is cheap
        credit_blocked = iv_rank < self.CREDIT_SPREAD_MIN_IV_RANK

        # Determine if high or low IV
        is_high_iv = iv_rank >= 50

        # Select strategy pool
        if is_high_iv and not credit_blocked:
            strategies = self.HIGH_IV_STRATEGIES.get(direction, ["iron_condor"])
        else:
            # Force LOW_IV (debit) strategies when IV Rank < 20
            strategies = self.LOW_IV_STRATEGIES.get(direction, ["long_call"])

        # Pick based on alignment status
        if alignment["status"] == "REJECT":
            # Conservative: sell premium or wait
            # BUT NEVER sell premium if IV Rank < 20
            if credit_blocked:
                strategy = "wait"
                action = "WAIT"
            else:
                strategy = "wait" if not is_high_iv else "iron_condor"
                action = "WAIT" if strategy == "wait" else "SELL_PREMIUM"
            delta = 0.16  # Conservative delta for premium selling
        elif alignment["status"] == "CAUTION":
            # Use defined-risk strategy
            # Respect IV Rank filter for credit strategies
            if direction == "bullish":
                if credit_blocked or not is_high_iv:
                    strategy = "call_debit_spread"
                    action = "BUY_CALL_SPREAD"
                else:
                    strategy = "bull_put_spread"
                    action = "SELL_PUT_SPREAD"
            elif direction == "bearish":
                if credit_blocked or not is_high_iv:
                    strategy = "put_debit_spread"
                    action = "BUY_PUT_SPREAD"
                else:
                    strategy = "bear_call_spread"
                    action = "SELL_CALL_SPREAD"
            else:
                if credit_blocked:
                    strategy = "long_butterfly"  # Debit strategy for neutral
                    action = "BUY_BUTTERFLY"
                else:
                    strategy = "iron_condor"
                    action = "IRON_CONDOR"
            delta = 0.30
        else:  # ALIGNED
            # Can be more aggressive
            strategy = strategies[0]
            if direction == "bullish":
                action = "BUY_CALL" if credit_blocked or not is_high_iv else "SELL_PUT"
            elif direction == "bearish":
                action = "BUY_PUT" if credit_blocked or not is_high_iv else "SELL_CALL"
            else:
                if credit_blocked:
                    action = "BUY_BUTTERFLY"  # Debit neutral strategy
                else:
                    action = "IRON_CONDOR"
            delta = 0.45 if not is_high_iv else 0.30

        return {
            "strategy": strategy,
            "action": action,
            "delta": delta,
            "is_high_iv": is_high_iv,
            "iv_rank_blocked_credit": credit_blocked,
            "iv_rank": iv_rank,
        }

    def _calculate_position_size(
        self, strategy: str, iv_rank: float, confidence: float
    ) -> dict[str, float]:
        """Calculate position size based on strategy and confidence."""

        # Base position size: 2% of portfolio
        base_size = 0.02

        # Adjust for confidence
        confidence_multiplier = 0.5 + (confidence * 0.5)  # 0.5x to 1.0x

        # Adjust for IV - smaller positions in high IV (more expensive)
        iv_multiplier = 1.0 - (iv_rank / 200)  # 0.5x at IV Rank 100, 1.0x at 0

        # Strategy-specific adjustments
        strategy_multipliers = {
            "wait": 0.0,
            "iron_condor": 1.2,  # Defined risk, can size up
            "covered_call": 1.0,
            "long_call": 0.8,  # Single leg, more risky
            "long_put": 0.8,
            "call_debit_spread": 1.0,
            "put_debit_spread": 1.0,
        }
        strategy_mult = strategy_multipliers.get(strategy, 1.0)

        final_size = base_size * confidence_multiplier * iv_multiplier * strategy_mult

        # Cap at 5% max
        final_size = min(final_size, 0.05)

        return {
            "size_pct": round(final_size * 100, 2),
            "dollar_amount": round(self.portfolio_value * final_size, 2),
            "base_size": base_size,
            "adjustments": {
                "confidence": confidence_multiplier,
                "iv": iv_multiplier,
                "strategy": strategy_mult,
            },
        }

    def _get_book_references(self, sentiment_signal: str, strategy: str) -> list[str]:
        """Get relevant book references for the trade."""

        if not self.book_retriever:
            return ["McMillan: Options as a Strategic Investment"]

        try:
            search_result = self.book_retriever.search_options_knowledge(
                query=f"{strategy} {sentiment_signal}", top_k=2
            )
            refs = []
            for result in search_result.get("book_results", []):
                chapter = result.get("chapter", "")
                page = result.get("page", "")
                refs.append(f"McMillan Ch.{chapter}, p.{page}")

            return refs if refs else ["McMillan: Options as a Strategic Investment"]

        except Exception as e:
            logger.warning(f"Failed to get book references: {e}")
            return ["McMillan: Options as a Strategic Investment"]

    def batch_enhance(self, signals: list[dict[str, Any]]) -> list[EnhancedSignal]:
        """
        Batch enhance multiple signals.

        Args:
            signals: List of dicts with ticker, signal, score, confidence

        Returns:
            List of EnhancedSignal objects
        """
        enhanced_signals = []

        for signal in signals:
            try:
                enhanced = self.enhance_signal(
                    ticker=signal["ticker"],
                    sentiment_signal=signal["signal"],
                    sentiment_score=signal.get("score", 0.0),
                    sentiment_confidence=signal.get("confidence", 0.5),
                    current_price=signal.get("price"),
                    current_iv=signal.get("iv"),
                    iv_rank=signal.get("iv_rank"),
                )
                enhanced_signals.append(enhanced)
            except Exception as e:
                logger.error(f"Failed to enhance signal for {signal.get('ticker')}: {e}")

        return enhanced_signals


# Convenience function
def get_signal_enhancer(portfolio_value: float = 10000.0) -> OptionsSignalEnhancer:
    """Get OptionsSignalEnhancer instance."""
    return OptionsSignalEnhancer(portfolio_value=portfolio_value)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    enhancer = OptionsSignalEnhancer(portfolio_value=10000.0)

    # Example: Enhance an overbought signal
    print("\n=== Testing Overbought Signal ===")
    signal = enhancer.enhance_signal(
        ticker="SPY",
        sentiment_signal="overbought",
        sentiment_score=-0.65,
        sentiment_confidence=0.80,
        current_price=450.0,
        current_iv=0.18,
        iv_rank=35.0,
        dte=7,
    )

    print(f"Ticker: {signal.ticker}")
    print(f"Original Signal: {signal.original_signal}")
    print(f"Expected Move: ±{signal.expected_move_pct:.1f}%")
    print(f"Price Range: ${signal.price_range_low:.2f} - ${signal.price_range_high:.2f}")
    print(f"Validated: {signal.is_validated} ({signal.alignment_status})")
    print(f"Reason: {signal.alignment_reason}")
    print(f"Recommendation: {signal.recommended_action}")
    print(f"Strategy: {signal.recommended_strategy}")
    print(f"Position Size: {signal.position_sizing_pct}%")
    print(f"McMillan Guidance: {signal.mcmillan_guidance}")

    # Example: Enhance a bullish signal with high IV
    print("\n=== Testing Bullish Signal with High IV ===")
    signal2 = enhancer.enhance_signal(
        ticker="NVDA",
        sentiment_signal="bullish",
        sentiment_score=0.72,
        sentiment_confidence=0.85,
        current_price=140.0,
        current_iv=0.45,
        iv_rank=75.0,
        dte=30,
    )

    print(f"Ticker: {signal2.ticker}")
    print(f"IV Rank: {signal2.iv_rank}")
    print(f"Validated: {signal2.is_validated} ({signal2.alignment_status})")
    print(f"Recommendation: {signal2.recommended_action}")
    print(f"Strategy: {signal2.recommended_strategy}")
