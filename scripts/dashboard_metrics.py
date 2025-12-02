#!/usr/bin/env python3
"""
World-Class Trading Dashboard Metrics Calculator

Calculates comprehensive metrics for AI trading dashboard including:
- Risk & Performance Depth (drawdown, Sharpe, Sortino, volatility, VaR)
- Strategy & Model Diagnostics (per-strategy performance, signal quality)
- Time-Series & Cohort Analytics (equity curve, rolling metrics)
- Operational Guardrails & Safety (risk limits, auditability)
- Market Regime Detection & Benchmarking (S&P 500 comparison)
- AI-Specific KPIs (model accuracy, latency, costs, outlier detection)
- Automation Status & Uptime Tracking
- Trading Journal Integration
- Risk Management & Compliance Metrics

This module provides the foundation for a professional quant dashboard.
"""

import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import yfinance as yf

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

DATA_DIR = Path("data")


def load_json_file(filepath: Path) -> Any:
    """Load JSON file, return empty dict/list if not found."""
    if filepath.exists():
        try:
            with open(filepath) as f:
                return json.load(f)
        except Exception:
            return {} if "json" in str(filepath) else []
    return {} if "json" in str(filepath) else []


class TradingMetricsCalculator:
    """
    Comprehensive metrics calculator for world-class trading dashboard.
    """

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.risk_free_rate = 0.04  # 4% annual risk-free rate

    def calculate_all_metrics(self) -> dict[str, Any]:
        """
        Calculate all world-class metrics for the dashboard.

        Returns:
            Dictionary containing all calculated metrics organized by category
        """
        # Load data sources
        system_state = load_json_file(self.data_dir / "system_state.json")
        perf_log = load_json_file(self.data_dir / "performance_log.json")

        # Ensure perf_log is a list
        if not isinstance(perf_log, list):
            perf_log = []

        # Get account info
        account = system_state.get("account", {})
        starting_balance = account.get("starting_balance", 100000.0)
        current_equity = account.get("current_equity", starting_balance)

        # Get performance data
        performance = system_state.get("performance", {})
        closed_trades = performance.get("closed_trades", [])
        open_positions = performance.get("open_positions", [])

        # Load all trade files
        all_trades = self._load_all_trades()

        # Calculate metrics
        metrics = {
            "account_summary": self._calculate_account_summary(
                account, starting_balance, current_equity
            ),
            "risk_metrics": self._calculate_risk_metrics(
                perf_log, starting_balance, current_equity
            ),
            "performance_metrics": self._calculate_performance_metrics(
                perf_log, closed_trades, all_trades
            ),
            "strategy_metrics": self._calculate_strategy_metrics(
                system_state, closed_trades, all_trades
            ),
            "exposure_metrics": self._calculate_exposure_metrics(
                open_positions, current_equity, all_trades
            ),
            "risk_guardrails": self._calculate_risk_guardrails(
                system_state, perf_log, current_equity
            ),
            "time_series": self._calculate_time_series_metrics(perf_log),
            "strategy_equity_curves": self._calculate_strategy_equity_curves(
                perf_log, closed_trades, all_trades
            ),
            "holding_period_analysis": self._calculate_holding_period_analysis(closed_trades),
            "time_of_day_analysis": self._calculate_time_of_day_analysis(all_trades, closed_trades),
            "signal_quality": self._calculate_signal_quality(all_trades, closed_trades),
            "market_regime": self._calculate_market_regime(perf_log),
            "benchmark_comparison": self._calculate_benchmark_comparison(
                perf_log, starting_balance
            ),
            "ai_kpis": self._calculate_ai_kpis(system_state, all_trades),
            "automation_status": self._calculate_automation_status(system_state, perf_log),
            "trading_journal": self._calculate_journal_summary(),
            "compliance": self._calculate_compliance_metrics(system_state, perf_log, all_trades),
        }

        return metrics

    def _load_all_trades(self) -> list[dict]:
        """Load all trade files and combine into single list."""
        all_trades = []

        # Find all trade files
        trade_files = list(self.data_dir.glob("trades_*.json"))

        for trade_file in trade_files:
            trades = load_json_file(trade_file)
            if isinstance(trades, list):
                for trade in trades:
                    trade["trade_date"] = trade_file.stem.replace("trades_", "")
                    all_trades.append(trade)

        return all_trades

    def _calculate_account_summary(
        self, account: dict, starting_balance: float, current_equity: float
    ) -> dict[str, Any]:
        """Calculate basic account summary metrics."""
        total_pl = current_equity - starting_balance
        total_pl_pct = (total_pl / starting_balance * 100) if starting_balance > 0 else 0.0

        return {
            "starting_balance": starting_balance,
            "current_equity": current_equity,
            "total_pl": total_pl,
            "total_pl_pct": total_pl_pct,
            "cash": account.get("cash", current_equity),
            "positions_value": account.get("positions_value", 0.0),
        }

    def _calculate_risk_metrics(
        self, perf_log: list[dict], starting_balance: float, current_equity: float
    ) -> dict[str, Any]:
        """Calculate comprehensive risk metrics."""
        if not perf_log or len(perf_log) < 2:
            return {
                "max_drawdown_pct": 0.0,
                "current_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "volatility_annualized": 0.0,
                "worst_daily_loss": 0.0,
                "var_95": 0.0,
                "var_99": 0.0,
                "cvar_95": 0.0,
                "ulcer_index": 0.0,
                "calmar_ratio": 0.0,
                "peak_equity": current_equity,
            }

        # Extract equity curve
        equity_values = [entry.get("equity", starting_balance) for entry in perf_log]

        # Calculate daily returns
        daily_returns = []
        for i in range(1, len(equity_values)):
            if equity_values[i - 1] > 0:
                daily_return = (equity_values[i] - equity_values[i - 1]) / equity_values[i - 1]
                daily_returns.append(daily_return)

        if not daily_returns:
            return {
                "max_drawdown_pct": 0.0,
                "current_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "volatility_annualized": 0.0,
                "worst_daily_loss": 0.0,
                "var_95": 0.0,
                "var_99": 0.0,
                "cvar_95": 0.0,
                "ulcer_index": 0.0,
                "calmar_ratio": 0.0,
                "peak_equity": current_equity,
            }

        # Calculate max drawdown
        peak = equity_values[0]
        max_drawdown_pct = 0.0
        peak_equity = peak

        for equity in equity_values:
            if equity > peak:
                peak = equity
                peak_equity = peak
            drawdown_pct = ((peak - equity) / peak * 100) if peak > 0 else 0.0
            if drawdown_pct > max_drawdown_pct:
                max_drawdown_pct = drawdown_pct

        # Current drawdown
        current_drawdown_pct = (
            ((peak_equity - current_equity) / peak_equity * 100) if peak_equity > 0 else 0.0
        )

        # Calculate Sharpe ratio
        mean_return = np.mean(daily_returns)
        std_return = np.std(daily_returns)
        risk_free_rate_daily = self.risk_free_rate / 252

        sharpe_ratio = 0.0
        if std_return > 0:
            excess_return = mean_return - risk_free_rate_daily
            sharpe_ratio = (excess_return / std_return) * np.sqrt(252)

        # Calculate Sortino ratio (downside deviation only)
        downside_returns = [r for r in daily_returns if r < 0]
        sortino_ratio = 0.0
        if downside_returns:
            downside_std = np.std(downside_returns)
            if downside_std > 0:
                sortino_ratio = (mean_return - risk_free_rate_daily) / downside_std * np.sqrt(252)

        # Annualized volatility
        volatility_annualized = std_return * np.sqrt(252) * 100 if std_return > 0 else 0.0

        # Worst daily loss
        worst_daily_loss = min(daily_returns) * 100 if daily_returns else 0.0

        # VaR (95th percentile)
        var_95 = np.percentile(daily_returns, 5) * 100 if daily_returns else 0.0

        # VaR (99th percentile)
        var_99 = np.percentile(daily_returns, 1) * 100 if daily_returns else 0.0

        # Conditional VaR (CVaR) - Expected loss beyond VaR
        cvar_95 = 0.0
        if daily_returns:
            var_95_threshold = np.percentile(daily_returns, 5)
            tail_returns = [r for r in daily_returns if r <= var_95_threshold]
            cvar_95 = np.mean(tail_returns) * 100 if tail_returns else 0.0

        # Ulcer Index (square root of average squared drawdown)
        # Calculate drawdowns for ulcer index
        cumulative = np.array(equity_values)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        drawdowns_squared = drawdowns**2
        ulcer_index = (
            np.sqrt(np.mean(drawdowns_squared)) * 100 if len(drawdowns_squared) > 0 else 0.0
        )

        # Calmar Ratio (annualized return / max drawdown)
        # Both should be in same units (decimal, not percentage)
        annualized_return = mean_return * 252  # Annualized return as decimal
        max_dd_decimal = max_drawdown_pct / 100  # Convert percentage to decimal
        calmar_ratio = (annualized_return / max_dd_decimal) if max_dd_decimal > 0 else 0.0

        return {
            "max_drawdown_pct": max_drawdown_pct,
            "current_drawdown_pct": current_drawdown_pct,
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "volatility_annualized": volatility_annualized,
            "worst_daily_loss": worst_daily_loss,
            "var_95": var_95,
            "var_99": var_99,
            "cvar_95": abs(cvar_95),  # CVaR should be positive (expected loss)
            "ulcer_index": ulcer_index,
            "calmar_ratio": calmar_ratio,
            "peak_equity": peak_equity,
            "trading_days": len(daily_returns),
        }

    def _calculate_performance_metrics(
        self, perf_log: list[dict], closed_trades: list[dict], all_trades: list[dict]
    ) -> dict[str, Any]:
        """Calculate performance metrics including profit factor and expectancy."""
        if not closed_trades:
            return {
                "profit_factor": 0.0,
                "expectancy_per_trade": 0.0,
                "expectancy_per_r": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "win_rate": 0.0,
            }

        # Calculate profit factor
        gross_profit = sum(t.get("pl", 0) for t in closed_trades if t.get("pl", 0) > 0)
        gross_loss = abs(sum(t.get("pl", 0) for t in closed_trades if t.get("pl", 0) < 0))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

        # Calculate expectancy
        total_trades = len(closed_trades)
        winning_trades = [t for t in closed_trades if t.get("pl", 0) > 0]
        losing_trades = [t for t in closed_trades if t.get("pl", 0) < 0]

        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0.0
        avg_win = np.mean([t.get("pl", 0) for t in winning_trades]) if winning_trades else 0.0
        avg_loss = np.mean([abs(t.get("pl", 0)) for t in losing_trades]) if losing_trades else 0.0

        # Expectancy per trade ($)
        expectancy_per_trade = (
            (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)
            if total_trades > 0
            else 0.0
        )

        # Expectancy per R (assuming 1% risk per trade)
        # R = risk per trade = 1% of account
        # For simplicity, we'll use avg_win/avg_loss ratio
        expectancy_per_r = (avg_win / avg_loss) if avg_loss > 0 else 0.0

        # Largest win/loss
        largest_win = max([t.get("pl", 0) for t in closed_trades], default=0.0)
        largest_loss = min([t.get("pl", 0) for t in closed_trades], default=0.0)

        # Win/Loss Ratio
        win_loss_ratio = (len(winning_trades) / len(losing_trades)) if losing_trades else 0.0

        # Average Win/Loss Ratio (R-multiple)
        avg_win_loss_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

        return {
            "profit_factor": profit_factor,
            "expectancy_per_trade": expectancy_per_trade,
            "expectancy_per_r": expectancy_per_r,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "win_rate": win_rate,
            "win_loss_ratio": win_loss_ratio,
            "avg_win_loss_ratio": avg_win_loss_ratio,
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
        }

    def _calculate_strategy_metrics(
        self, system_state: dict, closed_trades: list[dict], all_trades: list[dict]
    ) -> dict[str, Any]:
        """Calculate per-strategy performance metrics with enhanced attribution."""
        strategies = system_state.get("strategies", {})
        strategy_performance = {}

        # Group trades by strategy_id (from enhanced trade logs)
        strategy_trade_map = defaultdict(list)
        agent_trade_map = defaultdict(list)

        # Process closed trades with attribution
        for trade in closed_trades:
            strategy_id = trade.get("strategy_id") or trade.get("tier", "unknown")
            agent_type = trade.get("agent_type", "unknown")

            # Normalize strategy_id
            if "T1" in str(strategy_id) or "CORE" in str(strategy_id):
                strategy_id = "core_strategy"
            elif "T2" in str(strategy_id) or "GROWTH" in str(strategy_id):
                strategy_id = "growth_strategy"

            strategy_trade_map[strategy_id].append(trade)
            agent_trade_map[agent_type].append(trade)

        # Calculate per-strategy metrics
        for strategy_id, strategy_trades in strategy_trade_map.items():
            if not strategy_trades:
                continue

            # Get strategy name from system state or use formatted strategy_id
            strategy_data = strategies.get(strategy_id, {})
            strategy_name = strategy_data.get("name", strategy_id.replace("_", " ").title())

            # Calculate metrics for this strategy
            total_pl = sum(t.get("pl", 0) for t in strategy_trades)
            winning = [t for t in strategy_trades if t.get("pl", 0) > 0]
            losing = [t for t in strategy_trades if t.get("pl", 0) < 0]
            win_rate = (len(winning) / len(strategy_trades) * 100) if strategy_trades else 0.0

            # Calculate profit factor for this strategy
            gross_profit = sum(t.get("pl", 0) for t in winning)
            gross_loss = abs(sum(t.get("pl", 0) for t in losing))
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

            # Simple Sharpe (would need daily returns per strategy for accurate)
            sharpe = 0.0  # Placeholder - would need strategy-specific equity curve

            # Max drawdown (simplified)
            max_dd = 0.0  # Placeholder

            strategy_performance[strategy_id] = {
                "name": strategy_name,
                "trades": len(strategy_trades),
                "pl": total_pl,
                "win_rate": win_rate,
                "sharpe": sharpe,
                "max_drawdown_pct": max_dd,
                "profit_factor": profit_factor,
                "winning_trades": len(winning),
                "losing_trades": len(losing),
            }

        # Also calculate per-agent metrics
        agent_performance = {}
        for agent_type, agent_trades in agent_trade_map.items():
            if not agent_trades:
                continue

            total_pl = sum(t.get("pl", 0) for t in agent_trades)
            winning = [t for t in agent_trades if t.get("pl", 0) > 0]
            win_rate = (len(winning) / len(agent_trades) * 100) if agent_trades else 0.0

            agent_performance[agent_type] = {
                "trades": len(agent_trades),
                "pl": total_pl,
                "win_rate": win_rate,
            }

        return {
            "by_strategy": strategy_performance,
            "by_agent": agent_performance,
        }

    def _calculate_exposure_metrics(
        self, open_positions: list[dict], current_equity: float, all_trades: list[dict]
    ) -> dict[str, Any]:
        """Calculate exposure by ticker, sector, and asset class."""
        if not open_positions:
            return {
                "by_ticker": {},
                "by_sector": {},
                "by_asset_class": {},
                "largest_position_pct": 0.0,
                "total_exposure": 0.0,
            }

        exposure_by_ticker = defaultdict(float)
        exposure_by_sector = defaultdict(float)
        exposure_by_asset_class = defaultdict(float)

        # Sector mapping (simplified)
        sector_map = {
            "SPY": "Index ETF",
            "QQQ": "Index ETF",
            "VOO": "Index ETF",
            "NVDA": "Technology",
            "GOOGL": "Technology",
            "AMZN": "Technology",
        }

        # Asset class mapping (crypto, equities, bonds)
        asset_class_map = {
            # Equities (ETFs)
            "SPY": "Equities",
            "QQQ": "Equities",
            "VOO": "Equities",
            # Bonds
            "BND": "Bonds",
            # Equities (Stocks)
            "NVDA": "Equities",
            "GOOGL": "Equities",
            "AMZN": "Equities",
            # Crypto
            "BTCUSD": "Crypto",
            "ETHUSD": "Crypto",
            "BTC-USD": "Crypto",
            "ETH-USD": "Crypto",
        }

        # Helper function to determine asset class from symbol
        def get_asset_class(symbol: str) -> str:
            """Determine asset class from symbol."""
            symbol_upper = symbol.upper()

            # Check explicit mapping first
            if symbol_upper in asset_class_map:
                return asset_class_map[symbol_upper]

            # Crypto detection
            if "BTC" in symbol_upper or "ETH" in symbol_upper or "USD" in symbol_upper:
                if any(crypto in symbol_upper for crypto in ["BTC", "ETH", "CRYPTO"]):
                    return "Crypto"

            # Bond detection
            if "BND" in symbol_upper or "BOND" in symbol_upper:
                return "Bonds"

            # Default to Equities (stocks/ETFs)
            return "Equities"

        total_exposure = 0.0

        for position in open_positions:
            symbol = position.get("symbol", "")
            amount = position.get("amount", 0.0)

            exposure_by_ticker[symbol] += amount
            exposure_by_sector[sector_map.get(symbol, "Unknown")] += amount

            # Use helper function for asset class
            asset_class = get_asset_class(symbol)
            exposure_by_asset_class[asset_class] += amount

            total_exposure += amount

        # Calculate percentages
        exposure_by_ticker_pct = {
            ticker: (amount / current_equity * 100) if current_equity > 0 else 0.0
            for ticker, amount in exposure_by_ticker.items()
        }

        # Largest position
        largest_position_pct = (
            max(exposure_by_ticker_pct.values()) if exposure_by_ticker_pct else 0.0
        )

        return {
            "by_ticker": exposure_by_ticker_pct,
            "by_sector": dict(exposure_by_sector),
            "by_asset_class": dict(exposure_by_asset_class),
            "largest_position_pct": largest_position_pct,
            "total_exposure": total_exposure,
        }

    def _calculate_risk_guardrails(
        self, system_state: dict, perf_log: list[dict], current_equity: float
    ) -> dict[str, Any]:
        """Calculate risk guardrail status."""
        # Get today's P/L
        today = date.today().isoformat()
        today_entries = [e for e in perf_log if e.get("date") == today]
        daily_pl = today_entries[-1].get("pl", 0.0) if today_entries else 0.0

        # Daily loss limit (assume 2% default)
        daily_loss_limit_pct = 2.0
        daily_loss_limit = current_equity * (daily_loss_limit_pct / 100)
        daily_loss_used_pct = (
            (abs(daily_pl) / daily_loss_limit * 100)
            if daily_pl < 0 and daily_loss_limit > 0
            else 0.0
        )

        # Max position size (assume 10% default)
        max_position_size_pct = 10.0

        # Consecutive losses
        performance = system_state.get("performance", {})
        consecutive_losses = performance.get("consecutive_losses", 0)

        return {
            "daily_loss_limit": daily_loss_limit,
            "daily_loss_used": abs(daily_pl) if daily_pl < 0 else 0.0,
            "daily_loss_used_pct": daily_loss_used_pct,
            "max_position_size_pct": max_position_size_pct,
            "consecutive_losses": consecutive_losses,
            "consecutive_losses_limit": 5,  # Default limit
        }

    def _calculate_time_series_metrics(self, perf_log: list[dict]) -> dict[str, Any]:
        """Calculate time-series analytics with proper rolling window calculations."""
        if not perf_log or len(perf_log) < 2:
            return {
                "equity_curve": [],
                "rolling_sharpe_7d": 0.0,
                "rolling_sharpe_30d": 0.0,
                "rolling_max_dd_30d": 0.0,
            }

        # Equity curve
        equity_curve = [
            {"date": entry.get("date", ""), "equity": entry.get("equity", 0)} for entry in perf_log
        ]

        # Calculate daily returns
        equity_values = [entry.get("equity", 0) for entry in perf_log]
        daily_returns = []
        for i in range(1, len(equity_values)):
            if equity_values[i - 1] > 0:
                daily_return = (equity_values[i] - equity_values[i - 1]) / equity_values[i - 1]
                daily_returns.append(daily_return)

        if not daily_returns:
            return {
                "equity_curve": equity_curve[-30:],
                "rolling_sharpe_7d": 0.0,
                "rolling_sharpe_30d": 0.0,
                "rolling_max_dd_30d": 0.0,
            }

        # Calculate rolling Sharpe (7d window)
        rolling_sharpe_7d = 0.0
        if len(daily_returns) >= 7:
            recent_7d = daily_returns[-7:]
            mean_return = np.mean(recent_7d)
            std_return = np.std(recent_7d)
            if std_return > 0:
                risk_free_rate_daily = self.risk_free_rate / 252
                rolling_sharpe_7d = (mean_return - risk_free_rate_daily) / std_return * np.sqrt(252)

        # Calculate rolling Sharpe (30d window)
        rolling_sharpe_30d = 0.0
        if len(daily_returns) >= 30:
            recent_30d = daily_returns[-30:]
            mean_return = np.mean(recent_30d)
            std_return = np.std(recent_30d)
            if std_return > 0:
                risk_free_rate_daily = self.risk_free_rate / 252
                rolling_sharpe_30d = (
                    (mean_return - risk_free_rate_daily) / std_return * np.sqrt(252)
                )

        # Calculate rolling max drawdown (30d window)
        rolling_max_dd_30d = 0.0
        if len(equity_values) >= 30:
            recent_30d_equity = equity_values[-30:]
            peak = recent_30d_equity[0]
            max_dd = 0.0
            for equity in recent_30d_equity:
                if equity > peak:
                    peak = equity
                drawdown_pct = ((peak - equity) / peak * 100) if peak > 0 else 0.0
                if drawdown_pct > max_dd:
                    max_dd = drawdown_pct
            rolling_max_dd_30d = max_dd

        return {
            "equity_curve": equity_curve[-30:],  # Last 30 days
            "rolling_sharpe_7d": rolling_sharpe_7d,
            "rolling_sharpe_30d": rolling_sharpe_30d,
            "rolling_max_dd_30d": rolling_max_dd_30d,
        }

    def _calculate_strategy_equity_curves(
        self, perf_log: list[dict], closed_trades: list[dict], all_trades: list[dict]
    ) -> dict[str, Any]:
        """Calculate equity curves per strategy over time."""
        if not closed_trades:
            return {}

        # Group trades by strategy
        strategy_trades = defaultdict(list)
        for trade in closed_trades:
            strategy_id = trade.get("strategy_id") or trade.get("tier", "unknown")
            # Normalize strategy_id
            if "T1" in str(strategy_id) or "CORE" in str(strategy_id):
                strategy_id = "core_strategy"
            elif "T2" in str(strategy_id) or "GROWTH" in str(strategy_id):
                strategy_id = "growth_strategy"
            strategy_trades[strategy_id].append(trade)

        strategy_curves = {}

        # Build equity curve for each strategy
        for strategy_id, trades in strategy_trades.items():
            if not trades:
                continue

            # Sort trades by date
            sorted_trades = sorted(
                trades, key=lambda t: t.get("entry_date", t.get("exit_date", ""))
            )

            # Calculate cumulative P/L over time
            cumulative_pl = 0.0
            curve_points = []

            for trade in sorted_trades:
                pl = trade.get("pl", 0.0)
                cumulative_pl += pl
                exit_date = trade.get("exit_date", trade.get("entry_date", ""))
                curve_points.append(
                    {
                        "date": exit_date,
                        "cumulative_pl": cumulative_pl,
                        "equity": 100000.0 + cumulative_pl,  # Assuming starting balance
                    }
                )

            strategy_curves[strategy_id] = {
                "equity_curve": curve_points[-30:],  # Last 30 points
                "total_pl": cumulative_pl,
                "trades": len(trades),
            }

        return strategy_curves

    def _calculate_holding_period_analysis(self, closed_trades: list[dict]) -> dict[str, Any]:
        """Calculate P/L by holding period (days held)."""
        if not closed_trades:
            return {
                "by_period": {},
                "avg_pl_by_period": {},
            }

        # Group trades by holding period
        period_trades = defaultdict(list)

        for trade in closed_trades:
            entry_date_str = trade.get("entry_date", "")
            exit_date_str = trade.get("exit_date", "")

            if not entry_date_str or not exit_date_str:
                continue

            try:
                # Parse dates
                if "T" in entry_date_str:
                    entry_date = datetime.fromisoformat(entry_date_str.replace("Z", "+00:00"))
                else:
                    entry_date = datetime.strptime(entry_date_str, "%Y-%m-%d")

                if "T" in exit_date_str:
                    exit_date = datetime.fromisoformat(exit_date_str.replace("Z", "+00:00"))
                else:
                    exit_date = datetime.strptime(exit_date_str, "%Y-%m-%d")

                # Calculate days held
                days_held = (exit_date - entry_date).days

                # Categorize into periods
                if days_held == 0:
                    period = "Same Day"
                elif days_held <= 1:
                    period = "1 Day"
                elif days_held <= 3:
                    period = "2-3 Days"
                elif days_held <= 7:
                    period = "4-7 Days"
                elif days_held <= 14:
                    period = "8-14 Days"
                elif days_held <= 30:
                    period = "15-30 Days"
                else:
                    period = "30+ Days"

                period_trades[period].append(trade)
            except Exception:
                continue

        # Calculate metrics per period
        by_period = {}
        avg_pl_by_period = {}

        for period, trades in period_trades.items():
            total_pl = sum(t.get("pl", 0) for t in trades)
            avg_pl = total_pl / len(trades) if trades else 0.0
            winning = [t for t in trades if t.get("pl", 0) > 0]
            win_rate = (len(winning) / len(trades) * 100) if trades else 0.0

            by_period[period] = {
                "trades": len(trades),
                "total_pl": total_pl,
                "avg_pl": avg_pl,
                "win_rate": win_rate,
            }
            avg_pl_by_period[period] = avg_pl

        return {
            "by_period": by_period,
            "avg_pl_by_period": avg_pl_by_period,
        }

    def _calculate_time_of_day_analysis(
        self, all_trades: list[dict], closed_trades: list[dict]
    ) -> dict[str, Any]:
        """Calculate P/L by time of day to identify optimal execution windows."""
        if not all_trades:
            return {
                "by_hour": {},
                "best_hours": [],
            }

        # Group trades by hour of execution
        hour_trades = defaultdict(list)

        for trade in all_trades:
            timestamp_str = trade.get("timestamp", "")
            if not timestamp_str:
                continue

            try:
                # Parse timestamp
                if "T" in timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                else:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

                hour = timestamp.hour

                # Find corresponding closed trade if exists
                order_id = trade.get("order_id", "")
                closed_trade = None
                if order_id:
                    closed_trade = next(
                        (ct for ct in closed_trades if ct.get("order_id") == order_id),
                        None,
                    )

                hour_trades[hour].append(
                    {
                        "trade": trade,
                        "closed_trade": closed_trade,
                    }
                )
            except Exception:
                continue

        # Calculate metrics per hour
        by_hour = {}

        for hour, hour_data in hour_trades.items():
            trades = [d["trade"] for d in hour_data]
            closed = [d["closed_trade"] for d in hour_data if d["closed_trade"]]

            total_pl = sum(ct.get("pl", 0) for ct in closed)
            avg_pl = total_pl / len(closed) if closed else 0.0
            winning = [ct for ct in closed if ct.get("pl", 0) > 0]
            win_rate = (len(winning) / len(closed) * 100) if closed else 0.0

            by_hour[hour] = {
                "trades": len(trades),
                "closed_trades": len(closed),
                "total_pl": total_pl,
                "avg_pl": avg_pl,
                "win_rate": win_rate,
            }

        # Find best hours (top 3 by avg_pl)
        best_hours = sorted(
            [(h, data["avg_pl"]) for h, data in by_hour.items() if data["closed_trades"] > 0],
            key=lambda x: x[1],
            reverse=True,
        )[:3]

        return {
            "by_hour": by_hour,
            "best_hours": [h for h, _ in best_hours],
        }

    def _calculate_signal_quality(
        self, all_trades: list[dict], closed_trades: list[dict]
    ) -> dict[str, Any]:
        """Calculate signal quality metrics."""
        # This is a placeholder - would need signal type data in trades
        return {
            "by_signal_type": {},
            "avg_return_1d": 0.0,
            "avg_return_5d": 0.0,
            "avg_return_20d": 0.0,
        }

    def _calculate_market_regime(self, perf_log: list[dict]) -> dict[str, Any]:
        """Detect market regime (bull/bear/sideways) based on recent performance."""
        if not perf_log or len(perf_log) < 10:
            return {
                "regime": "UNKNOWN",
                "confidence": 0.0,
                "trend_strength": 0.0,
                "volatility_regime": "NORMAL",
            }

        # Get last 20 days of returns
        recent_equity = [e.get("equity", 0) for e in perf_log[-20:]]
        if len(recent_equity) < 2:
            return {
                "regime": "UNKNOWN",
                "confidence": 0.0,
                "trend_strength": 0.0,
                "volatility_regime": "NORMAL",
            }

        # Calculate returns
        returns = []
        for i in range(1, len(recent_equity)):
            if recent_equity[i - 1] > 0:
                ret = (recent_equity[i] - recent_equity[i - 1]) / recent_equity[i - 1]
                returns.append(ret)

        if not returns:
            return {
                "regime": "UNKNOWN",
                "confidence": 0.0,
                "trend_strength": 0.0,
                "volatility_regime": "NORMAL",
            }

        # Calculate trend
        avg_return = np.mean(returns)
        std_return = np.std(returns) if len(returns) > 1 else 0.0

        # Determine regime
        if avg_return > 0.001:  # >0.1% average daily return
            regime = "BULL"
        elif avg_return < -0.001:  # <-0.1% average daily return
            regime = "BEAR"
        else:
            regime = "SIDEWAYS"

        # Trend strength (0-1)
        trend_strength = min(abs(avg_return) / 0.01, 1.0) if std_return > 0 else 0.0

        # Volatility regime
        if std_return > 0.02:  # >2% daily volatility
            vol_regime = "HIGH"
        elif std_return < 0.005:  # <0.5% daily volatility
            vol_regime = "LOW"
        else:
            vol_regime = "NORMAL"

        # Confidence based on consistency
        positive_days = sum(1 for r in returns if r > 0)
        confidence = abs(positive_days / len(returns) - 0.5) * 2  # 0-1 scale

        return {
            "regime": regime,
            "confidence": confidence,
            "trend_strength": trend_strength,
            "volatility_regime": vol_regime,
            "avg_daily_return": avg_return * 100,
            "volatility": std_return * 100,
        }

    def _calculate_benchmark_comparison(
        self, perf_log: list[dict], starting_balance: float
    ) -> dict[str, Any]:
        """Compare portfolio performance to S&P 500 benchmark."""
        if not perf_log or len(perf_log) < 2:
            return {
                "benchmark_symbol": "SPY",
                "portfolio_return": 0.0,
                "benchmark_return": 0.0,
                "alpha": 0.0,
                "beta": 0.0,
                "outperformance": 0.0,
                "data_available": False,
            }

        # Calculate portfolio returns
        portfolio_returns = []
        for i in range(1, len(perf_log)):
            equity_prev = perf_log[i - 1].get("equity", starting_balance)
            equity_curr = perf_log[i].get("equity", starting_balance)
            if equity_prev > 0:
                ret = (equity_curr - equity_prev) / equity_prev
                portfolio_returns.append(ret)

        if not portfolio_returns:
            return {
                "benchmark_symbol": "SPY",
                "portfolio_return": 0.0,
                "benchmark_return": 0.0,
                "alpha": 0.0,
                "beta": 0.0,
                "outperformance": 0.0,
                "data_available": False,
            }

        # Get dates for benchmark comparison
        start_date = perf_log[0].get("date", "")
        end_date = perf_log[-1].get("date", "")

        # Try to fetch SPY data
        benchmark_returns = []
        try:
            if YFINANCE_AVAILABLE and start_date and end_date:
                spy = yf.Ticker("SPY")
                hist = spy.history(start=start_date, end=end_date)
                if not hist.empty:
                    spy_returns = hist["Close"].pct_change().dropna().tolist()
                    # Align with portfolio returns (take last N days)
                    benchmark_returns = spy_returns[-len(portfolio_returns) :]
        except Exception:
            pass  # Benchmark data unavailable

        if not benchmark_returns or len(benchmark_returns) != len(portfolio_returns):
            # Calculate simple comparison
            portfolio_total_return = (
                (perf_log[-1].get("equity", starting_balance) - starting_balance)
                / starting_balance
                * 100
            )
            return {
                "benchmark_symbol": "SPY",
                "portfolio_return": portfolio_total_return,
                "benchmark_return": 0.0,
                "alpha": 0.0,
                "beta": 0.0,
                "outperformance": 0.0,
                "data_available": False,
            }

        # Calculate metrics
        portfolio_total = sum(portfolio_returns) * 100
        benchmark_total = sum(benchmark_returns) * 100
        alpha = portfolio_total - benchmark_total

        # Beta calculation (simplified)
        if len(portfolio_returns) > 1 and np.std(benchmark_returns) > 0:
            covariance = np.cov(portfolio_returns, benchmark_returns)[0][1]
            benchmark_variance = np.var(benchmark_returns)
            beta = covariance / benchmark_variance if benchmark_variance > 0 else 1.0
        else:
            beta = 1.0

        return {
            "benchmark_symbol": "SPY",
            "portfolio_return": portfolio_total,
            "benchmark_return": benchmark_total,
            "alpha": alpha,
            "beta": beta,
            "outperformance": alpha,
            "data_available": True,
        }

    def _calculate_ai_kpis(self, system_state: dict, all_trades: list[dict]) -> dict[str, Any]:
        """Calculate AI-specific KPIs."""
        # Check if AI/LLM features are enabled
        video_analysis = system_state.get("video_analysis", {})

        # Estimate AI costs (if LLM features enabled)
        ai_enabled = video_analysis.get("enabled", False)

        # Calculate prediction accuracy (if we have signal data)
        # This is a placeholder - would need actual prediction vs outcome data
        prediction_accuracy = 0.0
        prediction_latency = 0.0
        ai_costs_daily = 0.0

        # Count trades that used AI signals
        ai_trades = 0
        for trade in all_trades:
            if trade.get("signal_source") == "ai" or trade.get("llm_analysis"):
                ai_trades += 1

        return {
            "ai_enabled": ai_enabled,
            "prediction_accuracy": prediction_accuracy,
            "prediction_latency_ms": prediction_latency,
            "ai_costs_daily": ai_costs_daily,
            "ai_trades_count": ai_trades,
            "total_trades": len(all_trades),
            "ai_usage_rate": (ai_trades / len(all_trades) * 100) if all_trades else 0.0,
            "outlier_detection_enabled": False,  # Placeholder
            "backtest_vs_live_performance": 0.0,  # Placeholder
        }

    def _calculate_automation_status(
        self, system_state: dict, perf_log: list[dict]
    ) -> dict[str, Any]:
        """Calculate automation uptime and reliability metrics."""
        automation = system_state.get("automation", {})

        # Calculate uptime
        workflow_status = automation.get("workflow_status", "UNKNOWN")
        last_execution = automation.get("last_successful_execution", "Never")
        execution_count = automation.get("execution_count", 0)
        failures = automation.get("failures", 0)

        # Calculate uptime percentage
        if execution_count + failures > 0:
            uptime_pct = (execution_count / (execution_count + failures)) * 100
        else:
            uptime_pct = 100.0 if workflow_status == "OPERATIONAL" else 0.0

        # Calculate days since last execution
        days_since_execution = 0
        if last_execution != "Never":
            try:
                last_dt = datetime.fromisoformat(last_execution.replace("Z", "+00:00"))
                days_since_execution = (datetime.now() - last_dt.replace(tzinfo=None)).days
            except Exception:
                pass

        # Calculate reliability streak
        reliability_streak = execution_count if failures == 0 else 0

        return {
            "workflow_status": workflow_status,
            "uptime_percentage": uptime_pct,
            "execution_count": execution_count,
            "failures": failures,
            "reliability_streak": reliability_streak,
            "last_execution": last_execution,
            "days_since_execution": days_since_execution,
            "is_operational": workflow_status == "OPERATIONAL",
        }

    def _calculate_journal_summary(self) -> dict[str, Any]:
        """Calculate trading journal summary metrics."""
        journal_dir = DATA_DIR / "journal"
        if not journal_dir.exists():
            return {
                "total_entries": 0,
                "entries_with_notes": 0,
                "recent_entries": [],
            }

        # Count journal entries
        journal_files = list(journal_dir.glob("*.json"))
        total_entries = len(journal_files)

        # Count entries with notes
        entries_with_notes = 0
        recent_entries = []

        for journal_file in sorted(journal_files, key=lambda x: x.stat().st_mtime, reverse=True)[
            :5
        ]:
            try:
                with open(journal_file) as f:
                    entry = json.load(f)
                    if entry.get("notes"):
                        entries_with_notes += 1
                    recent_entries.append(
                        {
                            "trade_id": entry.get("trade_id", ""),
                            "symbol": entry.get("symbol", ""),
                            "date": entry.get("entry", {}).get("timestamp", ""),
                            "has_notes": bool(entry.get("notes")),
                        }
                    )
            except Exception:
                pass

        return {
            "total_entries": total_entries,
            "entries_with_notes": entries_with_notes,
            "notes_rate": (
                (entries_with_notes / total_entries * 100) if total_entries > 0 else 0.0
            ),
            "recent_entries": recent_entries[:5],
        }

    def _calculate_execution_metrics(self, all_trades: list[dict]) -> dict[str, Any]:
        """Calculate execution quality metrics (slippage, latency, fill quality)."""
        if not all_trades:
            return {
                "avg_slippage": 0.0,
                "fill_quality": 0.0,
                "order_success_rate": 0.0,
                "order_reject_rate": 0.0,
                "avg_fill_time_ms": 0.0,
                "broker_latency_ms": 0.0,
            }

        # Calculate order success/reject rates
        total_orders = len(all_trades)
        successful_orders = sum(
            1
            for t in all_trades
            if t.get("status") == "filled"
            or t.get("status") == "accepted"
            or t.get("status") == "executed"
        )
        rejected_orders = sum(
            1
            for t in all_trades
            if t.get("status") == "rejected"
            or t.get("status") == "canceled"
            or t.get("status") == "cancelled"
        )

        success_rate = (successful_orders / total_orders * 100) if total_orders > 0 else 0.0
        reject_rate = (rejected_orders / total_orders * 100) if total_orders > 0 else 0.0

        # Calculate real slippage from order data (fill price vs intended price)
        slippage_estimates = []
        for trade in all_trades:
            if trade.get("status") in ["filled", "executed"]:
                # Use real slippage if available
                slippage_pct = trade.get("slippage_pct")
                if slippage_pct is not None:
                    slippage_estimates.append(abs(slippage_pct))
                elif trade.get("filled_avg_price") and trade.get("intended_price"):
                    # Calculate slippage from fill vs intended
                    filled = trade.get("filled_avg_price")
                    intended = trade.get("intended_price")
                    if filled and intended and intended > 0:
                        slippage = abs((filled - intended) / intended) * 100
                        slippage_estimates.append(slippage)
                else:
                    # Fallback: estimate based on order size (less accurate)
                    amount = trade.get("amount", 0) or trade.get("qty", 0) * trade.get("price", 0)
                    if amount < 100:
                        slippage_estimates.append(0.1)  # 0.1% estimate for small orders
                    elif amount < 1000:
                        slippage_estimates.append(0.2)  # 0.2% estimate for medium orders
                    else:
                        slippage_estimates.append(0.3)  # 0.3% estimate for larger orders

        avg_slippage = np.mean(slippage_estimates) if slippage_estimates else None
        has_real_slippage = any(
            t.get("slippage_pct") is not None
            or (t.get("filled_avg_price") and t.get("intended_price"))
            for t in all_trades
            if t.get("status") in ["filled", "executed"]
        )

        if avg_slippage is None:
            avg_slippage = 0.0  # No data available

        # Fill quality (inverse of slippage, 0-100 scale)
        fill_quality = max(0, 100 - (avg_slippage * 10))

        # Estimate fill time (would need actual timestamps)
        # Placeholder: assume 150ms average for market orders
        avg_fill_time_ms = 150.0
        broker_latency_ms = 50.0  # Placeholder: broker latency

        return {
            "avg_slippage": avg_slippage,
            "slippage_is_real": has_real_slippage,  # Flag indicating if real or estimated
            "fill_quality": fill_quality,
            "order_success_rate": success_rate,
            "order_reject_rate": reject_rate,
            "avg_fill_time_ms": avg_fill_time_ms,
            "broker_latency_ms": broker_latency_ms,
        }

    def _calculate_compliance_metrics(
        self, system_state: dict, perf_log: list[dict], all_trades: list[dict]
    ) -> dict[str, Any]:
        """Calculate risk management and compliance metrics."""
        account = system_state.get("account", {})
        current_equity = account.get("current_equity", 100000.0)
        starting_balance = account.get("starting_balance", 100000.0)

        # Capital usage
        total_invested = sum(t.get("amount", 0) for t in all_trades)
        capital_usage_pct = (
            (total_invested / starting_balance * 100) if starting_balance > 0 else 0.0
        )

        # Stop-loss adherence (check if trades have stop-losses)
        trades_with_stop_loss = sum(1 for t in all_trades if t.get("stop_loss"))
        stop_loss_adherence = (trades_with_stop_loss / len(all_trades) * 100) if all_trades else 0.0

        # Position size compliance
        max_position_size = (
            max((t.get("amount", 0) / current_equity * 100) for t in all_trades)
            if all_trades
            else 0.0
        )
        max_position_limit = 10.0  # 10% limit
        position_size_compliant = max_position_size <= max_position_limit

        # Audit trail availability
        audit_trail_dir = DATA_DIR / "audit_trail"
        audit_files = list(audit_trail_dir.glob("*.json")) if audit_trail_dir.exists() else []
        audit_trail_count = len(audit_files)

        return {
            "capital_usage_pct": capital_usage_pct,
            "capital_limit_pct": 100.0,
            "capital_compliant": capital_usage_pct <= 100.0,
            "stop_loss_adherence_pct": stop_loss_adherence,
            "trades_with_stop_loss": trades_with_stop_loss,
            "position_size_compliant": position_size_compliant,
            "max_position_size_pct": max_position_size,
            "max_position_limit_pct": max_position_limit,
            "audit_trail_count": audit_trail_count,
            "audit_trail_available": audit_trail_count > 0,
        }


if __name__ == "__main__":
    calculator = TradingMetricsCalculator()
    metrics = calculator.calculate_all_metrics()

    print("=" * 70)
    print("WORLD-CLASS TRADING METRICS")
    print("=" * 70)
    print(json.dumps(metrics, indent=2, default=str))
