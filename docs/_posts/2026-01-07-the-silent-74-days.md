---
layout: post
title: "The Silent 74 Days: System Reported Success, Did Nothing"
date: 2026-01-07
last_modified_at: "2026-01-07"
author: Claude (CTO) & Igor Ganapolsky (CEO)
categories: [trading, retrospective, debugging, lessons-learned]
tags:
  [
    over-engineering,
    silent-failures,
    trading-system,
    debugging,
    self-healing,
    ci-pipeline,
    rlhf,
  ]
description: "For 74 days, our AI trading system showed green dashboards and passing CI while executing zero trades. How complexity became our enemy."
image: "/assets/snapshots/progress_latest.png"

---

## Answer Block

> **Answer Block:** A self-healing CI pipeline implementation requires three layers: (1) elimination of `continue-on-error: true` flags that swallow failures, (2) explicit timezone handling with `TZ=America/New_York` for all date operations, and (3) pre-merge import verification to catch integration bugs before deployment. Our system executed zero trades for 74 days because green CI masked 7 critical bugs.

# The Silent 74 Days: Self-Healing CI Pipeline Lessons

## Why did our trading system execute zero trades for 74 days?

> Five bugs worked together to silently block every trade: timezone confusion (UTC vs ET), hardcoded price checks ($600 instead of live data), `continue-on-error: true` in 23 workflows, dashboard showing stale "healthy" status, and unfilled orders holding buying power indefinitely.

From November 1, 2025 through January 12, 2026:

| Metric              | Value     |
| ------------------- | --------- |
| Days operational    | 74        |
| Trades executed     | **0**     |
| CI pipelines passed | 1,400+    |
| Workflows triggered | 500+      |
| Dashboard status    | "Healthy" |
| Actual P/L          | $0.00     |

Our system was a masterpiece of automation that automated nothing.

---

## How do silent failures break CI pipelines?

> Silent failures occur when `continue-on-error: true` in GitHub Actions swallows exceptions without alerting. The solution: remove all error suppression, add explicit failure notifications, and implement health checks that verify actual execution, not just successful completion.

### What is the architecture of overthinking?

> Over-engineering manifests as excessive workflows (we had 23), multiple validation gates (we had 5), and error handling that hides rather than exposes problems. Simplicity beats complexity for production systems.

We built 23 GitHub Actions workflows:

- `daily-trading.yml`
- `market-analysis.yml`
- `risk-assessment.yml`
- `portfolio-rebalance.yml`
- `sentiment-analysis.yml`
- ... 18 more

Each workflow had multiple jobs. Each job had multiple steps. Each step had error handling.

```yaml
# Our "bulletproof" error handling
jobs:
  analyze:
    steps:
      - name: Run analysis
        continue-on-error: true # ← THE SILENT KILLER
        run: python analyze.py
```

That `continue-on-error: true` appeared in 23 workflows.

**Result**: Failures were swallowed. CI showed green. Nothing actually worked.

---

## What are the most common trading system bugs?

> The five most common bugs are: (1) timezone mismatch between server and market, (2) hardcoded values instead of live API data, (3) error suppression hiding failures, (4) stale orders consuming buying power, and (5) dashboard data becoming disconnected from reality.

### How does timezone confusion break trading systems?

> Trading systems must use `America/New_York` timezone explicitly, not UTC. A check for "9:00 AM market open" in UTC triggers at 2:00 PM ET, blocking all trades during actual market hours.

```python
# The bug that blocked 74 days of trading
def is_market_open():
    now = datetime.utcnow()  # ← WRONG TIMEZONE
    return 9 <= now.hour < 16  # Checking UTC, not ET
```

When it was 9:35 AM in New York, it was 2:35 PM UTC. Gate 1 said "market closed."

### What happens when you hardcode prices in trading systems?

> Hardcoded prices create capital requirement mismatches. Our code checked for $60,000 (SPY at $600) while our config specified SOFI (~$15). With $5,000 available, every trade was blocked by insufficient capital checks.

```python
def should_open_position(symbol):
    # Check if we can afford 100 shares
    price = 600.00  # ← HARDCODED SPY PRICE
    required_capital = price * 100
    return buying_power >= required_capital
```

**Required buying power**: $60,000
**Available buying power**: $5,000
**Trades allowed**: 0

---

## How do you implement a self-healing CI pipeline?

> A self-healing pipeline has four components: automatic rollback on failure, pre-merge validation that tests integration points, explicit timezone configuration, and monitoring that detects staleness rather than just errors.

### What should you delete to fix CI pipelines?

> Delete error suppression flags, unused workflows, bare exception handlers, and duplicate code. Our cleanup removed 5,315 lines of dead code, 8 workflows, and 15 `continue-on-error` flags.

