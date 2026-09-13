---
description: Run repository hygiene, lint checks, and pre-action verification
---

# Repository Hygiene

Execute repository hygiene verification:

1. Run `.venv/bin/python -m ruff check src scripts tests`
2. Run `.venv/bin/python scripts/audit_repository_hygiene.py --check`
3. Report any lint or hygiene findings.
