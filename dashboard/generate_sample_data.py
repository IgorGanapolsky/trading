#!/usr/bin/env python3
"""
Generate Sample Data for Dashboard Testing

This script generates realistic sample data for testing the trading dashboard.
Run this script to populate the data directory with sample trades, performance
metrics, positions, alerts, and system status.

Usage:
    python dashboard/generate_sample_data.py

Author: Trading System
Date: 2025-10-28
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from dashboard.data_exporter import DashboardExporter


def generate_realistic_trades(num_trades: int = 100):
    """Generate realistic trade data."""
    symbols = [
        "AAPL",
        "GOOGL",
        "MSFT",
        "TSLA",
        "AMZN",
        "NVDA",
        "META",
        "JPM",
        "V",
        "WMT",
    ]
    strategies = ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]
    sides = ["BUY", "SELL"]

    trades = []
    current_time = datetime.now()

    for i in range(num_trades):
        # Create trades going back in time
        trade_time = current_time - timedelta(hours=random.randint(0, 168))  # Last week

        symbol = random.choice(symbols)
        side = random.choice(sides)
        quantity = round(random.uniform(1, 20), 2)
        price = random.uniform(50, 500)
        amount = quantity * price
        strategy = random.choice(strategies)

        # Generate realistic P/L based on strategy tier
        strategy_tier = int(strategy.split()[1])
        base_pnl = random.gauss(0, 100)
        tier_multiplier = {1: 1.5, 2: 1.2, 3: 1.0, 4: 0.8}
        pnl = base_pnl * tier_multiplier[strategy_tier]

        trades.append(
            {
                "timestamp": trade_time.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": round(price, 2),
                "amount": round(amount, 2),
                "strategy": strategy,
                "pnl": round(pnl, 2),
                "status": "FILLED",
            }
        )

    return sorted(trades, key=lambda x: x["timestamp"], reverse=True)


def generate_realistic_performance(trades):
    """Generate realistic performance metrics based on trades."""
    # Calculate strategy performance
    strategies = {}
    for trade in trades:
        strategy = trade["strategy"]
        if strategy not in strategies:
            strategies[strategy] = {"pnl": 0.0, "trades": 0, "wins": 0}

        strategies[strategy]["pnl"] += trade["pnl"]
        strategies[strategy]["trades"] += 1
        if trade["pnl"] > 0:
            strategies[strategy]["wins"] += 1

    # Calculate win rates
    for strategy in strategies:
        total = strategies[strategy]["trades"]
        wins = strategies[strategy]["wins"]
        strategies[strategy]["win_rate"] = (wins / total * 100) if total > 0 else 0

    # Calculate totals
    total_pnl = sum(s["pnl"] for s in strategies.values())
    initial_capital = 100000
    total_value = initial_capital + total_pnl
    equity = total_value * 0.65
    cash = total_value * 0.35

    # Calculate daily P/L (last 24 hours)
    yesterday = datetime.now() - timedelta(hours=24)
    recent_trades = [
        t
        for t in trades
        if datetime.strptime(t["timestamp"], "%Y-%m-%d %H:%M:%S") > yesterday
    ]
    daily_pnl = sum(t["pnl"] for t in recent_trades)

    # Generate equity curve (last 30 days)
    equity_curve = []
    daily_pnl_history = []
    current_equity = initial_capital

    for i in range(30, -1, -1):
        date = datetime.now() - timedelta(days=i)
        daily_change = random.gauss(300, 500)  # Average $300 gain per day with variance
        current_equity += daily_change

        equity_curve.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "equity": round(max(current_equity, initial_capital * 0.95), 2),
            }
        )

        daily_pnl_history.append(
            {"date": date.strftime("%Y-%m-%d"), "pnl": round(daily_change, 2)}
        )

    # Format strategy data
    strategy_data = {}
    for name, data in strategies.items():
        strategy_data[name] = {
            "pnl": round(data["pnl"], 2),
            "trades": data["trades"],
            "win_rate": round(data["win_rate"], 2),
        }

    return {
        "total_value": round(total_value, 2),
        "cash": round(cash, 2),
        "equity": round(equity, 2),
        "daily_pnl": round(daily_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round((total_pnl / initial_capital * 100), 2),
        "strategies": strategy_data,
        "equity_curve": equity_curve,
        "daily_pnl_history": daily_pnl_history,
    }


def generate_realistic_positions():
    """Generate realistic current positions."""
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA", "AMZN"]
    positions = []

    for symbol in symbols[: random.randint(3, 6)]:
        quantity = round(random.uniform(5, 25), 2)
        avg_entry = random.uniform(100, 500)
        # Current price varies from entry by -5% to +10%
        price_change = random.uniform(-0.05, 0.10)
        current_price = avg_entry * (1 + price_change)

        cost_basis = quantity * avg_entry
        market_value = quantity * current_price
        unrealized_pnl = market_value - cost_basis
        unrealized_pnl_pct = (
            (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
        )

        positions.append(
            {
                "symbol": symbol,
                "quantity": round(quantity, 2),
                "avg_entry_price": round(avg_entry, 2),
                "current_price": round(current_price, 2),
                "market_value": round(market_value, 2),
                "cost_basis": round(cost_basis, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            }
        )

    return positions


def generate_realistic_alerts():
    """Generate realistic alert history."""
    alerts = []
    severities = ["INFO", "WARNING", "CRITICAL"]
    messages = {
        "INFO": [
            "Trading session started",
            "Daily P/L milestone reached",
            "Position opened successfully",
            "Target profit achieved",
        ],
        "WARNING": [
            "Consecutive losses: 3",
            "Position size approaching limit",
            "High volatility detected",
            "Slippage exceeds normal range",
        ],
        "CRITICAL": [
            "Circuit breaker triggered",
            "Daily loss limit approaching",
            "System health degraded",
            "API connection issue",
        ],
    }

    # Generate 10-15 recent alerts
    for i in range(random.randint(10, 15)):
        hours_ago = random.uniform(0.5, 72)  # Last 3 days
        timestamp = datetime.now() - timedelta(hours=hours_ago)

        severity = random.choice(severities)
        message = random.choice(messages[severity])

        alert = {
            "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "severity": severity,
            "message": message,
            "details": {},
        }

        # Add specific details based on message
        if "Consecutive losses" in message:
            alert["details"] = {"consecutive_losses": 3}
        elif "Position size" in message:
            alert["details"] = {"position_size_pct": 9.5}
        elif "P/L" in message:
            alert["details"] = {"pnl": random.uniform(500, 2000)}

        alerts.append(alert)

    return sorted(alerts, key=lambda x: x["timestamp"], reverse=True)


def generate_realistic_system_status():
    """Generate realistic system status."""
    # Mostly healthy system
    is_healthy = random.random() > 0.2  # 80% chance of healthy system

    if is_healthy:
        trading_enabled = True
        breakers = {
            "daily_loss_breaker": False,
            "drawdown_breaker": False,
            "consecutive_loss_breaker": False,
        }
        health = "HEALTHY"
    else:
        trading_enabled = False
        breakers = {
            "daily_loss_breaker": random.choice([True, False]),
            "drawdown_breaker": random.choice([True, False]),
            "consecutive_loss_breaker": random.choice([True, False]),
        }
        health = "WARNING"

    return {
        "trading_enabled": trading_enabled,
        "circuit_breakers": breakers,
        "system_health": health,
        "active_strategies": ["Tier 1", "Tier 2", "Tier 3", "Tier 4"],
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def main():
    """Generate and export all sample data."""
    print("=" * 70)
    print("GENERATING SAMPLE DATA FOR DASHBOARD")
    print("=" * 70)
    print()

    # Initialize exporter
    data_dir = Path(__file__).parent.parent / "data"
    exporter = DashboardExporter(str(data_dir))

    print(f"Data directory: {data_dir}")
    print()

    # Generate data
    print("Generating trades...")
    trades = generate_realistic_trades(num_trades=100)
    print(f"  Generated {len(trades)} trades")

    print("Generating performance metrics...")
    performance = generate_realistic_performance(trades)
    print(f"  Total P/L: ${performance['total_pnl']:,.2f}")
    print(f"  Total Value: ${performance['total_value']:,.2f}")

    print("Generating positions...")
    positions = generate_realistic_positions()
    print(f"  Generated {len(positions)} positions")

    print("Generating alerts...")
    alerts = generate_realistic_alerts()
    print(f"  Generated {len(alerts)} alerts")

    print("Generating system status...")
    status = generate_realistic_system_status()
    print(f"  System health: {status['system_health']}")
    print()

    # Export all data
    print("Exporting data to files...")
    exporter.export_all(
        trades=trades,
        performance=performance,
        positions=positions,
        alerts=alerts,
        status=status,
    )

    print()
    print("=" * 70)
    print("SAMPLE DATA GENERATION COMPLETED!")
    print("=" * 70)
    print()
    print("You can now run the dashboard with:")
    print("  streamlit run dashboard/dashboard.py")
    print()
    print("Or use the launch script:")
    print("  ./dashboard/run_dashboard.sh")
    print()


if __name__ == "__main__":
    main()
