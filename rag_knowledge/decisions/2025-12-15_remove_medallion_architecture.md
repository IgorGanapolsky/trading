# Architectural Decision: Remove Medallion Architecture

**Date**: 2025-12-15  
**Status**: Executed  
**Decision**: Remove unused Medallion Architecture implementation

## Context

The codebase had a fully-implemented Medallion Architecture (Bronze → Silver → Gold data pipeline) in `src/medallion/`, but it was not integrated into the main trading system.

### Implementation Status
- **Complete module**: `src/medallion/` with bronze.py, silver.py, gold.py, pipeline.py
- **Usage**: Only `src/ml/medallion_trainer.py` imported from it (no other integrations)
- **Data directories**: `data/bronze/`, `data/silver/`, `data/gold/` were all empty
- **Main systems**: Orchestrator, strategies, backtesting, data providers - none used Medallion

### Duplication Issue
`src/backtesting/data_cache.py` implemented its own "medallion-like" pattern but did NOT use the `src/medallion/` module - just borrowed the naming convention.

## Decision

**Removed Medallion Architecture** (YAGNI principle - You Aren't Gonna Need It)

### Rationale
1. **Not Used**: No integration with main trading pipeline after implementation
2. **Early Stage**: Day 9/90 R&D phase with $10/day paper trading
3. **Working System**: Current system achieves 87.5% win rate without it
4. **Complexity**: Added architectural overhead without delivering value
5. **No Data**: Empty data directories indicate zero production usage
6. **Can Re-add Later**: If data quality/ML becomes priority, can reimplement

### Alternatives Considered
- **Option A - Remove** ✅ (Chosen)
- **Option B - Integrate**: Wire into ML pipeline and orchestrator (premature optimization)
- **Option C - Keep dormant**: Adds technical debt without benefit

## Changes Made

### Files Removed
- `src/medallion/bronze.py`
- `src/medallion/silver.py`
- `src/medallion/gold.py`
- `src/medallion/pipeline.py`
- `src/medallion/integration.py`
- `src/medallion/__init__.py`
- `src/ml/medallion_trainer.py`

### Directories Removed
- `data/bronze/` (including alpaca/, polygon/, raw_ohlcv/)
- `data/silver/` (including features/, validated/, sentiment/)
- `data/gold/` (including feature_store/, ml_ready/, training_sets/)

### Impact
- **Zero functionality loss**: No systems depended on this module
- **Reduced complexity**: ~1000 lines of code removed
- **Cleaner codebase**: Removed unused architectural layer

## Future Considerations

If Medallion Architecture becomes needed:
1. **When**: Moving to live trading with >$100/day or encountering data quality issues
2. **How**: Reimplement with actual integration points defined upfront
3. **Integration**: Wire into `src/utils/market_data.py` and ML training pipeline
4. **Reference**: This decision document + original implementation (git history)

## Verification

```bash
# Confirmed no remaining imports
rg "from src.medallion|import.*medallion" src/ tests/
# Result: No matches

# Confirmed no broken tests
pytest tests/unit -v
# Result: All passed
```

## Related Documents
- `AGENTS.md`: "Never Do: Never merge directly to main"
- `docs/ARCHITECTURE.md`: Data flow documentation
- Git history: Full implementation preserved at commit before removal

---

**CTO Decision**: Clean, focused codebase > premature architectural patterns  
**CEO Approval**: Igor Ganapolsky (approved via architectural evaluation query)
