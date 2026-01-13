---
layout: default
title: Trading Lessons
permalink: /lessons/
---

# Trading Lessons Learned

16 lessons from our 90-day AI trading journey. All lessons stored in Vertex AI RAG.

---

## Journey Timeline

- **Days 1-67**: Paper trading with $100K account (learning phase)
- **Days 68-74**: Switched to $5K paper account (realistic budget simulation)
- **Current**: Accumulating $500 brokerage capital for first real CSP trade

---

## All Lessons

| ID | Lesson | Category | Date |
|----|--------|----------|------|
| LL-131 | Never tell CEO to run CI | Process | Jan 12 |
| LL-133 | Registry fix and hygiene | DevOps | Jan 12 |
| LL-134 | Options buying power = $0 | Trading | Jan 12 |
| LL-135 | Investment strategy comprehensive review | Strategy | Jan 12 |
| LL-137 | Branch and PR hygiene | DevOps | Jan 12 |
| LL-139 | Advanced RAG techniques assessment | Architecture | Jan 13 |
| LL-140 | Technical debt audit | Architecture | Jan 13 |
| LL-144 | Stale order threshold fix (24h→4h) | Trading | Jan 12 |
| LL-145 | Technical debt cleanup - dead code | Architecture | Jan 13 |
| LL-146 | GCP key security fix (chmod 600) | Security | Jan 13 |
| LL-147 | Placeholder tests removed for honesty | Testing | Jan 13 |
| LL-148 | Day 74 emergency fix - SPY to SOFI | Trading | Jan 13 |
| LL-149 | RAG system analysis | Architecture | Jan 13 |
| LL-150 | Sandbox vs GitHub API access | DevOps | Jan 12 |
| LL-151 | Safe dead code cleanup | Architecture | Jan 13 |
| LL-152 | Options buying power $0 root cause | Trading | Jan 13 |

---

## Key Insights

### Trading Lessons
- **LL-134/152**: Options buying power can be $0 even with $5K cash if positions are open
- **LL-144**: Stale orders block buying power - reduced threshold from 24h to 4h
- **LL-148**: Switched from SPY ($600 collateral) to SOFI ($500 collateral)

### Technical Lessons
- **LL-145**: Removed 3,827 lines of dead code
- **LL-146**: GCP keys must have chmod 600 for security
- **LL-147**: Never use `assert True` - it lies about coverage

### Process Lessons
- **LL-131**: CTO should execute, not delegate to CEO
- **LL-150**: Verify API access before assuming keys are invalid

---

## Essential Rules

1. **Phil Town Rule #1**: Don't lose money
2. **Strategy**: Sell CSPs on F/SOFI at $5 strike
3. **Capital needed**: $500 minimum
4. **Compound**: Reinvest all profits

---

[← Back to Home]({{ "/" | relative_url }})
