# 🤖 AI Trading System Wiki

Welcome to the **AI-Powered Automated Trading System** wiki!

---

## 📊 [Progress Dashboard](Progress-Dashboard)

**👉 [View Live Progress Dashboard →](https://igorganapolsky.github.io/trading/)**

    The system tracks progress toward financial independence:
    - North Star goal: **$6K/month after-tax financial independence (execute as fast as safely possible)**
    - Current strategy: **SPY iron condors (15-20 delta, $10-wide wings, up to 8 open option legs ~2 concurrent condors)**
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

## 📈 Current Status (Mar 04, 2026)

| Metric | Value |
|--------|-------|
| **Account Equity** | $100,143.29 |
| **Starting Capital** | $100,000 (Jan 30, 2026) |
| **Net Gain** | $+143.29 (+0.14%) |
| **Open Positions** | 0 Iron Condor(s) |
| **Strategy** | SPY Iron Condors (15-20 delta, $10-wide, max 8 open legs ~2 concurrent condors) |

### Open Iron Condors
*No open iron condor positions*

---

## 🎯 North Star Goal

**Vision**: Build a reliable autonomous SPY iron condor engine that reaches $6K/month after-tax as fast as safely possible.

| Phase | Timeline | Target | Status |
|-------|----------|--------|--------|
| **Phase 1: Validate** | Now → Jun 2026 | 30 trades, >75% win rate | 🔄 In progress (1/30) |
| **Phase 2: Scale** | Jul → Dec 2026 | 3 concurrent ICs, $500/mo | ⏳ Pending |
| **Phase 3: Grow** | 2027 | 5 ICs + credit spreads, $1,500/mo | ⏳ Pending |
| **Phase 4: Open** | 2028 | Packaged system for accounts $10K+ | ⏳ Pending |

**Strategy Parameters** (updated Feb 2026 — Rule #1 canonical exits):
- Profit target: **50%** of max profit
- Stop loss: **100%** of credit (cut losers fast)
- Expected value: **positive edge** with disciplined 50%/100% exits and 80%+ win rate

---

## 🛡️ Phil Town Rule #1 Enforcement

The **Iron Condor Guardian** runs every 30 minutes during market hours to enforce:

1. **Stop Loss**: Exit if loss reaches 100% of credit received
2. **7 DTE Exit**: Close positions at 7 days to expiration (gamma risk)
3. **50% Profit Take**: Lock in profits at 50% of max profit

*Automation ensures rules are followed without human intervention.*

---

*Last updated: 2026-03-04 10:01 ET by GitHub Actions*
