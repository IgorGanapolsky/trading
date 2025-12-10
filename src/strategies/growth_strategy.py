"""
Growth Trading Strategy - Tier 2 (20% Allocation)

This module implements a medium-risk stock picking strategy using multi-LLM consensus
for selecting high-growth stocks from the S&P 500 universe.

Strategy Overview:
- Weekly screening of S&P 500 stocks with AI
- Technical filters (momentum, RSI, volume)
- Multi-LLM consensus scoring (0-100)
- Top 2 stocks selection
- 3% stop-loss, 10% take-profit targets
- 2-4 week holding period with weekly review

Target: 15-25% annual returns
Risk Level: MEDIUM
"""

import contextlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import yfinance as yf

from src.rag.vector_db.chroma_client import get_rag_db
from src.safety.graham_buffett_safety import get_global_safety_analyzer
from src.utils.dcf_valuation import DCFValuationCalculator, get_global_dcf_calculator
from src.utils.external_signal_loader import get_signal_for_ticker, load_latest_signals
from src.utils.sentiment_loader import (
    get_sentiment_history,
    get_ticker_sentiment,
    load_latest_sentiment,
)
from src.utils.technical_indicators import calculate_adx, calculate_bollinger_bands

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open trading position."""

    symbol: str
    entry_price: float
    quantity: int
    entry_date: datetime
    stop_loss: float
    take_profit: float
    consensus_score: float


@dataclass
class Order:
    """Represents a trading order."""

    symbol: str
    action: str  # 'buy' or 'sell'
    quantity: int
    order_type: str  # 'market', 'limit', 'stop'
    limit_price: float | None = None
    stop_price: float | None = None
    reason: str = ""


@dataclass
class CandidateStock:
    """Represents a candidate stock for trading."""

    symbol: str
    technical_score: float
    consensus_score: float
    current_price: float
    momentum: float
    rsi: float
    macd_value: float
    macd_signal: float
    macd_histogram: float
    volume_ratio: float
    intrinsic_value: float | None = None
    dcf_discount: float | None = None
    sentiment_modifier: float = 0.0
    external_signal_score: float = 0.0
    external_signal_confidence: float = 0.0


class MultiLLMAnalyzer:
    """
    Mock Multi-LLM Analyzer for stock screening and ranking.

    In production, this would integrate with multiple LLM providers
    (OpenAI, Anthropic, etc.) to get consensus scores on stock potential.

    ARCHITECTURE NOTE (Dec 2025 - per Carlos Perez's LLM finance critique):
    ========================================================================
    LLMs should ONLY be used for:
      - Sentiment analysis (qualitative judgment)
      - News/trend synthesis (complex reasoning)
      - Market outlook (high-level interpretation)

    LLMs should NEVER be used for:
      - Filtering stocks by rules (RSI < 70, P/E < 15, etc.)
      - Applying technical conditions to lists
      - Backtesting or sequential rule application

    Why: LLMs suffer from "process corruption" on long sequences - they may
    silently drop rules halfway through a list without error messages.
    Use deterministic Python/pandas for all rule-based operations.

    See: @IntuitMachine's analysis on LLM working memory limitations.
    """

    def __init__(self):
        """Initialize the multi-LLM analyzer."""
        logger.info("Initializing MultiLLMAnalyzer")

    def screen_stocks(self, symbols: list[str]) -> list[str]:
        """
        Screen stocks using AI models.

        Args:
            symbols: List of stock symbols to screen

        Returns:
            List of promising stock symbols
        """
        logger.info(f"Screening {len(symbols)} stocks with AI models")
        # Mock implementation - in production, would use actual LLM APIs
        # For now, return a subset of symbols
        return symbols[:50] if len(symbols) > 50 else symbols

    def get_consensus_score(self, symbol: str, technical_data: dict) -> float:
        """
        Get multi-LLM consensus score for a stock.

        Args:
            symbol: Stock symbol
            technical_data: Dictionary of technical indicators

        Returns:
            Consensus score between 0-100
        """
        logger.debug(f"Getting consensus score for {symbol}")
        # Mock implementation - in production, would query multiple LLMs
        # and aggregate their scores

        # Simple scoring based on technical data for now
        score = 50.0  # Base score

        if technical_data.get("momentum", 0) > 0:
            score += 12
        if 30 < technical_data.get("rsi", 50) < 70:
            score += 12
        if technical_data.get("macd_histogram", 0) > 0:
            score += 13  # Bullish MACD
        if technical_data.get("volume_ratio", 1) > 1.2:
            score += 13

        return min(100.0, max(0.0, score))


class AlpacaTrader:
    """
    Mock Alpaca trading interface.

    In production, this would integrate with the actual Alpaca API
    for order execution and portfolio management.
    """

    def __init__(self):
        """Initialize the Alpaca trader."""
        logger.info("Initializing AlpacaTrader")
        self.positions: dict[str, Position] = {}

    def submit_order(self, order: Order) -> bool:
        """
        Submit a trading order.

        Args:
            order: Order to submit

        Returns:
            True if order was submitted successfully
        """
        logger.info(f"Submitting {order.action} order for {order.symbol}: {order.quantity} shares")
        # Mock implementation
        return True

    def get_position(self, symbol: str) -> Position | None:
        """
        Get current position for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Position object or None if no position exists
        """
        return self.positions.get(symbol)

    def get_all_positions(self) -> list[Position]:
        """
        Get all current positions.

        Returns:
            List of Position objects
        """
        return list(self.positions.values())

    def get_account_cash(self) -> float:
        """
        Get available cash in trading account.

        Returns:
            Available cash amount
        """
        # Mock implementation
        return 10000.0


class RiskManager:
    """
    Risk management utility for validating trades.

    Ensures trades comply with risk limits and portfolio constraints.
    """

    def __init__(self, max_position_size: float = 0.15, max_daily_loss: float = 0.05):
        """
        Initialize the risk manager.

        Args:
            max_position_size: Maximum position size as fraction of portfolio (default 15%)
            max_daily_loss: Maximum daily loss as fraction of portfolio (default 5%)
        """
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        logger.info(
            f"Initializing RiskManager (max_position={max_position_size}, max_loss={max_daily_loss})"
        )

    def validate_order(
        self, order: Order, portfolio_value: float, current_positions: int
    ) -> tuple[bool, str]:
        """
        Validate if an order meets risk requirements.

        Args:
            order: Order to validate
            portfolio_value: Current portfolio value
            current_positions: Number of current positions

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check position count
        if order.action == "buy" and current_positions >= 2:
            return False, "Maximum position count (2) reached"

        # Check position size
        if order.action == "buy":
            order_value = order.quantity * (order.limit_price or 0)
            position_fraction = order_value / portfolio_value if portfolio_value > 0 else 1.0

            if position_fraction > self.max_position_size:
                return (
                    False,
                    f"Position size ({position_fraction:.1%}) exceeds maximum ({self.max_position_size:.1%})",
                )

        return True, "Order validated"

    def check_stop_loss(self, position: Position, current_price: float) -> bool:
        """
        Check if stop-loss should be triggered.

        Args:
            position: Current position
            current_price: Current market price

        Returns:
            True if stop-loss should be triggered
        """
        return current_price <= position.stop_loss

    def check_take_profit(self, position: Position, current_price: float) -> bool:
        """
        Check if take-profit should be triggered.

        Args:
            position: Current position
            current_price: Current market price

        Returns:
            True if take-profit should be triggered
        """
        return current_price >= position.take_profit


class GrowthStrategy:
    """
    Growth Trading Strategy - Tier 2 (20% Allocation)

    Medium-risk stock picking strategy using multi-LLM consensus for
    selecting high-growth stocks from the S&P 500 universe.

    Strategy Parameters:
    - Weekly allocation: $10 (5 days * $2/day)
    - Position size: Top 2 stocks
    - Stop-loss: 3%
    - Take-profit: 10%
    - Holding period: 2-4 weeks
    - Review frequency: Weekly

    Target Annual Return: 15-25%
    Risk Level: MEDIUM
    """

    # S&P 500 tickers (sample - in production would load from file or API)
    SP500_TICKERS = [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "NVDA",
        "META",
        "TSLA",
        "BRK.B",
        "UNH",
        "XOM",
        "JNJ",
        "JPM",
        "V",
        "PG",
        "MA",
        "HD",
        "CVX",
        "ABBV",
        "MRK",
        "LLY",
        "UBER",
        "AVGO",
        "PEP",
        "COST",
        "KO",
        "WMT",
        "MCD",
        "CSCO",
        "TMO",
        "ABT",
        "ACN",
        "ADBE",
        "CRM",
        "NFLX",
        "AMD",
        "TXN",
        "DHR",
        "INTC",
        "VZ",
        "CMCSA",
        "PM",
        "NEE",
        "UPS",
        "HON",
        "ORCL",
        "NKE",
        "UNP",
        "IBM",
        "BA",
        "GE",
        "CAT",
        "PINS",
    ]
    PRIORITY_TICKERS = ["UBER", "LLY", "PINS"]

    def __init__(
        self,
        weekly_allocation: float = 1500.0,
        use_sentiment: bool = True,
        use_intelligent_investor: bool = True,
    ):
        """
        Initialize the Growth Strategy.

        Args:
            weekly_allocation: Weekly trading allocation in dollars (default $10 = 5 days * $2)
            use_sentiment: Whether to use sentiment scoring (default: True)
            use_intelligent_investor: Whether to use Intelligent Investor principles (default: True)
        """
        self.weekly_allocation = weekly_allocation
        # Dec 10, 2025: Widened stop-loss from 3% to 8% for better risk/reward
        # 3% was too tight - getting stopped out before trends develop
        self.stop_loss_pct = 0.08  # 8% stop-loss (widened from 3%)
        self.take_profit_pct = 0.12  # 12% take-profit (increased from 10%)
        self.max_positions = 2
        self.min_holding_weeks = 2
        self.max_holding_weeks = 8  # Extended from 4 to 8 weeks for trend capture
        self.use_sentiment = use_sentiment
        self.use_intelligent_investor = use_intelligent_investor

        # Initialize components
        self.llm_analyzer = MultiLLMAnalyzer()
        self.trader = AlpacaTrader()
        self.risk_manager = RiskManager(max_position_size=0.15, max_daily_loss=0.05)
        self.dcf_calculator: DCFValuationCalculator = get_global_dcf_calculator()
        self.external_signals_cache: dict[str, dict] = {}

        # Initialize Intelligent Investor safety analyzer
        if self.use_intelligent_investor:
            try:
                self.safety_analyzer = get_global_safety_analyzer()
                logger.info("Intelligent Investor safety analyzer initialized for GrowthStrategy")
            except Exception as e:
                logger.warning(f"Failed to initialize safety analyzer: {e}")
                self.safety_analyzer = None
        else:
            self.safety_analyzer = None

        # Initialize RAG Database
        try:
            self.rag_db = get_rag_db()
            logger.info("RAG Database initialized for GrowthStrategy")
        except Exception as e:
            logger.warning(f"Failed to initialize RAG Database: {e}")
            self.rag_db = None

        # RELAXED MARGIN (Dec 4, 2025): Reduced from 0.15 to 0.05 for realistic bull market valuations
        # Previous: 15% undervaluation required → rejected 60-70% of candidates
        # New: 5% margin → accepts fairly valued stocks (appropriate for growth investing)
        try:
            mos_env = float(os.getenv("DCF_MARGIN_OF_SAFETY", "0.05"))
        except ValueError:
            mos_env = 0.05
        self.required_margin_of_safety = max(0.0, min(0.5, mos_env))

        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0

        # Sentiment data cache (loaded once per execution)
        self.sentiment_data = None

        self.langchain_guard_enabled = (
            os.getenv("LANGCHAIN_APPROVAL_ENABLED", "false").lower() == "true"
        )
        self._langchain_agent = None

        logger.info(
            f"GrowthStrategy initialized with ${weekly_allocation} weekly allocation, "
            f"sentiment={'enabled' if use_sentiment else 'disabled'}, "
            f"intelligent_investor={'enabled' if use_intelligent_investor else 'disabled'}"
        )

    def execute_weekly(self) -> list[Order]:
        """
        Execute the weekly trading routine.

        This is the main entry point called once per week to:
        1. Screen candidates with AI
        2. Apply technical filters
        3. Get multi-LLM rankings
        4. Generate buy orders for top stocks
        5. Manage existing positions

        Returns:
            List of Order objects to execute
        """
        logger.info("=" * 80)
        logger.info("Starting weekly execution")
        logger.info("=" * 80)

        # Load latest external signals (sandbox feed)
        self.external_signals_cache = load_latest_signals()
        if self.external_signals_cache:
            logger.info(
                "Loaded %d external signals (sources: %s)",
                len(self.external_signals_cache),
                ", ".join(
                    sorted(
                        {
                            sig.get("source", "unknown")
                            for sig in self.external_signals_cache.values()
                        }
                    )
                ),
            )
        else:
            logger.info("No external signals found - proceeding with internal models only")

        orders = []

        # First, manage existing positions (exits, stop-losses, take-profits)
        management_orders = self.manage_existing_positions()
        orders.extend(management_orders)

        # Check if we can open new positions
        current_positions = len(self.trader.get_all_positions())
        available_slots = self.max_positions - current_positions

        if available_slots > 0:
            logger.info(f"Available slots for new positions: {available_slots}")

            # Screen candidates with AI
            candidates = self.screen_candidates_with_ai()
            logger.info(f"AI screening returned {len(candidates)} candidates")

            if candidates:
                # Apply technical filters
                filtered = self.apply_technical_filters(candidates)
                logger.info(f"Technical filters passed: {len(filtered)} stocks")

                if filtered:
                    # Get multi-LLM rankings
                    ranked = self.get_multi_llm_ranking(filtered)
                    logger.info(f"Multi-LLM ranking complete: {len(ranked)} stocks")

                    # Generate buy orders for top stocks
                    buy_orders = self._generate_buy_orders(ranked[:available_slots])
                    orders.extend(buy_orders)
        else:
            logger.info("No available slots for new positions")

        logger.info(f"Weekly execution complete: {len(orders)} orders generated")
        return orders

    def screen_candidates_with_ai(self) -> list[str]:
        """
        Screen S&P 500 stocks using AI models.

        Uses multi-LLM analysis to identify promising candidates based on:
        - News sentiment
        - Earnings trends
        - Market positioning
        - Growth potential

        Returns:
            List of stock symbols that passed AI screening
        """
        logger.info("Starting AI screening of S&P 500 stocks")

        # Get initial candidates from S&P 500
        base_universe = self.SP500_TICKERS.copy()
        for ticker in reversed(self.PRIORITY_TICKERS):
            if ticker not in base_universe:
                base_universe.insert(0, ticker)

        candidates = base_universe

        # Use LLM analyzer to screen
        screened = self.llm_analyzer.screen_stocks(candidates)

        logger.info(f"AI screening complete: {len(screened)}/{len(candidates)} stocks passed")
        return screened

    def apply_technical_filters(self, candidates: list[str]) -> list[CandidateStock]:
        """
        Apply technical filters to candidate stocks.

        Filters based on:
        - Momentum: Positive price momentum over 20 days
        - RSI: Between 30 and 70 (not oversold/overbought)
        - Volume: Above average volume (1.2x 20-day average)

        Args:
            candidates: List of stock symbols to filter

        Returns:
            List of CandidateStock objects that passed filters
        """
        logger.info(f"Applying technical filters to {len(candidates)} candidates")

        filtered_stocks = []

        for symbol in candidates:
            try:
                # Calculate technical score
                score = self.calculate_technical_score(symbol)

                # Get current price and technical indicators
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="3mo")

                if len(hist) < 20:
                    logger.debug(f"{symbol}: Insufficient data")
                    continue

                current_price = hist["Close"].iloc[-1]

                # Calculate indicators
                momentum = self._calculate_momentum(hist)
                rsi = self._calculate_rsi(hist)
                macd_value, macd_signal, macd_histogram = self._calculate_macd(hist)
                volume_ratio = self._calculate_volume_ratio(hist)

                # ADX REGIME FILTER (Dec 5, 2025): Calculate trend strength
                adx_value, plus_di, minus_di = calculate_adx(hist)

                # BOLLINGER BANDS (Dec 5, 2025): Calculate for mean-reversion signals
                bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(hist["Close"])
                # BB position: 0 = at lower band (oversold), 1 = at upper band (overbought)
                bb_position = (
                    (current_price - bb_lower) / (bb_upper - bb_lower)
                    if (bb_upper - bb_lower) > 0
                    else 0.5
                )

                # HARD FILTER: Skip ranging markets (ADX < 20) to avoid whipsaws
                if adx_value < 20.0:
                    logger.debug(
                        f"{symbol}: FILTERED OUT - ADX regime filter (ADX={adx_value:.1f} < 20). "
                        "Market is ranging/trendless."
                    )
                    continue

                # Apply filters - ENHANCED (Dec 5, 2025): "3 of 6" logic with ADX + Bollinger Bands
                # Added: ADX trending check and Bollinger Bands position for confirmation
                conditions = [
                    momentum > -0.02,  # Allow slight negative momentum (consolidation)
                    30 < rsi < 75,  # Wider RSI range (allow moderate overbought)
                    volume_ratio > 0.8,  # Lower volume requirement (accept quiet periods)
                    macd_histogram > -0.05,  # Allow near-crossover (not just bullish)
                    adx_value >= 25.0,  # Moderate to strong trend (ADX 25+)
                    bb_position < 0.7,  # Not overbought on Bollinger Bands (below upper band)
                ]
                conditions_met = sum(conditions)

                if conditions_met >= 3:  # Need at least 3 of 6 conditions
                    candidate = CandidateStock(
                        symbol=symbol,
                        technical_score=score,
                        consensus_score=0.0,  # Will be filled later
                        current_price=current_price,
                        momentum=momentum,
                        rsi=rsi,
                        macd_value=macd_value,
                        macd_signal=macd_signal,
                        macd_histogram=macd_histogram,
                        volume_ratio=volume_ratio,
                    )
                    filtered_stocks.append(candidate)
                    logger.debug(
                        f"{symbol}: PASSED {conditions_met}/6 conditions "
                        f"(momentum={momentum:.2f}, RSI={rsi:.1f}, "
                        f"MACD={macd_histogram:.4f}, vol_ratio={volume_ratio:.2f}, "
                        f"ADX={adx_value:.1f}, BB_pos={bb_position:.2f})"
                    )
                else:
                    logger.debug(
                        f"{symbol}: FILTERED OUT {conditions_met}/6 conditions "
                        f"(momentum={momentum:.2f}, RSI={rsi:.1f}, "
                        f"MACD={macd_histogram:.4f}, vol_ratio={volume_ratio:.2f}, "
                        f"ADX={adx_value:.1f}, BB_pos={bb_position:.2f})"
                    )

            except Exception as e:
                logger.warning(f"Error processing {symbol}: {e}")
                continue

        logger.info(f"Technical filtering complete: {len(filtered_stocks)} stocks passed")
        return filtered_stocks

    def get_multi_llm_ranking(self, candidates: list[CandidateStock]) -> list[CandidateStock]:
        """
        Get multi-LLM consensus scores and rank candidates with sentiment overlay.

        Combines:
        1. Technical score (from MACD, RSI, volume)
        2. LLM consensus score (multi-model agreement)
        3. Sentiment modifier (Reddit + News sentiment)
        4. DCF margin-of-safety filter + score
        5. External signal conviction (Alpha Vantage news + YouTube analysis)

        Final score weights:
            - 30% technical
            - 30% consensus
            - 15% sentiment (confidence-weighted)
            - 15% DCF discount (capped at 100)
            - 10% external signal score (mapped to 0-100)

        Args:
            candidates: List of candidate stocks to rank

        Returns:
            List of CandidateStock objects sorted by ranking (best first)
        """
        logger.info(f"Getting multi-LLM consensus scores for {len(candidates)} candidates")

        # Load sentiment data once (cached for all candidates)
        if self.use_sentiment and self.sentiment_data is None:
            try:
                self.sentiment_data = load_latest_sentiment()
                logger.info("Loaded sentiment data for ranking")

                if getattr(self, "sentiment_rag_enabled", True):
                    history = get_sentiment_history("SPY", limit=5)
                    formatted = [
                        f"{h['metadata'].get('snapshot_date')} "
                        f"(score={h['metadata'].get('sentiment_score', 0.0):.1f}, "
                        f"confidence={h['metadata'].get('confidence', 'n/a')})"
                        for h in history
                    ]
                    if formatted:
                        logger.info(
                            "Recent SPY sentiment snapshots (RAG): %s",
                            "; ".join(formatted),
                        )
            except Exception as e:
                logger.warning(f"Failed to load sentiment data: {e}")
                self.sentiment_data = {}

        # Get consensus scores from LLM analyzer + apply sentiment + DCF filter
        filtered_candidates: list[CandidateStock] = []
        for i, candidate in enumerate(candidates):
            technical_data = {
                "momentum": candidate.momentum,
                "rsi": candidate.rsi,
                "macd_value": candidate.macd_value,
                "macd_signal": candidate.macd_signal,
                "macd_histogram": candidate.macd_histogram,
                "volume_ratio": candidate.volume_ratio,
                "technical_score": candidate.technical_score,
            }
            # Expand candidate list with graph‑based related tickers (GraphRAG)
            related = self.kg.get_related_tickers(candidate.symbol, top_k=3)
            for rel_ticker, _weight in related:
                if rel_ticker not in [c.symbol for c in candidates]:
                    # Create a lightweight placeholder CandidateStock for the related ticker
                    placeholder = CandidateStock(
                        symbol=rel_ticker,
                        technical_score=0.0,
                        consensus_score=0.0,
                        current_price=0.0,
                        momentum=0.0,
                        rsi=0.0,
                        macd_value=0.0,
                        macd_signal=0.0,
                        macd_histogram=0.0,
                        volume_ratio=0.0,
                    )
                    candidates.append(placeholder)
                    logger.debug(
                        f"GraphRAG: added related ticker {rel_ticker} for {candidate.symbol}"
                    )

            # Get LLM consensus score
            consensus_score = self.llm_analyzer.get_consensus_score(
                candidate.symbol, technical_data
            )
            candidate.consensus_score = consensus_score

            # Apply sentiment modifier if enabled
            sentiment_modifier = 0
            if self.use_sentiment:
                # 1. Try RAG-based sentiment first (more accurate/recent)
                rag_sentiment_score = 0
                rag_article_count = 0

                if self.rag_db:
                    try:
                        # Fetch recent news from RAG
                        rag_news = self.rag_db.get_ticker_news(candidate.symbol, n_results=5)
                        if rag_news:
                            # Simple average of sentiment scores stored in metadata
                            scores = [n["metadata"].get("sentiment", 0.5) for n in rag_news]
                            rag_sentiment_score = (
                                sum(scores) / len(scores) * 100
                            )  # Convert 0-1 to 0-100
                            rag_article_count = len(rag_news)
                            logger.debug(
                                f"{candidate.symbol}: Found {rag_article_count} RAG articles, avg sentiment={rag_sentiment_score:.1f}"
                            )
                    except Exception as e:
                        logger.warning(f"RAG lookup failed for {candidate.symbol}: {e}")

                # 2. Fallback/Combine with legacy sentiment loader
                legacy_score = 50.0
                legacy_confidence = "low"

                if self.sentiment_data:
                    with contextlib.suppress(Exception):
                        legacy_score, legacy_confidence, _ = get_ticker_sentiment(
                            candidate.symbol,
                            self.sentiment_data,
                            default_score=50.0,
                        )

                # Blend scores: If RAG has data, weight it 70%, legacy 30%
                # If RAG has no data, use legacy 100%
                final_sentiment_score = legacy_score
                confidence_weight = {"high": 1.0, "medium": 0.6, "low": 0.3}.get(
                    legacy_confidence, 0.3
                )

                if rag_article_count > 0:
                    final_sentiment_score = (0.7 * rag_sentiment_score) + (0.3 * legacy_score)
                    confidence_weight = max(
                        confidence_weight, 0.8
                    )  # Boost confidence if we have fresh RAG news

                # Calculate modifier
                # Sentiment score 70+ = +15 bonus, 30- = -15 penalty
                sentiment_modifier = ((final_sentiment_score - 50) / 50) * 15 * confidence_weight

                logger.debug(
                    f"{candidate.symbol}: Combined Sentiment={final_sentiment_score:.1f} "
                    f"(RAG={rag_article_count}, Legacy={legacy_score:.1f}) → modifier={sentiment_modifier:+.1f}"
                )

            # Store sentiment modifier for logging
            candidate.sentiment_modifier = sentiment_modifier

            # Fetch DCF valuation and enforce margin of safety
            dcf_result = self.dcf_calculator.get_intrinsic_value(candidate.symbol)
            if not dcf_result:
                logger.info(
                    "Skipping %s - DCF valuation unavailable (requires Alpha Vantage fundamentals)",
                    candidate.symbol,
                )
                continue

            intrinsic_value = dcf_result.intrinsic_value
            if intrinsic_value <= 0:
                logger.info(
                    "Skipping %s - intrinsic value invalid (%.2f)",
                    candidate.symbol,
                    intrinsic_value,
                )
                continue

            discount = (intrinsic_value - candidate.current_price) / intrinsic_value
            candidate.intrinsic_value = intrinsic_value
            candidate.dcf_discount = discount

            if discount < self.required_margin_of_safety:
                logger.info(
                    "Skipping %s - margin of safety %.1f%% below threshold %.1f%%",
                    candidate.symbol,
                    discount * 100,
                    self.required_margin_of_safety * 100,
                )
                continue

            external_signal = get_signal_for_ticker(
                candidate.symbol, signals=self.external_signals_cache
            )
            if external_signal:
                candidate.external_signal_score = external_signal.get("score", 0.0)
                candidate.external_signal_confidence = external_signal.get("confidence", 0.0)

                if candidate.external_signal_score < -20:
                    logger.info(
                        "Skipping %s - external signals bearish (score=%.1f)",
                        candidate.symbol,
                        candidate.external_signal_score,
                    )
                    continue
            else:
                candidate.external_signal_score = 0.0
                candidate.external_signal_confidence = 0.0

            logger.debug(
                "%s: consensus=%.1f, sentiment=%.1f, MACD=%.4f, intrinsic=%.2f, discount=%.1f%%, external=%.1f",
                candidate.symbol,
                consensus_score,
                sentiment_modifier,
                candidate.macd_histogram,
                intrinsic_value,
                discount * 100,
                candidate.external_signal_score,
            )

            filtered_candidates.append(candidate)

        if not filtered_candidates:
            logger.warning("All candidates rejected after DCF margin-of-safety filter")
            return []

        # Rank by combined score (30% technical, 30% consensus, 15% sentiment, 15% DCF discount, 10% external)
        # Note: sentiment_modifier is in the same 0-100 scale, so it affects final ranking
        filtered_candidates.sort(
            key=lambda x: (
                0.30 * x.technical_score
                + 0.30 * x.consensus_score
                + 0.15 * (50 + x.sentiment_modifier)
                + 0.15 * min(100.0, max(0.0, (x.dcf_discount or 0.0) * 400))
                + 0.10 * min(100.0, max(0.0, (x.external_signal_score + 100) / 2))
                + 0.05 * len(self.kg.get_related_tickers(x.symbol, top_k=3))  # GraphRAG boost
            ),
            reverse=True,
        )

        logger.info("Multi-LLM ranking complete (with sentiment + DCF)")
        for i, candidate in enumerate(filtered_candidates[:5], 1):
            sentiment_mod = candidate.sentiment_modifier
            dcf_score = min(100.0, max(0.0, (candidate.dcf_discount or 0.0) * 400))
            external_score = min(100.0, max(0.0, (candidate.external_signal_score + 100) / 2))
            combined_score = (
                0.30 * candidate.technical_score
                + 0.30 * candidate.consensus_score
                + 0.15 * (50 + sentiment_mod)
                + 0.15 * dcf_score
                + 0.10 * external_score
            )
            logger.info(
                f"  #{i}: {candidate.symbol} (combined={combined_score:.1f}, technical={candidate.technical_score:.1f}, "
                f"consensus={candidate.consensus_score:.1f}, sentiment_mod={sentiment_mod:+.1f}, "
                f"dcf_discount={(candidate.dcf_discount or 0.0) * 100:.1f}%, external={candidate.external_signal_score:.1f}, "
                f"intrinsic={candidate.intrinsic_value:.2f})"
            )

        return filtered_candidates

    def manage_existing_positions(self) -> list[Order]:
        """
        Manage existing positions and generate exit orders.

        Checks each position for:
        - Stop-loss trigger (3% loss)
        - Take-profit trigger (10% gain)
        - Maximum holding period (4 weeks)
        - Minimum holding period (2 weeks) for regular review

        Returns:
            List of sell orders for positions that should be closed
        """
        logger.info("Managing existing positions")

        orders = []
        positions = self.trader.get_all_positions()

        if not positions:
            logger.info("No existing positions to manage")
            return orders

        logger.info(f"Checking {len(positions)} positions")

        for position in positions:
            try:
                # Get current price
                ticker = yf.Ticker(position.symbol)
                current_price = ticker.history(period="1d")["Close"].iloc[-1]

                # Calculate current P&L
                pnl_pct = (current_price - position.entry_price) / position.entry_price
                holding_days = (datetime.now() - position.entry_date).days
                holding_weeks = holding_days / 7

                logger.info(
                    f"  {position.symbol}: price=${current_price:.2f}, "
                    f"entry=${position.entry_price:.2f}, P&L={pnl_pct:.2%}, "
                    f"holding={holding_weeks:.1f}w"
                )

                # Check stop-loss
                if self.risk_manager.check_stop_loss(position, current_price):
                    logger.info(f"  -> STOP-LOSS TRIGGERED for {position.symbol}")
                    order = Order(
                        symbol=position.symbol,
                        action="sell",
                        quantity=position.quantity,
                        order_type="market",
                        reason=f"Stop-loss triggered at {current_price:.2f} (entry: {position.entry_price:.2f})",
                    )
                    orders.append(order)
                    self._record_trade(position, current_price, "stop_loss")
                    continue

                # Check take-profit
                if self.risk_manager.check_take_profit(position, current_price):
                    logger.info(f"  -> TAKE-PROFIT TRIGGERED for {position.symbol}")
                    order = Order(
                        symbol=position.symbol,
                        action="sell",
                        quantity=position.quantity,
                        order_type="market",
                        reason=f"Take-profit triggered at {current_price:.2f} (entry: {position.entry_price:.2f})",
                    )
                    orders.append(order)
                    self._record_trade(position, current_price, "take_profit")
                    continue

                # Check maximum holding period
                if holding_weeks >= self.max_holding_weeks:
                    logger.info(f"  -> MAX HOLDING PERIOD for {position.symbol}")
                    order = Order(
                        symbol=position.symbol,
                        action="sell",
                        quantity=position.quantity,
                        order_type="market",
                        reason=f"Maximum holding period ({self.max_holding_weeks}w) reached",
                    )
                    orders.append(order)
                    self._record_trade(position, current_price, "max_holding")
                    continue

                # Weekly review after minimum holding period
                if holding_weeks >= self.min_holding_weeks:
                    # Re-evaluate position
                    should_exit = self._should_exit_position(position, current_price)
                    if should_exit:
                        logger.info(f"  -> REVIEW EXIT for {position.symbol}")
                        order = Order(
                            symbol=position.symbol,
                            action="sell",
                            quantity=position.quantity,
                            order_type="market",
                            reason="Weekly review indicates exit",
                        )
                        orders.append(order)
                        self._record_trade(position, current_price, "review_exit")
                    else:
                        logger.info(f"  -> HOLD {position.symbol}")

            except Exception as e:
                logger.error(f"Error managing position {position.symbol}: {e}")
                continue

        logger.info(f"Position management complete: {len(orders)} exit orders generated")
        return orders

    def calculate_technical_score(self, symbol: str) -> float:
        """
        Calculate technical score for a stock.

        Combines multiple technical indicators into a single score (0-100):
        - Price momentum (20-day)
        - RSI (Relative Strength Index)
        - Volume trends
        - Moving average crossovers

        Args:
            symbol: Stock symbol

        Returns:
            Technical score between 0 and 100
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="3mo")

            if len(hist) < 20:
                return 0.0

            score = 0.0

            # Momentum score (0-20 points)
            momentum = self._calculate_momentum(hist)
            if momentum > 0:
                score += min(20, momentum * 10)

            # RSI score (0-20 points)
            rsi = self._calculate_rsi(hist)
            if 30 < rsi < 70:
                # Optimal range
                score += 20
            elif 20 < rsi < 80:
                # Acceptable range
                score += 12

            # MACD score (0-20 points) - NEW!
            macd_value, macd_signal, macd_histogram = self._calculate_macd(hist)
            if macd_histogram > 0:
                # Bullish MACD (above signal line)
                score += 20
            elif macd_histogram > -0.01:
                # Near crossover (potential reversal)
                score += 10
            elif macd_histogram < 0:
                # Bearish MACD (below signal line)
                score += 0

            # Volume score (0-20 points)
            # High volume = institutional participation (strong signal)
            # Low volume = low interest (weak signal, penalize)
            volume_ratio = self._calculate_volume_ratio(hist)
            if volume_ratio > 1.5:  # Volume 50% above average (high conviction)
                score += 20
            elif volume_ratio > 1.2:  # Volume 20% above average
                score += 12
            elif volume_ratio > 1.0:  # Slightly above average
                score += 8
            elif volume_ratio < 0.5:  # Volume 50% below average (low conviction)
                score -= 10  # Penalize low volume

            # Moving average score (0-20 points)
            ma_score = self._calculate_ma_score(hist)
            score += min(20, ma_score)

            return min(100.0, max(0.0, score))

        except Exception as e:
            logger.warning(f"Error calculating technical score for {symbol}: {e}")
            return 0.0

    def get_performance_metrics(self) -> dict:
        """
        Get strategy performance metrics.

        Returns:
            Dictionary containing performance statistics:
            - total_trades: Total number of trades executed
            - winning_trades: Number of profitable trades
            - win_rate: Percentage of winning trades
            - total_pnl: Total profit/loss
            - avg_return: Average return per trade
            - current_positions: Number of current positions
            - allocation_used: Percentage of allocation currently used
        """
        positions = self.trader.get_all_positions()
        cash = self.trader.get_account_cash()

        # Calculate current position values
        position_value = 0.0
        for pos in positions:
            try:
                ticker = yf.Ticker(pos.symbol)
                current_price = ticker.history(period="1d")["Close"].iloc[-1]
                position_value += current_price * pos.quantity
            except Exception:
                position_value += pos.entry_price * pos.quantity

        total_value = cash + position_value
        allocation_used = (position_value / total_value * 100) if total_value > 0 else 0

        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        avg_return = (self.total_pnl / self.total_trades) if self.total_trades > 0 else 0

        metrics = {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": win_rate,
            "total_pnl": self.total_pnl,
            "avg_return": avg_return,
            "current_positions": len(positions),
            "allocation_used": allocation_used,
            "position_value": position_value,
            "cash": cash,
            "total_value": total_value,
        }

        return metrics

    def _calculate_momentum(self, hist: pd.DataFrame) -> float:
        """Calculate price momentum over 20 days."""
        if len(hist) < 20:
            return 0.0

        closes = hist["Close"]
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]  # Take first column if duplicate

        current_price = float(closes.iloc[-1])
        price_20d_ago = float(closes.iloc[-20])

        if price_20d_ago == 0:
            return 0.0

        momentum = (current_price - price_20d_ago) / price_20d_ago
        return float(momentum)

    def _calculate_rsi(self, hist: pd.DataFrame, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(hist) < period + 1:
            return 50.0

        closes = hist["Close"]
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]

        deltas = closes.diff()

        gains = deltas.where(deltas > 0, 0.0)
        losses = -deltas.where(deltas < 0, 0.0)

        avg_gains = gains.rolling(window=period).mean()
        avg_losses = losses.rolling(window=period).mean()

        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))

        return float(rsi.iloc[-1])

    def _calculate_macd(
        self, hist: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        MACD is a trend-following momentum indicator that shows the relationship between
        two exponential moving averages (EMAs) of a security's price.

        Formula:
        - MACD Line = 12-day EMA - 26-day EMA
        - Signal Line = 9-day EMA of MACD Line
        - Histogram = MACD Line - Signal Line

        Trading Signals:
        - Bullish: MACD crosses above signal line (histogram > 0)
        - Bearish: MACD crosses below signal line (histogram < 0)
        - Momentum strength: Larger histogram = stronger momentum

        Args:
            hist: Historical price DataFrame with 'Close' column
            fast: Fast EMA period (default: 12)
            slow: Slow EMA period (default: 26)
            signal: Signal line EMA period (default: 9)

        Returns:
            Tuple of (macd_value, signal_line, histogram)
        """
        if len(hist) < slow + signal:
            return (0.0, 0.0, 0.0)

        closes = hist["Close"]
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]

        # Calculate exponential moving averages
        ema_fast = closes.ewm(span=fast, adjust=False).mean()
        ema_slow = closes.ewm(span=slow, adjust=False).mean()

        # MACD line = Fast EMA - Slow EMA
        macd_line = ema_fast - ema_slow

        # Signal line = 9-day EMA of MACD line
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()

        # MACD histogram = MACD line - Signal line
        histogram = macd_line - signal_line

        # Helper to safely get scalar float
        def get_scalar(val):
            if isinstance(val, pd.Series):
                val = val.iloc[0]
            return float(val) if not pd.isna(val) else 0.0

        # Return most recent values
        return (
            get_scalar(macd_line.iloc[-1]),
            get_scalar(signal_line.iloc[-1]),
            get_scalar(histogram.iloc[-1]),
        )

    def _calculate_volume_ratio(self, hist: pd.DataFrame) -> float:
        """Calculate current volume vs 20-day average."""
        if len(hist) < 20:
            return 1.0

        volumes = hist["Volume"]
        if isinstance(volumes, pd.DataFrame):
            volumes = volumes.iloc[:, 0]

        current_volume = float(volumes.iloc[-1])
        avg_volume = float(volumes.iloc[-20:].mean())

        if avg_volume == 0:
            return 1.0

        return current_volume / avg_volume

    def _calculate_ma_score(self, hist: pd.DataFrame) -> float:
        """Calculate moving average crossover score (0-20 points)."""
        if len(hist) < 50:
            return 0.0

        closes = hist["Close"]
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]

        ma20 = closes.rolling(window=20).mean()
        ma50 = closes.rolling(window=50).mean()

        current_price = float(closes.iloc[-1])
        current_ma20 = float(ma20.iloc[-1])
        current_ma50 = float(ma50.iloc[-1])

        score = 0.0

        # Price above both MAs (12 points)
        if current_price > current_ma20 and current_price > current_ma50:
            score += 12

        # Golden cross - MA20 above MA50 (8 points)
        if current_ma20 > current_ma50:
            score += 8

        return score

    def _generate_buy_orders(self, candidates: list[CandidateStock]) -> list[Order]:
        """Generate buy orders for top candidate stocks."""
        orders = []
        available_cash = self.trader.get_account_cash()
        cash_per_position = self.weekly_allocation / len(candidates) if candidates else 0

        logger.info(f"Generating buy orders for {len(candidates)} candidates")
        logger.info(f"Cash per position: ${cash_per_position:.2f}")

        for candidate in candidates:
            try:
                if candidate.dcf_discount is None or candidate.intrinsic_value is None:
                    logger.warning(
                        "Skipping order for %s - missing DCF metrics (discount=%s, intrinsic=%s)",
                        candidate.symbol,
                        candidate.dcf_discount,
                        candidate.intrinsic_value,
                    )
                    continue

                dcf_discount_pct = candidate.dcf_discount * 100
                if candidate.dcf_discount < self.required_margin_of_safety:
                    logger.info(
                        "Skipping order for %s - margin of safety %.1f%% below threshold %.1f%%",
                        candidate.symbol,
                        dcf_discount_pct,
                        self.required_margin_of_safety * 100,
                    )
                    continue

                # Calculate position size
                quantity = int(cash_per_position / candidate.current_price)

                if quantity < 1:
                    logger.warning(
                        f"Insufficient funds for {candidate.symbol} at ${candidate.current_price:.2f}"
                    )
                    continue

                # Validate order with risk manager
                dcf_score = min(100.0, max(0.0, candidate.dcf_discount * 400))
                combined_score = (
                    0.30 * candidate.technical_score
                    + 0.30 * candidate.consensus_score
                    + 0.15 * (50 + candidate.sentiment_modifier)
                    + 0.15 * dcf_score
                    + 0.10 * min(100.0, max(0.0, (candidate.external_signal_score + 100) / 2))
                )
                order = Order(
                    symbol=candidate.symbol,
                    action="buy",
                    quantity=quantity,
                    order_type="market",
                    limit_price=candidate.current_price,
                    reason=(
                        "Top ranked stock "
                        f"(combined={combined_score:.1f}, "
                        f"DCF discount={dcf_discount_pct:.1f}%, "
                        f"external_score={candidate.external_signal_score:.1f}, "
                        f"intrinsic=${candidate.intrinsic_value:.2f})"
                    ),
                )

                portfolio_value = available_cash
                current_positions = len(self.trader.get_all_positions())

                is_valid, reason = self.risk_manager.validate_order(
                    order, portfolio_value, current_positions
                )

                if is_valid:
                    # Intelligent Investor Safety Check (Graham-Buffett principles)
                    if self.use_intelligent_investor and self.safety_analyzer:
                        try:
                            logger.info(
                                f"  Running Intelligent Investor safety check for {candidate.symbol}..."
                            )
                            should_buy, safety_analysis = self.safety_analyzer.should_buy(
                                symbol=candidate.symbol,
                                market_price=candidate.current_price,
                                force_refresh=False,
                            )

                            if not should_buy:
                                logger.warning(
                                    f"  ❌ {candidate.symbol} REJECTED by Intelligent Investor principles"
                                )
                                logger.warning(
                                    f"     Safety Rating: {safety_analysis.safety_rating.value}"
                                )
                                if safety_analysis.reasons:
                                    for reason in safety_analysis.reasons[
                                        :2
                                    ]:  # Show first 2 reasons
                                        logger.warning(f"     Reason: {reason}")
                                if safety_analysis.defensive_investor_score is not None:
                                    logger.info(
                                        f"     Defensive Investor Score: {safety_analysis.defensive_investor_score:.1f}/100"
                                    )
                                if safety_analysis.mr_market_sentiment:
                                    logger.info(
                                        f"     Mr. Market Sentiment: {safety_analysis.mr_market_sentiment}"
                                    )
                                continue
                            else:
                                logger.info(
                                    f"  ✅ {candidate.symbol} PASSED Intelligent Investor Safety Check"
                                )
                                logger.info(
                                    f"     Safety Rating: {safety_analysis.safety_rating.value}"
                                )
                                if safety_analysis.defensive_investor_score is not None:
                                    logger.info(
                                        f"     Defensive Investor Score: {safety_analysis.defensive_investor_score:.1f}/100"
                                    )
                                if safety_analysis.mr_market_sentiment:
                                    logger.info(
                                        f"     Mr. Market Sentiment: {safety_analysis.mr_market_sentiment}"
                                    )
                        except Exception as e:
                            logger.warning(
                                f"  Intelligent Investor safety check error for {candidate.symbol} (proceeding): {e}"
                            )
                            # Fail-open: continue with trade if safety check unavailable

                    if self.langchain_guard_enabled and not self._langchain_guard(candidate.symbol):
                        logger.warning(
                            "  LangChain approval gate rejected order for %s",
                            candidate.symbol,
                        )
                        continue

                    orders.append(order)
                    logger.info(
                        f"  BUY order created: {candidate.symbol} x{quantity} @ ${candidate.current_price:.2f}"
                    )
                else:
                    logger.warning(f"  Order rejected for {candidate.symbol}: {reason}")

            except Exception as e:
                logger.error(f"Error generating buy order for {candidate.symbol}: {e}")
                continue

        return orders

    def _should_exit_position(self, position: Position, current_price: float) -> bool:
        """
        Determine if a position should be exited during weekly review.

        Considers:
        - Current P&L
        - Technical indicators
        - Consensus score changes
        """
        # Simple exit logic - can be enhanced with more sophisticated analysis
        pnl_pct = (current_price - position.entry_price) / position.entry_price

        # Exit if losing more than 2% (approaching stop-loss)
        if pnl_pct < -0.02:
            return True

        # Exit if consensus score has dropped significantly
        try:
            technical_score = self.calculate_technical_score(position.symbol)
            if technical_score < 40:  # Below threshold
                return True
        except Exception:
            pass

        return False

    def _record_trade(self, position: Position, exit_price: float, exit_reason: str):
        """Record trade results for performance tracking."""
        pnl = (exit_price - position.entry_price) * position.quantity
        pnl_pct = (exit_price - position.entry_price) / position.entry_price

        self.total_trades += 1
        if pnl > 0:
            self.winning_trades += 1

        self.total_pnl += pnl

        logger.info(
            f"Trade recorded: {position.symbol} {exit_reason} - P&L: ${pnl:.2f} ({pnl_pct:.2%})"
        )

    def _langchain_guard(self, symbol: str) -> bool:
        """
        Optional LangChain approval step for GrowthStrategy orders.
        """
        try:
            if self._langchain_agent is None:
                from langchain_agents.agents import build_price_action_agent

                self._langchain_agent = build_price_action_agent()

            prompt = (
                "You are the growth strategy approval co-pilot. Decide whether we "
                "should open a NEW long position today. Respond with only APPROVE "
                "or DECLINE.\n\n"
                f"Ticker: {symbol}\n"
                "Use the available sentiment and MCP tools to gather context. "
                "Decline if sentiment is negative, confidence is low, or data is stale."
            )

            response = self._langchain_agent.invoke({"input": prompt})
            text = response.get("output", "") if isinstance(response, dict) else str(response)

            normalized = text.strip().lower()
            approved = "approve" in normalized and "decline" not in normalized

            if approved:
                logger.info("LangChain approval granted for %s: %s", symbol, text)
            else:
                logger.warning("LangChain approval denied for %s: %s", symbol, text)

            return approved
        except Exception as exc:
            logger.error("LangChain approval gate error for %s: %s", symbol, exc)
            fail_open = os.getenv("LANGCHAIN_APPROVAL_FAIL_OPEN", "true").lower()
            if fail_open == "true":
                logger.warning("LangChain approval unavailable; defaulting to APPROVE (fail-open).")
                return True
            return False


