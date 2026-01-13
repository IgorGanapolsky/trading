"""Centralized trade recording module.

This module provides a single interface for recording trade execution results
to daily JSON files, eliminating duplicated file handling logic across scripts.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def record_trade_result(
    symbol: str,
    strategy: str,
    result: dict[str, Any],
    data_dir: str = "data",
    extra_fields: dict[str, Any] | None = None,
) -> Path:
    """Record trade execution result to daily JSON file.

    Handles file creation, reading existing trades, appending, and writing.
    Thread-safe for single-process use. Creates data directory if needed.

    Args:
        symbol: Trading symbol (e.g., 'F', 'SOFI', 'SPY')
        strategy: Strategy name used for filename (e.g., 'options_trades', 'credit_spreads')
        result: Trade execution result dictionary
        data_dir: Directory for storing trade files (default: 'data')
        extra_fields: Optional additional fields to include in the trade record

    Returns:
        Path to the trade file where result was saved

    Raises:
        IOError: If file cannot be read or written
        json.JSONDecodeError: If existing file contains invalid JSON

    Example:
        >>> path = record_trade_result(
        ...     symbol='F',
        ...     strategy='options_trades',
        ...     result={'status': 'ORDER_SUBMITTED', 'order_id': '123'},
        ...     extra_fields={'width': 5}
        ... )
        >>> print(f"Trade saved to {path}")
    """
    # Build file path with date suffix
    date_str = datetime.now().strftime("%Y%m%d")
    result_file = Path(data_dir) / f"{strategy}_{date_str}.json"

    # Ensure data directory exists
    result_file.parent.mkdir(parents=True, exist_ok=True)

    # Read existing trades
    trades: list[dict[str, Any]] = []
    if result_file.exists():
        try:
            with open(result_file) as f:
                content = f.read()
                if content.strip():  # Only parse if file has content
                    trades = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {result_file}, starting fresh: {e}")
            trades = []
        except OSError as e:
            logger.error(f"Failed to read {result_file}: {e}")
            raise

    # Build trade record
    trade_record: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "strategy": strategy,
        "result": result,
    }

    # Add extra fields if provided
    if extra_fields:
        trade_record.update(extra_fields)

    trades.append(trade_record)

    # Write updated trades
    try:
        with open(result_file, "w") as f:
            json.dump(trades, f, indent=2, default=str)
    except OSError as e:
        logger.error(f"Failed to write {result_file}: {e}")
        raise

    logger.info(f"Trade recorded to {result_file}")
    return result_file


def get_daily_trades(
    strategy: str,
    data_dir: str = "data",
    date: datetime | None = None,
) -> list[dict[str, Any]]:
    """Read trades from a daily JSON file.

    Args:
        strategy: Strategy name (e.g., 'options_trades', 'credit_spreads')
        data_dir: Directory containing trade files (default: 'data')
        date: Date to read trades for (default: today)

    Returns:
        List of trade records, empty list if file doesn't exist

    Example:
        >>> trades = get_daily_trades('options_trades')
        >>> print(f"Found {len(trades)} trades today")
    """
    if date is None:
        date = datetime.now()

    date_str = date.strftime("%Y%m%d")
    result_file = Path(data_dir) / f"{strategy}_{date_str}.json"

    if not result_file.exists():
        return []

    try:
        with open(result_file) as f:
            content = f.read()
            if content.strip():
                return json.loads(content)
            return []
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to read {result_file}: {e}")
        return []


def get_trade_count(
    strategy: str,
    data_dir: str = "data",
    date: datetime | None = None,
) -> int:
    """Get count of trades for a strategy on a given day.

    Args:
        strategy: Strategy name (e.g., 'options_trades', 'credit_spreads')
        data_dir: Directory containing trade files (default: 'data')
        date: Date to count trades for (default: today)

    Returns:
        Number of trades recorded for the strategy on the given day
    """
    return len(get_daily_trades(strategy, data_dir, date))
