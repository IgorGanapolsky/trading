from __future__ import annotations

"""
Backtest Engine Module

This module provides a lightweight backtesting engine for validating trading strategies
on historical data before deploying them in live trading. It simulates strategy execution
day-by-day and calculates comprehensive performance metrics.

Features:
    - Simulates daily strategy execution on historical data
    - Tracks portfolio value, trades, and P/L over time
    - Calculates key performance metrics (Sharpe, win rate, drawdown)
    - Works with existing CoreStrategy class
    - Uses yfinance for historical price data

Author: Trading System
Created: 2025-11-02
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from src.agents.rl_agent import RLFilter
from src.analyst.bias_store import BiasSnapshot
from src.backtesting.backtest_results import BacktestResults
from src.backtesting.bias_replay import BiasReplay
from src.risk.risk_manager import RiskManager
from src.utils.technical_indicators import calculate_technical_score

try:  # Optional dependency for point-in-time sentiment
    from rag_store.sqlite_store import SentimentSQLiteStore
except Exception:  # noqa: BLE001
    SentimentSQLiteStore = None  # type: ignore[misc]

# Import slippage model for realistic execution costs
try:
    from src.risk.slippage_model import SlippageModel, SlippageModelType

    SLIPPAGE_AVAILABLE = True
except ImportError:
    SLIPPAGE_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)


class BacktestEngine:
    """
    Lightweight backtesting engine for momentum-based ETF trading strategies.

    This engine simulates the execution of a trading strategy on historical data,
    tracking portfolio performance and calculating comprehensive metrics.

    Attributes:
        strategy: Trading strategy instance to backtest
        start_date: Start date for backtest (YYYY-MM-DD format)
        end_date: End date for backtest (YYYY-MM-DD format)
        initial_capital: Starting capital amount
        current_capital: Current available capital
        portfolio_value: Current total portfolio value
        positions: Current holdings {symbol: quantity}
        trades: List of executed trades
        equity_curve: Daily portfolio values
        dates: Trading dates
    """

    def __init__(
        self,
        strategy: Any,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        enable_slippage: bool = True,
        slippage_bps: float = 5.0,
        use_hybrid_gates: bool = False,
        hybrid_options: dict[str, Any] | None = None,
        bias_replay: BiasReplay | None = None,
        sentiment_store: SentimentSQLiteStore | None = None,
    ):
        """
        Initialize the backtest engine.

        Args:
            strategy: Trading strategy instance (e.g., CoreStrategy)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            initial_capital: Starting capital amount (default: $100,000)
            enable_slippage: Whether to model execution slippage (default: True)
            slippage_bps: Base slippage in basis points (default: 5 bps)

        Raises:
            ValueError: If dates are invalid or strategy is None
        """
        if strategy is None:
            raise ValueError("Strategy cannot be None")

        try:
            self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
            self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format. Use YYYY-MM-DD: {e}")

        if self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date")

        if initial_capital <= 0:
            raise ValueError("Initial capital must be positive")

        self.strategy = strategy
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.portfolio_value = initial_capital

        # Portfolio state
        self.positions: dict[str, float] = {}
        self.position_costs: dict[str, float] = {}  # Track cost basis

        # Performance tracking
        self.trades: list[dict[str, Any]] = []
        self.equity_curve: list[float] = [initial_capital]
        self.dates: list[str] = [start_date]

        # Price cache for efficiency
        self.price_cache: dict[str, pd.DataFrame] = {}

        # Slippage model for realistic execution costs
        self.enable_slippage = enable_slippage and SLIPPAGE_AVAILABLE
        self.slippage_model = None
        self.total_slippage_cost = 0.0  # Track cumulative slippage
        self.use_hybrid_gates = use_hybrid_gates
        self.hybrid_options = hybrid_options or {}
        self.hybrid_gate_rl: RLFilter | None = None
        self.hybrid_risk: RiskManager | None = None
        self.hybrid_sentiment: SyntheticSentimentModel | None = None
        self.momentum_min_score = float(os.getenv("MOMENTUM_MIN_SCORE", "0.0"))
        self.momentum_macd_threshold = float(os.getenv("MOMENTUM_MACD_THRESHOLD", "0.0"))
        self.momentum_rsi_overbought = float(os.getenv("MOMENTUM_RSI_OVERBOUGHT", "70.0"))
        self.momentum_volume_min = float(os.getenv("MOMENTUM_VOLUME_MIN", "0.8"))

        if self.enable_slippage:
            self.slippage_model = SlippageModel(
                model_type=SlippageModelType.COMPREHENSIVE,
                base_spread_bps=slippage_bps,
                market_impact_bps=10.0,
                latency_ms=100.0,
            )
            logger.info(f"Slippage model enabled: {slippage_bps} bps base spread")
        else:
            logger.warning("Slippage model disabled - results may be optimistic")

        if self.use_hybrid_gates:
            logger.info("Hybrid funnel simulation enabled for backtests.")
            self.hybrid_gate_rl = RLFilter()
            self.hybrid_risk = RiskManager()
            self.hybrid_sentiment = SyntheticSentimentModel(
                negative_threshold=float(os.getenv("LLM_NEGATIVE_SENTIMENT_THRESHOLD", "-0.2"))
            )

        logger.info(f"Backtest engine initialized: {start_date} to {end_date}")
        logger.info(f"Initial capital: ${initial_capital:,.2f}")
        logger.info(f"Strategy: {type(strategy).__name__}")

        self.bias_replay = bias_replay
        self.bias_replay_threshold = float(os.getenv("BACKTEST_BIAS_NEGATIVE_THRESHOLD", "-0.2"))
        if SentimentSQLiteStore is None:
            self.sentiment_store = None
        else:
            self.sentiment_store = sentiment_store

    def run(self) -> BacktestResults:
        """
        Execute the backtest and return comprehensive results.

        This method:
        1. Iterates through each trading day in the date range
        2. Simulates strategy execution for each day
        3. Tracks portfolio performance
        4. Calculates final metrics
        5. Returns BacktestResults object

        Returns:
            BacktestResults object containing all performance data and metrics

        Raises:
            Exception: If backtest execution fails
        """
        logger.info("=" * 80)
        logger.info("STARTING BACKTEST EXECUTION")
        logger.info("=" * 80)

        try:
            # Pre-load price data for all ETFs in strategy universe
            self._preload_price_data()

            # Get trading dates (weekdays only)
            trading_dates = self._get_trading_dates()

            logger.info(f"Total trading days: {len(trading_dates)}")

            # Simulate trading for each day
            for i, date in enumerate(trading_dates):
                self._simulate_trading_day(date)

                # Log progress every 10 days
                if (i + 1) % 10 == 0 or i == len(trading_dates) - 1:
                    logger.info(
                        f"Progress: {i + 1}/{len(trading_dates)} days "
                        f"({(i + 1) / len(trading_dates) * 100:.1f}%) - "
                        f"Portfolio: ${self.portfolio_value:,.2f}"
                    )

            # Calculate final metrics
            results = self._calculate_results()

            logger.info("=" * 80)
            logger.info("BACKTEST COMPLETE")
            logger.info("=" * 80)
            logger.info(f"Total Trades: {results.total_trades}")
            logger.info(
                f"Final Capital: ${results.final_capital:,.2f} ({results.total_return:+.2f}%)"
            )
            logger.info(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
            logger.info(f"Max Drawdown: {results.max_drawdown:.2f}%")
            logger.info(f"Win Rate: {results.win_rate:.1f}%")

            return results

        except Exception as e:
            logger.error(f"Backtest execution failed: {e}", exc_info=True)
            raise

    def _preload_price_data(self) -> None:
        """
        Pre-load historical price data for all ETFs using Alpaca API.
        More reliable than yfinance free tier.
        """
        logger.info("Pre-loading historical price data (Alpaca w/ yfinance fallback)...")

        alpaca_key = os.getenv("ALPACA_API_KEY")
        alpaca_secret = os.getenv("ALPACA_SECRET_KEY")
        use_alpaca = bool(alpaca_key and alpaca_secret)
        client: StockHistoricalDataClient | None = None

        if use_alpaca:
            client = StockHistoricalDataClient(alpaca_key, alpaca_secret)
        else:
            logger.warning(
                "Alpaca API credentials not found. Falling back to yfinance for backtests."
            )

        etf_universe = getattr(self.strategy, "etf_universe", ["SPY", "QQQ", "VOO"])

        for symbol in etf_universe:
            bars = None
            start_with_buffer = datetime.strptime(
                self.start_date.strftime("%Y-%m-%d"), "%Y-%m-%d"
            ) - timedelta(days=200)
            end_with_buffer = datetime.strptime(
                self.end_date.strftime("%Y-%m-%d"), "%Y-%m-%d"
            ) + timedelta(days=1)

            if use_alpaca and client:
                try:
                    req = StockBarsRequest(
                        symbol_or_symbols=symbol,
                        timeframe=TimeFrame.Day,
                        start=start_with_buffer,
                        end=end_with_buffer,
                        adjustment="all",
                    )

                    bars = client.get_stock_bars(req).df

                    if bars is not None and not bars.empty:
                        if "symbol" in bars.index.names:
                            bars = bars.droplevel("symbol")

                        bars = bars.rename(
                            columns={
                                "open": "Open",
                                "high": "High",
                                "low": "Low",
                                "close": "Close",
                                "volume": "Volume",
                            }
                        )
                    else:
                        logger.warning(f"No Alpaca data returned for {symbol}")
                except Exception as e:
                    logger.warning(
                        f"Failed to load Alpaca data for {symbol}: {e}. Will try yfinance."
                    )

            if (bars is None or bars.empty) and not self._load_with_yfinance(
                symbol, start_with_buffer, end_with_buffer
            ):
                logger.error(
                    "Unable to load historical data for %s via Alpaca or yfinance.", symbol
                )
            elif bars is not None and not bars.empty:
                self.price_cache[symbol] = bars
                logger.info(
                    "Loaded %s bars for %s from Alpaca",
                    len(bars),
                    symbol,
                )
            # yfinance handler populates cache internally

    def _load_with_yfinance(self, symbol: str, start: datetime, end: datetime) -> bool:
        """
        Load historical bars using yfinance when Alpaca data is unavailable.
        """
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                auto_adjust=False,
                actions=False,
            )
            if history is None or history.empty:
                logger.warning("yfinance returned no data for %s", symbol)
                return False

            # Ensure columns align with expected format
            history = history.rename(
                columns={
                    "Open": "Open",
                    "High": "High",
                    "Low": "Low",
                    "Close": "Close",
                    "Volume": "Volume",
                }
            )
            history.index = pd.to_datetime(history.index)
            self.price_cache[symbol] = history
            logger.info("Loaded %s bars for %s from yfinance fallback", len(history), symbol)
            return True
        except Exception as exc:
            logger.warning("yfinance fallback failed for %s: %s", symbol, exc)
            return False

    def _get_trading_dates(self) -> list[datetime]:
        """
        Generate list of trading dates (weekdays only) in the backtest period.

        Returns:
            List of datetime objects representing trading days
        """
        dates = []
        current_date = self.start_date

        while current_date <= self.end_date:
            # Only include weekdays (Monday=0 to Friday=4)
            if current_date.weekday() < 5:
                dates.append(current_date)
            current_date += timedelta(days=1)

        return dates

    def _simulate_trading_day(self, date: datetime) -> None:
        """
        Simulate strategy execution for a single trading day.

        Args:
            date: Trading date to simulate
        """
        date_str = date.strftime("%Y-%m-%d")

        # Check for exit conditions (stop-loss / take-profit)
        self._check_exit_conditions(date, date_str)

        try:
            if self.use_hybrid_gates:
                self._simulate_hybrid_day(date, date_str)
            else:
                self._simulate_dca_day(date, date_str)
        except Exception as exc:  # pragma: no cover - safety net
            logger.debug(f"Error simulating {date_str}: {exc}")

        # Record equity curve
        self._update_portfolio_value(date)
        self.equity_curve.append(self.portfolio_value)
        self.dates.append(date_str)

    def _check_exit_conditions(self, date: datetime, date_str: str) -> None:
        """
        Check and execute exit conditions for current positions.
        """
        # Create a copy of keys to allow modification during iteration
        for symbol in list(self.positions.keys()):
            quantity = self.positions[symbol]
            if quantity <= 0:
                continue

            current_price = self._get_price(symbol, date)
            if not current_price:
                continue

            # Calculate average entry price
            total_cost = self.position_costs.get(symbol, 0.0)
            avg_entry_price = total_cost / quantity if quantity > 0 else 0.0

            if avg_entry_price <= 0:
                continue

            # Calculate return percentage
            return_pct = (current_price - avg_entry_price) / avg_entry_price

            # Check Stop Loss
            stop_loss_pct = getattr(self.strategy, "stop_loss_pct", None)
            if stop_loss_pct and return_pct < -stop_loss_pct:
                self._execute_sell(
                    symbol=symbol,
                    date=date,
                    date_str=date_str,
                    quantity=quantity,
                    price=current_price,
                    reason=f"Stop Loss ({return_pct:.2%})",
                )
                continue

            # Check Take Profit
            take_profit_pct = getattr(self.strategy, "take_profit_pct", None)
            if take_profit_pct and return_pct > take_profit_pct:
                self._execute_sell(
                    symbol=symbol,
                    date=date,
                    date_str=date_str,
                    quantity=quantity,
                    price=current_price,
                    reason=f"Take Profit ({return_pct:.2%})",
                )

    def _execute_sell(
        self, symbol: str, date: datetime, date_str: str, quantity: float, price: float, reason: str
    ) -> None:
        """Execute a sell order."""
        executed_price, slippage_cost = self._apply_slippage_adjustment(
            symbol=symbol, date=date, base_price=price, notional=quantity * price, side="sell"
        )

        sale_value = quantity * executed_price

        # Calculate P&L correctly: subtract slippage cost from gross P&L
        gross_pnl = sale_value - self.position_costs[symbol]
        net_pnl = gross_pnl - slippage_cost  # Slippage reduces actual profit

        trade = {
            "date": date_str,
            "symbol": symbol,
            "action": "sell",
            "quantity": quantity,
            "price": executed_price,
            "base_price": price,
            "slippage_cost": slippage_cost,
            "amount": sale_value,
            "reason": reason,
            "pnl": net_pnl,  # Fixed: now accounts for slippage cost
            "gross_pnl": gross_pnl,  # Track gross for analysis
            "return_pct": (net_pnl / self.position_costs[symbol]) * 100,  # Fixed: net return %
        }
        self.trades.append(trade)

        # Update state
        self.current_capital += sale_value
        del self.positions[symbol]
        del self.position_costs[symbol]

        logger.info(f"{date_str}: SOLD {symbol} - {reason}")

    def _simulate_dca_day(self, date: datetime, date_str: str) -> None:
        """Legacy DCA-style backtest flow (pre-hybrid) with basic risk checks."""
        # Update portfolio value with current prices
        self._update_portfolio_value(date)

        # ============================================================
        # RISK CHECK 1: Daily Loss Circuit Breaker
        # ============================================================
        max_daily_loss_pct = float(os.getenv("MAX_DAILY_LOSS_PCT", "2.0")) / 100
        if self.portfolio_value < self.initial_capital * (1 - max_daily_loss_pct):
            daily_loss = (self.initial_capital - self.portfolio_value) / self.initial_capital
            logger.warning(
                f"{date_str}: Daily loss circuit breaker triggered "
                f"({daily_loss * 100:.2f}% > {max_daily_loss_pct * 100:.1f}% limit)"
            )
            return

        # Calculate momentum scores for this date
        momentum_scores = []

        for symbol in self.strategy.etf_universe:
            try:
                hist = self._get_historical_data(symbol, date)
                if hist is None:
                    logger.warning(f"{date_str}: No historical data for {symbol}")
                    continue
                if len(hist) < 50:
                    logger.warning(
                        f"{date_str}: Insufficient data for {symbol}: {len(hist)} bars (need 50)"
                    )
                    continue

                score = self._calculate_momentum_for_date(symbol, date)
                if score is not None:
                    momentum_scores.append({"symbol": symbol, "score": score})
                    logger.info(f"{date_str}: {symbol} momentum={score:.2f}")
                else:
                    logger.warning(f"{date_str}: Momentum calculation returned None for {symbol}")

            except Exception as exc:  # pragma: no cover - defensively continue
                logger.warning(f"Failed to calculate momentum for {symbol}: {exc}")
                continue

        if not momentum_scores:
            logger.warning(f"{date_str}: No valid momentum scores")
            return

        momentum_scores.sort(key=lambda x: x["score"], reverse=True)
        best_etf = momentum_scores[0]["symbol"]

        price = self._get_price(best_etf, date)
        if price is None:
            logger.debug(f"{date_str}: No price available for {best_etf}")
            return

        daily_allocation = self.strategy.daily_allocation
        effective_allocation = daily_allocation
        allocation_type = "DCA"

        if self.strategy.use_vca and self.strategy.vca_strategy:
            try:
                current_portfolio_value = self.portfolio_value
                vca_calc = self.strategy.vca_strategy.calculate_investment_amount(
                    current_portfolio_value, date
                )
                effective_allocation = vca_calc.adjusted_amount
                allocation_type = "VCA"

                if not vca_calc.should_invest:
                    logger.debug(
                        f"{date_str}: VCA recommends skipping investment: {vca_calc.reason}"
                    )
                    return
            except Exception as exc:
                logger.warning(f"{date_str}: VCA calculation failed, using base: {exc}")
                effective_allocation = daily_allocation

        if self.current_capital < effective_allocation:
            return

        # ============================================================
        # RISK CHECK 2: Maximum Position Size (15% of portfolio per symbol)
        # ============================================================
        max_position_pct = float(os.getenv("MAX_POSITION_SIZE_PCT", "15.0")) / 100
        current_position_value = self.positions.get(best_etf, 0.0) * price
        new_position_value = current_position_value + effective_allocation
        position_pct = new_position_value / self.portfolio_value if self.portfolio_value > 0 else 0

        if position_pct > max_position_pct:
            # Cap allocation to stay within limit
            max_additional = (max_position_pct * self.portfolio_value) - current_position_value
            if max_additional <= 0:
                logger.warning(
                    f"{date_str}: {best_etf} already at max position ({position_pct * 100:.1f}% "
                    f"> {max_position_pct * 100:.0f}% limit). Skipping."
                )
                return
            logger.info(
                f"{date_str}: Capping {best_etf} allocation from ${effective_allocation:.2f} "
                f"to ${max_additional:.2f} (position limit)"
            )
            effective_allocation = max_additional

        # ============================================================
        # RISK CHECK 3: Minimum Trade Size
        # ============================================================
        min_trade_size = float(os.getenv("MIN_TRADE_SIZE", "3.0"))
        if effective_allocation < min_trade_size:
            logger.debug(
                f"{date_str}: Allocation ${effective_allocation:.2f} below minimum ${min_trade_size}"
            )
            return

        executed_price, slippage_cost = self._apply_slippage_adjustment(
            symbol=best_etf,
            date=date,
            base_price=price,
            notional=effective_allocation,
        )

        quantity = effective_allocation / executed_price
        trade = {
            "date": date_str,
            "symbol": best_etf,
            "action": "buy",
            "quantity": quantity,
            "price": executed_price,
            "base_price": price,
            "slippage_cost": slippage_cost,
            "amount": effective_allocation,
            "reason": f"Daily {allocation_type} purchase",
            "risk_checks_passed": ["circuit_breaker", "position_limit", "min_trade_size"],
        }
        self.trades.append(trade)

        self.positions[best_etf] = self.positions.get(best_etf, 0.0) + quantity
        self.position_costs[best_etf] = (
            self.position_costs.get(best_etf, 0.0) + effective_allocation
        )
        self.current_capital -= effective_allocation

    def _simulate_hybrid_day(self, date: datetime, date_str: str) -> None:
        """Hybrid funnel-aware simulation that mirrors the production gates."""
        if not self.hybrid_gate_rl or not self.hybrid_risk or not self.hybrid_sentiment:
            logger.warning("Hybrid gate components not initialised. Skipping day.")
            return

        max_trades = int(self.hybrid_options.get("max_trades_per_day", 1))
        trades_placed = 0

        for symbol in self.strategy.etf_universe:
            hist = self._get_historical_data(symbol, date)
            if hist is None or len(hist) < 80:
                continue

            momentum_signal = self._calculate_momentum_snapshot(symbol, hist)
            if not momentum_signal["is_buy"]:
                continue

            rl_decision = self.hybrid_gate_rl.predict(momentum_signal["state"])
            if rl_decision["action"] != "long":
                continue

            snapshot = self._get_point_in_time_sentiment(symbol, date)
            if snapshot:
                sentiment = snapshot
            else:
                sentiment = self.hybrid_sentiment.score(hist)
            if not sentiment.get("accepted", False):
                continue

            price = float(hist["Close"].iloc[-1])
            notional = self.hybrid_risk.calculate_size(
                ticker=symbol,
                account_equity=self.portfolio_value,
                signal_strength=momentum_signal["strength"],
                rl_confidence=rl_decision["confidence"],
                sentiment_score=sentiment["score"],
                multiplier=rl_decision.get("suggested_multiplier", 1.0),
                current_price=price,
                hist=hist,
            )

            if notional <= 0 or self.current_capital <= 0:
                continue

            notional = min(notional, self.current_capital)
            executed_price, slippage_cost = self._apply_slippage_adjustment(
                symbol=symbol,
                date=date,
                base_price=price,
                notional=notional,
                hist=hist,
            )

            quantity = notional / executed_price
            self.positions[symbol] = self.positions.get(symbol, 0.0) + quantity
            self.position_costs[symbol] = self.position_costs.get(symbol, 0.0) + notional
            self.current_capital -= notional
            self.trades.append(
                {
                    "date": date_str,
                    "symbol": symbol,
                    "action": "buy",
                    "quantity": quantity,
                    "price": executed_price,
                    "amount": notional,
                    "slippage_cost": slippage_cost,
                    "reason": "hybrid_funnel_pass",
                    "gate_payload": {
                        "momentum": momentum_signal,
                        "rl": rl_decision,
                        "sentiment": sentiment,
                    },
                }
            )
            trades_placed += 1
            if trades_placed >= max_trades:
                break

    def _apply_slippage_adjustment(
        self,
        *,
        symbol: str,
        date: datetime,
        base_price: float,
        notional: float,
        side: str = "buy",
        hist: pd.DataFrame | None = None,
    ) -> tuple[float, float]:
        executed_price = base_price
        slippage_cost = 0.0

        if self.enable_slippage and self.slippage_model:
            hist = hist or self._get_historical_data(symbol, date)
            avg_volume = None
            volatility = None
            if hist is not None and len(hist) >= 20:
                avg_volume = hist["Volume"].tail(20).mean()
                returns = hist["Close"].pct_change().dropna()
                volatility = returns.tail(20).std() if len(returns) >= 20 else 0.02

            quantity_estimate = notional / base_price
            slippage_result = self.slippage_model.calculate_slippage(
                price=base_price,
                quantity=quantity_estimate,
                side=side,
                symbol=symbol,
                volume=avg_volume,
                volatility=volatility,
            )
            executed_price = slippage_result.executed_price
            slippage_cost = slippage_result.slippage_amount * quantity_estimate
            self.total_slippage_cost += slippage_cost

        return executed_price, slippage_cost

    def _get_historical_data(self, symbol: str, date: datetime) -> pd.DataFrame | None:
        """
        Get historical data for a symbol up to a specific date.

        Args:
            symbol: ETF symbol
            date: Date to get data up to

        Returns:
            DataFrame with historical data or None if unavailable
        """
        if symbol not in self.price_cache:
            return None

        hist = self.price_cache[symbol]

        # Convert date to timezone-aware datetime for comparison with Alpaca data
        if date.tzinfo is None:
            import pytz

            date = pytz.UTC.localize(date)

        # Filter to only include data up to the simulation date
        hist_filtered = hist[hist.index <= date]

        return hist_filtered if len(hist_filtered) > 0 else None

    def _calculate_momentum_snapshot(self, symbol: str, hist: pd.DataFrame) -> dict[str, Any]:
        score, indicators = calculate_technical_score(
            hist,
            symbol,
            macd_threshold=self.momentum_macd_threshold,
            rsi_overbought=self.momentum_rsi_overbought,
            volume_min=self.momentum_volume_min,
        )
        indicators = indicators or {}
        indicators["symbol"] = symbol

        strength = 0.0
        if score > 0:
            strength = score / (score + 100.0)

        is_buy = score > self.momentum_min_score
        return {
            "is_buy": is_buy,
            "strength": strength,
            "state": {
                **indicators,
                "momentum_strength": strength,
                "raw_score": score,
            },
        }

    def _calculate_momentum_for_date(self, symbol: str, date: datetime) -> float | None:
        """
        Calculate momentum score for a symbol at a specific date.

        Args:
            symbol: ETF symbol
            date: Date to calculate momentum for

        Returns:
            Momentum score or None if calculation fails
        """
        try:
            hist = self._get_historical_data(symbol, date)
            if hist is None or len(hist) < 126:  # Need at least 6 months
                return None

            # Simple momentum calculation (weighted returns)
            # This is a simplified version - adjust as needed
            returns_1m = self._calculate_period_return(hist, 21)
            returns_3m = self._calculate_period_return(hist, 63)
            returns_6m = self._calculate_period_return(hist, 126)

            momentum = (returns_1m * 0.5 + returns_3m * 0.3 + returns_6m * 0.2) * 100

            return momentum

        except Exception as e:
            logger.debug(f"Momentum calculation failed for {symbol}: {e}")
            return None

    def _calculate_period_return(self, hist: pd.DataFrame, periods: int) -> float:
        """
        Calculate return over specified number of periods.

        Args:
            hist: Historical price DataFrame
            periods: Number of periods to look back

        Returns:
            Period return as decimal
        """
        if len(hist) < periods:
            periods = len(hist) - 1

        if periods <= 0:
            return 0.0

        end_price = hist["Close"].iloc[-1]
        start_price = hist["Close"].iloc[-periods]

        return (end_price - start_price) / start_price

    def _get_bias_snapshot(self, symbol: str, date: datetime) -> BiasSnapshot | None:
        if not self.bias_replay:
            return None
        if date.tzinfo is None:
            aware_date = date.replace(tzinfo=timezone.utc)
        else:
            aware_date = date.astimezone(timezone.utc)
        try:
            return self.bias_replay.get_bias(symbol, aware_date)
        except Exception:
            return None

    def _bias_blocks_trade(self, symbol: str, date: datetime) -> bool:
        snapshot = self._get_bias_snapshot(symbol, date)
        if snapshot is None:
            return False
        return snapshot.score < self.bias_replay_threshold

    def _get_point_in_time_sentiment(
        self,
        symbol: str,
        date: datetime,
    ) -> dict[str, Any] | None:
        if not getattr(self, "sentiment_store", None):
            return None
        try:
            rows = list(
                self.sentiment_store.fetch_latest_by_ticker(  # type: ignore[union-attr]
                    symbol, limit=1, as_of=date
                )
            )
        except Exception:
            return None
        if not rows:
            return None
        row = rows[0]
        raw_score = row["score"]
        if raw_score is None:
            normalized = 0.0
        else:
            raw_float = float(raw_score)
            if raw_float > 1.0 or raw_float < -1.0:
                normalized = max(-1.0, min(1.0, (raw_float - 50.0) / 50.0))
            else:
                normalized = raw_float
        threshold = getattr(self.hybrid_sentiment, "negative_threshold", -0.2)
        accepted = normalized >= threshold
        return {
            "score": normalized,
            "accepted": accepted,
            "threshold": threshold,
            "reason": "rag_store_snapshot",
            "confidence": row.get("confidence"),
            "snapshot_date": row.get("snapshot_date"),
            "source": "rag_store",
        }

    def _get_price(self, symbol: str, date: datetime) -> float | None:
        """
        Get the closing price for a symbol on a specific date.

        Args:
            symbol: ETF symbol
            date: Date to get price for

        Returns:
            Closing price or None if unavailable
        """
        hist = self._get_historical_data(symbol, date)
        if hist is None or len(hist) == 0:
            return None

        return float(hist["Close"].iloc[-1])

    def _update_portfolio_value(self, date: datetime) -> None:
        """
        Update total portfolio value based on current positions and prices.

        Args:
            date: Current date for price lookup
        """
        positions_value = 0.0

        for symbol, quantity in self.positions.items():
            price = self._get_price(symbol, date)
            if price:
                positions_value += quantity * price

        self.portfolio_value = self.current_capital + positions_value

    def _calculate_results(self) -> BacktestResults:
        """
        Calculate comprehensive backtest results and metrics.

        Returns:
            BacktestResults object with all performance data
        """
        # Basic metrics
        final_capital = self.portfolio_value
        total_return = (final_capital - self.initial_capital) / self.initial_capital * 100

        # Calculate daily returns for Sharpe ratio
        daily_returns = np.diff(self.equity_curve) / self.equity_curve[:-1]

        # Sharpe ratio - with volatility floor to prevent extreme values
        # Requires minimum 30 trading days for statistical significance
        MIN_TRADING_DAYS = 30
        MIN_VOLATILITY_FLOOR = 0.0001  # 0.01% minimum daily volatility

        if len(daily_returns) >= MIN_TRADING_DAYS:
            mean_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            # Apply volatility floor to prevent extreme Sharpe ratios
            # (e.g., -45.86 from consistent small losses with near-zero volatility)
            std_return = max(std_return, MIN_VOLATILITY_FLOOR)
            risk_free_rate_daily = 0.04 / 252
            sharpe_ratio = (mean_return - risk_free_rate_daily) / std_return * np.sqrt(252)
            # Clamp extreme values to reasonable bounds
            sharpe_ratio = np.clip(sharpe_ratio, -10.0, 10.0)
        elif len(daily_returns) > 1:
            # Insufficient data for reliable Sharpe - compute but flag as unreliable
            mean_return = np.mean(daily_returns)
            std_return = max(np.std(daily_returns), MIN_VOLATILITY_FLOOR)
            risk_free_rate_daily = 0.04 / 252
            sharpe_ratio = (mean_return - risk_free_rate_daily) / std_return * np.sqrt(252)
            sharpe_ratio = np.clip(sharpe_ratio, -10.0, 10.0)
        else:
            sharpe_ratio = 0.0

        # Max drawdown
        cumulative_returns = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = abs(np.min(drawdown)) * 100

        # Win rate
        positive_days = np.sum(daily_returns > 0)
        win_rate = (positive_days / len(daily_returns) * 100) if len(daily_returns) > 0 else 0.0

        # Trade statistics
        total_trades = len(self.trades)
        profitable_trades = 0

        # Simple profit calculation per trade (simplified)
        for trade in self.trades:
            symbol = trade["symbol"]
            buy_price = trade["price"]
            # Get final price for this symbol
            final_price = self._get_price(symbol, self.end_date)
            if final_price and final_price > buy_price:
                profitable_trades += 1

        average_trade_return = (total_return / total_trades) if total_trades > 0 else 0.0

        # Calculate $100/day target metrics
        target_daily_net_income = 100.0
        daily_pnl_values = self._calculate_daily_pnl()
        avg_daily_pnl = np.mean(daily_pnl_values) if len(daily_pnl_values) > 0 else 0.0
        pct_days_above_target = (
            (
                np.sum(np.array(daily_pnl_values) >= target_daily_net_income)
                / len(daily_pnl_values)
                * 100
            )
            if len(daily_pnl_values) > 0
            else 0.0
        )
        worst_5day_drawdown, worst_20day_drawdown = self._calculate_rolling_drawdowns()

        results = BacktestResults(
            trades=self.trades,
            equity_curve=self.equity_curve,
            dates=self.dates,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            average_trade_return=average_trade_return,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            start_date=self.start_date.strftime("%Y-%m-%d"),
            end_date=self.end_date.strftime("%Y-%m-%d"),
            trading_days=len(self.dates) - 1,
            total_slippage_cost=self.total_slippage_cost,
            slippage_enabled=self.enable_slippage,
            avg_daily_pnl=avg_daily_pnl,
            pct_days_above_target=pct_days_above_target,
            worst_5day_drawdown=worst_5day_drawdown,
            worst_20day_drawdown=worst_20day_drawdown,
        )

        # Log slippage impact
        if self.enable_slippage and self.total_slippage_cost > 0:
            pnl = final_capital - self.initial_capital
            slippage_pct = (self.total_slippage_cost / pnl * 100) if pnl > 0 else 0
            logger.info(
                f"Total Slippage Cost: ${self.total_slippage_cost:.2f} ({slippage_pct:.1f}% of P&L)"
            )

        return results

    def _calculate_daily_pnl(self) -> list[float]:
        """
        Calculate daily P&L values from equity curve.

        Returns:
            List of daily P&L values
        """
        if len(self.equity_curve) < 2:
            return []

        daily_pnl = []
        for i in range(1, len(self.equity_curve)):
            daily_change = self.equity_curve[i] - self.equity_curve[i - 1]
            daily_pnl.append(daily_change)

        return daily_pnl

    def _calculate_rolling_drawdowns(self) -> tuple[float, float]:
        """
        Calculate worst 5-day and 20-day rolling drawdowns.

        Returns:
            Tuple of (worst_5day_drawdown, worst_20day_drawdown) in dollars
        """
        if len(self.equity_curve) < 6:
            return 0.0, 0.0

        equity_array = np.array(self.equity_curve)
        worst_5day = 0.0
        worst_20day = 0.0

        # Calculate rolling 5-day drawdowns
        for i in range(5, len(equity_array)):
            window_start = equity_array[i - 5]
            window_end = equity_array[i]
            drawdown = window_start - window_end  # Positive = loss
            worst_5day = max(worst_5day, drawdown)

        # Calculate rolling 20-day drawdowns
        for i in range(20, len(equity_array)):
            window_start = equity_array[i - 20]
            window_end = equity_array[i]
            drawdown = window_start - window_end  # Positive = loss
            worst_20day = max(worst_20day, drawdown)

        return worst_5day, worst_20day


class SyntheticSentimentModel:
    """Offline sentiment proxy derived from historical price/volume."""

    def __init__(self, negative_threshold: float = -0.2) -> None:
        self.negative_threshold = negative_threshold

    def score(self, hist: pd.DataFrame) -> dict[str, Any]:
        closes = hist["Close"].astype(float)
        returns = closes.pct_change().fillna(0.0)
        short_window = returns.tail(3).mean()
        medium_window = returns.tail(7).mean()
        volatility = returns.tail(10).std() if len(returns) >= 10 else returns.std()

        volume = hist["Volume"].astype(float)
        if len(volume) >= 20:
            volume_ratio = float(volume.iloc[-1] / max(volume.tail(20).mean(), 1e-6))
        else:
            volume_ratio = 1.0

        score = short_window * 15 + medium_window * 5 + (volume_ratio - 1.0) * 0.2 - volatility * 5
        score = max(-1.0, min(1.0, float(score)))
        accepted = score >= self.negative_threshold

        return {
            "score": score,
            "accepted": accepted,
            "threshold": self.negative_threshold,
            "reason": "synthetic_sentiment_proxy",
        }


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # This example shows how to use the backtest engine
    # In practice, you would import and use your actual CoreStrategy

    print("Backtest Engine - Example Usage")
    print("=" * 80)
    print("\nTo use this engine with your CoreStrategy:")
    print("\n  from src.strategies.core_strategy import CoreStrategy")
    print("  from src.backtesting.backtest_engine import BacktestEngine")
    print("\n  strategy = CoreStrategy(daily_allocation=6.0, use_sentiment=False)")
    print("  engine = BacktestEngine(")
    print("      strategy=strategy,")
    print('      start_date="2025-09-01",')
    print('      end_date="2025-10-31",')
    print("      initial_capital=100000")
    print("  )")
    print("  results = engine.run()")
    print("  print(results.generate_report())")
    print("\n" + "=" * 80)
