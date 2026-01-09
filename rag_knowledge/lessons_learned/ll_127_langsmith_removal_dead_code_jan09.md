# Lesson Learned #127: LangSmith Removal - Dead Code Cleanup

**Date**: January 9, 2026
**Severity**: P1 - High
**Category**: Code Hygiene / Dead Code

## What Happened

LangSmith was removed from the codebase on Jan 9, 2026, but the removal was incomplete:
- The main tracer file `src/observability/langsmith_tracer.py` was deleted
- But 4 source files still had try/except import blocks referencing the deleted file
- This would cause ImportError if those code paths were executed

## Files Affected

1. `src/execution/alpaca_executor.py` - Line 28
2. `src/risk/trade_gateway.py` - Line 41
3. `src/orchestrator/gates.py` - Line 55
4. `src/orchestrator/main.py` - Line 128

## Root Cause

When removing a module, the developer:
1. Deleted the module file
2. Updated `__init__.py` with removal comment
3. **FORGOT** to update all files that import from the module

This is a common pattern when removing dependencies.

## Fix Applied

Replaced all try/except import blocks with:
```python
# LangSmith removed Jan 9, 2026 - using Vertex AI RAG instead
LANGSMITH_AVAILABLE = False
```

The existing code gracefully handles `LANGSMITH_AVAILABLE = False` by skipping LangSmith operations.

## Prevention Protocol

When removing a module/dependency:
1. **BEFORE deleting**: Run `grep -rn "from <module>" src/`
2. List ALL files that import from the module
3. Update ALL importing files FIRST
4. THEN delete the module
5. Run `python3 -m py_compile` on all modified files
6. Run full test suite

## Verification Commands

```bash
# Find all imports from a module
grep -rn "from src.observability.langsmith" src/ --include="*.py"

# Verify Python files compile
find src -name "*.py" -exec python3 -m py_compile {} \;

# Check for dead imports
python3 -c "from src.orchestrator.main import TradingOrchestrator"
```

## Related

- Vertex AI RAG is the replacement for LangSmith observability
- `src/observability/__init__.py` was updated with removal comment
- Stub functions in `logging_config.py` provide backward compatibility

## Tags
#dead-code #langsmith #code-hygiene #import-error #refactoring
