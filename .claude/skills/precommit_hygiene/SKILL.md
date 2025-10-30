---
skill_id: precommit_hygiene
name: Pre-Commit Hygiene Orchestrator
version: 1.0.0
description: Automated code quality, file organization, and repository hygiene enforcement for pre-commit hooks
author: Trading System CTO
tags: [code-quality, pre-commit, linting, organization, best-practices]
tools:
  - check_file_organization
  - lint_python_code
  - validate_commit_message
  - check_secrets
  - organize_repository
  - run_all_checks
dependencies:
  - pre-commit
  - black
  - flake8
  - mypy
  - detect-secrets
---

# Pre-Commit Hygiene Orchestrator Skill

Enforces code quality, file organization, and repository best practices automatically.

## Overview

This skill provides:
- File organization enforcement (docs/, scripts/, src/ structure)
- Python code quality checks (black, flake8, mypy)
- Commit message validation
- Secret detection and prevention
- Automated file cleanup and organization
- Pre-commit hook integration

## Best Practices for 2025

### Repository Structure
```
trading/
├── .claude/              # Claude configuration and skills
├── .github/              # GitHub Actions workflows
├── docs/                 # All documentation (*.md files except README)
├── scripts/              # Utility scripts (*.sh, standalone *.py)
├── src/                  # Source code
│   ├── core/             # Core trading engine
│   ├── strategies/       # Trading strategies
│   └── utils/            # Utilities
├── tests/                # Test files
├── data/                 # Data files (in .gitignore)
├── logs/                 # Log files (in .gitignore)
├── reports/              # Generated reports
├── .env.example          # Example environment variables
├── .gitignore            # Git ignore rules
├── docker-compose.yml    # Docker configuration
├── Dockerfile            # Docker build
├── LICENSE               # License file
├── README.md             # Main documentation
└── requirements.txt      # Python dependencies
```

### Files That Should NOT Be in Root
- ❌ Multiple markdown files (should be in docs/)
- ❌ Utility Python scripts (should be in scripts/)
- ❌ Shell scripts (should be in scripts/)
- ❌ Research documents (should be in docs/research/)

### Files That SHOULD Be in Root
- ✅ README.md (main entry point)
- ✅ LICENSE
- ✅ .gitignore
- ✅ .env.example
- ✅ requirements.txt
- ✅ docker-compose.yml
- ✅ Dockerfile
- ✅ pyproject.toml (if using)

## Tools

### 1. check_file_organization

Checks if files are properly organized according to best practices.

**Parameters:**
- `fix` (optional): Automatically move files to correct locations (default: false)

**Returns:**
```json
{
  "success": true,
  "data": {
    "issues_found": 15,
    "issues": [
      {
        "file": "CTO_REPORT.md",
        "issue": "Documentation file in root",
        "recommendation": "Move to docs/",
        "severity": "warning"
      },
      {
        "file": "daily_checkin.py",
        "issue": "Utility script in root",
        "recommendation": "Move to scripts/",
        "severity": "warning"
      }
    ],
    "files_moved": 0,
    "summary": "15 files need reorganization"
  }
}
```

### 2. lint_python_code

Runs Python linters (black, flake8, mypy) on all Python files.

**Parameters:**
- `files` (optional): Specific files to lint (default: all .py files)
- `fix` (optional): Auto-fix issues where possible (default: false)

**Returns:**
```json
{
  "success": true,
  "data": {
    "black": {
      "passed": false,
      "files_need_formatting": 5,
      "files": ["src/core/trader.py"]
    },
    "flake8": {
      "passed": true,
      "violations": 0
    },
    "mypy": {
      "passed": false,
      "type_errors": 3,
      "files": ["src/strategies/core.py"]
    },
    "overall_passed": false
  }
}
```

### 3. validate_commit_message

Validates commit message follows conventions.

**Parameters:**
- `message` (required): Commit message to validate

**Returns:**
```json
{
  "success": true,
  "data": {
    "is_valid": true,
    "format": "conventional",
    "type": "feat",
    "scope": "trading",
    "subject": "Add risk management",
    "issues": []
  }
}
```

**Commit Message Format (Conventional Commits)**:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: feat, fix, docs, style, refactor, test, chore

### 4. check_secrets

Scans for accidentally committed secrets.

**Parameters:**
- `files` (optional): Files to scan (default: all staged files)

**Returns:**
```json
{
  "success": true,
  "data": {
    "secrets_found": 0,
    "violations": [],
    "safe_to_commit": true
  }
}
```

### 5. organize_repository

Automatically organizes repository according to best practices.

**Parameters:**
- `dry_run` (optional): Preview changes without applying (default: true)

