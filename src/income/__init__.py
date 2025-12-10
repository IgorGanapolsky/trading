"""
Income Module - Passive Income Tracking

Tracks various sources of passive income:
- Stock Lending (Alpaca FPSL)
- High-Yield Cash Interest (Alpaca 3.56% APY)
- Dividend Income
"""

from src.income.stock_lending import (
    StockLendingTracker,
    LendingIncomeSummary,
    LendingPosition,
    get_lending_income_for_report,
)

__all__ = [
    "StockLendingTracker",
    "LendingIncomeSummary",
    "LendingPosition",
    "get_lending_income_for_report",
]
