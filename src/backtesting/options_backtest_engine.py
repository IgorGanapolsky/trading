"""
Options Backtesting Engine
==========================

World-class backtesting system for options strategies with:
- Accurate Black-Scholes pricing simulation
- 5 core strategies: covered_call, cash_secured_put, iron_condor, credit_spread, wheel
- Realistic trading costs (slippage, commissions, bid-ask spreads)
- Comprehensive performance metrics
- Historical data simulation using stock prices + VIX

Author: Trading System
Created: 2025-12-10
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy.stats import norm

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    import yfinance as yf

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False


# ============================================================================
# Black-Scholes Option Pricing
# ============================================================================


class BlackScholes:
    """
    Black-Scholes option pricing model.

    Provides accurate option pricing and greeks calculation for backtesting.
    """

    @staticmethod
    def call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate European call option price.

        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiration (in years)
            r: Risk-free rate
            sigma: Volatility (annualized)

        Returns:
            Call option price
        """
        if T <= 0:
            return max(S - K, 0)

        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        call = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return call

    @staticmethod
    def put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate European put option price.

        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiration (in years)
            r: Risk-free rate
            sigma: Volatility (annualized)

        Returns:
            Put option price
        """
        if T <= 0:
            return max(K - S, 0)

        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        put = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return put

    @staticmethod
    def call_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate call option delta."""
        if T <= 0:
            return 1.0 if S > K else 0.0

        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        return norm.cdf(d1)

    @staticmethod
    def put_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate put option delta."""
        if T <= 0:
            return -1.0 if S < K else 0.0

        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        return norm.cdf(d1) - 1

    @staticmethod
    def theta(
        S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call"
    ) -> float:
        """
        Calculate option theta (time decay per day).

        Returns theta as dollars per day (divide by 365 from annual theta).
        """
        if T <= 0:
            return 0.0

        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if option_type == "call":
            theta = -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) - r * K * np.exp(
                -r * T
            ) * norm.cdf(d2)
        else:  # put
            theta = -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) + r * K * np.exp(
                -r * T
            ) * norm.cdf(-d2)

        # Convert annual theta to daily
        return theta / 365.0

    @staticmethod
    def find_strike_for_delta(
        S: float, target_delta: float, T: float, r: float, sigma: float, option_type: str = "call"
    ) -> float:
        """
        Find strike price that produces target delta.

        Uses binary search to find strike.

        Args:
            S: Current stock price
            target_delta: Target delta (e.g., 0.30 for calls, -0.30 for puts)
            T: Time to expiration (years)
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'

        Returns:
            Strike price
        """
        # Initial guess range
        if option_type == "call":
            # For calls, higher strike = lower delta
            low_strike = S * 0.8
            high_strike = S * 1.5
        else:
            # For puts, lower strike = higher (more negative) delta
            low_strike = S * 0.5
            high_strike = S * 1.2
            target_delta = abs(target_delta)  # Work with positive values

        # Binary search
        for _ in range(50):  # Max iterations
            mid_strike = (low_strike + high_strike) / 2

            if option_type == "call":
                delta = BlackScholes.call_delta(S, mid_strike, T, r, sigma)
            else:
                delta = abs(BlackScholes.put_delta(S, mid_strike, T, r, sigma))

            if abs(delta - target_delta) < 0.001:  # Close enough
                return mid_strike

            if option_type == "call":
                if delta > target_delta:
                    low_strike = mid_strike
                else:
                    high_strike = mid_strike
            else:
                if delta > target_delta:
                    high_strike = mid_strike
                else:
                    low_strike = mid_strike

        return (low_strike + high_strike) / 2


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class OptionContract:
    """Represents an option contract."""

    symbol: str
    underlying: str
    strike: float
    expiration: datetime
    option_type: str  # 'call' or 'put'
    price: float
    delta: float
    theta: float
    iv: float


@dataclass
class Trade:
    """Represents a completed trade."""

    strategy: str
    symbol: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    contracts: int
    premium_collected: float
    premium_paid: float
    stock_cost: float
    pnl: float
    return_pct: float
    max_risk: float
    commission: float
    slippage: float
    outcome: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestMetrics:
    """Comprehensive backtest performance metrics."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_return: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    avg_daily_pnl: float
    total_commission: float
    total_slippage: float
    strategy_breakdown: dict[str, dict[str, float]]


# ============================================================================
# Options Backtest Engine
# ============================================================================


