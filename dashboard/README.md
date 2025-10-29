# Trading System Dashboard

A comprehensive real-time monitoring dashboard built with Streamlit for tracking trading operations, portfolio performance, and risk metrics.

## Features

### 1. Real-time Portfolio Metrics
- Total portfolio value with P/L tracking
- Daily profit/loss with percentage change
- Win rate calculation
- Maximum drawdown monitoring

### 2. Strategy Performance Breakdown
- Tier 1-4 strategy comparison
- Individual strategy P/L
- Trade count per strategy
- Win rate per strategy

### 3. Interactive Charts
- **Equity Curve**: Track portfolio value over time
- **Daily P/L Bar Chart**: Visualize daily profit/loss patterns
- **Position Allocation Pie Chart**: Current portfolio composition

### 4. Recent Trades Table
- Last 10 trades with timestamps
- Symbol, side, quantity, and price
- Strategy classification
- P/L per trade

### 5. Current Positions
- Real-time position tracking
- Entry price vs. current price
- Unrealized P/L (dollars and percentage)
- Market value per position

### 6. Risk Metrics
- **Sharpe Ratio**: Risk-adjusted returns
- **Profit Factor**: Ratio of gross profit to gross loss
- **Average Win/Loss**: Trade performance analysis
- **Win Rate**: Percentage of winning trades
- **Max Drawdown**: Peak-to-trough decline

### 7. Alert History
- Critical alerts (circuit breakers, limit breaches)
- Warning alerts (consecutive losses, position size warnings)
- Info alerts (milestone achievements)
- Color-coded severity levels

### 8. System Status (Sidebar)
- Trading status (active/inactive)
- Circuit breaker states
  - Daily loss breaker
  - Drawdown breaker
  - Consecutive loss breaker
- System health indicator
- Active strategies list
- Last update timestamp

### 9. Dashboard Controls
- **Auto-refresh**: Toggle automatic data updates
- **Refresh Interval**: Configure update frequency (10-300 seconds)
- **Manual Refresh**: Button for immediate update
- **Time Range Filter**: Filter trades by date range
  - Last 24 Hours
  - Last 7 Days
  - Last 30 Days
  - All Time

## Installation

### Prerequisites
```bash
# Ensure you have Python 3.8+ installed
python --version
```

### Install Required Packages
The dashboard requires the following packages (already in requirements.txt):
```bash
streamlit==1.28.0
plotly==5.17.0
pandas==2.1.0
numpy==1.25.0
```

Install all dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Dashboard

Navigate to the dashboard directory and run:
```bash
cd /Users/ganapolsky_i/workspace/git/igor/trading
streamlit run dashboard/dashboard.py
```

Or from the project root:
```bash
streamlit run dashboard/dashboard.py
```

The dashboard will automatically open in your default web browser at `http://localhost:8501`

### Data Sources

The dashboard reads from the following files in the `data/` directory:

1. **trades.csv**: Trade history
   - Required columns: timestamp, symbol, side, quantity, price, amount, strategy, pnl, status

2. **performance.json**: Performance metrics
   - total_value, cash, equity, daily_pnl, total_pnl
   - strategies breakdown
   - equity_curve array
   - daily_pnl_history array

3. **positions.csv**: Current positions
   - Required columns: symbol, quantity, avg_entry_price, current_price, market_value, cost_basis, unrealized_pnl, unrealized_pnl_pct

4. **alerts.json**: Alert history
   - Array of alert objects with timestamp, severity, message, details

5. **system_status.json**: System state
   - trading_enabled, circuit_breakers, system_health, active_strategies

### Sample Data

If data files don't exist, the dashboard will automatically generate sample data for demonstration purposes. This allows you to:
- Test the dashboard functionality
- Understand the expected data format
- Preview the dashboard before connecting real data

### Connecting Real Data

To connect your trading system to the dashboard:

1. **Create data export functions** in your trading system:
```python
import json
import pandas as pd
from pathlib import Path

def export_trades_to_csv(trades, filepath):
    """Export trades to CSV format."""
    df = pd.DataFrame(trades)
    df.to_csv(filepath, index=False)

def export_performance_to_json(performance_data, filepath):
    """Export performance metrics to JSON."""
    with open(filepath, 'w') as f:
        json.dump(performance_data, f, indent=2)
```

2. **Schedule regular exports** (e.g., every minute):
```python
import schedule
import time

def update_dashboard_data():
    """Update all dashboard data files."""
    export_trades_to_csv(get_trades(), 'data/trades.csv')
    export_performance_to_json(get_performance(), 'data/performance.json')
    # ... update other files

schedule.every(60).seconds.do(update_dashboard_data)

while True:
    schedule.run_pending()
    time.sleep(1)
```

