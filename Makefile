SHELL := /bin/bash

.PHONY: hygiene
hygiene:
	scripts/worktree_hygiene.sh --prune