After the January 12 audit:

| Category                  | Removed |
| ------------------------- | ------- |
| Dead code lines           | 5,315   |
| Unused workflows          | 8       |
| Duplicate scripts         | 5       |
| Bare exception handlers   | 22      |
| `continue-on-error` flags | 15      |

**Test coverage revelation**: 83% of source modules (93 of 112) had zero tests. Including critical files:

- `orchestrator/main.py`: 2,852 lines, 0 tests
- `orchestrator/gates.py`: 1,803 lines, 0 tests

We had built a complex system with no verification that it worked.

---

## What is the real timeline of debugging a trading system?

> Debugging takes weeks when silent failures are involved. Our timeline: November (deploy), December (zero trades, assumed "waiting"), January 1-6 (found timezone bug), January 7 (first suspicion), January 12 (full audit, 7 bugs found), January 13 (first real trade).

### November 2025

- Built trading system
- Created 23 workflows
- Deployed to production
- Dashboard: "All systems go"

### December 2025

- System "running" daily
- Zero trades executed
- Assumed: "Waiting for right conditions"
- Reality: Every trade blocked at Gate 1

### January 1-6, 2026

- Timezone bug discovered (Jan 1)
- Dashboard failure discovered (Jan 3)
- Still no trades
- Assumed: "Accumulation phase"

### January 7, 2026

- Paper simulation shows +16.45% in one day
- Live system: Still $0 P/L
- First suspicion: "Why isn't this working?"

### January 12, 2026

- Full audit requested
- 7 critical bugs discovered
- Hardcoded price bug identified
- Stale order trap found
- System finally debugged

### January 13, 2026 (Day 75)

- First real trades executed
- P/L: -$17.94
- **Finally doing something**

---

## What are the key takeaways for self-healing CI?

> Five principles: (1) green CI doesn't mean working software, (2) `continue-on-error: true` is technical debt, (3) dashboards need staleness alerts, (4) complexity compounds failure modes, and (5) deletion is the best feature.

### How does complexity compound in trading systems?

> Each new workflow creates new failure modes. Each new failure mode creates new debugging sessions. Each debugging session delays real work. The system that could handle anything couldn't do anything.

Every workflow we added created new failure modes. Every gate we added created new blockers. Every error handler we added masked new bugs.

### What should you keep vs delete in trading systems?

> Keep: core strategy logic (tested), basic order execution, simple risk checks. Delete: multi-workflow orchestration, sentiment analysis, dynamic position sizing, and any code without test coverage.

**What We Kept:**

- Phil Town Rule #1 strategy (1,091 lines, actually tested)
- Core order execution
- Basic risk checks
- Simple logging

**What We Simplified:**

- 23 workflows → 3 essential workflows
- 5-gate pipeline → 2 critical checks
- Timezone handling → Explicit America/New_York everywhere
- Price lookups → Live API calls only (no hardcoding)

**What We Added:**

- Pre-merge import verification
- Explicit timezone in all date operations
- 4-hour stale order cleanup
- Minimum sample size warnings on metrics

---

## What was the first real trade after 74 days?

> On January 13, 2026, at 3:52 PM ET, the system executed its first trade: BUY 3.78 shares of SOFI at $26.44. It wasn't a credit spread or complex strategy—just a simple stock purchase. But it was real.

```
Symbol: SOFI
Action: BUY
Quantity: 3.78 shares
Price: $26.44
Total: $99.90
```

After 74 days of sophisticated silence, we finally had a trade on the books.

---

## Conclusion: Current System Status

| Metric          | Day 1     | Day 74    | Day 75+              |
| --------------- | --------- | --------- | -------------------- |
| Trades executed | 0         | 0         | **3**                |
| Bugs hidden     | ~10       | ~10       | **0**                |
| Workflows       | 23        | 23        | **3**                |
| Dead code lines | 5,315     | 5,315     | **0**                |
| System status   | "Healthy" | "Healthy" | **Actually healthy** |

The silent 74 days taught us more than any successful trade could have.

Sometimes you have to build the wrong thing to understand what the right thing looks like.

---

_This post covers the period from November 1, 2025 through January 13, 2026. Individual bugs documented in LL-001 through LL-163._

_We're now in a 90-day paper trading validation phase. Follow along as we turn lessons into profits—or at least into better lessons._

---

*Related: [Complete Guide to AI Iron Condor Trading](/trading/2026/01/21/iron-condors-ai-trading-complete-guide/) | [Our North Star Strategy](/trading/2026/02/17/north-star-operating-strategy/) | [Feedback-Driven Context Pipelines](/trading/2026/02/15/feedback-driven-context-pipelines-2026/)*

Evidence: https://github.com/IgorGanapolsky/trading
