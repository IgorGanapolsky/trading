# 🤖 AI Trading System Wiki

Welcome to the **AI-Powered Automated Trading System** wiki!

---

## 📊 [Progress Dashboard](Progress-Dashboard)

**👉 [View Live Progress Dashboard →](https://igorganapolsky.github.io/trading/)**

    The system tracks progress toward financial independence:
    - North Star goal: **$6K/month after-tax financial independence (execute as fast as safely possible)**
    - Current strategy: **SPY iron condors (15-20 delta, $10-wide wings, up to 5 concurrent positions)**
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

## 📈 Current Status (Feb 24, 2026)

| Metric | Value |
|--------|-------|
| **Account Equity** | $101,119.18 |
| **Starting Capital** | $100,000 (Jan 30, 2026) |
| **Net Gain** | $+1,119.18 (+1.12%) |
| **Open Positions** | 3 Iron Condor(s) |
| **Strategy** | SPY Iron Condors (15-20 delta, $10-wide, max 5 concurrent) |

### Open Iron Condors
| Expiry | Put Spread | Call Spread |
|--------|------------|-------------|
| Mar 27, 2026 | 640/650 | 715/725 |
| Mar 31, 2026 | 640/650 | 715/725 |
| Apr 02, 2026 | 640/650 | 715/725 |

---

## 🎯 North Star Goal

**Vision**: Build a reliable autonomous SPY iron condor engine that reaches $6K/month after-tax as fast as safely possible.

| Phase | Timeline | Target | Status |
|-------|----------|--------|--------|
| **Phase 1: Validate** | Now → Jun 2026 | 30 trades, >75% win rate | 🔄 In progress (1/30) |
| **Phase 2: Scale** | Jul → Dec 2026 | 3 concurrent ICs, $500/mo | ⏳ Pending |
| **Phase 3: Grow** | 2027 | 5 ICs + credit spreads, $1,500/mo | ⏳ Pending |
| **Phase 4: Open** | 2028 | Packaged system for accounts $10K+ | ⏳ Pending |

**Strategy Parameters** (updated Feb 2026 — positive EV):
- Profit target: **75%** of max profit (let winners run)
- Stop loss: **100%** of credit (cut losers fast)
- Expected value per trade: **+$94** at 80% win rate

---

## 🛡️ Phil Town Rule #1 Enforcement

The **Iron Condor Guardian** runs every 30 minutes during market hours to enforce:

1. **Stop Loss**: Exit if loss reaches 200% of credit received
2. **7 DTE Exit**: Close positions at 7 days to expiration (gamma risk)
3. **50% Profit Take**: Lock in profits at 50% of max profit

*Automation ensures rules are followed without human intervention.*

---

*Last updated: 2026-02-24 12:59 ET by GitHub Actions*
