SHELL := /bin/bash

.PHONY: hygiene test check ruff skill-check

# Worktree prune helper (local)
hygiene:
	scripts/worktree_hygiene.sh --prune

# Full test suite (may be long)
test:
	pytest tests/ -q

# Fast default: lint + repo hygiene tests
ruff:
	ruff check src/

skill-check:
	pytest tests/test_repo_docs_layout.py tests/test_repo_hygiene.py tests/test_killed_ic_workflows.py -q

check: ruff skill-check
