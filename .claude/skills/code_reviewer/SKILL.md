# Code Reviewer Skill

A Python-focused code review skill that identifies security issues, anti-patterns, and quality concerns.

## Activation

Invoke this skill after making code changes or when reviewing Python files:
```
/skill code_reviewer
```

## Review Checklist

### Critical (Must Fix)

**Security Issues:**
- [ ] No hardcoded secrets, API keys, or credentials
- [ ] No SQL injection vulnerabilities (use parameterized queries)
- [ ] No command injection (avoid shell=True, validate inputs)
- [ ] No unsafe pickle/eval usage
- [ ] Sensitive data not logged or exposed in errors

**Trading-Specific Security:**
- [ ] Alpaca API keys from environment only
- [ ] No hardcoded account numbers or positions
- [ ] Order validation before submission
- [ ] Position size limits enforced

**Logic Errors:**
- [ ] Division by zero protected
- [ ] Null/None checks on external data
- [ ] Edge cases handled (empty lists, zero values)
- [ ] Error handling doesn't swallow exceptions silently

### Warning (Should Fix)

**Anti-Patterns:**
- [ ] No bare `except:` clauses (catch specific exceptions)
- [ ] No mutable default arguments (use None + check)
- [ ] No global state modifications in functions
- [ ] No circular imports
- [ ] Functions under 50 lines

**Code Quality:**
- [ ] Single responsibility per function
- [ ] No magic numbers (use named constants)
- [ ] Type hints on public functions
- [ ] Docstrings on public APIs

**Trading-Specific:**
- [ ] Market hours checked before orders
- [ ] Stop-loss set on positions
- [ ] Position size respects capital limits
- [ ] Slippage/fees accounted for

### Suggestions (Nice to Have)

**Performance:**
- [ ] No N+1 queries or API calls in loops
- [ ] Large data uses generators/iterators
- [ ] Caching for expensive operations

**Maintainability:**
- [ ] Consistent naming conventions
- [ ] No dead code or commented-out blocks
- [ ] Tests for new functionality

## Review Command

Run this command to review recent changes:
```bash
git diff HEAD~1 --name-only -- '*.py' | xargs -I{} python3 -m ruff check {}
```

## Example Review Output

```
## Code Review: src/trading/executor.py

### Critical
- Line 45: API key appears hardcoded - use os.environ
- Line 89: No error handling on order submission

### Warning
- Line 23: Bare except clause - catch specific exceptions
- Line 67: Magic number 0.02 - define as COMMISSION_RATE constant

### Suggestions
- Line 34: Consider adding type hints to execute_trade()
- Line 78: Could benefit from retry logic on API timeout
```

## Integration

This skill works with:
- `precommit_hygiene` - Pre-commit checks
- `error_handling_protocols` - Error patterns
- `portfolio_risk_assessment` - Trading safety checks
