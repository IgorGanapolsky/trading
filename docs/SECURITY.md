# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in this project, please report it responsibly.

### How to Report

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Email the maintainer directly at: [Create a private security advisory](https://github.com/IgorGanapolsky/trading/security/advisories/new)
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: Within 48 hours of your report
- **Initial Assessment**: Within 7 days
- **Resolution Timeline**: Depends on severity
  - Critical: 24-72 hours
  - High: 1-2 weeks
  - Medium: 2-4 weeks
  - Low: Next release cycle

### Scope

This security policy covers:
- The trading application codebase
- Configuration files and templates
- CI/CD pipeline configurations
- Docker configurations

### Out of Scope

- Third-party dependencies (report to respective maintainers)
- Social engineering attacks
- Physical security

## Security Best Practices

This project follows these security practices:

### Secrets Management
- All API keys stored in `.env` files (never committed)
- `.env.example` provided as template without real values
- `detect-secrets` used in pre-commit hooks

### Code Security
- `bandit` security linting in CI/CD
- Dependency scanning via Dependabot
- No hardcoded credentials in source code

### Trading-Specific Security
- Paper trading mode for testing
- Promotion gate prevents unauthorized live trading
- Position size limits enforced
- Circuit breakers for unusual market conditions

## Security Features

- Environment variable validation on startup
- API key rotation support
- Audit logging for all trades
- Rate limiting on external API calls

## Acknowledgments

We appreciate responsible disclosure and will acknowledge security researchers who report valid vulnerabilities.
