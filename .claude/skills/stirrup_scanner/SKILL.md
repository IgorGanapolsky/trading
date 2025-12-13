# Stirrup Market Scanner Skill

## Purpose

Autonomous market scanning using Artificial Analysis' Stirrup framework. Runs independently of Claude Code sessions to provide 24/7 market monitoring.

## When to Use

- Setting up continuous market monitoring
- Running background research agents
- Generating signals while main system is idle
- Parallel multi-symbol scanning

## Installation

```bash
pip install stirrup
# Or with all extras:
pip install 'stirrup[all]'
```

Required environment variables:
- `OPENROUTER_API_KEY` - For LLM access
- `BRAVE_API_KEY` - For web search (optional)

## Quick Start

### Single Symbol Scan
```bash
python -m src.agents.stirrup_market_scanner --symbol BTCUSD --mode standard
```

### Multi-Symbol Scan
```bash
python -m src.agents.stirrup_market_scanner --symbols "BTCUSD,AAPL,SPY" --mode quick
```

### Continuous Monitoring (24/7)
```bash
python -m src.agents.stirrup_market_scanner --symbols "BTCUSD,ETHUSD" --continuous --interval 60
```

## Scan Modes

| Mode | Sources | Time | Use Case |
|------|---------|------|----------|
| `quick` | 2-3 | ~1 min | Headline check |
| `standard` | 5-7 | ~3 min | Regular scanning |
| `deep` | 10+ | ~10 min | Pre-trade research |

## Integration with Trading System

Scanner generates UDM-validated signals saved to:
```
data/scanner_signals/signal_YYYYMMDD_HHMMSS.json
```

Main trading system can consume these:
```python
from pathlib import Path
import json
from src.core.unified_domain_model import Signal

# Read latest signal
signals_dir = Path("data/scanner_signals")
latest = sorted(signals_dir.glob("*.json"))[-1]
signal_data = json.loads(latest.read_text())
```

## Custom Tools Included

| Tool | Description |
|------|-------------|
| `generate_trading_signal` | Creates UDM-validated signals |
| `check_market_status` | Checks if markets are open |

Plus all Stirrup DEFAULT_TOOLS:
- Web search and fetch
- Code execution
- Document I/O

## Architecture

```
Stirrup Agent
    │
    ├── Web Search (news, sentiment)
    │
    ├── Analysis (LLM reasoning)
    │
    └── generate_trading_signal()
            │
            └── UDM Signal (validated)
                    │
                    └── data/scanner_signals/*.json
                            │
                            └── Main Trading System
```

## Cost Optimization

Default model: `anthropic/claude-sonnet-4` via OpenRouter
- ~$0.003 per 1K tokens (input)
- ~$0.015 per 1K tokens (output)
- Typical scan: ~$0.05-0.15

For high-frequency scanning, consider:
- `anthropic/claude-haiku` (~10x cheaper)
- `deepseek/deepseek-chat` (very cheap)

## Running as Background Service

```bash
# Using nohup
nohup python -m src.agents.stirrup_market_scanner \
    --symbols "BTCUSD,ETHUSD" \
    --continuous \
    --interval 30 \
    > logs/scanner.log 2>&1 &

# Using systemd (production)
# See docs/deployment/stirrup_scanner.service
```

## Source

- [Stirrup GitHub](https://github.com/ArtificialAnalysis/Stirrup)
- [Stirrup Docs](https://stirrup.artificialanalysis.ai/)
- [Artificial Analysis](https://artificialanalysis.ai/)