**Returns:**
```json
{
  "success": true,
  "data": {
    "actions": [
      {
        "action": "move",
        "from": "CTO_REPORT.md",
        "to": "docs/CTO_REPORT.md"
      },
      {
        "action": "move",
        "from": "daily_checkin.py",
        "to": "scripts/daily_checkin.py"
      }
    ],
    "files_moved": 15,
    "directories_created": 2
  }
}
```

### 6. run_all_checks

Runs all pre-commit checks.

**Parameters:**
- `fix` (optional): Auto-fix issues where possible (default: false)

**Returns:**
```json
{
  "success": true,
  "data": {
    "checks_passed": 4,
    "checks_failed": 2,
    "results": {
      "file_organization": "passed",
      "python_linting": "failed",
      "commit_message": "passed",
      "secrets": "passed",
      "tests": "failed"
    },
    "blocking_issues": ["Python linting failed", "Tests failed"],
    "can_commit": false
  }
}
```

## Pre-Commit Hook Integration

Install pre-commit hooks:

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
python scripts/precommit_hygiene.py setup

# Install hooks
pre-commit install
```

### .pre-commit-config.yaml
```yaml
repos:
  - repo: local
    hooks:
      - id: file-organization
        name: Check File Organization
        entry: python .claude/skills/precommit_hygiene/scripts/precommit_hygiene.py check_file_organization
        language: system
        pass_filenames: false

      - id: python-black
        name: Python Black Formatting
        entry: black
        language: system
        types: [python]

      - id: python-flake8
        name: Python Flake8 Linting
        entry: flake8
        language: system
        types: [python]

      - id: python-mypy
        name: Python Type Checking
        entry: mypy
        language: system
        types: [python]

      - id: detect-secrets
        name: Detect Secrets
        entry: detect-secrets-hook
        language: system

      - id: commit-msg-validation
        name: Validate Commit Message
        entry: python .claude/skills/precommit_hygiene/scripts/precommit_hygiene.py validate_commit_message
        language: system
        stages: [commit-msg]
```

## Usage Examples

### Manual Check
```bash
# Check file organization
python .claude/skills/precommit_hygiene/scripts/precommit_hygiene.py check_file_organization

# Lint Python code
python .claude/skills/precommit_hygiene/scripts/precommit_hygiene.py lint_python_code

# Run all checks
python .claude/skills/precommit_hygiene/scripts/precommit_hygiene.py run_all_checks
```

### Auto-Fix
```bash
# Organize repository automatically
python .claude/skills/precommit_hygiene/scripts/precommit_hygiene.py organize_repository --no-dry-run

# Format Python code
python .claude/skills/precommit_hygiene/scripts/precommit_hygiene.py lint_python_code --fix
```

### Pre-Commit Hook
```bash
# Automatically runs on git commit
git add .
git commit -m "feat: Add new trading strategy"
# Pre-commit hooks run automatically
```

## Configuration

Create `.precommit-hygiene.json`:
```json
{
  "file_organization": {
    "docs_extensions": [".md"],
    "script_extensions": [".sh", ".py"],
    "exclude_from_root": [
      "README.md",
      "LICENSE",
      ".gitignore",
      ".env.example",
      "requirements.txt",
      "docker-compose.yml",
      "Dockerfile"
    ]
  },
  "python_linting": {
    "black": {
      "line_length": 100,
      "skip_string_normalization": false
    },
    "flake8": {
      "max_line_length": 100,
      "ignore": ["E203", "W503"]
    },
    "mypy": {
      "strict": true,
      "ignore_missing_imports": true
    }
  },
  "commit_message": {
    "format": "conventional",
    "types": ["feat", "fix", "docs", "style", "refactor", "test", "chore"],
    "scopes": ["trading", "risk", "strategy", "skills", "docs", "ci"]
  }
}
```

## Benefits

1. **Clean Repository**: Enforces consistent file organization
2. **Code Quality**: Catches issues before they're committed
3. **Security**: Prevents accidental secret commits
4. **Documentation**: Ensures commit messages are descriptive
5. **Automation**: Runs automatically, no manual intervention
6. **Best Practices**: Follows 2025 Python and Git standards

## Integration with CI/CD

This skill integrates with GitHub Actions:

```yaml
# .github/workflows/pre-commit.yml
name: Pre-Commit Checks
on: [push, pull_request]
jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -r requirements.txt
      - run: python .claude/skills/precommit_hygiene/scripts/precommit_hygiene.py run_all_checks
```

## Maintenance

- Update `.precommit-hygiene.json` as project evolves
- Review and update linting rules regularly
- Keep pre-commit hooks updated: `pre-commit autoupdate`
- Monitor for new best practices and tools
