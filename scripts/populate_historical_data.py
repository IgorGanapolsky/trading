#!/usr/bin/env python3
"""
Populate Historical Data for Backtesting

This script collects historical market data for the core ETF universe
to enable backtesting. Requires API keys to be configured.

Usage:
    python scripts/populate_historical_data.py

Environment Variables Required:
    - ALPACA_API_KEY and ALPACA_SECRET_KEY (recommended)
    - OR POLYGON_API_KEY (recommended)
    - OR ALPHA_VANTAGE_API_KEY (fallback)
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

from src.strategies.core_strategy import CoreStrategy
from src.utils.data_collector import DataCollector


def main():
    """Collect historical data for backtesting."""
    print("=" * 70)
    print("Historical Data Collection for Backtesting")
    print("=" * 70)

    # Get symbols from core strategy default universe
    symbols = CoreStrategy.DEFAULT_ETF_UNIVERSE
    print(f"\nCollecting data for symbols: {', '.join(symbols)}")
    print("Lookback period: 252 days (1 year of trading data)")
    print("\nNote: This requires API keys to be configured.")
    print("See docs/ENVIRONMENT_VARIABLES.md for setup instructions.\n")

    # Initialize collector
    collector = DataCollector(data_dir="data/historical")

    # Collect data (252 days = ~1 year of trading days)
    try:
        collector.collect_daily_data(symbols, lookback_days=252)
        print("\n" + "=" * 70)
        print("Data collection complete!")
        print("=" * 70)

        # Show summary
        print("\nCollected files:")
        for symbol in symbols:
            files = collector.get_existing_files(symbol)
            if files:
                latest = files[-1]
                data = collector.load_historical_data(symbol)
                if not data.empty:
                    print(f"  {symbol}: {len(data)} rows (latest: {latest.name})")
                else:
                    print(f"  {symbol}: No data collected (check API keys)")
            else:
                print(f"  {symbol}: No files found (check API keys)")

        print("\nTo verify data quality:")
        print("  python src/utils/data_collector.py --load SPY")

    except Exception as e:
        print(f"\nError during data collection: {e}")
        print("\nTroubleshooting:")
        print("1. Check that API keys are set in .env file")
        print("2. Verify ALPACA_API_KEY and ALPACA_SECRET_KEY are correct")
        print("3. Or configure POLYGON_API_KEY for alternative data source")
        print("4. See docs/ENVIRONMENT_VARIABLES.md for details")
        sys.exit(1)


if __name__ == "__main__":
    main()
