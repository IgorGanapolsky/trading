# Mandatory Rules

1. **Don't lie** - verify with commands before claiming anything
2. **Don't lose money** - protect capital first (Phil Town Rule #1)
3. **Use PRs** - never push directly to main, merge them yourself via GitHub API
4. **Fix it yourself** - never tell CEO to do manual work - DO IT YOURSELF
5. **No documentation** - don't create .md files (except rules)
6. **Trust hooks** - they provide context each session
7. **Safe cleanup** - run `python3 scripts/pre_cleanup_check.py <path>` before deleting code
8. **Verify before claiming** - say "I believe this is done, verifying now..." not "Done!"
9. **Query RAG first** - check Vertex AI RAG lessons BEFORE starting any task
10. **Learn from mistakes** - record errors in RAG and improve continuously

## Learning & RAG Protocol
- Record every trade and lesson in Vertex AI RAG
- Be your own coach - continuously improve
- When you make a mistake, record it in RAG

## Operational Security
- Run dry runs before merging to main
- Clean up stale branches after merging
- Ensure CI passes before merging

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
