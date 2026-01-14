---
layout: post
title: "25 RAG Lessons Published: Everything We Learned"
date: 2026-01-14
categories: [lessons, rag, documentation]
---

# 25 RAG Lessons Published: Everything We Learned

Our RAG (Retrieval-Augmented Generation) system contains 25 lessons learned. Until today, most were never published publicly. Here they all are.

---

## Critical Lessons

### 1. 200x Position Size Bug (Nov 3, 2025)
**Severity**: CRITICAL | **Impact**: $1,592

Trade executed at $1,600 instead of expected $8 due to unit confusion between shares and dollars.

**Root Cause**: Code calculated position in shares but passed to API expecting dollars.

**Prevention**: Always verify order size matches expected daily budget before submit. Add pre-trade size sanity check.

---

### 2. Hardcoded SPY Price Prevented All Trades (Jan 12, 2026)
**Severity**: CRITICAL | **Impact**: 74 days of zero trades

`should_open_position()` in simple_daily_trader.py hardcoded SPY price at $600 for collateral calculation, even when CONFIG specified SOFI ($14). Required $57,000 buying power when only $1,000 was needed.

**Prevention**: Always derive collateral requirements from the actual CONFIG symbol.

---

### 3. 74 Days Zero Trades - Complexity Killed Execution (Jan 13, 2026)
**Severity**: CRITICAL | **Impact**: 0 trades for 74 days

Trading system ran for 74 days with zero trades executed. Complex 5-gate pipeline, 23 workflows, and multiple `continue-on-error` flags masked all failures.

**Root Cause**: Over-engineering. Too many gates, too many workflows, insufficient end-to-end testing.

**Prevention**:
1. Simplify: One workflow, one strategy, one execution path
2. Remove all `continue-on-error` flags from critical paths
3. Add mandatory trade verification that fails loudly

---

### 4. CTO Made Claims Without Verifying RAG Data (Jan 13, 2026)
**Severity**: CRITICAL | **Impact**: Trust violation

CTO claimed theta decay income and profits while actual P/L was -$24.19. RAG webhook showed stale data (Last Trade: Jan 6) but CTO did not verify.

**Prevention**: ALWAYS query RAG webhook before making financial claims. Say "I don't know, let me verify" when uncertain.

---

### 5. System Added to Losing Position Without Stop-Loss (Jan 13, 2026)
**Severity**: CRITICAL | **Impact**: -$17.94

System increased SOFI put position from -1 to -2 contracts while already losing money. This VIOLATES Phil Town Rule #1: Don't lose money.

**Prevention**:
1. NEVER add to losing positions
2. Set stop-loss BEFORE entering any short option position
3. Max 1 CSP contract until profitable

---

## High Severity Lessons

### 6. Dashboard None Value TypeError (Jan 3, 2026)
Dashboard stopped updating for 3 days without visible error. `continue-on-error: true` suppressed the TypeError when formatting None values.

**Fix**: Use `'or 0'` pattern: `sortino = risk.get('sortino_ratio', 0) or 0`

---

### 7. Dialogflow Webhook Used Wrong Key (Jan 12, 2026)
Webhook looked for `paper_account.current_equity` but system_state.json has `paper_account.equity`. Showed $0 instead of $5000.

**Prevention**: Always verify JSON key names match between producer and consumer.

---

### 8. Hook Showed Wrong Account Data (Jan 13, 2026)
Trading context hook showed brokerage account ($60) instead of paper account ($5K), causing wrong recommendations.

**Root Cause**: Hook used ALPACA_API_KEY (brokerage) instead of ALPACA_PAPER_TRADING_5K_API_KEY.

---

### 9. Technical Debt Audit Findings (Jan 13, 2026)
Full codebase audit revealed:
- 83% of source modules have NO tests (93/112)
- 22 bare exception handlers
- 5 duplicate trader scripts
- 3 duplicate Dialogflow workflows
- Critical files like orchestrator/main.py (2852 LOC) have ZERO tests

---

### 10. Sandbox Cannot Push to Main (Jan 13, 2026)
Claude Code web sandbox blocks push to main with 403 error. Can only push to branches starting with 'claude/' and ending with session ID.

**Prevention**: Use GitHub Actions workflows to merge (auto-pr.yml, merge-branch.yml).

---

## Medium Severity Lessons

### 11. Market Order Slippage Warning
Large market orders can experience significant slippage during volatile periods.

