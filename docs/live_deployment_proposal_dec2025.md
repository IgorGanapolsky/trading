# Live Deployment Proposal - December 2025

**Date**: December 12, 2025
**Author**: CTO (Claude)
**Status**: DRAFT - Pending CEO Approval

---

## Executive Summary

External review suggests we're "2-4 weeks from $100/day real". After analysis, I **partially agree but recommend a more conservative path**.

### Key Findings

| Claim | Reality | My Assessment |
|-------|---------|---------------|
| "Fee drag shaves 12-18% of edge" | Fees are <0.01% of capital | **Wrong** - fees aren't the blocker |
| "Need dual-LLM veto layer" | Single point of failure exists | **Correct** - implement this |
| "8-14 sec latency is retail tourist" | Filled after market makers | **Correct** - need <2 sec |
| "$5k live tomorrow" | No proven backtest edge | **Premature** - need validation first |

---

## Current Reality Check

### Backtest Performance (Dec 5, 2025)
- **Scenarios passing promotion gate**: 0/13 (0%)
- **Win rate range**: 34-62%
- **Sharpe ratio range**: -7 to -2086 (all negative)
- **Required for promotion**: Win rate >60%, Sharpe >1.5

### What This Means
The base DCA momentum strategy has **no proven edge**. Deploying live capital now would be gambling, not trading.

---

## Proposed Deployment Path

### Phase 1: Enable Hybrid Gates (Immediate - no live capital)

```bash
# Enable all 4 gates in paper trading
export USE_HYBRID_GATES=true
export RL_CONFIDENCE_THRESHOLD=0.6
export LLM_NEGATIVE_SENTIMENT_THRESHOLD=-0.2
export RISK_USE_ATR_SCALING=true
```

**Validation period**: 14 days paper trading with hybrid gates
**Success criteria**: Win rate >55%, Sharpe >0.5

### Phase 2: Add Dual-LLM Veto (Week 2)

Implement secondary LLM confirmation:
```
Trade Decision Flow:
1. Momentum signal detected
2. RL filter approves (confidence >0.6)
3. Primary LLM (Haiku) confirms: "BUY"
4. Secondary LLM (Claude Sonnet) confirms: "AGREE"
5. If both agree → execute
6. If either rejects → skip trade
```

**Implementation**: Create `src/agents/llm_veto_agent.py`
**Cost**: ~$0.01-0.02 per trade (well within $100/mo budget)

### Phase 3: Reduce Latency (Week 2-3)

Options (in order of preference):
1. **Pre-compute signals at 9:30 AM** - Cache morning analysis, execute at 9:35
2. **Local Llama-3.1-70B via Ollama** - Requires beefy hardware (64GB RAM)
3. **Batch multiple signals** - Reduce API round trips

**Target**: <2 second end-to-end from signal to order

### Phase 4: Controlled Live Deployment (Week 4+)

**Prerequisites**:
- [ ] 14 days hybrid gates paper trading complete
- [ ] Win rate >55% achieved
- [ ] Sharpe ratio positive
- [ ] Dual-LLM veto implemented
- [ ] Latency <5 seconds

**Initial live parameters**:
```
Capital at risk: $1,000 (NOT $5,000)
Max risk per trade: 0.25% of capital ($2.50)
Daily investment: $10/day (Fibonacci Level 1)
Universe: Tier-1 ETFs only (SPY, QQQ, VOO)
Stop loss: 2% hard stop
Daily loss limit: $25 (circuit breaker)
```

---

## Risk Safeguards

### Pre-Trade
- [ ] Dual-LLM consensus required
- [ ] RL confidence >0.6
- [ ] Sentiment score >-0.2
- [ ] ATR-scaled position sizing

### During Trade
- [ ] 2% stop loss on all positions
- [ ] $25 daily loss circuit breaker
- [ ] No adding to losing positions

### Post-Trade
- [ ] Record all trade outcomes for RL learning
- [ ] Daily performance report to CEO
- [ ] Weekly review of win rate / Sharpe

---

## Honest Assessment

### Why NOT $5k Tomorrow

1. **No backtest edge**: 0/13 scenarios pass promotion gate
2. **Fibonacci philosophy**: Start with $1/day, scale on proven profits
3. **R&D phase**: We're Day 9 of 90 - still learning

### Why Live Deployment Eventually Makes Sense

1. Paper trading validates infrastructure, not profitability
2. Real fills, real fees, real psychology are different
3. System needs real data to improve RL models
4. Can't compound without real capital at work

---

## Recommended Next Steps

| Priority | Action | Owner | Timeline |
|----------|--------|-------|----------|
| P0 | Enable hybrid gates in paper | CTO | Today |
| P1 | Implement dual-LLM veto | CTO | 3 days |
| P1 | Run 14-day validation period | System | 2 weeks |
| P2 | Optimize latency | CTO | 1 week |
| P3 | Live deployment if criteria met | CEO approval | Week 4+ |

---

## CEO Decision Required

- [ ] **Option A**: Approve this conservative path (recommended)
- [ ] **Option B**: Fast-track to live with $1k and accept higher risk
- [ ] **Option C**: Continue paper-only until Day 30 review

**My recommendation**: Option A - the reviewer is right that paper trading is a science project, but deploying capital without proven edge is gambling. Let's prove edge first, then deploy.

---

*Prepared by CTO | December 12, 2025*
