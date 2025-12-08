"""
Crypto Trading Strategy - Experimental Allocation

This module implements a crypto-specific trading strategy for BTC and ETH
with tighter RSI thresholds and wider risk parameters adapted for crypto volatility.

Strategy Overview:
- Daily analysis of BTC/USD and ETH/USD
- Tighter RSI thresholds (40/60 vs stocks' 30/70)
- MACD crossover confirmation
- Volume > average confirmation
- 7% stop-loss (wider than stocks' 3-5%)
- 2% max position size (tighter than stocks)
- $10/day allocation on weekends (Alpaca minimum)

Target: High-risk experimental returns
Risk Level: VERY HIGH
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from src.core.alpaca_trader import AlpacaTrader
from src.core.risk_manager import RiskManager

# Configure logging
logger = logging.getLogger(__name__)

# Newsletter integration (optional)
try:
    from src.utils.newsletter_analyzer import NewsletterAnalyzer

    NEWSLETTER_AVAILABLE = True
except ImportError:
    NEWSLETTER_AVAILABLE = False
    logger.info("NewsletterAnalyzer not available - crypto trades will use algo-only signals")


class CryptoSentiment(Enum):
    """Crypto market sentiment classification."""

    VERY_BULLISH = "very_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    VERY_BEARISH = "very_bearish"


@dataclass
class CryptoScore:
    """Data class for crypto momentum analysis."""

    symbol: str
    score: float
    returns_1w: float
    returns_1m: float
    returns_3m: float
    volatility: float
    sharpe_ratio: float
    rsi: float
    macd_value: float
    macd_signal: float
    macd_histogram: float
    volume_ratio: float
    timestamp: datetime


@dataclass
class CryptoOrder:
    """Data class for crypto trade order details."""

    symbol: str
    action: str  # 'buy' or 'sell'
    quantity: float
    amount: float
    price: float | None
    order_type: str
    stop_loss: float | None
    timestamp: datetime
    reason: str


class CryptoStrategy:
    """
    Crypto trading strategy implementing momentum-based trading for BTC and ETH.

    This strategy:
    - Focuses on BTC/USD and ETH/USD pairs
    - Uses tighter RSI thresholds (40/60) adapted for crypto
    - Requires MACD crossover confirmation
    - Implements wider stop-loss (7%) for crypto volatility
    - Executes daily analysis with best coin selection
    - Implements risk management with tighter position limits

    Attributes:
        daily_amount (float): Dollar amount to invest daily
        crypto_universe (List[str]): List of crypto symbols to analyze
        rsi_oversold (int): RSI oversold threshold
        rsi_overbought (int): RSI overbought threshold
        stop_loss_pct (float): Stop-loss percentage
        max_position_pct (float): Maximum position size as % of portfolio
    """

    # Default crypto universe (Alpaca crypto symbols)
    DEFAULT_CRYPTO_UNIVERSE = ["BTCUSD", "ETHUSD"]

    # RSI parameters (tighter for crypto volatility)
    RSI_PERIOD = 14
    RSI_OVERSOLD = 40  # Tighter than stocks (30)
    RSI_OVERBOUGHT = 60  # Tighter than stocks (70)

    # MACD parameters
    MACD_FAST_PERIOD = 12
    MACD_SLOW_PERIOD = 26
    MACD_SIGNAL_PERIOD = 9

    # Risk parameters (adapted for crypto)
    DEFAULT_STOP_LOSS_PCT = 0.07  # 7% (wider than stocks' 3-5%)
    MAX_POSITION_PCT = 0.02  # 2% of portfolio (tighter than stocks)

    # Lookback periods for momentum (in days)
    LOOKBACK_1WEEK = 7
    LOOKBACK_1MONTH = 30
    LOOKBACK_3MONTH = 90

    # Momentum weights
    MOMENTUM_WEIGHTS = {
        "1week": 0.5,  # 50% weight to very recent (crypto moves fast)
        "1month": 0.3,  # 30% weight to medium-term
        "3month": 0.2,  # 20% weight to long-term
    }

    def __init__(
        self,
        trader=None,
        risk_manager=None,
        daily_amount: float | None = None,
        crypto_universe: list[str] | None = None,
        stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT,
    ):
        """
        Initialize the Crypto Strategy.

        Args:
            trader: AlpacaTrader instance (optional, will create if None)
            risk_manager: RiskManager instance (optional, will create if None)
            daily_amount: Daily investment amount in dollars (default: from env or $10 - Alpaca minimum)
            crypto_universe: List of crypto symbols (default: BTCUSD, ETHUSD)
            stop_loss_pct: Stop-loss percentage (default: 7%)

        Raises:
            ValueError: If daily_amount is non-positive
        """
        # Get daily amount from env var or use default
        if daily_amount is None:
            daily_amount = float(os.getenv("CRYPTO_DAILY_AMOUNT", "10.0"))

        if daily_amount <= 0:
            raise ValueError(f"daily_amount must be positive, got {daily_amount}")

        self.daily_amount = daily_amount
        self.crypto_universe = crypto_universe or self.DEFAULT_CRYPTO_UNIVERSE
        self.stop_loss_pct = stop_loss_pct

        # Strategy state
        self.current_holdings: dict[str, float] = {}
        self.total_invested: float = 0.0
        self.total_value: float = 0.0

        # Performance tracking
        self.daily_returns: list[float] = []
        self.trades_executed: list[CryptoOrder] = []
        self.score_history: list[CryptoScore] = []

        # Initialize dependencies (use provided or create new)
        try:
            self.trader = trader or AlpacaTrader(paper=True)
            self.risk_manager = risk_manager or RiskManager(
                max_daily_loss_pct=2.0,
                max_position_size_pct=self.MAX_POSITION_PCT * 100,  # Convert to percentage
                max_drawdown_pct=15.0,  # Higher for crypto
                max_consecutive_losses=3,
            )
            logger.info("Successfully initialized crypto dependencies")
        except Exception as e:
            logger.warning(f"Failed to initialize some dependencies: {e}")
            self.trader = None
            self.risk_manager = None

        # Initialize newsletter analyzer (optional)
        self.newsletter = None
        if NEWSLETTER_AVAILABLE:
            try:
                self.newsletter = NewsletterAnalyzer()
                logger.info(
                    "NewsletterAnalyzer initialized - will validate trades against CoinSnacks"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize NewsletterAnalyzer: {e}")
                self.newsletter = None

        logger.info(
            f"CryptoStrategy initialized: daily_amount=${daily_amount}, "
            f"crypto_universe={self.crypto_universe}, stop_loss={stop_loss_pct * 100}%"
        )

    def execute(self) -> dict:
        """
        Execute the crypto trading routine (compatible with autonomous_trader.py interface).

        Returns:
            Dict with execution results
        """
        logger.info("=" * 70)
        logger.info("CRYPTO STRATEGY - Daily Execution")
        logger.info("=" * 70)

        try:
            # Execute daily logic
            order = self.execute_daily()

            if order:
                return {
                    "success": True,
                    "symbol": order.symbol,
                    "amount": order.amount,
                    "quantity": order.quantity,
                    "price": order.price,
                    "reason": order.reason,
                }
            else:
                return {
                    "success": False,
                    "reason": "no_valid_trades",
                    "message": "No valid crypto opportunities today",
                }

        except Exception as e:
            logger.error(f"Crypto strategy execution failed: {e}")
            import traceback

            traceback.print_exc()
            return {"success": False, "reason": "error", "error": str(e)}

    def execute_daily(self) -> CryptoOrder | None:
        """
        Execute the daily crypto trading routine.

        This is the main entry point that orchestrates:
        1. Analyze all coins in universe
        2. Calculate momentum scores
        3. Select best coin
        4. Execute order if valid
        5. Risk management

        Returns:
            CryptoOrder if an order was placed, None otherwise

        Raises:
            Exception: If critical trading error occurs
        """
        logger.info("=" * 80)
        logger.info("Starting daily crypto strategy execution")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info(f"Daily allocation: ${self.daily_amount}")

        try:
            # Step 1: Calculate scores for all coins
            scores = self._calculate_all_scores()

            if not scores:
                logger.warning("No valid crypto opportunities today")
                return None

            # Step 2: Select best coin based on our algorithm
            best_coin = self.select_crypto()
            if not best_coin:
                logger.warning("No crypto selected - all failed filters")
                return None

            logger.info(f"Selected crypto (algorithm): {best_coin}")

            # Step 2.5: Validate against CoinSnacks newsletter
            validation = self.get_newsletter_validation(best_coin)

            if validation["available"]:
                logger.info(
                    f"Newsletter Validation: Our pick={best_coin}, "
                    f"CoinSnacks pick={validation['newsletter_pick']}, "
                    f"Agreement={validation['agreement']}"
                )

                if not validation["agreement"]:
                    logger.warning(
                        f"CONFLICT: Our algorithm picked {best_coin} but CoinSnacks recommends "
                        f"{validation['newsletter_pick']}. Reasoning: {validation['reasoning']}"
                    )
                    # Note: We still proceed with our pick but log the disagreement
                    # Future: Could implement weighted decision (70% algo, 30% newsletter)
                else:
                    logger.info(
                        f"AGREEMENT: CoinSnacks also recommends {best_coin}. "
                        f"Confidence boost: +{validation['confidence_boost']}"
                    )
            else:
                logger.info(f"Newsletter validation not available: {validation['reasoning']}")

            # Step 3: Get current price
            current_price = self._get_current_price(best_coin)
            if current_price is None:
                logger.error(f"Failed to get price for {best_coin}")
                return None

            # Step 4: Calculate quantity
            quantity = self.daily_amount / current_price

            # Step 5: Risk validation
            if not self._validate_trade(best_coin, quantity, current_price):
                logger.warning("Trade failed risk validation")
                return None

            # Step 6: Create order
            order = self._create_buy_order(
                symbol=best_coin,
                quantity=quantity,
                price=current_price,
            )

            # Step 7: Execute order via Alpaca
            if self.trader:
                executed_order = None
                try:
                    executed_order = self.trader.execute_order(
                        symbol=best_coin,
                        amount_usd=self.daily_amount,
                        side="buy",
                        tier="CRYPTO",
                    )
                    logger.info(f"Alpaca order executed: {executed_order['id']}")

                    # Step 7.5: Save trade to daily file for dashboard tracking
                    self._save_trade_to_daily_file(
                        symbol=best_coin,
                        action="BUY",
                        amount=self.daily_amount,
                        quantity=quantity,
                        price=current_price,
                        order_id=executed_order.get("id", ""),
                    )
                except Exception as e:
                    logger.error(f"Failed to execute order via Alpaca: {e}")
                    return None

                # Set stop-loss order (optional - crypto may not support stop orders)
                if order.stop_loss:
                    try:
                        self.trader.set_stop_loss(
                            symbol=best_coin, qty=quantity, stop_price=order.stop_loss
                        )
                        logger.info(f"Stop-loss set at ${order.stop_loss:.2f}")
                    except Exception as stop_loss_error:
                        # Stop-loss failure doesn't invalidate the trade
                        # Alpaca crypto doesn't support stop-loss orders
                        logger.warning(
                            f"Stop-loss order failed (this is expected for crypto): {stop_loss_error}. "
                            f"Trade executed successfully: {executed_order['id']}"
                        )

            # Step 8: Update state
            self._update_holdings(best_coin, quantity)
            self.total_invested += self.daily_amount
            self.trades_executed.append(order)

            logger.info(f"Order executed successfully: {order}")
            logger.info(f"Total invested to date: ${self.total_invested:.2f}")

            return order

        except Exception as e:
            logger.error(f"Error in daily execution: {str(e)}", exc_info=True)
            raise

    def get_newsletter_validation(self, our_pick: str) -> dict:
        """
        Fetch CoinSnacks recommendation and compare to our pick.

        Args:
            our_pick: The crypto symbol our algorithm selected (e.g., "BTCUSD")

        Returns:
            Dictionary with:
            - newsletter_pick: str or None (CoinSnacks recommendation)
            - agreement: bool (whether picks match)
            - confidence_boost: int (+10 or -10 points)
            - reasoning: str (CoinSnacks reasoning if available)
            - available: bool (whether newsletter data was available)
        """
        if not self.newsletter:
            return {
                "newsletter_pick": None,
                "agreement": None,
                "confidence_boost": 0,
                "reasoning": "Newsletter analyzer not available",
                "available": False,
            }

        try:
            # Get latest signals from CoinSnacks
            signals = self.newsletter.get_latest_signals()

            if not signals or "recommended_coin" not in signals:
                logger.warning("No CoinSnacks signals available")
                return {
                    "newsletter_pick": None,
                    "agreement": None,
                    "confidence_boost": 0,
                    "reasoning": "No CoinSnacks data available",
                    "available": False,
                }

            newsletter_pick = signals.get("recommended_coin")

            # Compare picks (handle different formats: BTCUSD vs BTC)
            our_coin = our_pick.replace("USD", "")  # BTCUSD -> BTC
            newsletter_coin = newsletter_pick.replace("USD", "") if newsletter_pick else None

            agreement = (our_coin == newsletter_coin) if newsletter_coin else False
            boost = 10 if agreement else -10

            return {
                "newsletter_pick": newsletter_pick,
                "agreement": agreement,
                "confidence_boost": boost,
                "reasoning": signals.get("reasoning", "No reasoning provided"),
                "available": True,
            }

        except Exception as e:
            logger.error(f"Error validating against newsletter: {e}")
            return {
                "newsletter_pick": None,
                "agreement": None,
                "confidence_boost": 0,
                "reasoning": f"Error: {str(e)}",
                "available": False,
            }

    def select_crypto(self) -> str | None:
        """
        Select the crypto with the highest momentum score.

        Returns:
            Symbol of the best crypto to purchase, or None if none qualify

        Raises:
            ValueError: If no valid crypto can be selected
        """
        logger.info("Selecting best crypto from universe")

        # Calculate scores
        scores = self._calculate_all_scores()

        if not scores:
            logger.warning("No valid crypto opportunities - all failed hard filters")
            return None

        # Sort by score
        scores.sort(key=lambda x: x.score, reverse=True)

        # Log rankings
        logger.info("Crypto Rankings:")
        for i, score in enumerate(scores, 1):
            logger.info(
                f"  {i}. {score.symbol}: {score.score:.2f} "
                f"(RSI: {score.rsi:.1f}, MACD: {score.macd_histogram:.4f})"
            )

        best_crypto = scores[0].symbol
        logger.info(f"Best crypto selected: {best_crypto} with score {scores[0].score:.2f}")

        return best_crypto

    def analyze_coin(self, symbol: str) -> dict:
        """
        Analyze a single crypto coin and return scoring metrics.

        Args:
            symbol: Crypto symbol (e.g., "BTCUSD", "ETHUSD")

        Returns:
            Dictionary containing:
            - score: Composite momentum score (0-100)
            - signals: Technical indicator signals
            - metrics: Raw technical metrics

        Raises:
            ValueError: If unable to analyze symbol
        """
        logger.info(f"Analyzing {symbol}")

        try:
            # Get historical data
            hist = self._get_historical_data(symbol)
            if hist is None or hist.empty:
                raise ValueError(f"Unable to fetch data for {symbol}")

            # Calculate all metrics
            returns_1w = self._calculate_period_return(hist, self.LOOKBACK_1WEEK)
            returns_1m = self._calculate_period_return(hist, self.LOOKBACK_1MONTH)
            returns_3m = self._calculate_period_return(hist, self.LOOKBACK_3MONTH)

            daily_returns = hist["Close"].pct_change().dropna()
            volatility = daily_returns.std() * np.sqrt(252)

            risk_free_rate = 0.04
            excess_return = returns_3m - risk_free_rate
            sharpe_ratio = excess_return / volatility if volatility > 0 else 0

            rsi = self._calculate_rsi(hist["Close"], self.RSI_PERIOD)
            macd_value, macd_signal, macd_histogram = self._calculate_macd(hist["Close"])
            volume_ratio = self._calculate_volume_ratio(hist)

            # Calculate composite score
            score = self._calculate_score(
                returns_1w=returns_1w,
                returns_1m=returns_1m,
                returns_3m=returns_3m,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                rsi=rsi,
                macd_histogram=macd_histogram,
                volume_ratio=volume_ratio,
            )

            # Build signals
            signals = {
                "momentum": "bullish" if returns_1m > 0 else "bearish",
                "rsi": self._classify_rsi(rsi),
                "macd": "bullish" if macd_histogram > 0 else "bearish",
                "volume": (
                    "high" if volume_ratio > 1.2 else "normal" if volume_ratio > 0.8 else "low"
                ),
            }

            # Build metrics
            metrics = {
                "returns_1w": returns_1w,
                "returns_1m": returns_1m,
                "returns_3m": returns_3m,
                "volatility": volatility,
                "sharpe_ratio": sharpe_ratio,
                "rsi": rsi,
                "macd_value": macd_value,
                "macd_signal": macd_signal,
                "macd_histogram": macd_histogram,
                "volume_ratio": volume_ratio,
            }

            result = {
                "score": score,
                "signals": signals,
                "metrics": metrics,
            }

            logger.info(
                f"{symbol} analysis: score={score:.2f}, "
                f"RSI={rsi:.1f}, MACD={macd_histogram:.4f}, "
                f"volume_ratio={volume_ratio:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            raise ValueError(f"Failed to analyze {symbol}") from e

    def get_performance_metrics(self) -> dict:
        """
        Calculate comprehensive performance metrics for the strategy.

        Returns:
            Dictionary containing performance statistics
        """
        logger.info("Calculating crypto performance metrics")

        # Calculate current portfolio value
        current_value = self._calculate_total_portfolio_value()

        # Basic metrics
        total_return = current_value - self.total_invested
        total_return_pct = (
            (total_return / self.total_invested * 100) if self.total_invested > 0 else 0.0
        )

        # Calculate Sharpe ratio
        if len(self.daily_returns) > 1:
            mean_return = np.mean(self.daily_returns)
            std_return = np.std(self.daily_returns)
            risk_free_rate_daily = 0.04 / 252
            sharpe_ratio = (
                (mean_return - risk_free_rate_daily) / std_return * np.sqrt(252)
                if std_return > 0
                else 0.0
            )
        else:
            sharpe_ratio = 0.0

        # Win rate
        positive_days = sum(1 for r in self.daily_returns if r > 0)
        win_rate = (positive_days / len(self.daily_returns) * 100) if self.daily_returns else 0.0

        # Trade statistics
        num_trades = len(self.trades_executed)
        average_trade_size = (
            sum(trade.amount for trade in self.trades_executed) / num_trades
            if num_trades > 0
            else 0.0
        )

        metrics = {
            "total_invested": self.total_invested,
            "current_value": current_value,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "sharpe_ratio": sharpe_ratio,
            "win_rate": win_rate,
            "num_trades": num_trades,
            "average_trade_size": average_trade_size,
            "current_holdings": self.current_holdings.copy(),
        }

        # Log summary
        logger.info("Crypto Performance Summary:")
        logger.info(f"  Total Invested: ${metrics['total_invested']:.2f}")
        logger.info(f"  Current Value: ${metrics['current_value']:.2f}")
        logger.info(
            f"  Total Return: ${metrics['total_return']:.2f} ({metrics['total_return_pct']:.2f}%)"
        )
        logger.info(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        logger.info(f"  Win Rate: {metrics['win_rate']:.1f}%")
        logger.info(f"  Number of Trades: {metrics['num_trades']}")

        return metrics

    # ==================== Private Helper Methods ====================

    def _calculate_all_scores(self) -> list[CryptoScore]:
        """Calculate scores for all coins in universe."""
        scores = []

        for symbol in self.crypto_universe:
            try:
                # Get historical data
                hist = self._get_historical_data(symbol)
                if hist is None or hist.empty:
                    logger.warning(f"{symbol}: Unable to fetch data")
                    continue

                # Calculate metrics
                returns_1w = self._calculate_period_return(hist, self.LOOKBACK_1WEEK)
                returns_1m = self._calculate_period_return(hist, self.LOOKBACK_1MONTH)
                returns_3m = self._calculate_period_return(hist, self.LOOKBACK_3MONTH)

                daily_returns = hist["Close"].pct_change().dropna()
                volatility = daily_returns.std() * np.sqrt(252)

                risk_free_rate = 0.04
                excess_return = returns_3m - risk_free_rate
                sharpe_ratio = excess_return / volatility if volatility > 0 else 0

                rsi = self._calculate_rsi(hist["Close"], self.RSI_PERIOD)
                macd_value, macd_signal, macd_histogram = self._calculate_macd(hist["Close"])
                volume_ratio = self._calculate_volume_ratio(hist)

                # HARD FILTER 1: Reject strongly bearish MACD (allow slightly negative for less conservative approach)
                # Changed from < 0 to < -50 to allow trades when MACD is recovering from bearish
                macd_threshold = float(os.getenv("CRYPTO_MACD_THRESHOLD", "-50.0"))
                if macd_histogram < macd_threshold:
                    logger.warning(
                        f"{symbol} REJECTED - Bearish MACD histogram ({macd_histogram:.4f} < {macd_threshold})"
                    )
                    continue

                # HARD FILTER 2: Reject overbought RSI (>60 for crypto)
                if rsi > self.RSI_OVERBOUGHT:
                    logger.warning(
                        f"{symbol} REJECTED - Overbought RSI ({rsi:.2f} > {self.RSI_OVERBOUGHT})"
                    )
                    continue

                # HARD FILTER 3: Require volume confirmation
                # Note: Weekend volume is typically lower, so threshold is 0.3 (30% of avg)
                if volume_ratio < 0.3:
                    logger.warning(f"{symbol} REJECTED - Low volume ({volume_ratio:.2f} < 0.3)")
                    continue

                # Calculate composite score
                score = self._calculate_score(
                    returns_1w=returns_1w,
                    returns_1m=returns_1m,
                    returns_3m=returns_3m,
                    volatility=volatility,
                    sharpe_ratio=sharpe_ratio,
                    rsi=rsi,
                    macd_histogram=macd_histogram,
                    volume_ratio=volume_ratio,
                )

                # Create score object
                score_obj = CryptoScore(
                    symbol=symbol,
                    score=score,
                    returns_1w=returns_1w,
                    returns_1m=returns_1m,
                    returns_3m=returns_3m,
                    volatility=volatility,
                    sharpe_ratio=sharpe_ratio,
                    rsi=rsi,
                    macd_value=macd_value,
                    macd_signal=macd_signal,
                    macd_histogram=macd_histogram,
                    volume_ratio=volume_ratio,
                    timestamp=datetime.now(),
                )

                scores.append(score_obj)
                self.score_history.append(score_obj)

            except Exception as e:
                logger.error(f"Failed to calculate score for {symbol}: {e}")
                continue

        return scores

    def _calculate_score(
        self,
        returns_1w: float,
        returns_1m: float,
        returns_3m: float,
        volatility: float,
        sharpe_ratio: float,
        rsi: float,
        macd_histogram: float,
        volume_ratio: float,
    ) -> float:
        """Calculate composite momentum score (0-100)."""
        # Weighted momentum score
        momentum_score = (
            returns_1w * self.MOMENTUM_WEIGHTS["1week"] * 100
            + returns_1m * self.MOMENTUM_WEIGHTS["1month"] * 100
            + returns_3m * self.MOMENTUM_WEIGHTS["3month"] * 100
        )

        # Adjust for volatility (penalize high volatility)
        volatility_penalty = volatility * 5  # Lower penalty than stocks (crypto is volatile)
        momentum_score -= volatility_penalty

        # Adjust for Sharpe ratio
        sharpe_bonus = sharpe_ratio * 3
        momentum_score += sharpe_bonus

        # RSI adjustment (bonus if in healthy range 40-60)
        if self.RSI_OVERSOLD < rsi < self.RSI_OVERBOUGHT:
            momentum_score += 5

        # MACD adjustment (already passed hard filter, so give bonus)
        if macd_histogram > 0:
            momentum_score += 10

        # Volume confirmation
        if volume_ratio > 1.5:
            momentum_score += 12
        elif volume_ratio > 1.2:
            momentum_score += 8

        # Normalize to 0-100 scale
        return max(0, min(100, momentum_score))

    def _get_historical_data(self, symbol: str) -> pd.DataFrame | None:
        """
        Fetch historical data for crypto symbol.

        Tries multiple sources:
        1. AlpacaTrader.get_historical_bars() (if trader available)
        2. yfinance (fallback)
        """
        lookback_days = self.LOOKBACK_3MONTH + 30  # Extra buffer
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        # Try AlpacaTrader first (if available)
        if self.trader:
            try:
                logger.info(f"Attempting to fetch {symbol} data from Alpaca...")
                bars = self.trader.get_historical_bars(
                    symbol=symbol, timeframe="1Day", limit=lookback_days
                )

                if bars and len(bars) > 0:
                    # Convert Alpaca bars to DataFrame
                    df_data = []
                    for bar in bars:
                        df_data.append(
                            {
                                "Open": bar.get("open", bar.get("o", 0)),
                                "High": bar.get("high", bar.get("h", 0)),
                                "Low": bar.get("low", bar.get("l", 0)),
                                "Close": bar.get("close", bar.get("c", 0)),
                                "Volume": bar.get("volume", bar.get("v", 0)),
                                "Date": pd.to_datetime(bar.get("timestamp", bar.get("t", ""))),
                            }
                        )

                    hist = pd.DataFrame(df_data)
                    hist.set_index("Date", inplace=True)

                    if len(hist) >= self.LOOKBACK_3MONTH * 0.7:
                        logger.info(
                            f"✅ Successfully fetched {len(hist)} bars from Alpaca for {symbol}"
                        )
                        return hist
                    else:
                        logger.warning(
                            f"Alpaca returned insufficient data for {symbol} ({len(hist)} bars)"
                        )
                else:
                    logger.warning(f"Alpaca returned empty data for {symbol}")
            except Exception as e:
                logger.warning(f"Alpaca data fetch failed for {symbol}: {e}, trying yfinance...")

        # Fallback to yfinance
        try:
            logger.info(f"Fetching {symbol} data from yfinance...")
            # For Alpaca crypto symbols (BTCUSD, ETHUSD), use yfinance with conversion
            # yfinance uses BTC-USD, ETH-USD format
            yf_symbol = symbol.replace("USD", "-USD")

            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(start=start_date, end=end_date)

            if hist.empty or len(hist) < self.LOOKBACK_3MONTH * 0.7:
                logger.warning(f"Insufficient data for {symbol} (got {len(hist)} bars)")
                return None

            logger.info(f"✅ Successfully fetched {len(hist)} bars from yfinance for {symbol}")
            return hist

        except Exception as e:
            logger.error(f"Error fetching data for {symbol} from yfinance: {e}")
            return None

    def _get_current_price(self, symbol: str) -> float | None:
        """
        Get current market price for crypto symbol.

        Tries AlpacaTrader first, then yfinance.
        """
        # Try AlpacaTrader first
        if self.trader:
            try:
                # Try to get latest bar
                bars = self.trader.get_historical_bars(symbol=symbol, timeframe="1Day", limit=1)
                if bars and len(bars) > 0:
                    price = bars[0].get("close", bars[0].get("c", None))
                    if price:
                        logger.info(f"✅ Got {symbol} price ${price:.2f} from Alpaca")
                        return float(price)
            except Exception as e:
                logger.debug(f"Alpaca price fetch failed for {symbol}: {e}, trying yfinance...")

        # Fallback to yfinance
        try:
            yf_symbol = symbol.replace("USD", "-USD")
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(period="1d")
            if not data.empty:
                price = float(data["Close"].iloc[-1])
                logger.info(f"✅ Got {symbol} price ${price:.2f} from yfinance")
                return price
            return None
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None

    def _calculate_period_return(self, hist: pd.DataFrame, periods: int) -> float:
        """Calculate return over specified number of periods."""
        if len(hist) < periods:
            periods = len(hist) - 1

        if periods <= 0:
            return 0.0

        end_price = hist["Close"].iloc[-1]
        start_price = hist["Close"].iloc[-periods]

        return (end_price - start_price) / start_price

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """Calculate Relative Strength Index (RSI)."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0

    def _calculate_macd(self, prices: pd.Series) -> tuple[float, float, float]:
        """Calculate MACD (Moving Average Convergence Divergence)."""
        from src.utils.technical_indicators import calculate_macd

        return calculate_macd(
            prices,
            fast_period=self.MACD_FAST_PERIOD,
            slow_period=self.MACD_SLOW_PERIOD,
            signal_period=self.MACD_SIGNAL_PERIOD,
        )

    def _calculate_volume_ratio(self, hist: pd.DataFrame) -> float:
        """Calculate volume ratio (current vs 20-day average)."""
        from src.utils.technical_indicators import calculate_volume_ratio

        return calculate_volume_ratio(hist, window=20)

    def _classify_rsi(self, rsi: float) -> str:
        """Classify RSI value."""
        if rsi < self.RSI_OVERSOLD:
            return "oversold"
        elif rsi > self.RSI_OVERBOUGHT:
            return "overbought"
        else:
            return "neutral"

    def _validate_trade(self, symbol: str, quantity: float, price: float) -> bool:
        """Validate trade against risk management rules."""
        trade_value = quantity * price

        # Basic validation
        if trade_value > self.daily_amount * 1.1:  # 10% tolerance
            logger.warning(f"Trade value ${trade_value:.2f} exceeds daily allocation")
            return False

        # Use RiskManager if available
        if self.risk_manager:
            try:
                account_value = self._calculate_total_portfolio_value() + self.total_invested
                if account_value == 0:
                    account_value = 10000.0  # Default

                validation = self.risk_manager.validate_trade(
                    symbol=symbol,
                    amount=trade_value,
                    sentiment_score=0.0,  # Neutral for crypto
                    account_value=account_value,
                    trade_type="BUY",
                )

                if not validation["valid"]:
                    logger.warning(f"Risk manager rejected trade: {validation['reason']}")
                    return False

                if validation["warnings"]:
                    for warning in validation["warnings"]:
                        logger.warning(f"Risk manager warning: {warning}")

                return True

            except Exception as e:
                logger.error(f"Error in risk validation: {e}")
                # Fall through to basic validation

        return True

    def _create_buy_order(
        self,
        symbol: str,
        quantity: float,
        price: float,
    ) -> CryptoOrder:
        """Create a buy order with stop-loss."""
        amount = quantity * price
        stop_loss_price = price * (1 - self.stop_loss_pct)

        return CryptoOrder(
            symbol=symbol,
            action="buy",
            quantity=quantity,
            amount=amount,
            price=price,
            order_type="market",
            stop_loss=stop_loss_price,
            timestamp=datetime.now(),
            reason="Daily crypto purchase - best momentum coin",
        )

    def _update_holdings(self, symbol: str, quantity: float) -> None:
        """Update current holdings after trade."""
        self.current_holdings[symbol] = self.current_holdings.get(symbol, 0.0) + quantity

        # Remove if quantity is now zero or negative
        if self.current_holdings[symbol] <= 0:
            self.current_holdings.pop(symbol, None)

    def _calculate_total_portfolio_value(self) -> float:
        """Calculate total current value of all holdings."""
        total = 0.0
        for symbol, quantity in self.current_holdings.items():
            price = self._get_current_price(symbol)
            if price:
                total += quantity * price
        return total

    def _save_trade_to_daily_file(
        self,
        symbol: str,
        action: str,
        amount: float,
        quantity: float,
        price: float,
        order_id: str,
        data_dir: Path = Path("data"),
    ) -> None:
        """
        Save trade to daily trade file (trades_YYYY-MM-DD.json).

        This ensures crypto trades are tracked in the same format as stock trades
        for dashboard reporting and system state updates.

        Args:
            symbol: Crypto symbol (e.g., "BTCUSD")
            action: Trade action ("BUY" or "SELL")
            amount: Dollar amount traded
            quantity: Quantity of crypto purchased
            price: Execution price
            order_id: Alpaca order ID
            data_dir: Data directory path (default: data/)
        """
        today = date.today().isoformat()
        trade_file = data_dir / f"trades_{today}.json"

        # Load existing trades for today
        trades = []
        if trade_file.exists():
            try:
                with open(trade_file) as f:
                    trades = json.load(f)
                    if not isinstance(trades, list):
                        trades = [trades] if trades else []
            except Exception:
                trades = []

        # Create trade record
        trade_data = {
            "symbol": symbol,
            "action": action,
            "amount": round(amount, 2),
            "quantity": quantity,
            "price": round(price, 2),
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "FILLED",
            "strategy": "CryptoStrategy",
            "order_id": order_id,
        }

        # Add new trade
        trades.append(trade_data)

        # Save updated trades
        try:
            # Ensure data directory exists
            data_dir.mkdir(parents=True, exist_ok=True)

            with open(trade_file, "w") as f:
                json.dump(trades, f, indent=2, default=str)

            logger.info(f"✅ Trade saved to {trade_file}: {symbol} {action} ${amount:.2f}")
        except Exception as e:
            logger.error(f"Failed to save trade to daily file: {e}")

    def manage_positions(self) -> list[CryptoOrder]:
        """
        Manage existing crypto positions - check stop-losses and take-profits.

        Since Alpaca crypto doesn't support stop-loss orders, we need to manually
        check positions and close them if stop-loss or take-profit is triggered.

        Returns:
            List of CryptoOrder objects for positions that should be closed
        """
        logger.info("=" * 80)
        logger.info("Managing Crypto Positions")
        logger.info("=" * 80)

        closed_positions = []

        try:
            # Get current positions from Alpaca
            if not self.trader:
                logger.warning("No trader instance available")
                return closed_positions

            positions = self.trader.get_positions()
            crypto_positions = [
                p
                for p in positions
                if p.get("symbol") in self.crypto_universe and p.get("side") == "long"
            ]

            if not crypto_positions:
                logger.info("No crypto positions to manage")
                return closed_positions

            logger.info(f"Checking {len(crypto_positions)} crypto positions")

            for pos in crypto_positions:
                symbol = pos.get("symbol")
                qty = float(pos.get("qty", 0))
                current_price = float(pos.get("current_price", 0))

                if qty <= 0 or current_price <= 0:
                    continue

                # Get entry price (need to track this - for now use avg_cost if available)
                avg_cost = float(pos.get("avg_entry_price", current_price))
                entry_price = avg_cost if avg_cost > 0 else current_price

                # Calculate P/L
                market_value = qty * current_price
                cost_basis = qty * entry_price
                unrealized_pl = market_value - cost_basis
                unrealized_plpc = (unrealized_pl / cost_basis) if cost_basis > 0 else 0.0

                logger.info(
                    f"  {symbol}: {qty:.6f} shares @ ${current_price:.2f} "
                    f"(Entry: ${entry_price:.2f}, P/L: ${unrealized_pl:.2f} ({unrealized_plpc * 100:.2f}%))"
                )

                # Check stop-loss (7% for crypto)
                if unrealized_plpc <= -self.stop_loss_pct:
                    logger.info(
                        f"  🛑 STOP-LOSS TRIGGERED: {unrealized_plpc * 100:.2f}% <= {-self.stop_loss_pct * 100:.1f}%"
                    )

                    try:
                        # Close the position
                        executed_order = self.trader.execute_order(
                            symbol=symbol,
                            amount_usd=market_value,
                            side="sell",
                            tier="CRYPTO",
                        )

                        logger.info(f"  ✅ Position closed: Order ID {executed_order.get('id')}")

                        # Create exit order record
                        exit_order = CryptoOrder(
                            symbol=symbol,
                            action="sell",
                            quantity=qty,
                            amount=market_value,
                            price=current_price,
                            order_type="market",
                            stop_loss=None,
                            timestamp=datetime.now(),
                            reason=f"Stop-loss triggered at {unrealized_plpc * 100:.2f}% loss",
                        )

                        closed_positions.append(exit_order)
                        self._update_holdings(symbol, -qty)

                    except Exception as e:
                        logger.error(f"  ❌ Failed to close position {symbol}: {e}")

                # Check take-profit (10% for crypto, same as stocks)
                elif unrealized_plpc >= 0.10:
                    logger.info(
                        f"  🎯 TAKE-PROFIT TRIGGERED: {unrealized_plpc * 100:.2f}% >= 10.0%"
                    )

                    try:
                        # Close the position
                        executed_order = self.trader.execute_order(
                            symbol=symbol,
                            amount_usd=market_value,
                            side="sell",
                            tier="CRYPTO",
                        )

                        logger.info(f"  ✅ Position closed: Order ID {executed_order.get('id')}")

                        # Create exit order record
                        exit_order = CryptoOrder(
                            symbol=symbol,
                            action="sell",
                            quantity=qty,
                            amount=market_value,
                            price=current_price,
                            order_type="market",
                            stop_loss=None,
                            timestamp=datetime.now(),
                            reason=f"Take-profit triggered at {unrealized_plpc * 100:.2f}% profit",
                        )

                        closed_positions.append(exit_order)
                        self._update_holdings(symbol, -qty)

                    except Exception as e:
                        logger.error(f"  ❌ Failed to close position {symbol}: {e}")
                else:
                    logger.info(
                        f"  ✅ Holding position (P/L {unrealized_plpc * 100:.2f}% within bounds)"
                    )

            if closed_positions:
                logger.info(f"Closed {len(closed_positions)} crypto positions")
            else:
                logger.info("No crypto positions ready for exit")

            return closed_positions

        except Exception as e:
            logger.error(f"Error managing crypto positions: {e}", exc_info=True)
            return closed_positions


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize strategy
    strategy = CryptoStrategy(daily_amount=10.0)

    # Execute daily routine
    order = strategy.execute_daily()

    if order:
        print(
            f"\nOrder executed: {order.action.upper()} {order.quantity:.6f} "
            f"{order.symbol} @ ${order.price:.2f}"
        )

    # Get performance metrics
    metrics = strategy.get_performance_metrics()
    print(f"\nCurrent Portfolio Value: ${metrics['current_value']:.2f}")
    print(f"Total Return: ${metrics['total_return']:.2f} ({metrics['total_return_pct']:.2f}%)")