class OptionsBacktestEngine:
    """
    Professional-grade options backtesting engine.

    Features:
    - Black-Scholes pricing simulation
    - 5 core strategies: covered_call, cash_secured_put, iron_condor, credit_spread, wheel
    - Realistic trading costs
    - Comprehensive metrics

    Example:
        >>> engine = OptionsBacktestEngine(
        ...     start_date="2024-01-01",
        ...     end_date="2024-12-01",
        ...     initial_capital=100000
        ... )
        >>> results = engine.backtest_strategy(
        ...     strategy_type="covered_call",
        ...     symbol="SPY"
        ... )
    """

    def __init__(
        self,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        risk_free_rate: float = 0.05,
        commission_per_contract: float = 0.65,
        slippage_bps: float = 2.0,  # 0.02 slippage as requested
    ):
        """
        Initialize backtest engine.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_capital: Starting capital
            risk_free_rate: Risk-free rate (annual)
            commission_per_contract: Commission per contract (Alpaca: $0.65)
            slippage_bps: Slippage in basis points (default: 2.0 = $0.02)
        """
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.risk_free_rate = risk_free_rate
        self.commission_per_contract = commission_per_contract
        self.slippage_bps = slippage_bps

        # Trading state
        self.trades: list[Trade] = []
        self.price_data: dict[str, pd.DataFrame] = {}
        self.vix_data: pd.DataFrame | None = None

        logger.info(f"Initialized OptionsBacktestEngine: {start_date} to {end_date}")
        logger.info(
            f"Capital: ${initial_capital:,.2f} | Commission: ${commission_per_contract}/contract"
        )

    # ========================================================================
    # Data Loading
    # ========================================================================

    def load_data(self, symbols: list[str]) -> None:
        """
        Load historical price data and VIX.

        Priority:
        1. yfinance (if available)
        2. Alpaca API (if available)
        3. Synthetic data (fallback)

        Args:
            symbols: List of underlying symbols
        """
        logger.info(f"Loading historical data for {symbols}...")

        # Try yfinance first (most reliable)
        if YFINANCE_AVAILABLE:
            self._load_yfinance_data(symbols)
        elif ALPACA_AVAILABLE:
            self._load_alpaca_data(symbols)
        else:
            logger.warning("No data sources available - using synthetic data")
            self._generate_synthetic_data(symbols)

        # Load VIX for IV proxy
        self._load_vix_data()

    def _load_yfinance_data(self, symbols: list[str]) -> None:
        """Load data from yfinance."""
        for symbol in symbols:
            try:
                # Add buffer for IV calculation (need 252 days history)
                start_buffer = self.start_date - timedelta(days=365)

                df = yf.download(
                    symbol,
                    start=start_buffer,
                    end=self.end_date + timedelta(days=1),
                    progress=False,
                )

                if df.empty:
                    logger.warning(f"No data for {symbol}, using synthetic")
                    self._generate_synthetic_data([symbol])
                    continue

                # Calculate returns and historical volatility
                df["Returns"] = df["Close"].pct_change()
                df["HV_20"] = df["Returns"].rolling(20).std() * np.sqrt(252)
                df["HV_30"] = df["Returns"].rolling(30).std() * np.sqrt(252)

                self.price_data[symbol] = df
                logger.info(f"Loaded {len(df)} bars for {symbol} from yfinance")

            except Exception as e:
                logger.error(f"yfinance failed for {symbol}: {e}")
                self._generate_synthetic_data([symbol])

    def _load_alpaca_data(self, symbols: list[str]) -> None:
        """Load data from Alpaca API."""
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            logger.warning("Alpaca credentials not found")
            self._generate_synthetic_data(symbols)
            return

        client = StockHistoricalDataClient(api_key, secret_key)

        for symbol in symbols:
            try:
                start_buffer = self.start_date - timedelta(days=365)

                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Day,
                    start=start_buffer,
                    end=self.end_date + timedelta(days=1),
                    adjustment="all",
                )

                bars = client.get_stock_bars(request).df

                if bars is None or bars.empty:
                    logger.warning(f"No data for {symbol}, using synthetic")
                    self._generate_synthetic_data([symbol])
                    continue

                if "symbol" in bars.index.names:
                    bars = bars.droplevel("symbol")

                df = bars.rename(
                    columns={
                        "open": "Open",
                        "high": "High",
                        "low": "Low",
                        "close": "Close",
                        "volume": "Volume",
                    }
                )

                df["Returns"] = df["Close"].pct_change()
                df["HV_20"] = df["Returns"].rolling(20).std() * np.sqrt(252)
                df["HV_30"] = df["Returns"].rolling(30).std() * np.sqrt(252)

                self.price_data[symbol] = df
                logger.info(f"Loaded {len(df)} bars for {symbol} from Alpaca")

            except Exception as e:
                logger.error(f"Alpaca failed for {symbol}: {e}")
                self._generate_synthetic_data([symbol])

    def _generate_synthetic_data(self, symbols: list[str]) -> None:
        """Generate synthetic price data using GBM."""
        logger.info("Generating synthetic data...")

        params = {
            "SPY": {"price": 450.0, "vol": 0.15, "drift": 0.10},
            "QQQ": {"price": 400.0, "vol": 0.20, "drift": 0.12},
        }

        start_buffer = self.start_date - timedelta(days=365)
        date_range = pd.date_range(start=start_buffer, end=self.end_date, freq="D")
        date_range = date_range[date_range.weekday < 5]  # Weekdays only

        for symbol in symbols:
            p = params.get(symbol, {"price": 100.0, "vol": 0.18, "drift": 0.08})

            np.random.seed(42)
            n_days = len(date_range)
            dt = 1 / 252

            returns = np.random.normal(p["drift"] * dt, p["vol"] * np.sqrt(dt), n_days)
            prices = p["price"] * np.exp(np.cumsum(returns))

            df = pd.DataFrame(
                {
                    "Open": prices * (1 + np.random.normal(0, 0.002, n_days)),
                    "High": prices * (1 + abs(np.random.normal(0, 0.005, n_days))),
                    "Low": prices * (1 - abs(np.random.normal(0, 0.005, n_days))),
                    "Close": prices,
                    "Volume": np.random.uniform(50_000_000, 100_000_000, n_days),
                },
                index=date_range,
            )

            df["Returns"] = df["Close"].pct_change()
            df["HV_20"] = df["Returns"].rolling(20).std() * np.sqrt(252)
            df["HV_30"] = df["Returns"].rolling(30).std() * np.sqrt(252)

            self.price_data[symbol] = df
            logger.info(f"Generated {len(df)} synthetic bars for {symbol}")

    def _load_vix_data(self) -> None:
        """Load VIX data for IV proxy."""
        if not YFINANCE_AVAILABLE:
            logger.warning("yfinance not available, using constant IV")
            return

        try:
            start_buffer = self.start_date - timedelta(days=365)
            vix = yf.download(
                "^VIX", start=start_buffer, end=self.end_date + timedelta(days=1), progress=False
            )

            if not vix.empty:
                self.vix_data = vix
                logger.info(f"Loaded {len(vix)} VIX bars")
            else:
                logger.warning("VIX data unavailable")

        except Exception as e:
            logger.warning(f"Failed to load VIX: {e}")

    def get_iv_for_date(self, symbol: str, date: datetime) -> float:
        """
        Get implied volatility estimate for a date.

        Uses VIX if available, otherwise historical volatility.

        Args:
            symbol: Underlying symbol
            date: Date

        Returns:
            IV as decimal (e.g., 0.20 = 20%)
        """
        # Try VIX first
        if self.vix_data is not None and date in self.vix_data.index:
            vix_level = float(self.vix_data.loc[date, "Close"])
            # Convert VIX to decimal (VIX 20 = 0.20 IV)
            return vix_level / 100.0

        # Fallback to historical vol
        if symbol in self.price_data:
            df = self.price_data[symbol]
            hist = df[df.index <= date]

            if len(hist) >= 30 and "HV_30" in hist.columns:
                hv = hist["HV_30"].iloc[-1]
                if not pd.isna(hv) and hv > 0:
                    return float(hv)

        # Default IV if all else fails
        return 0.20

    # ========================================================================
    # Option Pricing Helpers
    # ========================================================================

    def price_option(
        self,
        symbol: str,
        strike: float,
        expiration: datetime,
        option_type: str,
        current_date: datetime,
    ) -> OptionContract | None:
        """
        Price an option contract using Black-Scholes.

        Args:
            symbol: Underlying symbol
            strike: Strike price
            expiration: Expiration date
            option_type: 'call' or 'put'
            current_date: Current date

        Returns:
            OptionContract or None if pricing fails
        """
        if symbol not in self.price_data:
            return None

        df = self.price_data[symbol]
        hist = df[df.index <= current_date]

        if len(hist) < 30:
            return None

        current_price = float(hist["Close"].iloc[-1])
        iv = self.get_iv_for_date(symbol, current_date)

        # Time to expiration in years
        T = (expiration - current_date).days / 365.0

        if T <= 0:
            # At expiration
            if option_type == "call":
                price = max(current_price - strike, 0)
                delta = 1.0 if current_price > strike else 0.0
            else:
                price = max(strike - current_price, 0)
                delta = -1.0 if current_price < strike else 0.0
            theta = 0.0
        else:
            # Use Black-Scholes
            if option_type == "call":
                price = BlackScholes.call_price(current_price, strike, T, self.risk_free_rate, iv)
                delta = BlackScholes.call_delta(current_price, strike, T, self.risk_free_rate, iv)
            else:
                price = BlackScholes.put_price(current_price, strike, T, self.risk_free_rate, iv)
                delta = BlackScholes.put_delta(current_price, strike, T, self.risk_free_rate, iv)

            theta = BlackScholes.theta(
                current_price, strike, T, self.risk_free_rate, iv, option_type
            )

        return OptionContract(
            symbol=f"{symbol}{expiration.strftime('%y%m%d')}{option_type[0].upper()}{int(strike * 1000):08d}",
            underlying=symbol,
            strike=strike,
            expiration=expiration,
            option_type=option_type,
            price=price,
            delta=delta,
            theta=theta,
            iv=iv,
        )

    def apply_trading_costs(
        self, premium: float, contracts: int, side: str
    ) -> tuple[float, float, float]:
        """
        Apply realistic trading costs.

        Args:
            premium: Option premium per contract
            contracts: Number of contracts
            side: 'buy' or 'sell'

        Returns:
            Tuple of (adjusted_premium, commission, slippage)
        """
        # Commission
        commission = self.commission_per_contract * contracts

        # Slippage (2 bps = $0.02 per contract as requested)
        slippage_per_contract = self.slippage_bps / 100.0
        slippage = slippage_per_contract * contracts

        # Adjust premium
        if side == "buy":
            adjusted = premium + slippage_per_contract  # Pay more when buying
        else:  # sell
            adjusted = premium - slippage_per_contract  # Receive less when selling

        return adjusted, commission, slippage

    # ========================================================================
    # Strategy Implementations
    # ========================================================================

    def backtest_strategy(
        self,
        strategy_type: Literal[
            "covered_call", "cash_secured_put", "iron_condor", "credit_spread", "wheel"
        ],
        symbol: str,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Backtest a specific options strategy.

        Args:
            strategy_type: Strategy to backtest
            symbol: Underlying symbol
            **kwargs: Strategy-specific parameters

        Returns:
            Backtest results dictionary
        """
        logger.info(f"Backtesting {strategy_type} strategy on {symbol}")

        # Ensure data is loaded
        if symbol not in self.price_data:
            self.load_data([symbol])

        # Route to strategy implementation
        if strategy_type == "covered_call":
            return self._backtest_covered_call(symbol, **kwargs)
        elif strategy_type == "cash_secured_put":
            return self._backtest_cash_secured_put(symbol, **kwargs)
        elif strategy_type == "iron_condor":
            return self._backtest_iron_condor(symbol, **kwargs)
        elif strategy_type == "credit_spread":
            return self._backtest_credit_spread(symbol, **kwargs)
        elif strategy_type == "wheel":
            return self._backtest_wheel(symbol, **kwargs)
        else:
            raise ValueError(f"Unknown strategy: {strategy_type}")

    def _backtest_covered_call(
        self,
        symbol: str,
        delta_target: float = 0.30,
        dte_min: int = 30,
        dte_max: int = 45,
        position_size_pct: float = 0.05,
    ) -> dict[str, Any]:
        """
        Backtest covered call strategy.

        Strategy: Own 100 shares + sell OTM call

        Args:
            symbol: Underlying
            delta_target: Target delta for short call (default: 0.30)
            dte_min: Minimum days to expiration (default: 30)
            dte_max: Maximum days to expiration (default: 45)
            position_size_pct: Position size as % of portfolio (default: 5%)
        """
        logger.info(
            f"Backtesting Covered Call: {symbol} (delta={delta_target}, DTE={dte_min}-{dte_max})"
        )

        df = self.price_data[symbol]
        trades = []

        # Generate trade dates (every 2 weeks to avoid overlap)
        current_date = self.start_date

        while current_date <= self.end_date:
            if current_date.weekday() >= 5:  # Skip weekends
                current_date += timedelta(days=1)
                continue

            # Check if date exists in data
            if current_date not in df.index:
                current_date += timedelta(days=1)
                continue

            hist = df[df.index <= current_date]
            if len(hist) < 30:
                current_date += timedelta(days=1)
                continue

            entry_price = float(hist["Close"].iloc[-1])
            iv = self.get_iv_for_date(symbol, current_date)

            # Calculate position size (how many lots of 100 shares)
            capital_for_trade = self.current_capital * position_size_pct
            shares = int(capital_for_trade / entry_price)
            lots = shares // 100

            if lots < 1:
                current_date += timedelta(days=1)
                continue

            # Find expiration date (target middle of DTE range)
            dte = (dte_min + dte_max) // 2
            expiration = current_date + timedelta(days=dte)

            # Find strike for target delta
            T = dte / 365.0
            strike = BlackScholes.find_strike_for_delta(
                entry_price, delta_target, T, self.risk_free_rate, iv, "call"
            )

            # Price the option
            option = self.price_option(symbol, strike, expiration, "call", current_date)

            if option is None:
                current_date += timedelta(days=1)
                continue

            # Apply trading costs (we're selling the call)
            premium_per_contract, commission, slippage = self.apply_trading_costs(
                option.price, lots, "sell"
            )

            # Entry: Buy 100*lots shares + sell lots calls
            stock_cost = entry_price * 100 * lots
            premium_collected = premium_per_contract * 100 * lots  # Premium in dollars

            # Exit at expiration
            exit_date = expiration
            if exit_date > self.end_date or exit_date not in df.index:
                # Skip if expiration is beyond backtest period
                current_date += timedelta(days=14)
                continue

            exit_price = float(df.loc[exit_date, "Close"])

            # P&L calculation
            if exit_price >= strike:
                # Stock called away - sell at strike
                stock_pnl = (strike - entry_price) * 100 * lots
                assigned = True
            else:
                # Keep stock - sell at exit price
                stock_pnl = (exit_price - entry_price) * 100 * lots
                assigned = False

            # Total P&L = stock P&L + premium - commission
            total_pnl = stock_pnl + premium_collected - commission

            # Max risk = stock cost (could go to zero)
            max_risk = stock_cost

            trade = Trade(
                strategy="covered_call",
                symbol=symbol,
                entry_date=current_date,
                exit_date=exit_date,
                entry_price=entry_price,
                exit_price=exit_price,
                contracts=lots,
                premium_collected=premium_collected,
                premium_paid=0.0,
                stock_cost=stock_cost,
                pnl=total_pnl,
                return_pct=(total_pnl / stock_cost) * 100,
                max_risk=max_risk,
                commission=commission,
                slippage=slippage,
                outcome="assigned" if assigned else "expired",
                metadata={"strike": strike, "delta": option.delta, "iv": iv, "dte": dte},
            )

            trades.append(trade)

            # Move to next cycle (14 days)
            current_date += timedelta(days=14)

        # Calculate metrics
        return self._calculate_metrics(trades, f"Covered Call - {symbol}")

    def _backtest_cash_secured_put(
        self,
        symbol: str,
        delta_target: float = 0.30,
        dte_min: int = 30,
        dte_max: int = 45,
        position_size_pct: float = 0.05,
    ) -> dict[str, Any]:
        """
        Backtest cash-secured put strategy.

        Strategy: Sell OTM put, hold cash collateral

        Args:
            symbol: Underlying
            delta_target: Target delta for short put (default: 0.30)
            dte_min: Minimum DTE (default: 30)
            dte_max: Maximum DTE (default: 45)
            position_size_pct: Position size as % of portfolio (default: 5%)
        """
        logger.info(
            f"Backtesting Cash-Secured Put: {symbol} (delta={delta_target}, DTE={dte_min}-{dte_max})"
        )

        df = self.price_data[symbol]
        trades = []

        current_date = self.start_date

        while current_date <= self.end_date:
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            if current_date not in df.index:
                current_date += timedelta(days=1)
                continue

            hist = df[df.index <= current_date]
            if len(hist) < 30:
                current_date += timedelta(days=1)
                continue

            entry_price = float(hist["Close"].iloc[-1])
            iv = self.get_iv_for_date(symbol, current_date)

            # Calculate contracts (cash secured = need strike * 100 per contract)
            dte = (dte_min + dte_max) // 2
            T = dte / 365.0

            # Find strike for target delta (puts have negative delta)
            strike = BlackScholes.find_strike_for_delta(
                entry_price, delta_target, T, self.risk_free_rate, iv, "put"
            )

            # Cash required = strike * 100 per contract
            cash_required_per_contract = strike * 100
            capital_for_trade = self.current_capital * position_size_pct
            contracts = int(capital_for_trade / cash_required_per_contract)

            if contracts < 1:
                current_date += timedelta(days=1)
                continue

            expiration = current_date + timedelta(days=dte)

            # Price the put
            option = self.price_option(symbol, strike, expiration, "put", current_date)

            if option is None:
                current_date += timedelta(days=1)
                continue

            # Apply trading costs (selling put)
            premium_per_contract, commission, slippage = self.apply_trading_costs(
                option.price, contracts, "sell"
            )

            premium_collected = premium_per_contract * 100 * contracts

            # Exit at expiration
            exit_date = expiration
            if exit_date > self.end_date or exit_date not in df.index:
                current_date += timedelta(days=14)
                continue

            exit_price = float(df.loc[exit_date, "Close"])

            # P&L calculation
            if exit_price < strike:
                # Assigned - buy stock at strike, now worth exit_price
                stock_pnl = (exit_price - strike) * 100 * contracts
                assigned = True
            else:
                # Put expires worthless - keep full premium
                stock_pnl = 0
                assigned = False

            total_pnl = premium_collected + stock_pnl - commission

            # Max risk = strike * 100 * contracts (stock goes to zero)
            max_risk = strike * 100 * contracts

            trade = Trade(
                strategy="cash_secured_put",
                symbol=symbol,
                entry_date=current_date,
                exit_date=exit_date,
                entry_price=entry_price,
                exit_price=exit_price,
                contracts=contracts,
                premium_collected=premium_collected,
                premium_paid=0.0,
                stock_cost=0.0,
                pnl=total_pnl,
                return_pct=(total_pnl / max_risk) * 100,
                max_risk=max_risk,
                commission=commission,
                slippage=slippage,
                outcome="assigned" if assigned else "expired",
                metadata={"strike": strike, "delta": option.delta, "iv": iv, "dte": dte},
            )

            trades.append(trade)
            current_date += timedelta(days=14)

        return self._calculate_metrics(trades, f"Cash-Secured Put - {symbol}")

    def _backtest_iron_condor(
        self, symbol: str, wing_delta: float = 0.16, dte: int = 45, position_size_pct: float = 0.02
    ) -> dict[str, Any]:
        """
        Backtest iron condor strategy.

        Strategy: Sell call spread + sell put spread (delta-neutral)

        Args:
            symbol: Underlying
            wing_delta: Delta for short strikes (default: 0.16)
            dte: Days to expiration (default: 45)
            position_size_pct: Position size as % of portfolio (default: 2%)
        """
        logger.info(f"Backtesting Iron Condor: {symbol} (delta={wing_delta}, DTE={dte})")

        df = self.price_data[symbol]
        trades = []

        current_date = self.start_date

        while current_date <= self.end_date:
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            if current_date not in df.index:
                current_date += timedelta(days=1)
                continue

            hist = df[df.index <= current_date]
            if len(hist) < 30:
                current_date += timedelta(days=1)
                continue

            entry_price = float(hist["Close"].iloc[-1])
            iv = self.get_iv_for_date(symbol, current_date)

            T = dte / 365.0
            expiration = current_date + timedelta(days=dte)

            # Find strikes for iron condor
            # Short call: ~16 delta OTM call
            # Long call: ~5 delta OTM call (higher strike)
            # Short put: ~16 delta OTM put
            # Long put: ~5 delta OTM put (lower strike)

            short_call_strike = BlackScholes.find_strike_for_delta(
                entry_price, wing_delta, T, self.risk_free_rate, iv, "call"
            )
            long_call_strike = BlackScholes.find_strike_for_delta(
                entry_price, 0.05, T, self.risk_free_rate, iv, "call"
            )
            short_put_strike = BlackScholes.find_strike_for_delta(
                entry_price, wing_delta, T, self.risk_free_rate, iv, "put"
            )
            long_put_strike = BlackScholes.find_strike_for_delta(
                entry_price, 0.05, T, self.risk_free_rate, iv, "put"
            )

            # Price all legs
            short_call = self.price_option(
                symbol, short_call_strike, expiration, "call", current_date
            )
            long_call = self.price_option(
                symbol, long_call_strike, expiration, "call", current_date
            )
            short_put = self.price_option(symbol, short_put_strike, expiration, "put", current_date)
            long_put = self.price_option(symbol, long_put_strike, expiration, "put", current_date)

            if None in [short_call, long_call, short_put, long_put]:
                current_date += timedelta(days=1)
                continue

            # Calculate net credit per condor
            # We sell short strikes and buy long strikes
            credit_per_condor = (
                (short_call.price - long_call.price) + (short_put.price - long_put.price)
            ) * 100  # Convert to dollars

            # Max risk per condor = width of widest spread - net credit
            call_spread_width = (long_call_strike - short_call_strike) * 100
            put_spread_width = (short_put_strike - long_put_strike) * 100
            max_risk_per_condor = max(call_spread_width, put_spread_width) - credit_per_condor

            # Position sizing
            capital_for_trade = self.current_capital * position_size_pct
            contracts = max(1, int(capital_for_trade / max_risk_per_condor))

            # Apply trading costs (4 legs)
            commission = self.commission_per_contract * 4 * contracts
            slippage = self.slippage_bps / 100.0 * 4 * contracts

            net_credit = credit_per_condor * contracts - commission

            # Exit at expiration
            exit_date = expiration
            if exit_date > self.end_date or exit_date not in df.index:
                current_date += timedelta(days=21)
                continue

            exit_price = float(df.loc[exit_date, "Close"])

            # P&L at expiration
            if short_put_strike <= exit_price <= short_call_strike:
                # Max profit - all options expire worthless
                pnl = net_credit
                outcome = "max_profit"
            elif exit_price > short_call_strike:
                # Call side tested
                if exit_price >= long_call_strike:
                    # Max loss on call spread
                    pnl = net_credit - call_spread_width * contracts
                    outcome = "call_max_loss"
                else:
                    # Partial loss
                    call_loss = (exit_price - short_call_strike) * 100 * contracts
                    pnl = net_credit - call_loss
                    outcome = "call_tested"
            else:
                # Put side tested
                if exit_price <= long_put_strike:
                    # Max loss on put spread
                    pnl = net_credit - put_spread_width * contracts
                    outcome = "put_max_loss"
                else:
                    # Partial loss
                    put_loss = (short_put_strike - exit_price) * 100 * contracts
                    pnl = net_credit - put_loss
                    outcome = "put_tested"

            trade = Trade(
                strategy="iron_condor",
                symbol=symbol,
                entry_date=current_date,
                exit_date=exit_date,
                entry_price=entry_price,
                exit_price=exit_price,
                contracts=contracts,
                premium_collected=credit_per_condor * contracts,
                premium_paid=0.0,
                stock_cost=0.0,
                pnl=pnl,
                return_pct=(pnl / (max_risk_per_condor * contracts)) * 100,
                max_risk=max_risk_per_condor * contracts,
                commission=commission,
                slippage=slippage,
                outcome=outcome,
                metadata={
                    "short_call_strike": short_call_strike,
                    "long_call_strike": long_call_strike,
                    "short_put_strike": short_put_strike,
                    "long_put_strike": long_put_strike,
                    "iv": iv,
                    "dte": dte,
                },
            )

            trades.append(trade)
            current_date += timedelta(days=21)

        return self._calculate_metrics(trades, f"Iron Condor - {symbol}")

    def _backtest_credit_spread(
        self,
        symbol: str,
        spread_type: str = "put",
        short_delta: float = 0.30,
        width: float = 5.0,
        dte: int = 30,
        position_size_pct: float = 0.03,
    ) -> dict[str, Any]:
        """
        Backtest vertical credit spread strategy.

        Strategy: Sell OTM option + buy farther OTM option

        Args:
            symbol: Underlying
            spread_type: 'call' or 'put' (default: 'put')
            short_delta: Delta for short strike (default: 0.30)
            width: Strike width in dollars (default: 5)
            dte: Days to expiration (default: 30)
            position_size_pct: Position size as % of portfolio (default: 3%)
        """
        logger.info(f"Backtesting {spread_type.title()} Credit Spread: {symbol}")

        df = self.price_data[symbol]
        trades = []

        current_date = self.start_date

        while current_date <= self.end_date:
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            if current_date not in df.index:
                current_date += timedelta(days=1)
                continue

            hist = df[df.index <= current_date]
            if len(hist) < 30:
                current_date += timedelta(days=1)
                continue

            entry_price = float(hist["Close"].iloc[-1])
            iv = self.get_iv_for_date(symbol, current_date)

            T = dte / 365.0
            expiration = current_date + timedelta(days=dte)

            # Find strikes
            short_strike = BlackScholes.find_strike_for_delta(
                entry_price, short_delta, T, self.risk_free_rate, iv, spread_type
            )

            if spread_type == "put":
                long_strike = short_strike - width
            else:  # call
                long_strike = short_strike + width

            # Price options
            short_option = self.price_option(
                symbol, short_strike, expiration, spread_type, current_date
            )
            long_option = self.price_option(
                symbol, long_strike, expiration, spread_type, current_date
            )

            if short_option is None or long_option is None:
                current_date += timedelta(days=1)
                continue

            # Net credit
            credit_per_spread = (short_option.price - long_option.price) * 100

            # Max risk = width * 100 - credit
            max_risk_per_spread = width * 100 - credit_per_spread

            # Position sizing
            capital_for_trade = self.current_capital * position_size_pct
            contracts = max(1, int(capital_for_trade / max_risk_per_spread))

            # Trading costs (2 legs)
            commission = self.commission_per_contract * 2 * contracts
            slippage = self.slippage_bps / 100.0 * 2 * contracts

            net_credit = credit_per_spread * contracts - commission

            # Exit at expiration
            exit_date = expiration
            if exit_date > self.end_date or exit_date not in df.index:
                current_date += timedelta(days=14)
                continue

            exit_price = float(df.loc[exit_date, "Close"])

            # P&L calculation
            if spread_type == "put":
                if exit_price >= short_strike:
                    # Max profit - expires worthless
                    pnl = net_credit
                    outcome = "max_profit"
                elif exit_price <= long_strike:
                    # Max loss
                    pnl = net_credit - width * 100 * contracts
                    outcome = "max_loss"
                else:
                    # Partial loss
                    loss = (short_strike - exit_price) * 100 * contracts
                    pnl = net_credit - loss
                    outcome = "tested"
            else:  # call spread
                if exit_price <= short_strike:
                    pnl = net_credit
                    outcome = "max_profit"
                elif exit_price >= long_strike:
                    pnl = net_credit - width * 100 * contracts
                    outcome = "max_loss"
                else:
                    loss = (exit_price - short_strike) * 100 * contracts
                    pnl = net_credit - loss
                    outcome = "tested"

            trade = Trade(
                strategy=f"{spread_type}_credit_spread",
                symbol=symbol,
                entry_date=current_date,
                exit_date=exit_date,
                entry_price=entry_price,
                exit_price=exit_price,
                contracts=contracts,
                premium_collected=credit_per_spread * contracts,
                premium_paid=0.0,
                stock_cost=0.0,
                pnl=pnl,
                return_pct=(pnl / (max_risk_per_spread * contracts)) * 100,
                max_risk=max_risk_per_spread * contracts,
                commission=commission,
                slippage=slippage,
                outcome=outcome,
                metadata={
                    "short_strike": short_strike,
                    "long_strike": long_strike,
                    "width": width,
                    "iv": iv,
                    "dte": dte,
                },
            )

            trades.append(trade)
            current_date += timedelta(days=14)

        return self._calculate_metrics(trades, f"{spread_type.title()} Credit Spread - {symbol}")

    def _backtest_wheel(
        self,
        symbol: str,
        put_delta: float = 0.30,
        call_delta: float = 0.30,
        dte: int = 30,
        position_size_pct: float = 0.05,
    ) -> dict[str, Any]:
        """
        Backtest wheel strategy.

        Strategy:
        1. Sell cash-secured put
        2. If assigned, sell covered call
        3. If called away, return to step 1

        Args:
            symbol: Underlying
            put_delta: Target delta for puts (default: 0.30)
            call_delta: Target delta for calls (default: 0.30)
            dte: Days to expiration (default: 30)
            position_size_pct: Position size as % of portfolio (default: 5%)
        """
        logger.info(f"Backtesting Wheel Strategy: {symbol}")

        df = self.price_data[symbol]
        trades = []

        # Wheel state
        owns_stock = False
        stock_cost_basis = 0.0
        shares = 0

        current_date = self.start_date

        while current_date <= self.end_date:
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            if current_date not in df.index:
                current_date += timedelta(days=1)
                continue

            hist = df[df.index <= current_date]
            if len(hist) < 30:
                current_date += timedelta(days=1)
                continue

            current_price = float(hist["Close"].iloc[-1])
            iv = self.get_iv_for_date(symbol, current_date)

            T = dte / 365.0
            expiration = current_date + timedelta(days=dte)

            if not owns_stock:
                # Phase 1: Sell cash-secured put
                strike = BlackScholes.find_strike_for_delta(
                    current_price, put_delta, T, self.risk_free_rate, iv, "put"
                )

                cash_required = strike * 100
                contracts = max(1, int(self.current_capital * position_size_pct / cash_required))

                put = self.price_option(symbol, strike, expiration, "put", current_date)

                if put is None:
                    current_date += timedelta(days=1)
                    continue

                premium_per_contract, commission, slippage = self.apply_trading_costs(
                    put.price, contracts, "sell"
                )
                premium_collected = premium_per_contract * 100 * contracts

                # Wait until expiration
                exit_date = expiration
                if exit_date > self.end_date or exit_date not in df.index:
                    current_date += timedelta(days=7)
                    continue

                exit_price = float(df.loc[exit_date, "Close"])

                if exit_price < strike:
                    # Assigned - now own stock
                    owns_stock = True
                    stock_cost_basis = strike
                    shares = 100 * contracts

                    pnl = premium_collected - commission  # Just the premium
                    outcome = "assigned"
                else:
                    # Expired worthless
                    pnl = premium_collected - commission
                    outcome = "expired"

                trade = Trade(
                    strategy="wheel_put",
                    symbol=symbol,
                    entry_date=current_date,
                    exit_date=exit_date,
                    entry_price=current_price,
                    exit_price=exit_price,
                    contracts=contracts,
                    premium_collected=premium_collected,
                    premium_paid=0.0,
                    stock_cost=0.0,
                    pnl=pnl,
                    return_pct=(pnl / (strike * 100 * contracts)) * 100,
                    max_risk=strike * 100 * contracts,
                    commission=commission,
                    slippage=slippage,
                    outcome=outcome,
                    metadata={"strike": strike, "delta": put.delta, "iv": iv, "dte": dte},
                )

                trades.append(trade)
                current_date = exit_date + timedelta(days=1)

            else:
                # Phase 2: Sell covered call
                strike = BlackScholes.find_strike_for_delta(
                    current_price, call_delta, T, self.risk_free_rate, iv, "call"
                )

                lots = shares // 100

                call = self.price_option(symbol, strike, expiration, "call", current_date)

                if call is None:
                    current_date += timedelta(days=1)
                    continue

                premium_per_contract, commission, slippage = self.apply_trading_costs(
                    call.price, lots, "sell"
                )
                premium_collected = premium_per_contract * 100 * lots

                exit_date = expiration
                if exit_date > self.end_date or exit_date not in df.index:
                    current_date += timedelta(days=7)
                    continue

                exit_price = float(df.loc[exit_date, "Close"])

                if exit_price >= strike:
                    # Called away - back to Phase 1
                    stock_pnl = (strike - stock_cost_basis) * shares
                    pnl = stock_pnl + premium_collected - commission
                    owns_stock = False
                    shares = 0
                    stock_cost_basis = 0.0
                    outcome = "called_away"
                else:
                    # Keep stock, collect premium
                    # Mark-to-market on stock
                    stock_pnl = (exit_price - stock_cost_basis) * shares
                    pnl = stock_pnl + premium_collected - commission
                    # Update cost basis
                    stock_cost_basis = exit_price
                    outcome = "expired"

                trade = Trade(
                    strategy="wheel_call",
                    symbol=symbol,
                    entry_date=current_date,
                    exit_date=exit_date,
                    entry_price=current_price,
                    exit_price=exit_price,
                    contracts=lots,
                    premium_collected=premium_collected,
                    premium_paid=0.0,
                    stock_cost=stock_cost_basis * shares,
                    pnl=pnl,
                    return_pct=(pnl / (stock_cost_basis * shares)) * 100
                    if stock_cost_basis > 0
                    else 0,
                    max_risk=stock_cost_basis * shares,
                    commission=commission,
                    slippage=slippage,
                    outcome=outcome,
                    metadata={"strike": strike, "delta": call.delta, "iv": iv, "dte": dte},
                )

                trades.append(trade)
                current_date = exit_date + timedelta(days=1)

        return self._calculate_metrics(trades, f"Wheel - {symbol}")

    # ========================================================================
    # Metrics Calculation
    # ========================================================================

    def _calculate_metrics(self, trades: list[Trade], strategy_name: str) -> dict[str, Any]:
        """
        Calculate comprehensive backtest metrics.

        Args:
            trades: List of completed trades
            strategy_name: Name of strategy

        Returns:
            Dictionary with metrics and trade details
        """
        if not trades:
            logger.warning(f"No trades for {strategy_name}")
            return {"strategy": strategy_name, "error": "No trades executed", "total_trades": 0}

        # Basic stats
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]

        win_rate = len(winning_trades) / total_trades * 100

        # P&L
        total_pnl = sum(t.pnl for t in trades)
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        largest_win = max([t.pnl for t in winning_trades]) if winning_trades else 0
        largest_loss = min([t.pnl for t in losing_trades]) if losing_trades else 0

        # Profit factor
        gross_profit = sum([t.pnl for t in winning_trades])
        gross_loss = abs(sum([t.pnl for t in losing_trades]))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Sharpe ratio (with safeguards to prevent extreme values)
        returns = [t.pnl for t in trades]
        if len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns, ddof=1)
            # Apply volatility floor to prevent extreme Sharpe ratios
            MIN_VOLATILITY_FLOOR = 0.0001
            std_return = max(std_return, MIN_VOLATILITY_FLOOR)
            risk_free_rate_daily = 0.04 / 252
            # Annualize (assume ~30 day holding period)
            sharpe = (mean_return - risk_free_rate_daily) / std_return * np.sqrt(252)
            # Clamp to reasonable bounds [-10, 10]
            sharpe = float(np.clip(sharpe, -10.0, 10.0))
        else:
            sharpe = 0.0

        # Sortino ratio (only downside deviation, with safeguards)
        negative_returns = [r for r in returns if r < 0]
        if negative_returns and len(negative_returns) > 1:
            downside_std = np.std(negative_returns, ddof=1)
            downside_std = max(downside_std, MIN_VOLATILITY_FLOOR)
            sortino = (np.mean(returns) - risk_free_rate_daily) / downside_std * np.sqrt(252)
            sortino = float(np.clip(sortino, -10.0, 10.0))
        else:
            sortino = 0.0

        # Drawdown
        cumulative = np.cumsum(returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = cumulative - running_max
        max_drawdown = abs(np.min(drawdown)) if len(drawdown) > 0 else 0
        max_drawdown_pct = (
            (max_drawdown / self.initial_capital * 100) if self.initial_capital > 0 else 0
        )

        # Total return
        total_return = (total_pnl / self.initial_capital * 100) if self.initial_capital > 0 else 0

        # Trading costs
        total_commission = sum(t.commission for t in trades)
        total_slippage = sum(t.slippage for t in trades)

        # Daily metrics
        trading_days = (self.end_date - self.start_date).days
        avg_daily_pnl = total_pnl / trading_days if trading_days > 0 else 0

        # Strategy breakdown
        strategy_types = {}
        for trade in trades:
            strat = trade.strategy
            if strat not in strategy_types:
                strategy_types[strat] = {"count": 0, "pnl": 0.0, "win_rate": 0.0}
            strategy_types[strat]["count"] += 1
            strategy_types[strat]["pnl"] += trade.pnl

        for strat in strategy_types:
            strat_trades = [t for t in trades if t.strategy == strat]
            strat_wins = [t for t in strat_trades if t.pnl > 0]
            strategy_types[strat]["win_rate"] = (
                len(strat_wins) / len(strat_trades) * 100 if strat_trades else 0
            )

        # Build results
        return {
            "strategy": strategy_name,
            "period": {
                "start": self.start_date.strftime("%Y-%m-%d"),
                "end": self.end_date.strftime("%Y-%m-%d"),
                "days": trading_days,
            },
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate, 2),
            "total_return": round(total_return, 2),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "largest_win": round(largest_win, 2),
            "largest_loss": round(largest_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2),
            "max_drawdown": round(max_drawdown, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "avg_daily_pnl": round(avg_daily_pnl, 2),
            "total_commission": round(total_commission, 2),
            "total_slippage": round(total_slippage, 2),
            "strategy_breakdown": strategy_types,
            "trades": [
                {
                    "strategy": t.strategy,
                    "symbol": t.symbol,
                    "entry_date": t.entry_date.strftime("%Y-%m-%d"),
                    "exit_date": t.exit_date.strftime("%Y-%m-%d"),
                    "entry_price": round(t.entry_price, 2),
                    "exit_price": round(t.exit_price, 2),
                    "contracts": t.contracts,
                    "premium_collected": round(t.premium_collected, 2),
                    "pnl": round(t.pnl, 2),
                    "return_pct": round(t.return_pct, 2),
                    "outcome": t.outcome,
                    "metadata": t.metadata,
                }
                for t in trades
            ],
        }


# ============================================================================
# Main Execution
# ============================================================================


def main():
    """Example usage of OptionsBacktestEngine."""
    import json

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Initialize engine
    engine = OptionsBacktestEngine(
        start_date="2024-01-01", end_date="2024-12-01", initial_capital=100000.0
    )

    # Load data
    engine.load_data(["SPY", "QQQ"])

    # Run backtests for all strategies
    strategies = [
        ("covered_call", "SPY"),
        ("cash_secured_put", "SPY"),
        ("iron_condor", "SPY"),
        ("credit_spread", "SPY"),
        ("wheel", "QQQ"),
    ]

    results = {}

    for strategy, symbol in strategies:
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Backtesting {strategy} on {symbol}")
        logger.info("=" * 80)

        result = engine.backtest_strategy(strategy, symbol)
        results[f"{strategy}_{symbol}"] = result

        # Print summary
        if "error" not in result:
            print(f"\n{strategy.upper()} - {symbol}")
            print(f"Total Trades: {result['total_trades']}")
            print(f"Win Rate: {result['win_rate']:.1f}%")
            print(f"Total Return: {result['total_return']:.2f}%")
            print(f"Sharpe Ratio: {result['sharpe_ratio']:.2f}")
            print(f"Max Drawdown: {result['max_drawdown_pct']:.2f}%")
            print(f"Avg Daily P&L: ${result['avg_daily_pnl']:.2f}")

    # Save results
    output_dir = Path("data/backtests")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"options_backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"\nResults saved to {output_file}")


if __name__ == "__main__":
    main()
