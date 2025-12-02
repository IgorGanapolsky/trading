---
skill_id: local_ci_runner
name: Local CI Runner (ACT)
version: 1.0.0
description: Run GitHub Actions workflows locally using ACT in Docker before pushing to verify CI will pass
author: Trading System CTO
tags: [ci, docker, act, github-actions, pre-commit, verification]
tools:
  - run_workflow
  - run_lint_check
  - run_all_checks
  - verify_before_push
dependencies:
  - docker
  - act (nektos/act)
---

# Local CI Runner Skill (ACT)

Run GitHub Actions workflows locally in Docker before pushing to ensure CI passes.

## Overview

This skill uses [ACT](https://github.com/nektos/act) to run GitHub Actions workflows locally in Docker containers. This catches CI failures before they hit GitHub, saving time and avoiding failed PR checks.

## Why Local CI?

1. **Catch failures early**: Don't wait 2-3 minutes for GitHub CI to fail
2. **Iterate faster**: Fix lint/test issues locally before pushing
3. **Save CI minutes**: Avoid burning GitHub Actions minutes on failures
4. **Pre-commit integration**: Automatically verify before each commit

## Installation

### Prerequisites

```bash
# Install Docker (if not installed)
brew install --cask docker

# Install ACT
brew install act

# Verify installation
act --version
docker --version
```

### First-Time Setup

```bash
# Pull the required Docker image (medium size, good balance)
act -P ubuntu-latest=catthehacker/ubuntu:act-latest

# Or use smaller image for faster runs
act -P ubuntu-latest=catthehacker/ubuntu:act-22.04
```

## Tools

### 1. run_workflow

Run a specific GitHub Actions workflow locally.

**Usage:**
```bash
# Run a specific workflow
act -W .github/workflows/lint.yml

# Run with specific event
act push -W .github/workflows/ci.yml

# Run specific job
act -j lint -W .github/workflows/ci.yml
```

### 2. run_lint_check

Quick lint verification using the lint workflow.

**Usage:**
```bash
# Run lint checks only
act -j "Lint & Format" -W .github/workflows/ci.yml --container-architecture linux/amd64

# Or run ruff directly (faster, no Docker)
uvx ruff check . && uvx ruff format --check .
```

### 3. run_all_checks

Run all CI checks locally.

**Usage:**
```bash
# Run full CI suite
act push -W .github/workflows/ci.yml --container-architecture linux/amd64

# Run with secrets (if needed)
act push --secret-file .env.ci
```

### 4. verify_before_push

Comprehensive pre-push verification.

**Usage:**
```bash
# Quick verification (lint + type check)
uvx ruff check . && uvx ruff format --check . && mypy src/

# Full verification with ACT
act push -W .github/workflows/ci.yml --container-architecture linux/amd64
```

## Pre-Commit Integration

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: local-ci-lint
        name: Local CI Lint Check
        entry: bash -c 'uvx ruff check . && uvx ruff format --check .'
        language: system
        pass_filenames: false
        stages: [pre-push]

      - id: local-ci-full
        name: Local CI Full Check (ACT)
        entry: bash -c 'act -j "Lint & Format" -W .github/workflows/ci.yml --container-architecture linux/amd64 2>/dev/null || echo "ACT not available, skipping"'
        language: system
        pass_filenames: false
        stages: [pre-push]
        verbose: true
```

## Quick Commands

```bash
# List available workflows
act -l

# List jobs in a workflow
act -l -W .github/workflows/ci.yml

# Dry run (show what would happen)
act -n push

# Run with verbose output
act -v push -W .github/workflows/ci.yml

# Run on Apple Silicon (M1/M2/M3)
act --container-architecture linux/amd64 push
```

## Common Issues & Solutions

### 1. Docker not running
```bash
# Start Docker Desktop or
open -a Docker
```

### 2. Image pull fails
```bash
# Use smaller image
act -P ubuntu-latest=catthehacker/ubuntu:act-22.04
```

### 3. Apple Silicon (M1/M2/M3) issues
```bash
# Always add architecture flag
act --container-architecture linux/amd64
```

### 4. Secrets not available
```bash
# Create .env.ci file with secrets
echo "GITHUB_TOKEN=xxx" > .env.ci
act --secret-file .env.ci
```

## Integration with Claude CTO Workflow

### Before Every Push

1. Run `uvx ruff check . && uvx ruff format --check .`
2. If lint passes, run `act -j "Lint & Format"` for full verification
3. If ACT passes, push with confidence

### Pre-Commit Hook Enforcement

The pre-commit hook should:
1. Run ruff lint/format (fast, always)
2. Run ACT lint job (optional, on pre-push)

### CI Verification Protocol

**MANDATORY before pushing any PR:**

```bash
# Step 1: Quick lint check (always do this)
uvx ruff check . && uvx ruff format --check .

# Step 2: If changes are significant, run ACT
act -j "Lint & Format" -W .github/workflows/ci.yml --container-architecture linux/amd64

# Step 3: Only push if both pass
git push origin branch-name
```

## Best Practices (Anthropic Test & Evaluate Guidelines)

Following [Anthropic's testing best practices](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests):

1. **Define Success Criteria**: CI must pass before merge
2. **Automated Verification**: Pre-commit hooks catch issues early
3. **Fast Feedback**: Local CI is faster than GitHub CI
4. **Consistent Environment**: Docker ensures reproducibility
5. **Incremental Testing**: Run targeted checks (lint only vs full suite)

## Configuration

Create `.actrc` in project root:

```
-P ubuntu-latest=catthehacker/ubuntu:act-latest
--container-architecture linux/amd64
-W .github/workflows/ci.yml
```

Then just run:
```bash
act push
```

## Maintenance

- Update ACT: `brew upgrade act`
- Update Docker images: `docker pull catthehacker/ubuntu:act-latest`
- Review workflows when CI config changes