3. **Integrate with your trading system**:
```python
from src.core.alpaca_trader import AlpacaTrader
from src.core.risk_manager import RiskManager

# After each trade
trader = AlpacaTrader()
positions = trader.get_positions()
performance = trader.get_portfolio_performance()

# Export to dashboard
export_dashboard_data(positions, performance)
```

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Trading System Dashboard                                        │
│  Last Updated: 2025-10-28 22:45:30                              │
├─────────────────────────────────────────────────────────────────┤
│  [Total Value] [Daily P/L] [Win Rate] [Max Drawdown]           │
├─────────────────────────────────────────────────────────────────┤
│  Strategy Performance Breakdown                                  │
│  ┌────────┬──────────┬────────┬──────────┐                     │
│  │Strategy│   P/L    │ Trades │ Win Rate │                     │
│  └────────┴──────────┴────────┴──────────┘                     │
├─────────────────────────────────────────────────────────────────┤
│  [Equity Curve Chart] │ [Daily P/L Bar Chart]                   │
├─────────────────────────────────────────────────────────────────┤
│  Recent Trades                                                   │
│  ┌──────────┬────────┬──────┬─────┬───────┬────────┬──────┐   │
│  │Timestamp │ Symbol │ Side │ Qty │ Price │Strategy│ P/L  │   │
│  └──────────┴────────┴──────┴─────┴───────┴────────┴──────┘   │
├─────────────────────────────────────────────────────────────────┤
│  Current Positions                                               │
│  ┌────────┬─────┬────────┬─────────┬───────┬─────────┐         │
│  │Symbol  │ Qty │ Entry  │ Current │ Value │ P/L (%) │         │
│  └────────┴─────┴────────┴─────────┴───────┴─────────┘         │
│  [Position Allocation Pie Chart]                                │
├─────────────────────────────────────────────────────────────────┤
│  Risk Metrics                                                    │
│  [Sharpe] [Profit Factor] [Avg Win] [Avg Loss] [Win Rate]      │
├─────────────────────────────────────────────────────────────────┤
│  Recent Alerts                                                   │
│  🚨 CRITICAL - Circuit breaker triggered                        │
│  ⚠️  WARNING - Consecutive losses: 3                            │
│  ℹ️  INFO - Daily P&L milestone reached                         │
└─────────────────────────────────────────────────────────────────┘

Sidebar:
┌─────────────────────────┐
│ System Status           │
│ ● Trading: ACTIVE       │
│                         │
│ Circuit Breakers        │
│ ○ Daily Loss: OK        │
│ ○ Drawdown: OK          │
│ ○ Consecutive Loss: OK  │
│                         │
│ ● System Health: HEALTHY│
│                         │
│ Active Strategies       │
│ - Tier 1                │
│ - Tier 2                │
│ - Tier 3                │
│ - Tier 4                │
│                         │
│ Controls                │
│ ☑ Auto-refresh          │
│ ⟷ Interval: 60s        │
│ [Refresh Now]           │
│                         │
│ Filters                 │
│ ⏱ Last 7 Days          │
└─────────────────────────┘
```

## Configuration

### Auto-Refresh Settings
- Default: Enabled with 60-second interval
- Range: 10-300 seconds
- Can be disabled for manual control

### Data Refresh Frequency
For production use, update data files based on your trading frequency:
- **High-frequency trading**: Every 5-10 seconds
- **Day trading**: Every 30-60 seconds
- **Swing trading**: Every 5-15 minutes

### Performance Optimization
- Use data pagination for large trade histories
- Cache expensive calculations
- Optimize Plotly chart rendering
- Consider database backend for production

## Troubleshooting

### Dashboard not loading
```bash
# Check if streamlit is installed
pip show streamlit

# Reinstall if necessary
pip install --upgrade streamlit
```

### Data not displaying
- Verify data files exist in `data/` directory
- Check file permissions
- Validate JSON/CSV format
- Review error messages in console

### Slow performance
- Reduce refresh interval
- Limit trade history displayed
- Check system resources
- Consider data aggregation

## Advanced Features

### Custom Metrics
Add custom metrics by modifying the `calculate_risk_metrics()` function:
```python
def calculate_custom_metric(trades_df):
    # Your custom calculation
    return metric_value
```

### Additional Charts
Add new visualizations:
```python
def render_custom_chart(data):
    fig = go.Figure()
    # Configure your chart
    st.plotly_chart(fig)
```

### Export Reports
Generate PDF/Excel reports:
```python
def export_report():
    # Generate report from dashboard data
    df.to_excel('report.xlsx')
```

## Security Considerations

1. **Authentication**: Add Streamlit authentication for production
2. **Data Access**: Restrict file permissions on data directory
3. **API Keys**: Never display sensitive credentials
4. **Network**: Use HTTPS in production
5. **Access Control**: Implement role-based access if needed

## Production Deployment

### Using Streamlit Cloud
```bash
# Push to GitHub
git add dashboard/
git commit -m "Add trading dashboard"
git push

# Deploy via Streamlit Cloud dashboard
# https://streamlit.io/cloud
```

### Using Docker
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "dashboard/dashboard.py"]
```

### Using systemd (Linux)
```ini
[Unit]
Description=Trading Dashboard
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/path/to/trading
ExecStart=/usr/bin/streamlit run dashboard/dashboard.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review Streamlit documentation: https://docs.streamlit.io
3. Check Plotly documentation: https://plotly.com/python/

## License

Part of the Trading System project.

## Version History

- **v1.0.0** (2025-10-28): Initial release
  - Real-time portfolio monitoring
  - Strategy performance tracking
  - Risk metrics calculation
  - Interactive charts
  - Alert system
  - Auto-refresh capability
