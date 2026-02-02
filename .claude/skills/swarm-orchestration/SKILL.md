---
name: swarm-orchestration
description: Multi-agent swarm orchestration for trading system tasks. Coordinates parallel agents for market analysis, trading execution, maintenance, and research.
version: 1.0.0
author: Claude Code CTO
invocation: /swarm [mode] or auto-triggered by scheduler
---

# Swarm Orchestration Skill

Master multi-agent orchestration for the AI Trading System using parallel task execution and specialized agent swarms.

## Trigger

- `/swarm analysis` - Pre-market analysis swarm (5 agents)
- `/swarm trade` - Trading execution with signal validation
- `/swarm review` - EOD position review swarm
- `/swarm cleanup` - Daily maintenance swarm
- `/swarm research` - Weekend research swarm
- Auto-triggered by cron scheduler based on time of day

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │         SWARM ORCHESTRATOR          │
                    │   (Leader Agent - Coordinates All)  │
                    └─────────────────┬───────────────────┘
                                      │
        ┌─────────────────┬───────────┼───────────────┬─────────────────┐
        │                 │           │               │                 │
        v                 v           v               v                 v
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   SENTIMENT   │ │  TECHNICALS   │ │     RISK      │ │ OPTIONS CHAIN │ │     NEWS      │
│    Agent      │ │    Agent      │ │    Agent      │ │    Agent      │ │    Agent      │
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
       │                 │                 │                 │                 │
       └─────────────────┴─────────────────┴─────────────────┴─────────────────┘
                                           │
                                           v
                              ┌─────────────────────────┐
                              │   SIGNAL AGGREGATOR     │
                              │   (Consensus Decision)  │
                              └─────────────────────────┘
```

## Core Primitives

### Agent Types

| Type | Purpose | Used In |
|------|---------|---------|
| `sentiment` | Market sentiment analysis via news/social | Pre-market |
| `technicals` | Technical indicators (RSI, MACD, Bollinger) | Pre-market |
| `risk` | Position risk assessment, Phil Town Rule #1 | Pre-market, EOD |
| `options-chain` | Options chain analysis, IV, Greeks | Pre-market |
| `news` | Breaking news, earnings, macro events | Pre-market |
| `cleanup` | Dead code, test runner, RAG reindex | Maintenance |
| `research` | YouTube learning, strategy backtesting | Weekend |
| `backtest` | Strategy validation against historical data | Weekend |

### Task System

Tasks are managed in `~/.claude/tasks/trading/` with:

```json
{
  "id": "task-001",
  "name": "sentiment-analysis",
  "status": "pending|in_progress|completed|failed",
  "owner": "sentiment-agent",
  "blockedBy": [],
  "result": null,
  "created": "2026-02-01T09:25:00Z"
}
```

### Communication

Agents communicate via inbox files at `~/.claude/teams/trading/inboxes/`:

```json
{
  "type": "signal",
  "from": "technicals-agent",
  "signal": "bullish",
  "confidence": 0.72,
  "data": { "rsi": 45, "macd_cross": "bullish" }
}
```

## Swarm Modes

### 1. Pre-Market Analysis (9:25 AM ET)

Spawns 5 parallel agents:

```bash
# Orchestrator creates tasks
TaskCreate("Analyze SPY sentiment", agent: "sentiment")
TaskCreate("Calculate technicals", agent: "technicals")
TaskCreate("Assess risk parameters", agent: "risk")
TaskCreate("Scan options chain", agent: "options-chain")
TaskCreate("Check breaking news", agent: "news")

# Agents execute in parallel
# Results aggregated after all complete
# Consensus signal generated
```

**Output**: `data/analysis/pre_market_YYYY-MM-DD.json`

### 2. Trading Execution (9:35 AM ET)

Only triggers if pre-market signals align:

```python
# Signal validation (from pre_market analysis)
signals = load_pre_market_analysis()
if signals["consensus"] >= 0.7:  # 70%+ alignment
    execute_iron_condor_setup()
else:
    log("Signals misaligned, no trade today")
