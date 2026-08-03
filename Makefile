SHELL := /bin/bash
PYTHON ?= python3.11
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
TRADING_ENV ?= paper
export TRADING_ENV

.PHONY: setup lint ruff format test coverage audit security health skill-check check dry-run hygiene production-scorecard

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e ".[dev,security]"

lint:
	$(VENV_PYTHON) -m ruff check src scripts tests
	$(VENV_PYTHON) -m ruff format --check src scripts tests

ruff: lint

format:
	$(VENV_PYTHON) -m ruff check --fix src scripts tests
	$(VENV_PYTHON) -m ruff format src scripts tests

test:
	$(VENV_PYTHON) -m pytest -q

coverage:
	$(VENV_PYTHON) -m pytest --cov=src --cov=scripts --cov-branch \
		--cov-report=term-missing --cov-report=xml --cov-report=json --cov-report=html -q

audit:
	$(VENV_PYTHON) scripts/audit_repository_hygiene.py --check

security:
	$(VENV_PYTHON) -m pip_audit
	$(VENV)/bin/bandit -q -r src scripts mcp -lll -iii

health:
	SYSTEM_HEALTH_BOUNDED=1 $(VENV_PYTHON) scripts/system_health_check.py

skill-check:
	$(VENV_PYTHON) -m pytest tests/test_repo_docs_layout.py tests/test_repo_hygiene.py tests/test_killed_ic_workflows.py tests/test_judge_panel.py -q
	$(VENV_PYTHON) scripts/judge_panel.py --self-check

check: lint audit security skill-check test

dry-run: health
	$(VENV_PYTHON) scripts/spy_put_credit.py --dry-run
	$(VENV_PYTHON) scripts/residual_ic_manager.py --dry-run

hygiene:
	scripts/worktree_hygiene.sh --prune
