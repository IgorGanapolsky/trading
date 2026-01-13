# Technical Debt Audit - January 13, 2026

**ID**: ll_154_tech_debt_audit_jan13
**Date**: 2026-01-13
**Severity**: HIGH

## Summary

Comprehensive codebase audit revealed significant technical debt:

## 1. Dead Code (Must Remove)

- `CHECKPOINT_GATES` and `PipelineCheckpointer` unused in `src/orchestrator/gates.py:40-44`
- `src/ml/__init__.py` is a stub with no functionality
- 3 unreferenced scripts not in any workflow

## 2. Unnecessary .md Files (Remove)

| File | Issue |
|------|-------|
| `TRIGGER_TRADE.md` | Empty, just timestamp |
| `rag_knowledge/market_intel/README.md` | Empty stub |
| `docs/reports.md` | Outdated day count |
| `.claude/SESSION_START_CHECKLIST.md` | Contains resolved items |
| `docs/404.md` | Not referenced |
| `src/orchestrator/AGENTS.md` | Orphaned |
| `data/rag/berkshire_letters/README.md` | Feature not used |
| `docs/lessons.md` | Redundant with lessons_learned/ |

## 3. Test Coverage Gaps (CRITICAL)

| Statistic | Value |
|-----------|-------|
| Total source modules | 86 |
| Modules with tests | 19 (22%) |
| Modules without tests | 67 (78%) |

### CRITICAL UNTESTED MODULES:

1. `src.safety.pre_trade_smoke_test` (229 lines) - Blocks trading on failures
2. `src.core.alpaca_trader` (1,176 lines) - Main trading interface
3. `src.trading.options_executor` (981 lines) - Executes all options trades
4. `src.core.options_client` - Options data retrieval
5. `src.core.config` - System configuration

### Broken Tests:
- `test_rule_one_options.py` imports non-existent `src.learning.rlhf_storage`
- `test_trading_pipeline.py` imports non-existent `src.core.indicators`
- `test_options_risk_monitor.py` - Disabled stub
- `test_risk_manager.py` - Disabled stub

## 4. Duplicate Code (Consolidate)

- Sentiment: `utils/sentiment.py`, `utils/sentiment_loader.py`, `analyst/bias_store.py`
- Options: `data/iv_data_provider.py`, `core/options_client.py`
- Risk: `risk/risk_manager.py`, `risk/options_risk_monitor.py`, `risk/position_manager.py`

## Action Plan

**Phase 1 (Immediate):**
- Remove dead imports from gates.py
- Delete unnecessary .md files
- Fix broken test imports

**Phase 2 (This Week):**
- Add tests for CRITICAL modules (Tier 1)
- Re-enable disabled test stubs

**Phase 3 (Ongoing):**
- Consolidate duplicate implementations
- Improve test coverage to 80%+

## Tags
tech-debt, cleanup, tests, coverage, audit
