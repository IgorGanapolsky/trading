import pandas as pd
from src.backtesting.backtest_engine import BacktestEngine


class DummyStrategy:
    """Minimal strategy for smoke testing."""

    etf_universe = ["TEST"]
    daily_allocation = 1000.0
    use_vca = False
    vca_strategy = None
    stop_loss_pct = None
    take_profit_pct = None


def run_backtest(fixture_csv: str, seed: int = 42) -> float:
    """
    Run a deterministic backtest using a fixture CSV.
    Returns the total PnL.
    """
    # Read fixture
    df = pd.read_csv(fixture_csv)

    # Ensure columns match BacktestEngine expectations (Capitalized)
    # User fixture: timestamp,open,high,low,close,volume
    df = df.rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    )

    # Handle timestamp
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        # Ensure UTC timezone
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        else:
            df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
        df = df.set_index("timestamp")

    # Determine date range
    start_date = df.index.min().strftime("%Y-%m-%d")
    end_date = df.index.max().strftime("%Y-%m-%d")

    # Initialize engine with dummy strategy
    strategy = DummyStrategy()

    # BacktestEngine constructor checks dates.
    # If fixture has only one day, start_date might equal end_date, which valid?
    # BacktestEngine check: if self.start_date >= self.end_date: raise ValueError
    # So we need at least 2 days or adjust logic.
    # The user fixture has only 1 row: 2020-01-01.
    # We might need to fake the end_date to be start_date + 1 day for the engine to initialize,
    # OR the engine runs on trading_dates list.

    # If using single-day fixture, BacktestEngine needs end_date > start_date (or cover the day)
    # The engine runs loop on _get_trading_dates() which checks start <= date <= end.
    # But initialization checks start < end?
    # BacktestEngine line 113: if self.start_date >= self.end_date: raise ValueError
    # So we MUST have start_date < end_date.

    if start_date == end_date:
        from datetime import datetime, timedelta

        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        end_date = end_dt.strftime("%Y-%m-%d")

    engine = BacktestEngine(
        strategy=strategy,
        start_date=start_date,
        end_date=end_date,
        initial_capital=100000.0,
        enable_slippage=False,  # Deterministic behavior
    )

    # Mock price cache directly
    engine.price_cache["TEST"] = df

    # Override _preload_price_data to do nothing
    engine._preload_price_data = lambda: None

    # Run
    results = engine.run()

    # Return PnL
    return results.final_capital - results.initial_capital
