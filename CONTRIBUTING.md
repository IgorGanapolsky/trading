# Contributing to the Trading System

Thank you for your interest in contributing to the Trading System project! This document outlines the guidelines and workflows for contributing.

## Development Workflow

1.  **Fork and Clone**: Fork the repository and clone it locally.
2.  **Create a Branch**: Create a new branch for your feature or fix.
    ```bash
    git checkout -b feat/your-feature-name
    # or
    git checkout -b fix/your-fix-name
    ```
3.  **Install Dependencies**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    pip install -r requirements-dev.in
    ```
4.  **Make Changes**: Implement your changes.
5.  **Run Tests**: Ensure all tests pass.
    ```bash
    pytest tests/
    ```
6.  **Lint and Format**: Run pre-commit hooks.
    ```bash
    pre-commit run --all-files
    ```
7.  **Commit**: Use Conventional Commits.
    ```bash
    git commit -m "feat: add new momentum indicator"
    ```
8.  **Push and PR**: Push to your fork and open a Pull Request.

## Commit Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/):

-   `feat`: A new feature
-   `fix`: A bug fix
-   `docs`: Documentation only changes
-   `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
-   `refactor`: A code change that neither fixes a bug nor adds a feature
-   `perf`: A code change that improves performance
-   `test`: Adding missing tests or correcting existing tests
-   `chore`: Changes to the build process or auxiliary tools and libraries such as documentation generation

## Pull Request Process

1.  Ensure your PR description clearly explains the changes and links to any relevant issues.
2.  Include screenshots or logs if applicable.
3.  Wait for CI checks to pass.
4.  Address any review comments.

## Code Style

-   We use `ruff` for linting and formatting.
-   We use `mypy` for static type checking.
-   Follow PEP 8 guidelines.

## Testing

-   Add unit tests for new logic.
-   Run the smoke test suite: `python tests/test_smoke.py`.
-   Ensure backtests are reproducible.

## Questions?

If you have questions, please open an issue or contact the maintainers.
