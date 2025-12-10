"""
Tests for Options Backtesting Engine

Comprehensive test suite covering:
- Black-Scholes pricing and Greeks
- Options position tracking
- Strategy simulation
- Metrics calculation
- Report generation
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from src.backtesting.options_backtest import (
    BacktestMetrics,
    BlackScholesPricer,
    OptionsBacktestEngine,
    OptionsLeg,
    OptionsPosition,
    OptionType,
    StrategyType,
)

logging.basicConfig(level=logging.INFO)


class TestBlackScholesPricer:
    """Test Black-Scholes pricing model."""

    def test_atm_call_price(self):
        """Test at-the-money call option pricing."""
        pricer = BlackScholesPricer()

        result = pricer.calculate(
            spot=100.0,
            strike=100.0,
            time_to_expiry=0.25,  # 3 months
            risk_free_rate=0.05,
            volatility=0.20,
            option_type=OptionType.CALL,
        )

        # ATM call should have positive price
        assert result["price"] > 0
        # Delta should be around 0.5 for ATM call
        assert 0.45 < result["delta"] < 0.55
        # Gamma should be positive
        assert result["gamma"] > 0
        # Theta should be negative (time decay)
        assert result["theta"] < 0
        # Vega should be positive
        assert result["vega"] > 0

    def test_otm_call_lower_price(self):
        """Test that OTM calls are cheaper than ATM calls."""
        pricer = BlackScholesPricer()

        atm_result = pricer.calculate(
            spot=100.0,
            strike=100.0,
            time_to_expiry=0.25,
            risk_free_rate=0.05,
            volatility=0.20,
            option_type=OptionType.CALL,
        )

        otm_result = pricer.calculate(
            spot=100.0,
            strike=105.0,  # 5% OTM
            time_to_expiry=0.25,
            risk_free_rate=0.05,
            volatility=0.20,
            option_type=OptionType.CALL,
        )

        # OTM call should be cheaper than ATM
        assert otm_result["price"] < atm_result["price"]
        # OTM call should have lower delta
        assert otm_result["delta"] < atm_result["delta"]

    def test_put_call_parity(self):
        """Test put-call parity relationship."""
        pricer = BlackScholesPricer()

        call = pricer.calculate(
            spot=100.0,
            strike=100.0,
            time_to_expiry=1.0,
            risk_free_rate=0.05,
            volatility=0.20,
            option_type=OptionType.CALL,
        )

        put = pricer.calculate(
            spot=100.0,
            strike=100.0,
            time_to_expiry=1.0,
            risk_free_rate=0.05,
            volatility=0.20,
            option_type=OptionType.PUT,
        )

        # Put-call parity: C - P = S - K*e^(-rT)
        # For ATM: S = K, so C - P ≈ K(1 - e^(-rT))
        parity_value = 100 * (1 - np.exp(-0.05 * 1.0))
        actual_diff = call["price"] - put["price"]

        # Allow 1% tolerance
        assert abs(actual_diff - parity_value) < 1.0

    def test_expiration_intrinsic_value(self):
        """Test option value at expiration equals intrinsic value."""
        pricer = BlackScholesPricer()

        # ITM call at expiration
        call = pricer.calculate(
            spot=105.0,
            strike=100.0,
            time_to_expiry=0.0,
            risk_free_rate=0.05,
            volatility=0.20,
            option_type=OptionType.CALL,
        )

        # Should equal intrinsic value
        assert abs(call["price"] - 5.0) < 0.01

        # OTM put at expiration
        put = pricer.calculate(
            spot=105.0,
            strike=100.0,
            time_to_expiry=0.0,
            risk_free_rate=0.05,
            volatility=0.20,
            option_type=OptionType.PUT,
        )

        # Should be worthless
        assert put["price"] < 0.01

    def test_iv_estimation(self):
        """Test IV estimation from HV."""
        pricer = BlackScholesPricer()

        hv = 0.20
        iv = pricer.implied_volatility_from_hv(hv, iv_multiplier=1.2)

        # IV should be 20% higher than HV
        assert abs(iv - 0.24) < 0.001


class TestOptionsLeg:
    """Test individual options leg."""

    def test_leg_creation(self):
        """Test creating an options leg."""
        leg = OptionsLeg(
            option_type=OptionType.CALL,
            strike=100.0,
            expiration=datetime(2024, 12, 31),
            quantity=-1,  # Short call
            entry_premium=2.50,
            delta=0.30,
        )

        assert leg.option_type == OptionType.CALL
        assert leg.strike == 100.0
        assert leg.quantity == -1
        assert leg.is_short
        assert not leg.is_long

    def test_long_leg(self):
        """Test long leg identification."""
        leg = OptionsLeg(
            option_type=OptionType.PUT,
            strike=95.0,
            expiration=datetime(2024, 12, 31),
            quantity=1,  # Long put
            entry_premium=1.50,
        )

        assert leg.is_long
        assert not leg.is_short


class TestOptionsPosition:
    """Test complete options position."""

    def test_covered_call_entry_cost(self):
        """Test covered call entry cost calculation."""
        # Short call - we receive premium
        leg = OptionsLeg(
            option_type=OptionType.CALL,
            strike=105.0,
            expiration=datetime(2024, 12, 31),
            quantity=-1,
            entry_premium=2.50,
            delta=0.30,
            theta=-0.05,
        )

        position = OptionsPosition(
            symbol="SPY",
            strategy=StrategyType.COVERED_CALL,
            legs=[leg],
            entry_date=datetime(2024, 11, 1),
            entry_price=100.0,
        )

        position.calculate_entry_cost(commission_per_contract=0.65)

        # Entry cost should be negative (we received credit)
        # Premium received: -2.50 * 100 = -250
        # Commission: 0.65
        # Total: -250 + 0.65 = -249.35
        assert position.entry_cost < 0
        assert abs(position.entry_cost - (-249.35)) < 0.01

    def test_credit_spread_entry_cost(self):
        """Test credit spread entry cost calculation."""
        # Short OTM put (receive premium)
        short_put = OptionsLeg(
            option_type=OptionType.PUT,
            strike=95.0,
            expiration=datetime(2024, 12, 31),
            quantity=-1,
            entry_premium=2.00,
        )

        # Long OTM put (pay premium)
        long_put = OptionsLeg(
            option_type=OptionType.PUT,
            strike=90.0,
            expiration=datetime(2024, 12, 31),
            quantity=1,
            entry_premium=0.80,
        )

        position = OptionsPosition(
            symbol="SPY",
            strategy=StrategyType.CREDIT_SPREAD,
            legs=[short_put, long_put],
            entry_date=datetime(2024, 11, 1),
            entry_price=100.0,
        )

        position.calculate_entry_cost(commission_per_contract=0.65)

        # Net credit: (2.00 - 0.80) * 100 = 120
        # Commission: 2 * 0.65 = 1.30
        # Entry cost: -120 + 1.30 = -118.70
        assert position.entry_cost < 0
        assert abs(position.entry_cost - (-118.70)) < 0.01

    def test_position_pnl_profitable(self):
        """Test P/L calculation for profitable trade."""
        leg = OptionsLeg(
            option_type=OptionType.CALL,
            strike=105.0,
            expiration=datetime(2024, 12, 31),
            quantity=-1,
            entry_premium=2.50,
        )

        position = OptionsPosition(
            symbol="SPY",
            strategy=StrategyType.COVERED_CALL,
            legs=[leg],
            entry_date=datetime(2024, 11, 1),
            entry_price=100.0,
        )

        position.calculate_entry_cost(commission_per_contract=0.65)

        # Exit premium: option expires worthless (0)
        exit_premiums = [0.0]
        pnl = position.calculate_pnl(exit_premiums, commission_per_contract=0.65)

        # Entry: received 250 - 0.65 commission = 249.35 credit
        # Exit: pay 0 - 0.65 commission = -0.65
        # P/L: -0.65 - (-249.35) = 248.70
        assert pnl > 240
        assert position.is_closed

    def test_position_pnl_loss(self):
        """Test P/L calculation for losing trade."""
        leg = OptionsLeg(
            option_type=OptionType.CALL,
            strike=105.0,
            expiration=datetime(2024, 12, 31),
            quantity=-1,
            entry_premium=2.50,
        )

        position = OptionsPosition(
            symbol="SPY",
            strategy=StrategyType.COVERED_CALL,
            legs=[leg],
            entry_date=datetime(2024, 11, 1),
            entry_price=100.0,
        )

        position.calculate_entry_cost(commission_per_contract=0.65)

        # Exit premium: option is now worth 5.00 (we have to buy it back)
        exit_premiums = [5.00]
        pnl = position.calculate_pnl(exit_premiums, commission_per_contract=0.65)

        # Entry: received 250 - 0.65 = 249.35 credit
        # Exit: pay 500 + 0.65 = -500.65
        # P/L: -500.65 - (-249.35) = -251.30
        assert pnl < 0
        assert abs(pnl - (-251.30)) < 0.01

    def test_days_in_trade(self):
        """Test days in trade calculation."""
        position = OptionsPosition(
            symbol="SPY",
            strategy=StrategyType.IRON_CONDOR,
            legs=[],
            entry_date=datetime(2024, 11, 1),
            entry_price=100.0,
            exit_date=datetime(2024, 11, 30),
        )

        assert position.days_in_trade() == 29


class TestOptionsBacktestEngine:
    """Test options backtest engine."""

    @pytest.fixture
    def engine(self):
        """Create backtest engine for testing."""
        return OptionsBacktestEngine(
            start_date="2024-01-01",
            end_date="2024-03-31",
            initial_capital=100000.0,
        )

    @pytest.fixture
    def sample_data(self):
        """Create sample historical data."""
        dates = pd.date_range(start="2023-01-01", end="2024-12-31", freq="D")
        dates = dates[dates.weekday < 5]  # Weekdays only

        # Generate realistic price data
        np.random.seed(42)
        prices = 100 * np.exp(np.cumsum(np.random.normal(0.0005, 0.01, len(dates))))

        df = pd.DataFrame(
            {
                "Open": prices * (1 + np.random.uniform(-0.002, 0.002, len(dates))),
                "High": prices * (1 + np.random.uniform(0, 0.01, len(dates))),
                "Low": prices * (1 - np.random.uniform(0, 0.01, len(dates))),
                "Close": prices,
                "Volume": np.random.uniform(50e6, 150e6, len(dates)),
            },
            index=dates,
        )

        df["Returns"] = df["Close"].pct_change()
        df["HV_20"] = df["Returns"].rolling(20).std() * np.sqrt(252)
        df["HV_30"] = df["Returns"].rolling(30).std() * np.sqrt(252)
        df["IV_Est"] = df["HV_30"] * 1.2

        return df

    def test_engine_initialization(self, engine):
        """Test engine initialization."""
        assert engine.initial_capital == 100000.0
        assert engine.current_capital == 100000.0
        assert len(engine.positions) == 0
        assert len(engine.closed_positions) == 0

    def test_data_loading(self, engine, sample_data, monkeypatch):
        """Test historical data loading."""

        # Mock yfinance
        class MockTicker:
            def history(self, start, end, auto_adjust=False):
                return sample_data

        def mock_ticker(symbol):
            return MockTicker()

        import yfinance

        monkeypatch.setattr(yfinance, "Ticker", mock_ticker)

        # Load data
        hist = engine.load_historical_options_data("SPY")

        assert not hist.empty
        assert "HV_20" in hist.columns
        assert "IV_Est" in hist.columns

    def test_covered_call_simulation(self, engine, sample_data):
        """Test covered call trade simulation."""
        # Add sample data to engine
        engine.price_data["SPY"] = sample_data

        # Create covered call position
        entry_date = datetime(2024, 1, 15)
        entry_price = float(
            sample_data.loc[sample_data.index.date <= entry_date.date(), "Close"].iloc[-1]
        )

        leg = OptionsLeg(
            option_type=OptionType.CALL,
            strike=entry_price * 1.05,  # 5% OTM
            expiration=datetime(2024, 2, 15),  # 30 days
            quantity=-1,
            entry_premium=2.50,
            delta=0.30,
            theta=-0.05,
        )

        position = OptionsPosition(
            symbol="SPY",
            strategy=StrategyType.COVERED_CALL,
            legs=[leg],
            entry_date=entry_date,
            entry_price=entry_price,
        )

        position.calculate_entry_cost()

        # Simulate trade
        result = engine.simulate_trade(position)

        assert result.is_closed
        assert result.exit_date is not None
        assert result.pnl != 0.0

    def test_iron_condor_simulation(self, engine, sample_data):
        """Test iron condor trade simulation."""
        engine.price_data["SPY"] = sample_data

        entry_date = datetime(2024, 1, 15)
        entry_price = float(
            sample_data.loc[sample_data.index.date <= entry_date.date(), "Close"].iloc[-1]
        )

        # Iron condor: sell OTM put spread + sell OTM call spread
        legs = [
            # Put spread
            OptionsLeg(
                option_type=OptionType.PUT,
                strike=entry_price * 0.95,  # Short put
                expiration=datetime(2024, 2, 15),
                quantity=-1,
                entry_premium=2.00,
                delta=-0.16,
            ),
            OptionsLeg(
                option_type=OptionType.PUT,
                strike=entry_price * 0.90,  # Long put
                expiration=datetime(2024, 2, 15),
                quantity=1,
                entry_premium=0.80,
                delta=-0.05,
            ),
            # Call spread
            OptionsLeg(
                option_type=OptionType.CALL,
                strike=entry_price * 1.05,  # Short call
                expiration=datetime(2024, 2, 15),
                quantity=-1,
                entry_premium=2.00,
                delta=0.16,
            ),
            OptionsLeg(
                option_type=OptionType.CALL,
                strike=entry_price * 1.10,  # Long call
                expiration=datetime(2024, 2, 15),
                quantity=1,
                entry_premium=0.80,
                delta=0.05,
            ),
        ]

        position = OptionsPosition(
            symbol="SPY",
            strategy=StrategyType.IRON_CONDOR,
            legs=legs,
            entry_date=entry_date,
            entry_price=entry_price,
        )

        position.calculate_entry_cost()

        # Simulate trade
        result = engine.simulate_trade(position)

        assert result.is_closed
        assert len(result.legs) == 4
        # Iron condor should receive net credit
        assert result.entry_cost < 0

    def test_backtest_with_strategy(self, engine, sample_data, monkeypatch):
        """Test full backtest with simple strategy."""

        # Mock yfinance
        class MockTicker:
            def history(self, start, end, auto_adjust=False):
                return sample_data

        def mock_ticker(symbol):
            return MockTicker()

        import yfinance

        monkeypatch.setattr(yfinance, "Ticker", mock_ticker)

        # Define simple covered call strategy
        def covered_call_strategy(symbol, date, hist):
            # Trade every 30 days
            if date.day not in [1, 15]:
                return None

            current_price = float(hist["Close"].iloc[-1])
            iv = float(hist["IV_Est"].iloc[-1])

            if pd.isna(iv) or iv <= 0:
                return None

            # Create covered call 5% OTM
            strike = current_price * 1.05
            expiration = date + timedelta(days=30)

            leg = OptionsLeg(
                option_type=OptionType.CALL,
                strike=strike,
                expiration=expiration,
                quantity=-1,
                entry_premium=current_price * 0.025,  # ~2.5% premium
                delta=0.30,
                theta=-0.05,
            )

            return OptionsPosition(
                symbol=symbol,
                strategy=StrategyType.COVERED_CALL,
                legs=[leg],
                entry_date=date,
                entry_price=current_price,
            )

        # Run backtest
        metrics = engine.run_backtest(
            strategy=covered_call_strategy,
            symbols=["SPY"],
            trade_frequency_days=14,
        )

        # Verify metrics
        assert metrics.total_trades > 0
        assert metrics.total_return != 0.0
        assert metrics.sharpe_ratio != 0.0
        assert 0 <= metrics.win_rate <= 100

    def test_metrics_calculation_empty(self, engine):
        """Test metrics calculation with no trades."""
        metrics = engine.calculate_metrics()

        assert metrics.total_trades == 0
        assert metrics.total_return == 0.0
        assert metrics.sharpe_ratio == 0.0

    def test_report_generation(self, engine, tmp_path):
        """Test report generation."""
        # Create dummy metrics
        metrics = BacktestMetrics(
            start_date="2024-01-01",
            end_date="2024-03-31",
            trading_days=60,
            total_return=15.5,
            cagr=12.3,
            avg_daily_return=0.25,
            sharpe_ratio=1.85,
            sortino_ratio=2.10,
            max_drawdown=8.5,
            avg_drawdown=2.3,
            calmar_ratio=1.45,
            total_trades=20,
            winning_trades=15,
            losing_trades=5,
            win_rate=75.0,
            profit_factor=2.5,
            avg_win=150.0,
            avg_loss=60.0,
            avg_trade=100.0,
            largest_win=500.0,
            largest_loss=120.0,
            avg_days_in_trade=28.5,
            total_commissions=26.0,
            commission_pct=1.2,
        )

        # Add some equity curve data
        engine.equity_curve = [100000 + i * 500 for i in range(61)]

        # Generate report
        report_path = engine.generate_report(metrics, output_dir=tmp_path)

        assert report_path.exists()
        assert report_path.suffix == ".txt"

        # Read report
        content = report_path.read_text()
        assert "OPTIONS BACKTEST REPORT" in content
        assert "Total Return: +15.50%" in content
        assert "Win Rate: 75.0%" in content


class TestStrategyExamples:
    """Test example strategy implementations."""

    def test_covered_call_construction(self):
        """Test building a covered call position."""
        entry_date = datetime(2024, 1, 15)
        entry_price = 100.0

        leg = OptionsLeg(
            option_type=OptionType.CALL,
            strike=105.0,
            expiration=entry_date + timedelta(days=30),
            quantity=-1,
            entry_premium=2.50,
            delta=0.30,
        )

        position = OptionsPosition(
            symbol="SPY",
            strategy=StrategyType.COVERED_CALL,
            legs=[leg],
            entry_date=entry_date,
            entry_price=entry_price,
        )

        position.calculate_entry_cost()

        # Verify structure
        assert len(position.legs) == 1
        assert position.legs[0].is_short
        assert position.entry_cost < 0  # Received credit

    def test_credit_spread_construction(self):
        """Test building a credit spread position."""
        entry_date = datetime(2024, 1, 15)
        entry_price = 100.0

        legs = [
            OptionsLeg(
                option_type=OptionType.PUT,
                strike=95.0,
                expiration=entry_date + timedelta(days=45),
                quantity=-1,
                entry_premium=2.00,
                delta=-0.16,
            ),
            OptionsLeg(
                option_type=OptionType.PUT,
                strike=90.0,
                expiration=entry_date + timedelta(days=45),
                quantity=1,
                entry_premium=0.80,
                delta=-0.05,
            ),
        ]

        position = OptionsPosition(
            symbol="SPY",
            strategy=StrategyType.CREDIT_SPREAD,
            legs=legs,
            entry_date=entry_date,
            entry_price=entry_price,
        )

        position.calculate_entry_cost()

        # Verify structure
        assert len(position.legs) == 2
        assert position.legs[0].is_short
        assert position.legs[1].is_long
        assert position.entry_cost < 0  # Net credit received

    def test_straddle_construction(self):
        """Test building a straddle position."""
        entry_date = datetime(2024, 1, 15)
        entry_price = 100.0

        legs = [
            OptionsLeg(
                option_type=OptionType.CALL,
                strike=100.0,
                expiration=entry_date + timedelta(days=30),
                quantity=1,
                entry_premium=5.00,
                delta=0.50,
            ),
            OptionsLeg(
                option_type=OptionType.PUT,
                strike=100.0,
                expiration=entry_date + timedelta(days=30),
                quantity=1,
                entry_premium=5.00,
                delta=-0.50,
            ),
        ]

        position = OptionsPosition(
            symbol="SPY",
            strategy=StrategyType.STRADDLE,
            legs=legs,
            entry_date=entry_date,
            entry_price=entry_price,
        )

        position.calculate_entry_cost()

        # Verify structure
        assert len(position.legs) == 2
        assert position.legs[0].is_long
        assert position.legs[1].is_long
        assert position.entry_cost > 0  # Paid debit
        # Net delta should be near zero for ATM straddle
        assert abs(position.net_delta) < 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
