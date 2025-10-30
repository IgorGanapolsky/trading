"""
Dashboard Data Exporter

This module provides functions to export trading system data to formats
that can be consumed by the dashboard. Use this to integrate your live
trading system with the monitoring dashboard.

Features:
- Export trades to CSV
- Export performance metrics to JSON
- Export positions to CSV
- Export alerts to JSON
- Export system status to JSON

Usage:
    from dashboard.data_exporter import DashboardExporter

    exporter = DashboardExporter(data_dir='data/')
    exporter.export_all(trades, performance, positions, alerts, status)

Author: Trading System
Date: 2025-10-28
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class DashboardExporter:
    """Exports trading system data for dashboard consumption."""

    def __init__(self, data_dir: str = "data/"):
        """
        Initialize the data exporter.

        Args:
            data_dir: Directory where data files will be saved
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.trades_file = self.data_dir / "trades.csv"
        self.performance_file = self.data_dir / "performance.json"
        self.positions_file = self.data_dir / "positions.csv"
        self.alerts_file = self.data_dir / "alerts.json"
        self.system_status_file = self.data_dir / "system_status.json"

    def export_trades(self, trades: List[Dict]) -> None:
        """
        Export trades to CSV file.

        Args:
            trades: List of trade dictionaries with required fields:
                - timestamp: Trade timestamp (str or datetime)
                - symbol: Trading symbol
                - side: BUY or SELL
                - quantity: Number of shares
                - price: Execution price
                - amount: Total dollar amount
                - strategy: Strategy name (e.g., 'Tier 1')
                - pnl: Profit/loss for the trade
                - status: Order status (e.g., 'FILLED')

        Example:
            trades = [
                {
                    'timestamp': '2025-10-28 10:30:00',
                    'symbol': 'AAPL',
                    'side': 'BUY',
                    'quantity': 10,
                    'price': 175.50,
                    'amount': 1755.00,
                    'strategy': 'Tier 1',
                    'pnl': 0.0,
                    'status': 'FILLED'
                }
            ]
            exporter.export_trades(trades)
        """
        try:
            df = pd.DataFrame(trades)

            # Ensure required columns exist
            required_cols = [
                "timestamp",
                "symbol",
                "side",
                "quantity",
                "price",
                "amount",
                "strategy",
                "pnl",
                "status",
            ]

            for col in required_cols:
                if col not in df.columns:
                    df[col] = None

            # Convert timestamp to datetime if needed
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"])

            # Sort by timestamp
            df = df.sort_values("timestamp", ascending=False)

            # Save to CSV
            df.to_csv(self.trades_file, index=False)
            print(f"[EXPORTER] Exported {len(trades)} trades to {self.trades_file}")

        except Exception as e:
            print(f"[EXPORTER] Error exporting trades: {e}")

    def export_performance(self, performance: Dict) -> None:
        """
        Export performance metrics to JSON file.

        Args:
            performance: Performance dictionary with required fields:
                - total_value: Total portfolio value
                - cash: Available cash
                - equity: Total equity value
                - daily_pnl: Today's profit/loss
                - total_pnl: Total profit/loss
                - total_pnl_pct: Total P/L percentage
                - strategies: Dict of strategy performance
                - equity_curve: List of equity history
                - daily_pnl_history: List of daily P/L

        Example:
            performance = {
                'total_value': 125000.0,
                'cash': 45000.0,
                'equity': 80000.0,
                'daily_pnl': 1250.75,
                'total_pnl': 25000.0,
                'total_pnl_pct': 25.0,
                'strategies': {
                    'Tier 1': {'pnl': 8500.0, 'trades': 45, 'win_rate': 62.5}
                },
                'equity_curve': [
                    {'date': '2025-10-28', 'equity': 125000.0}
                ],
                'daily_pnl_history': [
                    {'date': '2025-10-28', 'pnl': 1250.75}
                ]
            }
            exporter.export_performance(performance)
        """
        try:
            # Ensure required fields exist
            default_performance = {
                "total_value": 0.0,
                "cash": 0.0,
                "equity": 0.0,
                "daily_pnl": 0.0,
                "total_pnl": 0.0,
                "total_pnl_pct": 0.0,
                "strategies": {},
                "equity_curve": [],
                "daily_pnl_history": [],
            }

            # Merge with defaults
            export_data = {**default_performance, **performance}

            # Add metadata
            export_data["last_updated"] = datetime.now().isoformat()

            # Save to JSON
            with open(self.performance_file, "w") as f:
                json.dump(export_data, f, indent=2)

            print(f"[EXPORTER] Exported performance metrics to {self.performance_file}")

        except Exception as e:
            print(f"[EXPORTER] Error exporting performance: {e}")

    def export_positions(self, positions: List[Dict]) -> None:
        """
        Export current positions to CSV file.

        Args:
            positions: List of position dictionaries with required fields:
                - symbol: Trading symbol
                - quantity: Number of shares held
                - avg_entry_price: Average entry price
                - current_price: Current market price
                - market_value: Current market value
                - cost_basis: Total cost basis
                - unrealized_pnl: Unrealized profit/loss
                - unrealized_pnl_pct: Unrealized P/L percentage

        Example:
            positions = [
                {
                    'symbol': 'AAPL',
                    'quantity': 15.5,
                    'avg_entry_price': 175.20,
                    'current_price': 182.30,
                    'market_value': 2825.65,
                    'cost_basis': 2715.60,
                    'unrealized_pnl': 110.05,
                    'unrealized_pnl_pct': 4.05
                }
            ]
            exporter.export_positions(positions)
        """
        try:
            df = pd.DataFrame(positions)

            # Ensure required columns exist
            required_cols = [
                "symbol",
                "quantity",
                "avg_entry_price",
                "current_price",
                "market_value",
                "cost_basis",
                "unrealized_pnl",
                "unrealized_pnl_pct",
            ]

            for col in required_cols:
                if col not in df.columns:
                    df[col] = 0.0

            # Save to CSV
            df.to_csv(self.positions_file, index=False)
            print(
                f"[EXPORTER] Exported {len(positions)} positions to {self.positions_file}"
            )

        except Exception as e:
            print(f"[EXPORTER] Error exporting positions: {e}")

    def export_alerts(self, alerts: List[Dict]) -> None:
        """
        Export alert history to JSON file.

        Args:
            alerts: List of alert dictionaries with required fields:
                - timestamp: Alert timestamp
                - severity: INFO, WARNING, or CRITICAL
                - message: Alert message
                - details: Additional details dictionary

        Example:
            alerts = [
                {
                    'timestamp': '2025-10-28 10:30:00',
                    'severity': 'WARNING',
                    'message': 'Consecutive losses: 3',
                    'details': {'consecutive_losses': 3}
                }
            ]
            exporter.export_alerts(alerts)
        """
        try:
            # Ensure required fields
            for alert in alerts:
                if "timestamp" not in alert:
                    alert["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if "severity" not in alert:
                    alert["severity"] = "INFO"
                if "details" not in alert:
                    alert["details"] = {}

            # Save to JSON
            with open(self.alerts_file, "w") as f:
                json.dump(alerts, f, indent=2)

            print(f"[EXPORTER] Exported {len(alerts)} alerts to {self.alerts_file}")

        except Exception as e:
            print(f"[EXPORTER] Error exporting alerts: {e}")

    def export_system_status(self, status: Dict) -> None:
        """
        Export system status to JSON file.

        Args:
            status: System status dictionary with required fields:
                - trading_enabled: Boolean indicating if trading is active
                - circuit_breakers: Dict of circuit breaker states
                - system_health: System health status (HEALTHY, WARNING, ERROR)
                - active_strategies: List of active strategy names
                - last_update: Last update timestamp

        Example:
            status = {
                'trading_enabled': True,
                'circuit_breakers': {
                    'daily_loss_breaker': False,
                    'drawdown_breaker': False,
                    'consecutive_loss_breaker': False
                },
                'system_health': 'HEALTHY',
                'active_strategies': ['Tier 1', 'Tier 2', 'Tier 3', 'Tier 4']
            }
            exporter.export_system_status(status)
        """
        try:
            # Ensure required fields
            default_status = {
                "trading_enabled": False,
                "circuit_breakers": {
                    "daily_loss_breaker": False,
                    "drawdown_breaker": False,
                    "consecutive_loss_breaker": False,
                },
                "system_health": "UNKNOWN",
                "active_strategies": [],
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            # Merge with defaults
            export_data = {**default_status, **status}
            export_data["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Save to JSON
            with open(self.system_status_file, "w") as f:
                json.dump(export_data, f, indent=2)

            print(f"[EXPORTER] Exported system status to {self.system_status_file}")

        except Exception as e:
            print(f"[EXPORTER] Error exporting system status: {e}")

    def export_all(
        self,
        trades: Optional[List[Dict]] = None,
        performance: Optional[Dict] = None,
        positions: Optional[List[Dict]] = None,
        alerts: Optional[List[Dict]] = None,
        status: Optional[Dict] = None,
    ) -> None:
        """
        Export all data types at once.

        Args:
            trades: List of trade dictionaries (optional)
            performance: Performance metrics dictionary (optional)
            positions: List of position dictionaries (optional)
            alerts: List of alert dictionaries (optional)
            status: System status dictionary (optional)

        Example:
            exporter.export_all(
                trades=trades_list,
                performance=performance_dict,
                positions=positions_list,
                alerts=alerts_list,
                status=status_dict
            )
        """
        print("[EXPORTER] Starting data export...")

        if trades is not None:
            self.export_trades(trades)

        if performance is not None:
            self.export_performance(performance)

        if positions is not None:
            self.export_positions(positions)

        if alerts is not None:
            self.export_alerts(alerts)

        if status is not None:
            self.export_system_status(status)

        print("[EXPORTER] Data export completed")


def export_from_alpaca_trader(trader, risk_manager, exporter):
    """
    Helper function to export data from AlpacaTrader and RiskManager.

    Args:
        trader: AlpacaTrader instance
        risk_manager: RiskManager instance
        exporter: DashboardExporter instance

    Example:
        from src.core.alpaca_trader import AlpacaTrader
        from src.core.risk_manager import RiskManager
        from dashboard.data_exporter import DashboardExporter, export_from_alpaca_trader

        trader = AlpacaTrader(paper=True)
        risk_mgr = RiskManager()
        exporter = DashboardExporter()

        export_from_alpaca_trader(trader, risk_mgr, exporter)
    """
    try:
        # Get positions from trader
        positions_data = trader.get_positions()
        if positions_data:
            exporter.export_positions(positions_data)

        # Get performance from trader
        performance_data = trader.get_portfolio_performance()
        if performance_data:
            # Convert to dashboard format
            dashboard_performance = {
                "total_value": performance_data.get("portfolio_value", 0),
                "cash": performance_data.get("cash", 0),
                "equity": performance_data.get("equity", 0),
                "daily_pnl": performance_data.get("profit_loss", 0),
                "total_pnl": performance_data.get("profit_loss", 0),
                "total_pnl_pct": performance_data.get("profit_loss_pct", 0),
                "strategies": {},  # Would need to track separately
                "equity_curve": [],  # Would need to track over time
                "daily_pnl_history": [],  # Would need to track over time
            }
            exporter.export_performance(dashboard_performance)

        # Get risk metrics
        risk_metrics = risk_manager.get_risk_metrics()

        # Export alerts
        if "alerts" in risk_metrics:
            exporter.export_alerts(risk_metrics["alerts"])

        # Export system status
        status = {
            "trading_enabled": not risk_metrics["account_metrics"][
                "circuit_breaker_triggered"
            ],
            "circuit_breakers": {
                "daily_loss_breaker": risk_metrics["account_metrics"][
                    "circuit_breaker_triggered"
                ],
                "drawdown_breaker": False,
                "consecutive_loss_breaker": risk_metrics["trade_statistics"][
                    "consecutive_losses"
                ]
                >= risk_metrics["risk_limits"]["max_consecutive_losses_limit"],
            },
            "system_health": (
                "HEALTHY"
                if not risk_metrics["account_metrics"]["circuit_breaker_triggered"]
                else "WARNING"
            ),
            "active_strategies": ["Tier 1", "Tier 2", "Tier 3", "Tier 4"],
        }
        exporter.export_system_status(status)

        print("[EXPORTER] Successfully exported data from trading system")

    except Exception as e:
        print(f"[EXPORTER] Error exporting from trading system: {e}")


# Example usage and testing
if __name__ == "__main__":
    print("=" * 70)
    print("DASHBOARD DATA EXPORTER - Example Usage")
    print("=" * 70)

    # Initialize exporter
    exporter = DashboardExporter(data_dir="../data/")

    # Example trades
    sample_trades = [
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 10,
            "price": 175.50,
            "amount": 1755.00,
            "strategy": "Tier 1",
            "pnl": 55.25,
            "status": "FILLED",
        },
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": "GOOGL",
            "side": "BUY",
            "quantity": 5,
            "price": 138.20,
            "amount": 691.00,
            "strategy": "Tier 2",
            "pnl": 22.50,
            "status": "FILLED",
        },
    ]

    # Example performance
    sample_performance = {
        "total_value": 125000.0,
        "cash": 45000.0,
        "equity": 80000.0,
        "daily_pnl": 1250.75,
        "total_pnl": 25000.0,
        "total_pnl_pct": 25.0,
        "strategies": {
            "Tier 1": {"pnl": 8500.0, "trades": 45, "win_rate": 62.5},
            "Tier 2": {"pnl": 6200.0, "trades": 38, "win_rate": 58.3},
        },
        "equity_curve": [{"date": "2025-10-28", "equity": 125000.0}],
        "daily_pnl_history": [{"date": "2025-10-28", "pnl": 1250.75}],
    }

    # Example positions
    sample_positions = [
        {
            "symbol": "AAPL",
            "quantity": 15.5,
            "avg_entry_price": 175.20,
            "current_price": 182.30,
            "market_value": 2825.65,
            "cost_basis": 2715.60,
            "unrealized_pnl": 110.05,
            "unrealized_pnl_pct": 4.05,
        }
    ]

    # Example alerts
    sample_alerts = [
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "severity": "INFO",
            "message": "Trading session started",
            "details": {},
        }
    ]

    # Example system status
    sample_status = {
        "trading_enabled": True,
        "circuit_breakers": {
            "daily_loss_breaker": False,
            "drawdown_breaker": False,
            "consecutive_loss_breaker": False,
        },
        "system_health": "HEALTHY",
        "active_strategies": ["Tier 1", "Tier 2", "Tier 3", "Tier 4"],
    }

    # Export all data
    exporter.export_all(
        trades=sample_trades,
        performance=sample_performance,
        positions=sample_positions,
        alerts=sample_alerts,
        status=sample_status,
    )

    print("\n" + "=" * 70)
    print("Example completed successfully!")
    print("Check the ../data/ directory for exported files")
    print("=" * 70)