def main():
    """Main entry point for testing the strategy."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize strategy
    strategy = GrowthStrategy(weekly_allocation=10.0)

    # Execute weekly routine
    orders = strategy.execute_weekly()

    # Display results
    print("\n" + "=" * 80)
    print("GROWTH STRATEGY - WEEKLY EXECUTION RESULTS")
    print("=" * 80)
    print(f"\nOrders Generated: {len(orders)}")
    print("\nOrder Details:")
    for i, order in enumerate(orders, 1):
        print(f"\n  Order #{i}:")
        print(f"    Symbol: {order.symbol}")
        print(f"    Action: {order.action.upper()}")
        print(f"    Quantity: {order.quantity}")
        print(f"    Type: {order.order_type}")
        print(f"    Reason: {order.reason}")

    # Display performance metrics
    metrics = strategy.get_performance_metrics()
    print("\n" + "=" * 80)
    print("PERFORMANCE METRICS")
    print("=" * 80)
    print(f"\n  Total Trades: {metrics['total_trades']}")
    print(f"  Winning Trades: {metrics['winning_trades']}")
    print(f"  Win Rate: {metrics['win_rate']:.1f}%")
    print(f"  Total P&L: ${metrics['total_pnl']:.2f}")
    print(f"  Avg Return: {metrics['avg_return']:.2f}%")
    print(f"  Current Positions: {metrics['current_positions']}")
    print(f"  Allocation Used: {metrics['allocation_used']:.1f}%")
    print(f"  Position Value: ${metrics['position_value']:.2f}")
    print(f"  Cash: ${metrics['cash']:.2f}")
    print(f"  Total Value: ${metrics['total_value']:.2f}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
