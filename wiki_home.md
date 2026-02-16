# 🤖 AI Trading System Wiki

Welcome to the **AI-Powered Automated Trading System** wiki!

---

## 📊 [Progress Dashboard](Progress-Dashboard)

**👉 [View Live Progress Dashboard →](https://igorganapolsky.github.io/trading/)**

The system tracks progress toward Financial Independence:
- North Star goal: **$6,000/month after-tax**
- Current strategy: **Iron Condors on SPY**
- Phil Town Rule #1: **Don't lose money**

---

## 🚀 Quick Links

### Documentation
- [CLAUDE.md](https://github.com/IgorGanapolsky/trading/blob/main/.claude/CLAUDE.md) - Strategy & directives
- [System State](https://github.com/IgorGanapolsky/trading/blob/main/data/system_state.json) - Live account data

### System Status
- [GitHub Actions](https://github.com/IgorGanapolsky/trading/actions) - Execution logs
- [RAG Chat](https://igorganapolsky.github.io/trading/rag-query/) - Query lessons learned

### Key Features
- **Iron Condor Guardian**: Automated Rule #1 enforcement (stop loss, 7 DTE exit, 50% profit take)
- **RLHF System**: Thompson Sampling + ShieldCortex memory
- **CI/CD**: 1300+ tests, self-healing workflows
- **Multi-Agent Swarm**: Analysis, execution, and monitoring agents

---

## 📈 Current Status (Feb 16, 2026)

| Metric | Value |
|--------|-------|
| **Account Equity** | $101,632.61 |
| **Starting Capital** | $100,000 (Jan 30, 2026) |
| **Net Gain** | $+1,632.61 (+1.63%) |
| **Open Positions** | 0 Iron Condor(s) |
| **Strategy** | SPY Iron Condors (15-20 delta) |

### Open Iron Condors
*No open iron condor positions*

---

## 🎯 North Star Goal

**Target**: Financial Independence = **$6,000/month after-tax**

| Metric | Value |
|--------|-------|
| **Current Equity** | $101,633 |
| **Target Capital** | $600,000 |
| **Progress** | 16.9% |
| **Completed IC Trades** | 1 of 30 required |
| **Realized IC P/L** | $41 |
| **Months Remaining** | 44 |
| **Required CAGR** | 60.8% |
| **Estimated CAGR** | 0.73% |
| **Probability** | 36.4% (low) |

**Deadline**: Nov 14, 2029

⚠️ **INSUFFICIENT DATA** — 29 more completed trades needed before projections are valid

---

## 🛡️ Phil Town Rule #1 Enforcement

The **Iron Condor Guardian** runs every 30 minutes during market hours to enforce:

1. **Stop Loss**: Exit if loss reaches 200% of credit received
2. **7 DTE Exit**: Close positions at 7 days to expiration (gamma risk)
3. **50% Profit Take**: Lock in profits at 50% of max profit

*Automation ensures rules are followed without human intervention.*

---

*Last updated: 2026-02-16 11:51 ET by GitHub Actions*
