# Trading System Orchestrator

The main orchestrator (`src/main.py`) is the entry point that coordinates all trading strategies on a defined schedule.

## Overview

The orchestrator manages three trading strategies:
- **CoreStrategy (Tier 1)**: Daily momentum index investing (60% allocation)
- **GrowthStrategy (Tier 2)**: Weekly stock picking (20% allocation)
- **IPOStrategy (Tier 3)**: IPO analysis and tracking (10% allocation)

## Features

- **Scheduled Execution**: Automated strategy execution at market hours
- **Risk Management**: Circuit breakers and position sizing
- **Health Monitoring**: Continuous health checks and status reporting
- **Error Handling**: Comprehensive logging and alert system
- **Graceful Shutdown**: Signal handling for clean termination
- **Testing Mode**: Run-once mode for strategy testing

## Prerequisites

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. **Required API Keys**
   - Alpaca API key and secret (for trading)
   - OpenRouter API key (for LLM analysis)

## Usage

### Scheduled Mode (Production)

Run the orchestrator in continuous mode with scheduled execution:

```bash
# Paper trading (default)
python src/main.py --mode paper

# Live trading (requires confirmation)
python src/main.py --mode live
```

### Manual Execution Mode (Testing)

Execute strategies once and exit:

```bash
# Run all strategies once
python src/main.py --mode paper --run-once

# Run specific strategy
python src/main.py --mode paper --run-once --strategy core
python src/main.py --mode paper --run-once --strategy growth
python src/main.py --mode paper --run-once --strategy ipo
```

### Debug Mode

Enable verbose logging:

```bash
python src/main.py --mode paper --log-level DEBUG
```

### Custom Log Directory

Specify a different log directory:

```bash
python src/main.py --mode paper --log-dir /path/to/logs
```

## Execution Schedule

The orchestrator runs strategies on the following schedule (Eastern Time):

| Time       | Task                        | Frequency  |
|------------|----------------------------|------------|
| 9:30 AM ET | Risk counter reset         | Daily      |
| 9:35 AM ET | Core Strategy execution    | Daily      |
| 9:35 AM ET | Growth Strategy execution  | Monday     |
| 10:00 AM ET| IPO deposit tracking       | Daily      |
| 10:00 AM ET| IPO opportunity check      | Wednesday  |
| Every hour | Health status update       | Hourly     |

## Configuration

All configuration is loaded from the `.env` file:

### Trading Configuration
```env
PAPER_TRADING=true              # Use paper trading
DAILY_INVESTMENT=10.0           # Daily investment amount
```

### Tier Allocations
```env
TIER1_ALLOCATION=0.60           # Core Strategy (60%)
TIER2_ALLOCATION=0.20           # Growth Strategy (20%)
TIER3_ALLOCATION=0.10           # IPO Strategy (10%)
TIER4_ALLOCATION=0.10           # Reserved (10%)
```

### Risk Management
```env
MAX_DAILY_LOSS_PCT=2.0          # Maximum daily loss (2%)
MAX_POSITION_SIZE_PCT=10.0      # Maximum position size (10%)
MAX_DRAWDOWN_PCT=10.0           # Maximum drawdown (10%)
STOP_LOSS_PCT=5.0               # Trailing stop-loss (5%)
```

## Logging

The orchestrator creates detailed logs in the `logs/` directory:

- **trading_system.log**: Main application log with rotation (10MB max, 5 backups)
- **trading_errors.log**: Error-only log for debugging
- **Console output**: Real-time status and important events

Log rotation ensures logs don't grow unbounded.

## Health Monitoring

The orchestrator provides health status through the `get_health_status()` method:

```python
{
    'status': 'healthy',           # overall status
    'running': true,               # orchestrator running flag
    'mode': 'paper',               # trading mode
    'account_value': 10000.0,      # current portfolio value
    'buying_power': 5000.0,        # available buying power
    'daily_pl': 150.0,             # today's P&L
    'circuit_breaker': false,      # risk limit status
    'last_executions': {           # last execution times
        'core_strategy': '2025-10-28T09:35:00',
        'growth_strategy': '2025-10-28T09:35:00',
        'ipo_strategy': '2025-10-28T10:00:00'
    },
    'errors': []                   # recent errors
}
```

## Error Handling

The orchestrator includes comprehensive error handling:

1. **Strategy Errors**: Logged and alerted, but don't stop other strategies
2. **Risk Limit Breaches**: Trading automatically suspended via circuit breakers
3. **API Failures**: Retried with exponential backoff (handled by components)
4. **Graceful Shutdown**: SIGTERM/SIGINT handled cleanly

## Safety Features

1. **Circuit Breakers**: Automatic trading suspension on risk limit breach
2. **Confirmation Prompts**: Live trading requires explicit confirmation
3. **Paper Trading Default**: Always defaults to paper trading for safety
4. **Order Cancellation**: All pending orders cancelled on shutdown
5. **Risk Validation**: All trades validated before execution

## Testing

Run the test script to verify setup:

```bash
python test_main.py
```

This will verify:
- All dependencies are installed
- Imports work correctly
- Logger setup is functional

## Troubleshooting

### Import Errors
```bash
# Install dependencies
pip install -r requirements.txt
```

### API Connection Errors
```bash
# Verify .env file has correct API keys
cat .env | grep ALPACA_API_KEY
```

### Schedule Not Running
- Check timezone settings (must be America/New_York)
- Verify current time is after scheduled execution time
- Check logs for error messages

### Trading Blocked
- Check risk manager status in logs
- Verify daily loss hasn't exceeded limit
- Check account status with Alpaca

## Architecture

```
TradingOrchestrator
├── CoreStrategy (Tier 1)
│   ├── Daily execution at 9:35 AM ET
│   └── Momentum index investing (SPY, QQQ, VOO)
├── GrowthStrategy (Tier 2)
│   ├── Weekly execution on Mondays at 9:35 AM ET
│   └── S&P 500 stock picking with AI
├── IPOStrategy (Tier 3)
│   ├── Daily deposit tracking at 10:00 AM ET
│   └── Weekly opportunity check on Wednesdays
├── AlpacaTrader
│   └── Order execution and portfolio management
└── RiskManager
    └── Circuit breakers and position sizing
```

## Monitoring

For production deployment, consider:

1. **Process Management**: Use systemd or supervisor to keep orchestrator running
2. **Log Monitoring**: Set up log aggregation (ELK, Splunk, etc.)
3. **Alerting**: Configure email/webhook alerts in .env
4. **Health Checks**: Periodic health status checks via monitoring service

## Example Systemd Service

Create `/etc/systemd/system/trading-orchestrator.service`:

```ini
[Unit]
Description=Trading System Orchestrator
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/path/to/trading
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python src/main.py --mode paper
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable trading-orchestrator
sudo systemctl start trading-orchestrator
sudo systemctl status trading-orchestrator
```

## Development

To extend the orchestrator:

1. Add new strategies in `src/strategies/`
2. Import and initialize in `TradingOrchestrator.__init__()`
3. Create execution method (e.g., `_execute_new_strategy()`)
4. Add to schedule in `setup_schedule()`

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review error messages in console output
3. Verify configuration in `.env` file
4. Test with `--run-once` mode first

## License

See LICENSE file for details.
