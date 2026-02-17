SHELL := /bin/bash

.PHONY: hygiene autonomous-gate autonomous-gate-full
hygiene:
	scripts/worktree_hygiene.sh --prune

autonomous-gate:
	python3 scripts/agent_handoff_gate.py --mode quick --base-ref $${BASE_REF:-origin/main}

autonomous-gate-full:
	python3 scripts/agent_handoff_gate.py --mode full --base-ref $${BASE_REF:-origin/main}