```

**Checklist validation**:
- SPY only
- 5% max position size ($5,000)
- Iron condor structure verified
- 15-20 delta short strikes
- 30-45 DTE
- Stop-loss defined

### 3. EOD Position Review (3:45 PM ET)

Reviews open positions:

```bash
TaskCreate("Check position P/L", agent: "risk")
TaskCreate("Evaluate exit conditions", agent: "options-chain")
TaskCreate("Log daily performance", agent: "cleanup")
```

**Exit triggers**:
- 50% max profit reached
- 7 DTE approaching
- Stop-loss at 200% of credit

### 4. Daily Cleanup (8:00 PM ET)

Maintenance swarm:

```bash
TaskCreate("Run pytest suite", agent: "cleanup")
TaskCreate("Scan dead code", agent: "cleanup")
TaskCreate("Reindex RAG", agent: "cleanup")
TaskCreate("Verify system_state.json", agent: "cleanup")
```

### 5. Weekend Research (Sunday 8 AM ET)

Learning and backtesting:

```bash
TaskCreate("Ingest Phil Town content", agent: "research")
TaskCreate("Backtest iron condor params", agent: "backtest")
TaskCreate("Update strategy parameters", agent: "research")
TaskCreate("Generate weekly insights", agent: "research")
```

## Execution Backends

| Backend | Description | When Used |
|---------|-------------|-----------|
| `in-process` | Fast, invisible execution | Default for CI/scheduled |
| `tmux` | Visible panes, persistent | Local development |
| `background` | Async with notifications | Long-running tasks |

## Signal Aggregation

Consensus algorithm for trading decisions:

```python
def aggregate_signals(agent_results: list) -> dict:
    """Aggregate agent signals using weighted voting."""
    weights = {
        "technicals": 0.30,  # Technical analysis
        "risk": 0.25,        # Risk assessment
        "options-chain": 0.20,  # Options data
        "sentiment": 0.15,   # Market sentiment
        "news": 0.10         # News events
    }

    score = sum(
        r["signal"] * weights[r["agent"]]
        for r in agent_results
    )

    return {
        "consensus": score,
        "decision": "trade" if score >= 0.7 else "hold",
        "signals": agent_results
    }
```

## Usage Examples

### Manual Trigger

```bash
# Pre-market analysis
/swarm analysis

# Check swarm status
/swarm status

# Force trading mode
/swarm trade --force

# Weekend research
/swarm research
```

### Programmatic Trigger

```python
from orchestration.swarm import SwarmOrchestrator

swarm = SwarmOrchestrator(team="trading")
swarm.run_mode("analysis")
results = swarm.wait_for_completion()
```

## Integration Points

- **SessionStart Hook**: Auto-detects time, triggers appropriate mode
- **Cron Scheduler**: `launchd` plist for macOS automation
- **GitHub Actions**: Fallback scheduler for cloud execution
- **RAG System**: Results indexed for learning
- **system_state.json**: Canonical data source

## Error Handling

```python
try:
    swarm.execute()
except AgentTimeout:
    swarm.kill_hung_agents()
    notify("Swarm timeout - agents killed")
except SignalMismatch:
    log("No consensus reached - holding")
except Exception as e:
    record_lesson(f"Swarm error: {e}")
    raise
```

## Cost Controls

- Max 5 agents per swarm (API cost management)
- 30-second timeout per agent task
- Local LanceDB for embeddings (no Vertex AI)
- Weekend research only on Sundays

## Related Files

- `.claude/hooks/autonomous_orchestrator.sh` - SessionStart orchestration
- `.claude/scripts/orchestration/swarm_runner.py` - Python swarm executor
- `.claude/scripts/orchestration/scheduler.py` - Cron-style scheduler
- `com.trading.autonomous.plist` - macOS launchd config

## Phil Town Alignment

Every swarm mode enforces Rule #1:

1. **Pre-market**: Risk agent validates position sizing
2. **Execution**: Mandatory checklist before any trade
3. **EOD**: Stop-loss monitoring active
4. **Cleanup**: System integrity verified
5. **Research**: Learning improves decision quality

---

*Swarm orchestration adapted from Kieran Klaassen's multi-agent patterns*
