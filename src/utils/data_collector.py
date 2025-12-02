"""
Data Collection Module for Historical Market Data

Systematically archives OHLCV data for ML training and backtesting.
"""

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from src.utils.market_data import get_market_data_provider

logger = logging.getLogger(__name__)


class DataCollector:
    """Collects and archives historical market data."""

    def __init__(self, data_dir: str = "data/historical"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.market_data = get_market_data_provider()
        logger.info(f"DataCollector initialized: {self.data_dir}")

    def collect_daily_data(self, symbols: list[str], lookback_days: int = 30) -> None:
        """
        Collect and save daily OHLCV data for symbols.

        Args:
            symbols: List of ticker symbols
            lookback_days: Days of history to fetch (default: 30)
        """
        logger.info(
            f"Collecting data for {len(symbols)} symbols with {lookback_days} days lookback"
        )

        for symbol in symbols:
            try:
                logger.info(f"Fetching data for {symbol}...")

                result = self.market_data.get_daily_bars(symbol, lookback_days)
                data = result.data
                if data.empty:  # pragma: no cover - defensive
                    logger.warning(f"No data returned for {symbol} after fallbacks")
                    continue

                # Save to CSV
                filepath = self.save_to_csv(symbol, data)
                logger.info(f"Saved {len(data)} rows for {symbol} to {filepath}")

            except Exception as e:
                logger.error(f"Error collecting data for {symbol}: {str(e)}")
                continue

    def save_to_csv(self, symbol: str, data: pd.DataFrame) -> str:
        """
        Save OHLCV data to CSV file.

        Args:
            symbol: Ticker symbol
            data: DataFrame with OHLCV data

        Returns:
            Path to saved file
        """
        # Generate filename with today's date
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"{symbol}_{today}.csv"
        filepath = self.data_dir / filename

        # Check if file already exists
        if filepath.exists():
            logger.info(f"File {filepath} already exists, appending new data")
            existing_data = pd.read_csv(filepath, index_col=0, parse_dates=True)

            # Combine and remove duplicates based on date index
            combined = pd.concat([existing_data, data])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined.to_csv(filepath)
        else:
            # Save new file
            data.to_csv(filepath)

        return str(filepath)

    def get_existing_files(self, symbol: Optional[str] = None) -> list[Path]:
        """
        List existing CSV files in data directory.

        Args:
            symbol: Optional symbol to filter by

        Returns:
            List of Path objects for matching files
        """
        pattern = f"{symbol}_*.csv" if symbol else "*.csv"

        files = list(self.data_dir.glob(pattern))
        return sorted(files)

    def load_historical_data(self, symbol: str) -> pd.DataFrame:
        """
        Load all historical data for a symbol from CSV files.

        Args:
            symbol: Ticker symbol

        Returns:
            Combined DataFrame with all historical data
        """
        files = self.get_existing_files(symbol)

        if not files:
            logger.warning(f"No historical data found for {symbol}")
            return pd.DataFrame()

        # Load and combine all files
        dataframes = []
        for file in files:
            df = pd.read_csv(file, index_col=0, parse_dates=True)
            dataframes.append(df)

        # Combine and remove duplicates
        combined = pd.concat(dataframes)
        combined = combined[~combined.index.duplicated(keep="last")]
        combined.sort_index(inplace=True)

        logger.info(f"Loaded {len(combined)} rows for {symbol} from {len(files)} files")
        return combined


def main():
    """CLI interface for data collection."""
    parser = argparse.ArgumentParser(description="Collect historical market data")
    parser.add_argument(
        "--symbols",
        type=str,
        default="SPY,QQQ,VOO,NVDA,GOOGL",
        help="Comma-separated list of symbols (default: SPY,QQQ,VOO,NVDA,GOOGL)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=30,
        help="Days of historical data to fetch (default: 30)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/historical",
        help="Directory to store data (default: data/historical)",
    )
    parser.add_argument("--list", action="store_true", help="List existing data files")
    parser.add_argument("--load", type=str, help="Load and display historical data for a symbol")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize collector
    collector = DataCollector(data_dir=args.data_dir)

    # Handle different modes
    if args.list:
        files = collector.get_existing_files()
        print(f"\nFound {len(files)} data files:")
        for file in files:
            print(f"  {file}")
    elif args.load:
        data = collector.load_historical_data(args.load)
        print(f"\nHistorical data for {args.load}:")
        print(data.head(10))
        print(f"\nTotal rows: {len(data)}")
        print(f"Date range: {data.index.min()} to {data.index.max()}")
    else:
        # Collect data
        symbols = [s.strip() for s in args.symbols.split(",")]
        collector.collect_daily_data(symbols, lookback_days=args.lookback)
        print(f"\nData collection complete for {len(symbols)} symbols")


if __name__ == "__main__":
    main()
