import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.backtesting.backtest_engine import BacktestEngine
from src.strategies.core_strategy import CoreStrategy

class TestDeterministicBacktest(unittest.TestCase):
    def setUp(self):
        self.start_date = "2023-01-01"
        self.end_date = "2023-01-31"
        self.initial_capital = 100000.0
        self.strategy = CoreStrategy()
        
    def create_synthetic_data(self, start_val, slope, dates):
        n = len(dates)
        # Linear trend
        close = np.linspace(start_val, start_val + slope * n, n)
        # Add some noise or structure if needed, but linear is fine for deterministic check
        
        df = pd.DataFrame({
            "Open": close,
            "High": close,
            "Low": close,
            "Close": close,
            "Volume": np.full(n, 1000000)
        }, index=dates)
        return df

    @patch("src.backtesting.backtest_engine.BacktestEngine._preload_price_data")
    def test_deterministic_run(self, mock_preload):
        """
        Run a backtest with synthetic deterministic data.
        SPY has the strongest trend, so the strategy should pick it.
        """
        import logging
        logging.basicConfig(level=logging.DEBUG)
        
        engine = BacktestEngine(
            strategy=self.strategy,
            start_date=self.start_date,
            end_date=self.end_date,
            initial_capital=self.initial_capital,
            enable_slippage=False # Disable slippage for exact math
        )
        
        def side_effect():
            # Generate dates including buffer for indicators
            start_dt = datetime.strptime(self.start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(self.end_date, "%Y-%m-%d")
            
            # 300 days buffer (ensure > 126 trading days)
            buffer_start = start_dt - timedelta(days=400) 
            dates = pd.date_range(start=buffer_start, end=end_dt, freq="B", tz="UTC")
            
            print(f"Generated {len(dates)} days of data")
            
            # Populate all symbols
            universe = getattr(self.strategy, "etf_universe", ["SPY", "QQQ", "VOO"])
            for sym in universe:
                slope = 0.01
                if sym == "SPY": slope = 0.1
                elif sym == "QQQ": slope = 0.05
                
                engine.price_cache[sym] = self.create_synthetic_data(100, slope, dates)
            
        mock_preload.side_effect = side_effect
        
        results = engine.run()
        
        # Assertions
        print(f"Total Return: {results.total_return}%")
        print(f"Trades: {len(results.trades)}")
        
        # Should be positive return
        self.assertGreater(results.total_return, 0)
        
        # Should have trades
        self.assertGreater(len(results.trades), 0)
        
        # Check that SPY was the primary target
        spy_trades = [t for t in results.trades if t['symbol'] == 'SPY']
        self.assertGreater(len(spy_trades), 0)
        
        # Deterministic check:
        # With linear growth and no slippage, the result should be exactly reproducible.
        # We can assert the exact number of trades or return if we want strict regression testing.
        # For now, just ensuring it runs and produces logical output is a good smoke test.

if __name__ == "__main__":
    unittest.main()
