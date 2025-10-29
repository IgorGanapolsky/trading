# Dashboard Quick Start Guide

## Complete File Path

**Dashboard Location:** `/Users/ganapolsky_i/workspace/git/igor/trading/dashboard/dashboard.py`

## Installation & Setup

### 1. Install Dependencies

First, ensure all required packages are installed:

```bash
cd /Users/ganapolsky_i/workspace/git/igor/trading
pip install -r requirements.txt
```

The dashboard requires:
- `streamlit==1.28.0`
- `plotly==5.17.0`
- `pandas==2.1.0`
- `numpy==1.25.0`

### 2. Generate Sample Data (Optional)

To test the dashboard with sample data before connecting your live trading system:

```bash
cd /Users/ganapolsky_i/workspace/git/igor/trading
python3 dashboard/generate_sample_data.py
```

This will create sample files in the `data/` directory:
- `data/trades.csv`
- `data/performance.json`
- `data/positions.csv`
- `data/alerts.json`
- `data/system_status.json`

### 3. Launch the Dashboard

**Option A - Using the launch script:**
```bash
cd /Users/ganapolsky_i/workspace/git/igor/trading
./dashboard/run_dashboard.sh
```

**Option B - Direct streamlit command:**
```bash
cd /Users/ganapolsky_i/workspace/git/igor/trading
streamlit run dashboard/dashboard.py
```

**Option C - From anywhere:**
```bash
streamlit run /Users/ganapolsky_i/workspace/git/igor/trading/dashboard/dashboard.py
```

The dashboard will automatically open in your browser at `http://localhost:8501`

## Quick Test (Without Installation)

If you want to verify the file structure without running:

```bash
# Check the main dashboard file
ls -lh /Users/ganapolsky_i/workspace/git/igor/trading/dashboard/dashboard.py

# View the dashboard code
cat /Users/ganapolsky_i/workspace/git/igor/trading/dashboard/dashboard.py
```

## Dashboard Features

Once running, you'll see:

### Top Metrics (Row 1)
- **Total Portfolio Value** - Current total portfolio value with P/L
- **Daily P/L** - Today's profit/loss with percentage
- **Win Rate** - Percentage of winning trades
- **Max Drawdown** - Maximum peak-to-trough decline

### Strategy Performance (Row 2)
Table showing performance breakdown for Tier 1-4 strategies:
- P/L per strategy
- Number of trades
- Win rate per strategy

### Charts (Row 3)
- **Equity Curve** - Portfolio value over time (interactive)
- **Daily P/L Chart** - Bar chart of daily profit/loss

### Recent Trades (Row 4)
Table of the last 10 trades with:
- Timestamp
- Symbol, Side, Quantity, Price
- Strategy classification
- P/L per trade
- Status

### Current Positions (Row 5)
- List of all open positions
- Entry price vs current price
- Unrealized P/L ($ and %)
- Position allocation pie chart

### Risk Metrics (Row 6)
- Sharpe Ratio
- Profit Factor
- Average Win/Loss
- Win Rate
- Max Drawdown

### Alerts (Row 7)
Recent system alerts with color-coded severity:
- 🚨 Critical (red)
- ⚠️ Warning (yellow)
- ℹ️ Info (blue)

### Sidebar
- **System Status** - Trading enabled/disabled
- **Circuit Breakers** - Daily loss, drawdown, consecutive losses
- **System Health** - Overall health indicator
- **Active Strategies** - List of running strategies
- **Controls** - Auto-refresh toggle, refresh interval, manual refresh
- **Filters** - Time range selection

## Connecting Live Data

To integrate with your trading system, use the `DashboardExporter` class:

```python
from dashboard.data_exporter import DashboardExporter

# Initialize exporter
exporter = DashboardExporter(data_dir='data/')

# Export data (call this regularly, e.g., every 60 seconds)
exporter.export_all(
    trades=your_trades_list,
    performance=your_performance_dict,
    positions=your_positions_list,
    alerts=your_alerts_list,
    status=your_system_status_dict
)
```

### Example Integration

```python
import schedule
import time
from src.core.alpaca_trader import AlpacaTrader
from src.core.risk_manager import RiskManager
from dashboard.data_exporter import DashboardExporter

trader = AlpacaTrader(paper=True)
risk_mgr = RiskManager()
exporter = DashboardExporter()

def update_dashboard():
    """Update dashboard data every minute."""
    try:
        # Get current data
        positions = trader.get_positions()
        performance = trader.get_portfolio_performance()
        risk_metrics = risk_mgr.get_risk_metrics()

        # Format and export
        # ... format your data ...

        exporter.export_all(
            positions=positions,
            performance=performance,
            # ... other data ...
        )
    except Exception as e:
        print(f"Error updating dashboard: {e}")

# Schedule updates every 60 seconds
schedule.every(60).seconds.do(update_dashboard)

# Run scheduler
while True:
    schedule.run_pending()
    time.sleep(1)
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'streamlit'"
```bash
pip install streamlit plotly pandas numpy
```

### "FileNotFoundError: data/trades.csv"
The dashboard will generate sample data automatically if files don't exist.
Alternatively, run: `python3 dashboard/generate_sample_data.py`

### Dashboard won't load
- Check that you're in the project root directory
- Verify streamlit is installed: `streamlit --version`
- Check for port conflicts: `lsof -i :8501`

### Slow performance
- Reduce auto-refresh interval in sidebar
- Filter trades to shorter time range
- Check system resources

## Configuration

### Auto-Refresh
- Default: 60 seconds
- Range: 10-300 seconds
- Toggle in sidebar

### Time Range Filter
- Last 24 Hours
- Last 7 Days (default)
- Last 30 Days
- All Time

## File Structure

```
/Users/ganapolsky_i/workspace/git/igor/trading/dashboard/
├── dashboard.py              # Main dashboard application (884 lines)
├── data_exporter.py          # Data export utilities
├── generate_sample_data.py   # Sample data generator
├── run_dashboard.sh          # Launch script
├── README.md                 # Full documentation
└── QUICKSTART.md            # This file
```

## Next Steps

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Generate sample data**: `python3 dashboard/generate_sample_data.py`
3. **Launch dashboard**: `./dashboard/run_dashboard.sh`
4. **Explore the UI**: Navigate through all sections
5. **Integrate live data**: Use `DashboardExporter` to connect your trading system

## Support

- Full documentation: `dashboard/README.md`
- Data exporter examples: See `dashboard/data_exporter.py`
- Streamlit docs: https://docs.streamlit.io
- Plotly docs: https://plotly.com/python/

---

**Created:** 2025-10-28
**Status:** Production-ready
**Location:** `/Users/ganapolsky_i/workspace/git/igor/trading/dashboard/dashboard.py`
