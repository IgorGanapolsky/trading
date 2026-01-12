# Mandatory Rules

1. **Don't lie** - verify with commands before claiming anything
2. **Don't lose money** - protect capital first
3. **Use PRs** - never push directly to main
4. **Fix it yourself** - never tell CEO to do manual work
5. **No documentation** - don't create .md files
6. **Trust hooks** - they provide context each session
7. **Safe cleanup** - run `python3 scripts/pre_cleanup_check.py <path>` before deleting code

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

**Lesson: PR #1445 deleted 26,000 lines without checking imports → broke CI for hours**
