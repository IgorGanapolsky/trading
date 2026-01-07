# Technical Debt Registry

**Last Audit**: January 7, 2026
**Auditor**: Claude (CTO)
**Status**: Active tracking

## Executive Summary

| Category | Issues | Severity | Est. Effort |
|----------|--------|----------|-------------|
| DRY Violations | 500+ duplicate lines | CRITICAL | 2-3 days |
| Dead Code | 19 unused files + 50 stubs | HIGH | 1 day |
| Test Coverage | 15% (target: 70%) | CRITICAL | 2-3 weeks |
| Documentation | Outdated comments | MEDIUM | 1 day |

---

## 1. DRY VIOLATIONS (Don't Repeat Yourself)

### 1.1 Duplicate Cache Methods (CRITICAL)
**Files**: 4 sentiment analyzer classes
**Lines to consolidate**: ~150

| File | Methods |
|------|---------|
| `src/utils/tiktok_sentiment.py` | `_get_cache_file()`, `_load_from_cache()`, `_save_to_cache()` |
| `src/utils/linkedin_sentiment.py` | Same 3 methods |
| `src/utils/reddit_sentiment.py` | Same 3 methods |
| `src/utils/unified_sentiment.py` | Same 3 methods |

**Solution**: Extract to `SentimentAnalyzerBase` class or `src/utils/cache_utils.py`

### 1.2 Hardcoded Timeouts (HIGH)
**Files**: 15+ files
**Occurrences**: 15+

**Created**: `src/utils/constants.py` with centralized values
**TODO**: Update all files to import from constants

### 1.3 Duplicate Retry Logic (HIGH)
**Files**:
- `src/utils/retry_decorator.py` - `retry_with_backoff()`
- `src/utils/self_healing.py` - `with_retry()`
- `src/utils/market_data.py` - 4 identical `_fetch_*_with_retries()` methods

**Solution**: Keep only `retry_with_backoff()`, delete duplicate

### 1.4 Duplicate Validation Methods (MEDIUM)
**Files**:
- `src/risk/trade_gateway.py:568` - `validate_trade()`
- `src/safety/mandatory_trade_gate.py:53` - `validate_trade_mandatory()`
- `src/core/risk_manager.py:410` - `validate_trade()`

**Solution**: Consolidate to single validation function

---

## 2. DEAD CODE

### 2.1 Never-Imported Files (19 files)
These files exist but are never imported:

1. `src/safety/position_enforcer.py`
2. `src/strategies/precious_metals_strategy.py` (DISABLED)
3. `src/rag/rl_feedback.py`
4. `src/rag/process_rewards.py`
5. `src/utils/yfinance_wrapper.py`
6. `src/utils/bogleheads_integration.py`
7. `src/utils/tax_optimization.py`
8. `src/utils/finnhub_client.py`
9. `src/analytics/profit_target_tracker.py`
10. `src/orchestration/elite_orchestrator.py`
11. `src/utils/tool_definitions.py`
12. `src/utils/logging_config.py`
13. `src/rag/enforcer.py`
14. `src/analytics/live_vs_backtest_tracker.py`
15-19. Additional files

**Action**: Review each, delete or integrate

### 2.2 Stub Classes (50+ occurrences)
Inline stubs for deleted `agent_framework` module in:
- `src/orchestration/elite_orchestrator.py` (lines 22-33)
- `src/orchestration/mcp_trading.py` (lines 23-45)
- `src/orchestrator/failure_isolation.py` (lines 14-26)

**Action**: Remove stubs, use proper type definitions

### 2.3 Deprecated Components
- ChromaDB (removed Jan 7, 2026)
- LangChain agents (removed)
- Kalshi prediction markets (removed Dec 2025)
- Tradier broker (removed Dec 2025)
- Treasury/Bond strategies (removed - Phil Town doesn't use)

---

## 3. TEST COVERAGE GAPS

### Current Status
- **Coverage**: 15% (CI threshold)
- **Target**: 70%
- **Tested modules**: 20 of 131 (15.3%)

### Critical Untested Modules

| Module | Lines | Risk |
|--------|-------|------|
| `orchestrator/main.py` | 3,260 | CRITICAL - Controls entire trading loop |
| `orchestrator/gates.py` | 1,815 | CRITICAL - Trade validation |
| `risk/*.py` (10 modules) | 3,761 | CRITICAL - Risk management |
| `core/alpaca_trader.py` | 1,175 | CRITICAL - Broker interface |
| `agents/*.py` (17 modules) | 4,500+ | HIGH - Decision making |
| `trading/options_executor.py` | 981 | HIGH - Order execution |

### Tests with High Skip Rates
- `test_rag_operational.py`: 136% skip ratio
- `test_rag_vector_db.py`: 83% skip ratio
- `test_rag_ml_safety.py`: 78% skip ratio

---

## 4. DOCUMENTATION ISSUES

### 4.1 Outdated Comments
- References to ChromaDB (deprecated)
- References to LangChain (removed)
- TODO comments from Dec 2025 not addressed

### 4.2 Missing Docstrings
- Many utility functions lack docstrings
- Some classes have incomplete documentation

---

## 5. ACTION PLAN

### Phase 1: Immediate (This Week)
- [x] Create `src/utils/constants.py`
- [x] Fix stub `__init__.py` files
- [ ] Delete 19 unused files (after review)
- [ ] Remove inline stubs

### Phase 2: Short-term (2 Weeks)
- [ ] Add tests for `orchestrator/main.py`
- [ ] Add tests for risk modules
- [ ] Increase CI threshold to 30%
- [ ] Consolidate cache methods

### Phase 3: Medium-term (1 Month)
- [ ] Achieve 50% test coverage
- [ ] Consolidate all retry logic
- [ ] Update all hardcoded timeouts to use constants
- [ ] Remove all deprecated code references

### Phase 4: Long-term (3 Months)
- [ ] Achieve 70% test coverage
- [ ] Add mutation testing
- [ ] Implement continuous refactoring pipeline

---

## 6. TRACKING

### Debt Reduction Progress
| Date | Coverage | DRY Issues | Dead Files |
|------|----------|------------|------------|
| Jan 7, 2026 | 15% | 500+ lines | 19 |
| Jan 14, 2026 | TBD | TBD | TBD |

### Metrics to Track
- Test coverage percentage
- Duplicate code lines (via `pylint --duplicate-code`)
- Unused imports (via `flake8`)
- Cyclomatic complexity (via `radon`)
