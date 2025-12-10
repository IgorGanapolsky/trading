# Contributing to Trading

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- A GitHub account

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/trading.git
   cd trading
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e ".[dev]"  # Install dev dependencies
   ```

4. **Set up pre-commit hooks**
   ```bash
   pip install pre-commit
   pre-commit install
   ```

5. **Copy environment template**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys for testing
   ```

## Development Workflow

### Branch Naming

- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions or updates

Example: `feature/add-momentum-indicator`

### Making Changes

1. **Create a new branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write clean, readable code
   - Add type hints where possible
   - Include docstrings for functions

3. **Run tests**
   ```bash
   pytest tests/ -v
   ```

4. **Run linting**
   ```bash
   ruff check .
   ruff format .
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks
- `perf:` - Performance improvements

### Pull Request Process

1. **Push your branch**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a Pull Request**
   - Use a clear, descriptive title
   - Reference any related issues
   - Describe what changes you made and why

3. **PR Checklist**
   - [ ] Tests pass locally
   - [ ] Linting passes
   - [ ] Documentation updated (if needed)
   - [ ] No secrets or credentials included

4. **Code Review**
   - Address reviewer feedback
   - Keep the PR focused and small

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_promotion_gate.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run smoke tests
python tests/test_smoke.py
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use fixtures from `tests/conftest.py`

## Code Style

### Python Style Guide

- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use descriptive variable names
- We use `ruff` for linting and formatting
- We use `mypy` for static type checking

### Documentation

- Add docstrings to all public functions
- Update README.md for user-facing changes
- Add inline comments for complex logic

## Project Structure

```
trading/
├── src/                    # Source code
│   ├── agents/            # AI agents
│   ├── core/              # Core infrastructure
│   ├── strategies/        # Trading strategies
│   └── utils/             # Utilities
├── tests/                  # Test files
├── scripts/               # CLI scripts
├── config/                # Configuration files
├── data/                  # Data files (gitignored)
└── docs/                  # Documentation
```

## Getting Help

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- Use discussions for questions

## Recognition

Contributors will be recognized in the project README.

Thank you for contributing!