**Prevention**: Use limit orders for large positions. Add slippage tolerance checks.

---

### 12. Momentum Signal False Positive
MACD crossover signals unreliable in low-volume conditions.

**Prevention**: Add volume filter: only trade when volume > 80% of 20-day average.

---

### 13. Stale Data Detection
System used 24-hour old market data for trading decision.

**Prevention**: Verify data timestamp < 5 minutes before any trade. Block trading on stale data.

---

### 14. Server Timezone vs Trading Timezone Mismatch (Jan 1, 2026)
Hook script used system date (UTC) instead of trading timezone (ET) for TODAY variable, causing wrong dates near midnight.

**Prevention**: Always use `TZ=America/New_York` prefix for date commands in trading context.

---

### 15. Removed 1396 Lines of Dead Test Code (Jan 13, 2026)
Deleted 3 test files importing non-existent modules. Tests were written for modules that were later deleted without cleanup.

**Prevention**: When deleting a module, always search for and delete corresponding test files.

---

### 16. Tests Must Be Sandbox-Resilient (Jan 13, 2026)
Tests that import optional dependencies must use `pytest.mark.skipif` to handle sandbox environments.

---

### 17. Massive Dead Code Cleanup - 5,315 Lines Removed (Jan 13, 2026)
Deleted broken test files (1,396 lines) and unused sentiment modules (3,919 lines).

**Prevention**: Run `pre_cleanup_check.py` before deleting modules.

---

### 18. find_put_option() Hardcoded SPY Price (Jan 13, 2026)
Incomplete fix - `should_open_position()` was fixed but `find_put_option()` was missed.

**Prevention**: When fixing bugs, grep ALL occurrences.

---

### 19. Missing Market Hours Check (Jan 13, 2026)
simple_daily_trader.py attempted trades outside market hours. Alpaca rejected orders silently.

**Prevention**: Always check market hours FIRST in trading logic.

---

### 20. GitHub Pages 404.html Links (Jan 12, 2026)
404.md had hardcoded `/lessons/` link without `/trading` baseurl prefix.

**Fix**: Use `relative_url` filter: `{{ "/" | relative_url }}`

---

## Success Lessons

### 21. PROOF OF LIFE: First Trades Executed (Jan 13, 2026)
**Severity**: INFO (Success!)

System successfully executed trades on paper account after 74 days of zero trades. TRIGGER_TRADE.md push activated claude-agent-utility workflow.

---

### 22. Created Pre-Trade Stop-Loss Verification (Jan 13, 2026)
Created `verify_stops_in_place.py` to enforce Phil Town Rule #1. Script verifies all short option positions have stop-loss orders before allowing new trades.

---

## Strategic Lessons

### 23. North Star Review - System Working, Strategy Failing (Jan 13, 2026)
CEO asked: Will we reach North Star $100/day?

**Analysis**: Infrastructure works (webhook accurate, RAG has 19 lessons). Strategy FAILS (total P/L -$12.71, added to losing positions, stop-losses exist but not verified running).

---

### 24. Comprehensive Investment Strategy Review (Jan 13, 2026)
Full review revealed:
1. Phil Town Rule #1 code exists but NOT enforced before trades
2. We ARE profitable (+$17.76 / 0.36%) but felt like failure due to 74 days of no execution
3. Credit spreads ARE the correct pivot for $100/day goal with $5K capital

---

### 25. CTO Reported Stale Data as Current Fact (Jan 13, 2026)
CTO read system_state.json showing -$12.71 P/L and reported it as current. Alpaca dashboard showed actual P/L was +$19.62. CEO had to correct with screenshot.

**Prevention**: When API unavailable, SAY SO explicitly. Never report local cache as current fact.

---

## Summary

| Severity | Count | Key Pattern |
|----------|-------|-------------|
| CRITICAL | 5 | Hardcoded values, trust violations |
| HIGH | 5 | Schema mismatches, wrong data sources |
| MEDIUM | 10 | Technical debt, cleanup needed |
| INFO | 2 | Successes to replicate |
| STRATEGIC | 3 | North Star alignment |

**Most Common Root Cause**: Hardcoded values that weren't updated when configuration changed.

**Most Impactful Fix**: Remove `continue-on-error` flags from critical paths - they hide failures.

---

*These 25 lessons are now indexed in our RAG system and published publicly. We won't make the same mistakes twice.*
