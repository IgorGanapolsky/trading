<div align="center">

# SPY Iron Condor Trader

### Autonomous AI-Powered Options Trading

**Autonomous AI-powered iron condor trading on SPY. Open source. Self-healing. Learning from every trade.**

[![Paper Equity](https://img.shields.io/badge/Paper_Equity-$95%2C431-brightgreen?style=for-the-badge)](https://igorganapolsky.github.io/trading/rag-query/)
[![Lessons Learned](https://img.shields.io/badge/Lessons_Learned-122%2B-blue?style=for-the-badge)](#self-healing-cicd)
[![Win Rate](https://img.shields.io/badge/Win_Rate-Tracking-yellow?style=for-the-badge)](#performance)
[![License](https://img.shields.io/badge/License-MIT-orange?style=for-the-badge)](LICENSE)

[Progress Dashboard](https://igorganapolsky.github.io/trading/rag-query/) | [Architecture](#architecture) | [Quick Start](#quick-start) | [Roadmap](#roadmap)

</div>

---

## Why This Exists

**The goal**: Generate $6,000/month in after-tax passive options income. That's financial independence.

**The problem**: Manual iron condor trading is tedious, emotional, and error-prone. You forget to close at 50% profit. You panic-sell during a dip. You miss the VIX spike that should have kept you out of the trade entirely.

**The solution**: AI agents that execute, monitor, and learn autonomously — removing the human from the execution loop while keeping them in control of strategy.

This system was built by a developer-trader who got tired of losing money to discipline failures. Every line of code exists because something went wrong in a real trading session.

---

## How It Works

```
📡 Market Scan       →  VIX check, market conditions, data quality gate
🤖 LLM Consensus     →  Multiple AI models vote on trade entry (not one model — a quorum)
⚡ MLeg Execution     →  Atomic 4-leg order via Alpaca (all legs fill or none do)
📊 Position Monitor   →  50% profit target · 100% stop-loss · 7 DTE exit
🧠 RAG Learning Loop  →  Every outcome feeds back into the knowledge base for next time
```

The system checks VIX and market conditions before every trade. If VIX > 30 or data is unavailable, it blocks entry. When conditions pass, multiple LLM agents form consensus on the trade. Execution uses Alpaca's multi-leg order API — all four iron condor legs fill atomically or not at all, preventing orphan positions. After every trade, the outcome is recorded and fed into a RAG knowledge base so the system learns from its own history.

<p align="center">
  <img src="docs/assets/trading_pipeline.png" alt="Trading Pipeline Architecture" width="700"/>
</p>

---

## Key Features

| Feature | What It Does | Why It Matters |
|---|---|---|
| **Multi-Agent LLM Consensus** | Multiple AI models vote on every trade decision | No single point of failure in decision-making |
| **MLeg Atomic Execution** | All 4 iron condor legs fill together or not at all | Zero orphan positions — no naked risk exposure |
| **Self-Healing CI/CD** | 122+ documented lessons fed back into the system | The system literally gets smarter after every failure |
| **RAG Knowledge Base** | Retrieves past trade lessons before making decisions | Institutional memory that compounds over time |
| **Risk Management** | 5% max risk, 100% stop-loss, 7 DTE exit rule | Phil Town Rule #1: Don't lose money |
| **Real-time Alpaca Integration** | Paper and live trading on the same broker API | Low barrier to entry, seamless paper→live transition |
| **GRPO Learning** | Reinforcement learning from paired trade outcomes | Strategy parameters evolve based on real results |

---

## Quick Start

**Prerequisites**: Python 3.11+, an [Alpaca](https://alpaca.markets/) paper trading account

```bash
# Clone the repo
git clone https://github.com/IgorGanapolsky/trading.git
cd trading

# Install dependencies
pip install -r requirements.txt

# Configure your environment
cp .env.example .env  # Add your Alpaca API keys

# Run system health check
python scripts/system_health_check.py

# Start paper trading
python src/orchestration/daggr_workflow.py
```

---

## Architecture

The system is built around three core pillars:

- **Orchestrator** (`src/orchestration/`) — Coordinates the full trading workflow from market scan to order execution
- **AI Agents** (`src/agents/`) — Multiple LLM-based agents that analyze conditions and form trade consensus
- **Safety Gates** (`src/core/`) — Risk management, position limits, VIX checks, and stop-loss enforcement
- **RAG System** (`rag_knowledge/`) — 122+ lessons learned, automatically retrieved and applied before decisions

<p align="center">
  <img src="docs/assets/llm_gateway_architecture.png" alt="LLM Gateway Architecture" width="700"/>
</p>

---

## Performance

> We publish real numbers, not cherry-picked backtests.

| Metric | Value |
|---|---|
| Paper Account Equity | $95,431 |
| Starting Capital | $100,000 |
| Closed Trades | 1 |
| Closed Trade P/L | +$41 (win) |
| Open Positions | 4 legs (1 complete iron condor, Apr '26 expiry) |
| Validation Day | 61 of 90 |
| Strategy | 15-delta SPY iron condors, $10-wide wings, 30-45 DTE |

**Live account**: $0 equity. The initial $20 was lost during pre-system-fix testing. No live capital is deployed until the 90-day paper validation completes with 30+ trades at 80%+ win rate.

This is a system under active validation. The numbers above are real, pulled from Alpaca's paper trading API, and synced automatically via CI.

---

## Roadmap

| Phase | Status | Description |
|---|---|---|
| **Phase 1 — Paper Validation** | **In Progress** | 90-day paper trading. Target: 30+ iron condor trades, 80%+ win rate. Prove the system works before risking real capital. |
| **Phase 2 — Live Deployment** | Planned | Deploy with real capital on Alpaca. Start small, scale with confidence. |
| **Phase 3 — Managed Service (Pro)** | Planned | Hosted version for retail traders who want the system without running infrastructure. |
| **Phase 4 — Enterprise API** | Planned | API access for prop firms and fintech platforms. Custom strategies, multi-account, white-label. |

---

## Risk Rules

This system enforces strict risk management at the code level — not as guidelines, but as hard gates:

- **Max 5% risk per position** ($5,000 on a $100K account)
- **Stop-loss at 100% of credit received** — no exceptions, enforced in code
- **Exit at 50% profit or 7 DTE** — whichever comes first
- **Max 2 concurrent iron condors** (8 legs total)
- **System halts if live price data or VIX is unavailable**
- **No naked options. No undefined risk. Ever.**

---

## Contributing

Contributions are welcome. This is an active project with real trading implications, so please:

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Run tests (`pytest tests/ -q`) and lint (`ruff check src/`)
4. Open a PR with a clear description of what and why

If you find this project useful, consider giving it a star — it helps others discover it.

---

## License

[MIT](LICENSE) — Use it, fork it, build on it.

---

<div align="center">

**Built by [Igor Ganapolsky](https://github.com/IgorGanapolsky)**

*"The market doesn't care about your feelings. That's why we let AI handle execution."*

</div>
