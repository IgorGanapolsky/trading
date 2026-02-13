# Mandatory Rules

These supplement Core Directives in CLAUDE.md. Do not duplicate what is already there.

1. **No documentation** -- don't create .md files (except rules)
2. **Trust hooks** -- they provide context each session
3. **Safe cleanup** -- run `python3 scripts/pre_cleanup_check.py <path>` before deleting code

## Cleanup Protocol (Prevents Breaking CI)

Before deleting ANY code:

```bash
# 1. Check dependencies
python3 scripts/pre_cleanup_check.py src/module_to_delete.py

# 2. If dependencies found:
#    - Delete tests FIRST
#    - Create stub if source files import it
#    - Update scripts that import it

# 3. After deletion:
python3 scripts/system_health_check.py
pytest tests/ -x --tb=short
```

**Lesson: PR #1445 deleted 26,000 lines without checking imports -> broke CI for hours**
