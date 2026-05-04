import numpy as np


class BullPutSpreadBacktester:
    def __init__(self):
        self.trades: list[dict] = []
        self.results: dict = {}

    def calculate_spread_premium(
        self, underlying_price: float, strike_short: float, strike_long: float, dte: int
    ) -> float:
        """Calculate theoretical premium for bull put spread"""
        return max(0, strike_short - strike_long) * 0.3

    def backtest_strategy(self, start_date: str, end_date: str) -> dict:
        """Run backtest for bull put spread strategy"""
        return {"total_return": 0.0, "win_rate": 0.0, "max_drawdown": 0.0}

    def add_trade(self, trade_data: dict):
        """Add trade to backtest"""
        self.trades.append(trade_data)

    def calculate_metrics(self) -> dict:
        """Calculate performance metrics"""
        if not self.trades:
            return {}

        returns = [trade.get("pnl", 0) for trade in self.trades]
        return {
            "total_trades": len(self.trades),
            "avg_return": np.mean(returns) if returns else 0,
            "volatility": np.std(returns) if returns else 0,
        }
