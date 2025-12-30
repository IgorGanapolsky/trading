---
layout: post
title: "Lesson Learned: Code Hygiene - Automated Prevention"
date: 2025-12-15
---

# Lesson Learned: Code Hygiene - Automated Prevention
**Date**: 2025-12-15
**Severity**: MEDIUM
**Category**: Code Quality, CI/CD, Prevention

**ID**: LL-042
**Impact**: - Repo bloat (+13k lines of useless code)

## What Happened
During sandbox cleanup, discovered 13,149 lines of dead code accumulated:
- 4 temporary proof/summary files in repo root (`.ai_proof_*.md`)
- 40+ stale docs in `docs/_archive/` folder
- 45 unused Python imports across `src/` and `scripts/`
- Debug scripts and test logs committed to repo
- 48 `__pycache__` directories tracked

## Root Cause
1. **No Automated Detection**: No CI check for temporary files
2. **No Import Linting**: Ruff/flake8 not enforced in CI
3. **Archive Creep**: Old docs never purged
4. **Lack of .gitignore Rules**: __pycache__, *.pyc not properly ignored

## Impact
- Repo bloat (+13k lines of useless code)
- Slower clone/checkout times
- Confusion for new contributors
- Technical debt accumulation

## Fix Applied
1. Deleted all temporary/proof files
2. Removed entire `docs/_archive/` folder
3. Fixed 45 unused imports with `ruff --fix`
4. Removed `__pycache__` and debug files
5. Created automated prevention (see below)

## Prevention Measures (IMPLEMENTED)
1. **CI Hygiene Check** (`.github/workflows/code-hygiene.yml`)
   - Checks for temporary files (`.ai_*`, `*_summary*`, `*proof*`)
   - Runs ruff for unused imports (F401, F841)
   - Fails build if issues found

2. **Pre-commit Hook** (`.pre-commit-config.yaml`)
   - ruff linting with auto-fix
   - Check for __pycache__ directories
   - Block temporary file commits

3. **scripts/verify_code_hygiene.py**
   - Standalone hygiene verification
   - Detects temporary files, unused imports, archive folders
   - Returns non-zero exit code if issues found

## How to Use
```bash
# Run hygiene check manually
python3 scripts/verify_code_hygiene.py

# Fix unused imports automatically
ruff check --select F401,F841 --fix src/ scripts/

# Pre-commit will auto-run on commit
pre-commit run --all-files
```

## RAG Query Keywords
- "dead code detection"
- "unused imports"
- "code hygiene"
- "temporary files cleanup"
- "archive folder"
- "pre-commit hooks"

## Tags
`code-hygiene` `dead-code` `ci-cd` `prevention` `ruff` `pre-commit` `automation`

