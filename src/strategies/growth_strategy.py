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

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

import yfinance as yf
import pandas as pd
import numpy as np


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
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
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
    volume_ratio: float


class MultiLLMAnalyzer:
    """
    Mock Multi-LLM Analyzer for stock screening and ranking.

    In production, this would integrate with multiple LLM providers
    (OpenAI, Anthropic, etc.) to get consensus scores on stock potential.
    """

    def __init__(self):
        """Initialize the multi-LLM analyzer."""
        logger.info("Initializing MultiLLMAnalyzer")

    def screen_stocks(self, symbols: List[str]) -> List[str]:
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

    def get_consensus_score(self, symbol: str, technical_data: Dict) -> float:
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
            score += 15
        if 30 < technical_data.get("rsi", 50) < 70:
            score += 15
        if technical_data.get("volume_ratio", 1) > 1.2:
            score += 20

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
        self.positions: Dict[str, Position] = {}

    def submit_order(self, order: Order) -> bool:
        """
        Submit a trading order.

        Args:
            order: Order to submit

        Returns:
            True if order was submitted successfully
        """
        logger.info(
            f"Submitting {order.action} order for {order.symbol}: {order.quantity} shares"
        )
        # Mock implementation
        return True

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get current position for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Position object or None if no position exists
        """
        return self.positions.get(symbol)

    def get_all_positions(self) -> List[Position]:
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
    ) -> Tuple[bool, str]:
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
            position_fraction = (
                order_value / portfolio_value if portfolio_value > 0 else 1.0
            )

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
    ]

    def __init__(self, weekly_allocation: float = 10.0):
        """
        Initialize the Growth Strategy.

        Args:
            weekly_allocation: Weekly trading allocation in dollars (default $10 = 5 days * $2)
        """
        self.weekly_allocation = weekly_allocation
        self.stop_loss_pct = 0.03  # 3% stop-loss
        self.take_profit_pct = 0.10  # 10% take-profit
        self.max_positions = 2
        self.min_holding_weeks = 2
        self.max_holding_weeks = 4

        # Initialize components
        self.llm_analyzer = MultiLLMAnalyzer()
        self.trader = AlpacaTrader()
        self.risk_manager = RiskManager(max_position_size=0.15, max_daily_loss=0.05)

        # Performance tracking
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0

        logger.info(
            f"GrowthStrategy initialized with ${weekly_allocation} weekly allocation"
        )

    def execute_weekly(self) -> List[Order]:
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

    def screen_candidates_with_ai(self) -> List[str]:
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
        candidates = self.SP500_TICKERS.copy()

        # Use LLM analyzer to screen
        screened = self.llm_analyzer.screen_stocks(candidates)

        logger.info(
            f"AI screening complete: {len(screened)}/{len(candidates)} stocks passed"
        )
        return screened

    def apply_technical_filters(self, candidates: List[str]) -> List[CandidateStock]:
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
                volume_ratio = self._calculate_volume_ratio(hist)

                # Apply filters
                if momentum > 0 and 30 < rsi < 70 and volume_ratio > 1.2:
                    candidate = CandidateStock(
                        symbol=symbol,
                        technical_score=score,
                        consensus_score=0.0,  # Will be filled later
                        current_price=current_price,
                        momentum=momentum,
                        rsi=rsi,
                        volume_ratio=volume_ratio,
                    )
                    filtered_stocks.append(candidate)
                    logger.debug(
                        f"{symbol}: PASSED (momentum={momentum:.2f}, RSI={rsi:.1f}, vol_ratio={volume_ratio:.2f})"
                    )
                else:
                    logger.debug(
                        f"{symbol}: FILTERED OUT (momentum={momentum:.2f}, RSI={rsi:.1f}, vol_ratio={volume_ratio:.2f})"
                    )

            except Exception as e:
                logger.warning(f"Error processing {symbol}: {e}")
                continue

        logger.info(
            f"Technical filtering complete: {len(filtered_stocks)} stocks passed"
        )
        return filtered_stocks

    def get_multi_llm_ranking(
        self, candidates: List[CandidateStock]
    ) -> List[CandidateStock]:
        """
        Get multi-LLM consensus scores and rank candidates.

        Queries multiple LLM providers to get consensus on each stock's potential,
        then ranks stocks by combined technical + consensus scores.

        Args:
            candidates: List of candidate stocks to rank

        Returns:
            List of CandidateStock objects sorted by ranking (best first)
        """
        logger.info(
            f"Getting multi-LLM consensus scores for {len(candidates)} candidates"
        )

        # Get consensus scores from LLM analyzer
        for candidate in candidates:
            technical_data = {
                "momentum": candidate.momentum,
                "rsi": candidate.rsi,
                "volume_ratio": candidate.volume_ratio,
                "technical_score": candidate.technical_score,
            }

            consensus_score = self.llm_analyzer.get_consensus_score(
                candidate.symbol, technical_data
            )
            candidate.consensus_score = consensus_score

            logger.debug(f"{candidate.symbol}: consensus_score={consensus_score:.1f}")

        # Rank by combined score (50% technical, 50% consensus)
        candidates.sort(
            key=lambda x: (0.5 * x.technical_score + 0.5 * x.consensus_score),
            reverse=True,
        )

        logger.info("Multi-LLM ranking complete")
        for i, candidate in enumerate(candidates[:5], 1):
            combined_score = (
                0.5 * candidate.technical_score + 0.5 * candidate.consensus_score
            )
            logger.info(
                f"  #{i}: {candidate.symbol} (combined={combined_score:.1f}, "
                f"technical={candidate.technical_score:.1f}, "
                f"consensus={candidate.consensus_score:.1f})"
            )

        return candidates

    def manage_existing_positions(self) -> List[Order]:
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

        logger.info(
            f"Position management complete: {len(orders)} exit orders generated"
        )
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

            # Momentum score (0-25 points)
            momentum = self._calculate_momentum(hist)
            if momentum > 0:
                score += min(25, momentum * 10)

            # RSI score (0-25 points)
            rsi = self._calculate_rsi(hist)
            if 30 < rsi < 70:
                # Optimal range
                score += 25
            elif 20 < rsi < 80:
                # Acceptable range
                score += 15

            # Volume score (0-25 points)
            volume_ratio = self._calculate_volume_ratio(hist)
            if volume_ratio > 1.5:
                score += 25
            elif volume_ratio > 1.2:
                score += 15
            elif volume_ratio > 1.0:
                score += 10

            # Moving average score (0-25 points)
            ma_score = self._calculate_ma_score(hist)
            score += ma_score

            return min(100.0, max(0.0, score))

        except Exception as e:
            logger.warning(f"Error calculating technical score for {symbol}: {e}")
            return 0.0

    def get_performance_metrics(self) -> Dict:
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
            except:
                position_value += pos.entry_price * pos.quantity

        total_value = cash + position_value
        allocation_used = (position_value / total_value * 100) if total_value > 0 else 0

        win_rate = (
            (self.winning_trades / self.total_trades * 100)
            if self.total_trades > 0
            else 0
        )
        avg_return = (
            (self.total_pnl / self.total_trades) if self.total_trades > 0 else 0
        )

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

        current_price = hist["Close"].iloc[-1]
        price_20d_ago = hist["Close"].iloc[-20]

        momentum = (current_price - price_20d_ago) / price_20d_ago
        return momentum

    def _calculate_rsi(self, hist: pd.DataFrame, period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(hist) < period + 1:
            return 50.0

        closes = hist["Close"]
        deltas = closes.diff()

        gains = deltas.where(deltas > 0, 0.0)
        losses = -deltas.where(deltas < 0, 0.0)

        avg_gains = gains.rolling(window=period).mean()
        avg_losses = losses.rolling(window=period).mean()

        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1]

    def _calculate_volume_ratio(self, hist: pd.DataFrame) -> float:
        """Calculate current volume vs 20-day average."""
        if len(hist) < 20:
            return 1.0

        current_volume = hist["Volume"].iloc[-1]
        avg_volume = hist["Volume"].iloc[-20:].mean()

        if avg_volume == 0:
            return 1.0

        return current_volume / avg_volume

    def _calculate_ma_score(self, hist: pd.DataFrame) -> float:
        """Calculate moving average crossover score."""
        if len(hist) < 50:
            return 0.0

        closes = hist["Close"]
        ma20 = closes.rolling(window=20).mean()
        ma50 = closes.rolling(window=50).mean()

        current_price = closes.iloc[-1]
        current_ma20 = ma20.iloc[-1]
        current_ma50 = ma50.iloc[-1]

        score = 0.0

        # Price above both MAs
        if current_price > current_ma20 and current_price > current_ma50:
            score += 15

        # Golden cross (MA20 above MA50)
        if current_ma20 > current_ma50:
            score += 10

        return score

    def _generate_buy_orders(self, candidates: List[CandidateStock]) -> List[Order]:
        """Generate buy orders for top candidate stocks."""
        orders = []
        available_cash = self.trader.get_account_cash()
        cash_per_position = (
            self.weekly_allocation / len(candidates) if candidates else 0
        )

        logger.info(f"Generating buy orders for {len(candidates)} candidates")
        logger.info(f"Cash per position: ${cash_per_position:.2f}")

        for candidate in candidates:
            try:
                # Calculate position size
                quantity = int(cash_per_position / candidate.current_price)

                if quantity < 1:
                    logger.warning(
                        f"Insufficient funds for {candidate.symbol} at ${candidate.current_price:.2f}"
                    )
                    continue

                # Validate order with risk manager
                order = Order(
                    symbol=candidate.symbol,
                    action="buy",
                    quantity=quantity,
                    order_type="market",
                    limit_price=candidate.current_price,
                    reason=f"Top ranked stock (score={0.5 * candidate.technical_score + 0.5 * candidate.consensus_score:.1f})",
                )

                portfolio_value = available_cash
                current_positions = len(self.trader.get_all_positions())

                is_valid, reason = self.risk_manager.validate_order(
                    order, portfolio_value, current_positions
                )

                if is_valid:
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
        except:
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
            f"Trade recorded: {position.symbol} {exit_reason} - "
            f"P&L: ${pnl:.2f} ({pnl_pct:.2%})"
        )


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
